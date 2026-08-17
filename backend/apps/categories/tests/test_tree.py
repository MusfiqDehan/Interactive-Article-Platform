"""The category tree: paths, moves, deletion, and breadcrumbs."""

import pytest
from django.core.exceptions import ValidationError

from apps.categories.models import MAX_DEPTH, Category

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


class TestPaths:
    def test_a_new_category_is_a_root(self, category_factory):
        root = category_factory(name="Technology")
        assert root.depth == 0
        assert root.parent_id is None
        assert root.url_path == root.slug
        assert root.path == str(root.pk).zfill(10)

    def test_a_child_inherits_the_parents_path(self, category_factory, default_site):
        root = category_factory(name="Technology")
        child = Category.objects.create(
            site=default_site, name="Machine Learning", parent=root
        )
        assert child.depth == 1
        assert child.path == f"{root.path}.{str(child.pk).zfill(10)}"
        assert child.url_path == f"{root.slug}/{child.slug}"

    def test_paths_sort_in_tree_order(self, category_factory, default_site):
        root = category_factory(name="A")
        child = Category.objects.create(site=default_site, name="A-child", parent=root)
        sibling = category_factory(name="B")
        ordered = list(Category.unscoped.order_by("path").values_list("pk", flat=True))
        # Zero-padded segments are what make a plain lexical sort agree with the
        # tree; without the padding "10" sorts before "2".
        assert ordered.index(child.pk) == ordered.index(root.pk) + 1
        assert ordered.index(sibling.pk) > ordered.index(child.pk)

    def test_bengali_slugs_survive_into_url_path(self, category_factory, default_site):
        root = category_factory(name="প্রযুক্তি")
        child = Category.objects.create(
            site=default_site, name="যান্ত্রিক অনুবাদ", parent=root
        )
        assert "যান্ত্রিক" in child.slug
        assert child.url_path == f"{root.slug}/{child.slug}"


class TestMoves:
    def test_moving_rewrites_every_descendant_url(self, category_factory, default_site):
        old_root = category_factory(name="Old")
        new_root = category_factory(name="New")
        mid = Category.objects.create(site=default_site, name="Mid", parent=old_root)
        leaf = Category.objects.create(site=default_site, name="Leaf", parent=mid)
        assert leaf.url_path == f"{old_root.slug}/{mid.slug}/{leaf.slug}"

        mid.move_to(new_root)

        leaf.refresh_from_db()
        mid.refresh_from_db()
        assert mid.url_path == f"{new_root.slug}/{mid.slug}"
        assert leaf.url_path == f"{new_root.slug}/{mid.slug}/{leaf.slug}"
        assert leaf.depth == 2
        assert leaf.path.startswith(f"{mid.path}.")

    def test_cannot_move_under_own_descendant(self, category_factory, default_site):
        root = category_factory(name="Root")
        child = Category.objects.create(site=default_site, name="Child", parent=root)
        # The failure mode this guards is silent: the database is perfectly
        # happy with the cycle, and the whole branch simply stops appearing
        # under any root.
        with pytest.raises(ValidationError):
            root.move_to(child)
        root.refresh_from_db()
        assert root.parent_id is None

    def test_cannot_be_its_own_parent(self, category_factory):
        root = category_factory(name="Root")
        with pytest.raises(ValidationError):
            root.move_to(root)

    def test_depth_is_capped(self, category_factory, default_site):
        node = category_factory(name="L0")
        for level in range(1, MAX_DEPTH):
            node = Category.objects.create(
                site=default_site, name=f"L{level}", parent=node
            )
        too_deep = category_factory(name="Extra")
        with pytest.raises(ValidationError):
            too_deep.move_to(node)

    def test_cannot_move_across_sites(self, category_factory, other_site):
        here = category_factory(name="Here")
        there = Category.objects.create(site=other_site, name="There")
        with pytest.raises(ValidationError):
            here.move_to(there)

    def test_renaming_a_parent_rewrites_child_urls(self, category_factory, default_site):
        root = category_factory(name="Technology")
        child = Category.objects.create(site=default_site, name="AI", parent=root)
        root.slug = "tech"
        root.save()
        child.refresh_from_db()
        assert child.url_path == f"tech/{child.slug}"


class TestDeletion:
    def test_deleting_a_parent_is_refused(self, category_factory, default_site):
        root = category_factory(name="Root")
        Category.objects.create(site=default_site, name="Child", parent=root)
        with pytest.raises(ValidationError):
            root.delete()
        assert Category.unscoped.filter(pk=root.pk).exists()


class TestTreeAPI:
    def test_tree_is_nested_and_unpaginated(
        self, auth_client, admin, category_factory, default_site
    ):
        root = category_factory(name="Technology")
        Category.objects.create(site=default_site, name="AI", parent=root)
        category_factory(name="Culture")

        body = auth_client(admin).get(f"{BASE}/categories/tree/").json()
        assert isinstance(body, list) and len(body) == 2
        tech = next(node for node in body if node["name"] == "Technology")
        assert [child["name"] for child in tech["children"]] == ["AI"]

    def test_move_endpoint_reports_changed_paths(
        self, auth_client, admin, category_factory, default_site
    ):
        old_root = category_factory(name="Old")
        new_root = category_factory(name="New")
        mid = Category.objects.create(site=default_site, name="Mid", parent=old_root)
        leaf = Category.objects.create(site=default_site, name="Leaf", parent=mid)

        response = auth_client(admin).post(
            f"{BASE}/categories/{mid.slug}/move/",
            {"parent": new_root.pk},
            format="json",
        )
        assert response.status_code == 200
        changed = {row["id"]: row for row in response.json()["changed_paths"]}
        # Both the moved node and its descendant, so the UI can offer a
        # redirect for each URL that just stopped resolving.
        assert set(changed) == {mid.pk, leaf.pk}
        assert changed[leaf.pk]["from"] == f"{old_root.slug}/{mid.slug}/{leaf.slug}"
        assert changed[leaf.pk]["to"] == f"{new_root.slug}/{mid.slug}/{leaf.slug}"

    def test_illegal_move_is_409(
        self, auth_client, admin, category_factory, default_site
    ):
        root = category_factory(name="Root")
        child = Category.objects.create(site=default_site, name="Child", parent=root)
        response = auth_client(admin).post(
            f"{BASE}/categories/{root.slug}/move/", {"parent": child.pk}, format="json"
        )
        assert response.status_code == 409
        assert response.json()["code"] == "illegal_move"

    def test_breadcrumbs_follow_the_tree(
        self, public_client, article_factory, category_factory, default_site
    ):
        root = category_factory(name="Technology")
        child = Category.objects.create(site=default_site, name="AI", parent=root)
        # One FK at any depth: the trail is derived from the node's ancestors,
        # so it stays correct however deep the article sits.
        article = article_factory(status="published", is_live=True, category=child)
        from apps.syndication.models import Placement

        Placement.objects.update_or_create(
            article=article,
            site=default_site,
            defaults={"is_primary": True, "is_live": True, "path_slug": article.slug},
        )

        body = public_client().get(f"/api/v1/public/articles/{article.slug}/").json()
        assert [step["name"] for step in body["category_path"]] == ["Technology", "AI"]
