"""Regression tests for role-based permissions.

The bug these guard: every role check read ``request.user.role`` directly, and
``AnonymousUser`` has no such attribute -- so an unauthenticated request that
reached an object-level check raised AttributeError and surfaced as a 500
instead of a 401/403.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from common.permissions import (
    IsAdminOrAuthor,
    IsAdminUser,
    IsAuthorOrReadOnly,
    IsOwnerOrAdmin,
    is_admin,
    user_role,
)

factory = APIRequestFactory()


def request_as(user, method="get"):
    request = getattr(factory, method)("/")
    request.user = user
    return request


class TestUserRoleHelper:
    def test_anonymous_returns_empty_string(self):
        assert user_role(AnonymousUser()) == ""

    def test_none_returns_empty_string(self):
        assert user_role(None) == ""

    def test_authenticated_returns_role(self, admin):
        assert user_role(admin) == "admin"

    def test_is_admin_is_false_for_anonymous(self):
        assert is_admin(AnonymousUser()) is False


@pytest.mark.django_db
class TestPermissionClassesRejectAnonymous:
    """Anonymous access must be denied, never raise."""

    def test_is_admin_user(self):
        assert IsAdminUser().has_permission(request_as(AnonymousUser()), None) is False

    def test_is_admin_or_author(self):
        assert (
            IsAdminOrAuthor().has_permission(request_as(AnonymousUser()), None) is False
        )

    def test_is_owner_or_admin_denies_at_view_level(self):
        # The important one: previously there was no has_permission at all, so
        # anonymous requests fell through to has_object_permission and crashed.
        assert (
            IsOwnerOrAdmin().has_permission(request_as(AnonymousUser()), None) is False
        )

    def test_is_owner_or_admin_object_check_does_not_raise(self, article_factory):
        article = article_factory()
        assert (
            IsOwnerOrAdmin().has_object_permission(
                request_as(AnonymousUser()), None, article
            )
            is False
        )

    def test_is_author_or_read_only_write_does_not_raise(self, article_factory):
        article = article_factory()
        assert (
            IsAuthorOrReadOnly().has_object_permission(
                request_as(AnonymousUser(), "post"), None, article
            )
            is False
        )

    def test_is_author_or_read_only_allows_anonymous_read(self, article_factory):
        article = article_factory()
        assert (
            IsAuthorOrReadOnly().has_object_permission(
                request_as(AnonymousUser()), None, article
            )
            is True
        )


@pytest.mark.django_db
class TestRolesAreHonoured:
    def test_admin_passes_admin_only(self, admin):
        assert IsAdminUser().has_permission(request_as(admin), None) is True

    def test_author_fails_admin_only(self, author):
        assert IsAdminUser().has_permission(request_as(author), None) is False

    def test_author_passes_admin_or_author(self, author):
        assert IsAdminOrAuthor().has_permission(request_as(author), None) is True

    def test_reader_fails_admin_or_author(self, reader):
        assert IsAdminOrAuthor().has_permission(request_as(reader), None) is False

    def test_owner_can_access_own_object(self, article_factory, author):
        article = article_factory(author=author)
        assert (
            IsOwnerOrAdmin().has_object_permission(request_as(author), None, article)
            is True
        )

    def test_non_owner_cannot_access(self, article_factory, reader):
        article = article_factory()
        assert (
            IsOwnerOrAdmin().has_object_permission(request_as(reader), None, article)
            is False
        )

    def test_admin_can_access_any_object(self, article_factory, admin):
        article = article_factory()
        assert (
            IsOwnerOrAdmin().has_object_permission(request_as(admin), None, article)
            is True
        )


@pytest.mark.django_db
class TestHasSiteRole:
    def _view(self, role="author"):
        class View:
            required_site_role = role

        return View()

    def _request(self, user, site):
        request = request_as(user)
        request.site = site
        return request

    def test_anonymous_is_denied(self, default_site):
        from common.permissions import HasSiteRole

        assert (
            HasSiteRole().has_permission(self._request(AnonymousUser(), default_site), self._view())
            is False
        )

    def test_viewer_cannot_reach_author_endpoints(
        self, author, membership_factory, default_site
    ):
        from common.permissions import HasSiteRole

        membership_factory(author, default_site, role="viewer")
        request = self._request(author, default_site)
        assert HasSiteRole().has_permission(request, self._view("author")) is False

    def test_author_passes_author_endpoints(
        self, author, membership_factory, default_site
    ):
        from common.permissions import HasSiteRole

        membership_factory(author, default_site, role="author")
        request = self._request(author, default_site)
        assert HasSiteRole().has_permission(request, self._view("author")) is True
        assert HasSiteRole().has_permission(request, self._view("editor")) is False

    def test_membership_is_cached_on_the_request(
        self, author, membership_factory, default_site
    ):
        from common.permissions import HasSiteRole, site_membership

        membership_factory(author, default_site, role="author")
        request = self._request(author, default_site)
        first = site_membership(request)
        second = site_membership(request)
        assert first is second
        assert HasSiteRole().has_permission(request, self._view("author")) is True


@pytest.mark.django_db
class TestCanEditSiteArticle:
    def test_author_cannot_write_someone_elses_article(
        self, article_factory, author, user_factory, membership_factory, default_site
    ):
        from common.permissions import CanEditSiteArticle

        membership_factory(author, default_site, role="author")
        other = user_factory(role="author")
        article = article_factory(author=other, status="published")
        request = request_as(author, "patch")
        request.site = default_site
        assert (
            CanEditSiteArticle().has_object_permission(request, None, article) is False
        )

    def test_author_can_write_own_article(
        self, article_factory, author, membership_factory, default_site
    ):
        from common.permissions import CanEditSiteArticle

        membership_factory(author, default_site, role="author")
        article = article_factory(author=author, status="published")
        request = request_as(author, "patch")
        request.site = default_site
        assert CanEditSiteArticle().has_object_permission(request, None, article) is True

    def test_editor_can_write_any_article(
        self, article_factory, author, user_factory, membership_factory, default_site
    ):
        from common.permissions import CanEditSiteArticle

        membership_factory(author, default_site, role="editor")
        other = user_factory(role="author")
        article = article_factory(author=other, status="published")
        request = request_as(author, "patch")
        request.site = default_site
        assert CanEditSiteArticle().has_object_permission(request, None, article) is True


@pytest.mark.django_db
class TestMediaDetailEndpoint:
    def test_anonymous_get_is_denied_not_a_server_error(
        self, api_client, author, default_site
    ):
        """End-to-end: an anonymous media GET used to raise AttributeError -> 500."""
        from django.core.files.base import ContentFile

        from apps.media_library.models import MediaFile

        media = MediaFile.objects.create(
            site=default_site,
            file=ContentFile(b"x", name="t.png"),
            file_type="image",
            uploaded_by=author,
        )
        response = api_client.get(f"/api/v1/studio/media/{media.id}/")
        assert response.status_code in (401, 403)
