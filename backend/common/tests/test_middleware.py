"""Tests for tenant resolution."""

import pytest

from apps.tenancy.models import SiteDomain

pytestmark = pytest.mark.django_db


class TestResolutionOrder:
    def test_api_key_wins(self, api_client, api_key_factory, other_site, default_site):
        """An API key is an unambiguous tenant claim and outranks the Host."""
        _, raw = api_key_factory(other_site, scopes=["read:content"])
        api_client.credentials(HTTP_X_API_KEY=raw)
        response = api_client.get("/api/v1/public/site/")
        assert response.status_code == 200
        assert response.json()["slug"] == other_site.slug

    def test_site_header_used_when_no_api_key(
        self, auth_client, admin, other_site, default_site
    ):
        response = auth_client(admin).get(
            "/api/v1/studio/articles/", HTTP_X_CMS_SITE=other_site.slug
        )
        assert response.status_code == 200

    def test_host_resolution(self, auth_client, admin, other_site):
        response = auth_client(admin).get(
            "/api/v1/studio/articles/", HTTP_HOST=other_site.primary_domain
        )
        assert response.status_code == 200

    def test_host_alias_resolution(self, auth_client, admin, other_site):
        SiteDomain.objects.create(site=other_site, domain="alias.example.com")
        response = auth_client(admin).get(
            "/api/v1/studio/articles/", HTTP_HOST="alias.example.com"
        )
        assert response.status_code == 200

    def test_falls_back_to_default(self, auth_client, admin, default_site, article_factory):
        # testserver matches no site, so resolution lands on the default.
        article_factory(status="published", title="Default Site Article")
        body = auth_client(admin).get("/api/v1/studio/articles/").json()
        assert body["results"][0]["title"] == "Default Site Article"

    def test_unknown_host_does_not_error(self, auth_client, admin, default_site):
        response = auth_client(admin).get(
            "/api/v1/studio/articles/", HTTP_HOST="nowhere.invalid"
        )
        assert response.status_code == 200

    def test_inactive_site_is_not_resolved_by_host(
        self, auth_client, admin, other_site, default_site
    ):
        other_site.is_active = False
        other_site.save()
        response = auth_client(admin).get(
            "/api/v1/studio/articles/", HTTP_HOST=other_site.primary_domain
        )
        # Falls back to the default site rather than serving a disabled tenant.
        assert response.status_code == 200
        assert response.wsgi_request.site.pk == default_site.pk


class TestRequestAttributes:
    def test_sets_site_and_key_attributes(self, api_client, api_key_factory, default_site):
        _, raw = api_key_factory(default_site, scopes=["read:content"])
        api_client.credentials(HTTP_X_API_KEY=raw)
        request = api_client.get("/api/v1/public/site/").wsgi_request
        assert request.site == default_site
        assert request.api_key is not None
        assert "read:content" in request.api_scopes

    def test_invalid_key_leaves_api_key_none(self, api_client, default_site):
        api_client.credentials(HTTP_X_API_KEY="ia_live_bogus")
        request = api_client.get("/api/v1/public/articles/").wsgi_request
        assert request.api_key is None
        # A site is still resolved from the Host header, so a bad key produces a
        # clean 403 from the permission class rather than a crash in the view.
        assert request.site == default_site

    def test_contextvar_does_not_leak_between_requests(self, api_client, default_site):
        from common.tenancy import get_current_site

        api_client.get("/api/v1/public/articles/")
        # The middleware resets in process_response; nothing should survive.
        assert get_current_site() is None
