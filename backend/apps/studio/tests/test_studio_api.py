"""Tests for the authoring API."""

import pytest

from apps.syndication.models import Placement
from apps.tenancy.models import ApiKey

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


class TestAuth:
    def test_anonymous_is_rejected(self, api_client):
        assert api_client.get(f"{BASE}/articles/").status_code in (401, 403)

    def test_user_without_membership_is_rejected(self, auth_client, author):
        assert auth_client(author).get(f"{BASE}/articles/").status_code == 403

    def test_global_admin_bypasses_membership(self, auth_client, admin):
        assert auth_client(admin).get(f"{BASE}/articles/").status_code == 200

    def test_member_is_allowed(self, auth_client, author, membership_factory, default_site):
        membership_factory(author, default_site, role="author")
        assert auth_client(author).get(f"{BASE}/articles/").status_code == 200

    def test_role_hierarchy_is_enforced(
        self, auth_client, author, membership_factory, default_site
    ):
        # Categories require `editor`; an `author` sits below that.
        membership_factory(author, default_site, role="author")
        assert auth_client(author).get(f"{BASE}/categories/").status_code == 403

    def test_editor_can_reach_categories(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="editor")
        assert auth_client(author).get(f"{BASE}/categories/").status_code == 200


class TestArticles:
    def test_pagination_is_25(self, auth_client, admin, article_factory):
        for _ in range(30):
            article_factory()
        body = auth_client(admin).get(f"{BASE}/articles/").json()
        # Denser than the legacy surface's 12.
        assert len(body["results"]) == 25
        assert body["count"] == 30

    def test_list_exposes_internal_state(self, auth_client, admin, article_factory):
        article_factory(status="published")
        row = auth_client(admin).get(f"{BASE}/articles/").json()["results"][0]
        # The studio needs what the public API deliberately hides.
        assert "is_live" in row and "word_count" in row

    def test_create_stamps_site_and_author(self, auth_client, admin, default_site):
        response = auth_client(admin).post(
            f"{BASE}/articles/",
            {"title": "Studio Made", "content": {"blocks": []}, "status": "draft"},
            format="json",
        )
        assert response.status_code == 201

        from apps.articles.models import Article

        article = Article.unscoped.get(title="Studio Made")
        assert article.site_id == default_site.pk
        assert article.author == admin

    def test_create_also_creates_a_primary_placement(self, auth_client, admin):
        client = auth_client(admin)
        client.post(
            f"{BASE}/articles/",
            {"title": "With Placement", "content": {"blocks": []}},
            format="json",
        )
        from apps.articles.models import Article

        article = Article.unscoped.get(title="With Placement")
        placement = Placement.objects.get(article=article, is_primary=True)
        assert placement.path_slug == article.slug
        # Not live yet: articles are born as drafts.
        assert placement.is_live is False

        # Publishing is a transition, never a field assignment.
        client.post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )
        placement.refresh_from_db()
        assert placement.is_live is True

    def test_status_cannot_be_set_by_a_plain_write(self, auth_client, admin):
        """A PATCH must not be able to bypass the state machine.

        If it could, an author could publish without the role check, without an
        audit entry, and without the publish chain ever running.
        """
        client = auth_client(admin)
        client.post(
            f"{BASE}/articles/",
            {"title": "Sneaky", "content": {"blocks": []}, "status": "published"},
            format="json",
        )
        from apps.articles.models import Article

        article = Article.unscoped.get(title="Sneaky")
        assert article.status == "draft"
        assert article.is_live is False

        client.patch(
            f"{BASE}/articles/{article.slug}/",
            {"status": "published"},
            format="json",
        )
        article.refresh_from_db()
        assert article.status == "draft"

    def test_detail_includes_placements(self, auth_client, admin, article_factory):
        article = article_factory(status="published")
        body = auth_client(admin).get(f"{BASE}/articles/{article.slug}/").json()
        assert len(body["placements"]) == 1
        assert body["placements"][0]["is_primary"] is True

    def test_content_is_sanitized_on_write(self, auth_client, admin):
        response = auth_client(admin).post(
            f"{BASE}/articles/",
            {
                "title": "Hostile",
                "content": {
                    "blocks": [
                        {"type": "paragraph", "data": {"text": "<script>x()</script>hi"}}
                    ]
                },
            },
            format="json",
        )
        assert response.status_code == 201
        assert "<script" not in response.json()["content"]["blocks"][0]["data"]["text"]

    def test_unknown_block_type_is_rejected(self, auth_client, admin):
        response = auth_client(admin).post(
            f"{BASE}/articles/",
            {"title": "Bad", "content": {"blocks": [{"type": "evil", "data": {}}]}},
            format="json",
        )
        assert response.status_code == 400

    def test_author_sees_own_drafts_but_not_others(
        self, auth_client, author, membership_factory, default_site, article_factory, user_factory
    ):
        membership_factory(author, default_site, role="author")
        other = user_factory(role="author")
        article_factory(author=author, status="draft", title="My Draft")
        article_factory(author=other, status="draft", title="Their Draft")
        article_factory(author=other, status="published", title="Their Published")

        titles = {
            r["title"] for r in auth_client(author).get(f"{BASE}/articles/").json()["results"]
        }
        assert "My Draft" in titles
        assert "Their Published" in titles
        assert "Their Draft" not in titles

    def test_add_placement(self, auth_client, admin, article_factory, other_site):
        article = article_factory(status="published")
        response = auth_client(admin).post(
            f"{BASE}/articles/{article.slug}/placements/",
            {
                "site": other_site.pk,
                "path_slug": "syndicated",
                "is_live": True,
                "canonical_to_primary": True,
            },
            format="json",
        )
        assert response.status_code == 201
        assert Placement.objects.filter(article=article, site=other_site).exists()


class TestApiKeys:
    def test_owner_can_mint_a_key(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        response = auth_client(author).post(
            f"{BASE}/api-keys/", {"name": "partner"}, format="json"
        )
        assert response.status_code == 201
        body = response.json()
        # Raw key is returned exactly once, at creation.
        assert body["key"].startswith("ia_live_")
        assert "warning" in body

    def test_editor_cannot_mint_a_key(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="editor")
        assert (
            auth_client(author).post(f"{BASE}/api-keys/", {"name": "x"}, format="json").status_code
            == 403
        )

    def test_list_never_exposes_the_hash_or_raw_key(self, auth_client, admin, default_site):
        ApiKey.generate(default_site, "existing")
        row = auth_client(admin).get(f"{BASE}/api-keys/").json()["results"][0]
        assert "hashed_key" not in row
        assert "key" not in row

    def test_delete_revokes_rather_than_destroys(self, auth_client, admin, default_site):
        api_key, _ = ApiKey.generate(default_site, "doomed")
        assert auth_client(admin).delete(f"{BASE}/api-keys/{api_key.pk}/").status_code == 204

        api_key.refresh_from_db()
        # Kept for the audit trail, but no longer usable.
        assert api_key.revoked_at is not None
        assert api_key.is_usable is False


class TestSettings:
    def test_owner_can_read_settings(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        response = auth_client(author).get(f"{BASE}/settings/")
        assert response.status_code == 200
        assert "title_template" in response.json()

    def test_secret_is_write_only(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        body = auth_client(author).get(f"{BASE}/settings/").json()
        assert "revalidate_secret" not in body
