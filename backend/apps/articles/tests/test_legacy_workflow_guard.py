"""Status is not an ordinary writable field on any surface.

Publishing goes through `POST /studio/articles/{slug}/transition/` so that it is
role-guarded, audited, and followed by the publish chain. This file exists
because the removed legacy API once exposed `status` as a plain serializer
field, which let an author publish their own work with a one-line PATCH --
skipping the editor requirement, the audit entry, and cache invalidation. The
hole is closed by `read_only_fields`, and read-only-ness is the kind of thing
that gets undone by a well-meaning refactor, so it is asserted rather than
assumed.
"""

import pytest

from apps.editorial.models import AuditLogEntry

LIST_URL = "/api/v1/studio/articles/"

pytestmark = pytest.mark.django_db


class TestStatusIsNotDirectlyWritable:
    def test_author_cannot_self_publish_via_patch(
        self, auth_client, author, article_factory, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)

        response = auth_client(author).patch(
            f"{LIST_URL}{article.slug}/", {"status": "published"}, format="json"
        )

        # Ignored, not rejected -- DRF drops read-only fields silently. What
        # matters is that the article did not move.
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.status == "draft"
        assert article.is_live is False

    def test_no_audit_entry_is_forged(
        self, auth_client, author, article_factory, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        auth_client(author).patch(
            f"{LIST_URL}{article.slug}/", {"status": "published"}, format="json"
        )
        assert not AuditLogEntry.objects.filter(
            article=article, action="publish"
        ).exists()

    def test_even_an_admin_cannot_set_status_directly(
        self, auth_client, admin, article_factory
    ):
        article = article_factory(status="draft")
        auth_client(admin).patch(
            f"{LIST_URL}{article.slug}/", {"status": "published"}, format="json"
        )
        # Being allowed to publish is not the same as being allowed to bypass
        # the chain that makes a publish take effect.
        article.refresh_from_db()
        assert article.status == "draft"

    def test_edits_that_do_not_touch_status_still_work(
        self, auth_client, author, article_factory, default_site, membership_factory
    ):
        membership_factory(author, default_site, role="author")
        article = article_factory(status="draft", author=author)
        response = auth_client(author).patch(
            f"{LIST_URL}{article.slug}/", {"title": "Edited"}, format="json"
        )
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.title == "Edited"
