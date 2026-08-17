"""The category tree.

An **adjacency list** (``parent`` FK) with two denormalised columns, ``path``
and ``url_path``, rather than MPTT or treebeard. Both of those replace the
default manager and override ``save()``, and ``Category.save()`` already owns
custom Unicode-slug logic that would have to be threaded back through their
node API; the flat-to-tree backfill would likewise have to run row-by-row
through that API instead of one bulk ``RunPython``. The tree here is at most
``MAX_DEPTH`` levels and a few hundred nodes per site, where a prefix scan on
an indexed column is not merely adequate but faster than a nested-set read.

``path`` is built from **primary keys**, zero-padded so lexical order matches
tree order, and is what descendant queries scan. ``url_path`` is built from
slugs and is what URLs and breadcrumbs use. They are separate on purpose: a
slug rename must rewrite every descendant URL, and if descendant lookup also
went through slugs, the rename would have to find the rows it is about to
change using the values it is changing.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction

from common.slugs import unique_slug
from common.tenancy import TenantModel

#: Deeper than this and breadcrumbs stop being navigable. Enforced on move.
MAX_DEPTH = 4
#: Width of one ``path`` segment. 10 digits covers any bigint pk we will meet
#: and keeps the string sortable without a numeric cast.
_SEGMENT_WIDTH = 10


def _segment(pk: int) -> str:
    return str(pk).zfill(_SEGMENT_WIDTH)


class Category(TenantModel):
    # name/slug uniqueness is per-site: two tenants may each have a "Tech"
    # category. Moved off global unique=True while there is a single site and
    # trivial data -- swapping a unique index under live multi-tenant data is
    # considerably riskier.
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, allow_unicode=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        help_text="NULL for a root category.",
    )
    #: Zero-padded pk path including this node, e.g. "0000000003.0000000011".
    #: Descendants are found with ``path__startswith=f"{self.path}."``.
    path = models.CharField(max_length=255, blank=True, default="", db_index=True)
    #: Slug path without a leading slash, e.g. "technology/machine-learning".
    url_path = models.CharField(max_length=800, blank=True, default="", db_index=True)
    depth = models.PositiveSmallIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "categories"
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["site", "slug"], name="category_unique_site_slug"),
            models.UniqueConstraint(fields=["site", "name"], name="category_unique_site_name"),
        ]
        indexes = [models.Index(fields=["site", "parent", "order"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(
                self.name,
                Category.unscoped.filter(site_id=self.site_id).exclude(pk=self.pk),
                fallback=uuid.uuid4().hex[:8],
            )
        if self.parent_id:
            # The tenant is always the parent's. Deriving it here rather than
            # trusting the caller means a child can never end up on a different
            # site than its parent, where it would be unreachable through
            # either site's tree.
            self.site_id = self.parent.site_id

        previous = None
        if self.pk:
            previous = (
                Category.unscoped.filter(pk=self.pk)
                .values("parent_id", "slug", "path")
                .first()
            )

        super().save(*args, **kwargs)

        # Recompute this node's own denormalised columns, then push the change
        # down. Done after the insert because a root node's path contains its
        # own pk, which does not exist until the row does.
        moved = previous is None or previous["parent_id"] != self.parent_id
        renamed = previous is not None and previous["slug"] != self.slug
        if moved or renamed or not self.path:
            self._rebuild_subtree()

    def delete(self, *args, **kwargs):
        # PROTECT on `parent` already refuses to orphan children; say so in
        # terms an editor can act on rather than surfacing a FK error.
        if self.children.exists():
            raise ValidationError(
                "Move or delete this category's children before deleting it."
            )
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.name

    # -- tree -----------------------------------------------------------

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def ancestors(self):
        """Root-first ancestors, in one query, derived from ``path``."""
        if not self.path or "." not in self.path:
            return Category.unscoped.none()
        pks = [int(segment) for segment in self.path.split(".")[:-1]]
        return sorted(
            Category.unscoped.filter(pk__in=pks), key=lambda c: pks.index(c.pk)
        )

    def descendants(self):
        """Every node below this one, in tree order, in one indexed scan."""
        if not self.path:
            return Category.unscoped.none()
        return Category.unscoped.filter(path__startswith=f"{self.path}.").order_by("path")

    @transaction.atomic
    def move_to(self, parent, *, order=None):
        """Reparent this category, rewriting the whole subtree's paths.

        Raises ``ValidationError`` rather than corrupting the tree when the
        move would create a cycle or exceed ``MAX_DEPTH``. The cycle check is
        the one that matters: making a node a child of its own descendant
        detaches that entire branch from the root with no error at the database
        level, and the only symptom is categories vanishing from the tree.
        """
        if parent is not None:
            if parent.pk == self.pk:
                raise ValidationError("A category cannot be its own parent.")
            if parent.path and parent.path.startswith(f"{self.path}."):
                raise ValidationError(
                    "Cannot move a category beneath one of its own descendants."
                )
            if parent.site_id != self.site_id:
                raise ValidationError("Cannot move a category to another site.")

            subtree_height = max(
                [0] + [d.depth - self.depth for d in self.descendants()]
            )
            if parent.depth + 1 + subtree_height >= MAX_DEPTH:
                raise ValidationError(
                    f"That move would nest categories more than {MAX_DEPTH} deep."
                )

        self.parent = parent
        if order is not None:
            self.order = order
        self.save()
        return self

    def _rebuild_subtree(self):
        """Recompute ``path``/``url_path``/``depth`` here and below.

        Walks children explicitly instead of doing a SQL string-replace on the
        prefix: ``url_path`` segments are Unicode slugs of unbounded content,
        and a substring rewrite would silently corrupt any descendant whose own
        slug happens to contain the old prefix.
        """
        parent = self.parent
        self.path = f"{parent.path}.{_segment(self.pk)}" if parent else _segment(self.pk)
        self.url_path = f"{parent.url_path}/{self.slug}" if parent else self.slug
        self.depth = (parent.depth + 1) if parent else 0
        Category.unscoped.filter(pk=self.pk).update(
            path=self.path, url_path=self.url_path, depth=self.depth
        )

        # The new parent values travel down the walk explicitly. Re-reading
        # `node.parent` instead would work only because the row was just
        # UPDATEd, and would cost a query per node to rediscover a value we
        # already hold.
        stack = [(self.path, self.url_path, self.depth, self.pk)]
        while stack:
            parent_path, parent_url, parent_depth, parent_pk = stack.pop()
            for node in Category.unscoped.filter(parent_id=parent_pk).only("id", "slug"):
                path = f"{parent_path}.{_segment(node.pk)}"
                url_path = f"{parent_url}/{node.slug}" if parent_url else node.slug
                depth = parent_depth + 1
                Category.unscoped.filter(pk=node.pk).update(
                    path=path, url_path=url_path, depth=depth
                )
                stack.append((path, url_path, depth, node.pk))
