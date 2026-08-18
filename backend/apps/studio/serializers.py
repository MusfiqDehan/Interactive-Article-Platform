"""Serializers for the authoring API (``/api/v1/studio/``).

Unlike the public surface, these expose internal state an editor needs --
``is_live``, ``word_count``, ``content_hash``, placement summaries -- because
the studio is the tool for managing exactly those things.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.articles.models import Article
from apps.articles.serializers import validate_blocks
from apps.categories.models import MAX_DEPTH, Category
from apps.taxonomy.models import set_tags, tags_for
from apps.taxonomy.serializers import TagSerializer
from apps.media_library.models import MediaFile
from apps.syndication.models import Placement
from apps.tenancy.models import ApiKey, Site, SiteMembership, SiteSettings

User = get_user_model()


class StudioAuthorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "name", "avatar", "role")

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class StudioPlacementSerializer(serializers.ModelSerializer):
    site_slug = serializers.CharField(source="site.slug", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    url = serializers.CharField(read_only=True)
    canonical_url = serializers.SerializerMethodField()

    class Meta:
        model = Placement
        fields = (
            "id", "site", "site_slug", "site_name", "path_slug",
            "is_primary", "is_live", "canonical_to_primary",
            "override_title", "override_excerpt", "published_at",
            "order", "url", "canonical_url",
        )
        read_only_fields = ("id", "is_primary")

    def get_canonical_url(self, obj):
        return obj.resolved_canonical()


class StudioCategorySerializer(serializers.ModelSerializer):
    article_count = serializers.IntegerField(read_only=True, required=False)
    child_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = (
            "id", "name", "slug", "description", "image", "is_active",
            "order", "parent", "path", "url_path", "depth", "child_count",
            "article_count", "created_at", "updated_at",
        )
        # path/url_path/depth are derived from the tree by Category.save(); a
        # client that could set them could describe a shape that does not exist.
        read_only_fields = (
            "id", "slug", "path", "url_path", "depth", "created_at", "updated_at",
        )

    def validate_parent(self, value):
        if value is None:
            return value
        instance = self.instance
        if instance is not None:
            if value.pk == instance.pk:
                raise serializers.ValidationError("A category cannot be its own parent.")
            if instance.path and value.path.startswith(f"{instance.path}."):
                raise serializers.ValidationError(
                    "Cannot move a category beneath one of its own descendants."
                )
        if value.depth + 1 >= MAX_DEPTH:
            raise serializers.ValidationError(
                f"Categories nest at most {MAX_DEPTH} levels deep."
            )
        return value


class StudioCategoryNodeSerializer(StudioCategorySerializer):
    """A category with its subtree inlined, for the tree view.

    Recursion is bounded by ``MAX_DEPTH``, and the whole tree is assembled from
    one query in the view -- ``children`` reads a prefetched list rather than
    issuing a query per node, which on a four-level tree would otherwise be the
    classic N+1 that only shows up once a real taxonomy exists.
    """

    children = serializers.SerializerMethodField()

    class Meta(StudioCategorySerializer.Meta):
        fields = StudioCategorySerializer.Meta.fields + ("children",)

    def get_children(self, obj):
        children = self.context.get("children_by_parent", {}).get(obj.pk, [])
        return StudioCategoryNodeSerializer(children, many=True, context=self.context).data


class StudioCategoryMoveSerializer(serializers.Serializer):
    parent = serializers.IntegerField(allow_null=True)
    order = serializers.IntegerField(required=False, min_value=0)


class StudioArticleListSerializer(serializers.ModelSerializer):
    author = StudioAuthorSerializer(read_only=True)
    category_name = serializers.CharField(source="category.name", default=None, read_only=True)
    placement_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Article
        fields = (
            "id", "title", "slug", "author", "category", "category_name",
            "excerpt", "featured_image", "status", "is_live", "is_featured",
            "reading_time", "word_count", "views_count",
            "published_at", "created_at", "updated_at", "placement_count",
        )


class StudioArticleDetailSerializer(serializers.ModelSerializer):
    author = StudioAuthorSerializer(read_only=True)
    placements = StudioPlacementSerializer(many=True, read_only=True)
    #: Embedded rather than left to a second request: the editor's Publish
    #: button has to know its primary action before it can render, and a split
    #: button that flickers through a default state is worse than a slower load.
    available_transitions = serializers.SerializerMethodField()
    #: Write a list of names or slugs; unknown ones are created. Reads back as
    #: the resolved tags, so the client never has to guess what a free-typed
    #: name turned into.
    tags = serializers.SerializerMethodField()
    tag_slugs = serializers.ListField(
        child=serializers.CharField(max_length=120),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Article
        fields = (
            "id", "title", "slug", "author", "category",
            "content", "excerpt", "featured_image", "status", "is_live",
            "is_featured", "reading_time", "word_count", "views_count",
            "content_hash", "published_at", "last_published_at",
            "unpublished_at", "scheduled_publish_at", "scheduled_unpublish_at",
            "locale", "created_at", "updated_at",
            "placements", "available_transitions", "tags", "tag_slugs",
        )
        read_only_fields = (
            "id", "slug", "author", "is_live", "reading_time", "word_count",
            "views_count", "content_hash", "published_at", "last_published_at",
            "unpublished_at", "created_at", "updated_at", "placements",
            "available_transitions", "tags",
            # Status is moved only through the transition endpoint, never by a
            # plain PATCH -- otherwise the state machine's guards, role checks
            # and audit entries can all be bypassed with a one-line request.
            "status",
        )

    def get_available_transitions(self, article):
        from apps.editorial.transitions import available

        request = self.context.get("request")
        if request is None:
            return []
        return available(article, request.user, site=getattr(request, "site", None))

    def get_tags(self, article):
        return TagSerializer(tags_for(article), many=True).data

    def validate_content(self, value):
        return validate_blocks(value)

    def create(self, validated_data):
        slugs = validated_data.pop("tag_slugs", None)
        article = super().create(validated_data)
        if slugs is not None:
            set_tags(article, slugs, site=article.site)
        return article

    def update(self, instance, validated_data):
        # Popped before the super() call because `tag_slugs` is not a model
        # field; leaving it in validated_data makes ModelSerializer.update()
        # setattr it onto the article and the next save() raises.
        slugs = validated_data.pop("tag_slugs", None)
        article = super().update(instance, validated_data)
        if slugs is not None:
            set_tags(article, slugs, site=article.site)
        return article


class StudioMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MediaFile
        fields = (
            "id", "file", "url", "file_type", "title", "alt_text",
            "file_size", "mime_type", "uploaded_by", "created_at",
        )
        read_only_fields = ("id", "file_size", "mime_type", "uploaded_by", "created_at")

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return ""


class StudioSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = (
            "id", "name", "slug", "kind", "primary_domain", "base_url",
            "locale", "is_default", "is_active", "created_at",
        )
        read_only_fields = ("id", "created_at")


class StudioMembershipSerializer(serializers.ModelSerializer):
    """A person's role on the current site.

    Writes take an ``email`` rather than a user id: an owner inviting a
    colleague knows their address, not their primary key, and forcing a user
    lookup first turns one action into two. The user must already exist --
    creating accounts is registration's job, not the people screen's.
    """

    user = StudioAuthorSerializer(read_only=True)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = SiteMembership
        fields = ("id", "user", "email", "role", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def validate_email(self, value):
        user = User.objects.filter(email__iexact=value).first()
        if user is None:
            raise serializers.ValidationError(
                "No account with that email. They need to register first."
            )
        self._user = user
        return value

    def create(self, validated_data):
        validated_data.pop("email", None)
        user = getattr(self, "_user", None)
        if user is None:
            raise serializers.ValidationError({"email": ["This field is required."]})
        site = validated_data.pop("site")
        membership, created = SiteMembership.objects.get_or_create(
            site=site, user=user, defaults=validated_data
        )
        if not created:
            # Re-inviting someone who is already a member is a role change, not
            # a duplicate-key error the owner has to decode.
            membership.role = validated_data.get("role", membership.role)
            membership.save(update_fields=["role"])
        return membership


class StudioScheduleEntrySerializer(serializers.ModelSerializer):
    """One article on the publishing calendar.

    ``at`` collapses the three dates a calendar cell can represent -- scheduled
    publish, scheduled unpublish, actual publication -- into a single sortable
    field, with ``kind`` saying which it is. The alternative, three date fields
    the client re-buckets, means every calendar consumer reimplements the same
    branch and one of them gets it wrong.
    """

    author_name = serializers.CharField(source="author.username", default="", read_only=True)
    at = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = (
            "id", "title", "slug", "status", "is_live", "author_name",
            "at", "kind", "scheduled_publish_at", "scheduled_unpublish_at",
            "published_at",
        )

    def get_kind(self, article):
        if article.scheduled_publish_at and article.status == "scheduled":
            return "scheduled_publish"
        if article.scheduled_unpublish_at:
            return "scheduled_unpublish"
        return "published"

    def get_at(self, article):
        value = {
            "scheduled_publish": article.scheduled_publish_at,
            "scheduled_unpublish": article.scheduled_unpublish_at,
            "published": article.published_at,
        }[self.get_kind(article)]
        return value.isoformat() if value else None


class StudioSiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        exclude = ("id", "site")
        # Never echo the shared secret back to a browser.
        extra_kwargs = {"revalidate_secret": {"write_only": True}}


class StudioApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = (
            "id", "name", "prefix", "scopes", "last_used_at",
            "expires_at", "revoked_at", "rate_limit_per_minute", "created_at",
        )
        # hashed_key is never exposed; the raw key is returned once, on create.
        read_only_fields = ("id", "prefix", "last_used_at", "created_at")
