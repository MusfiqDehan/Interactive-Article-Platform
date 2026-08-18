"""Tests for the tenancy models, especially API key handling."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.tenancy.models import ApiKey, Site, SiteDomain

pytestmark = pytest.mark.django_db


class TestSite:
    def test_only_one_default_site(self, default_site):
        # Partial unique index: a second default must be rejected outright.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Site.objects.create(
                    name="Another",
                    slug="another",
                    primary_domain="another.example.com",
                    base_url="https://another.example.com",
                    is_default=True,
                )

    def test_many_non_default_sites_allowed(self, default_site, other_site):
        assert Site.objects.filter(is_default=False).count() >= 1

    def test_domain_is_normalised(self, db):
        site = Site.objects.create(
            name="Case",
            slug="case",
            primary_domain="  EXAMPLE.COM  ",
            base_url="https://example.com/",
        )
        assert site.primary_domain == "example.com"
        # Trailing slash stripped so url_for() never double-slashes.
        assert site.base_url == "https://example.com"

    def test_url_for(self, default_site):
        assert default_site.url_for("articles/x") == f"{default_site.base_url}/articles/x"
        assert default_site.url_for("/articles/x") == f"{default_site.base_url}/articles/x"

    def test_get_default(self, default_site):
        assert Site.get_default() == default_site


class TestApiKey:
    def test_generate_returns_raw_key_once(self, default_site):
        api_key, raw = ApiKey.generate(default_site, "test")
        assert raw.startswith("ia_live_")
        assert api_key.prefix == raw[:12]
        # Only the hash is persisted -- the raw value must not be recoverable.
        assert raw not in api_key.hashed_key
        assert api_key.hashed_key == ApiKey.hash_key(raw)

    def test_resolve_valid_key(self, default_site):
        api_key, raw = ApiKey.generate(default_site, "test")
        assert ApiKey.resolve(raw) == api_key

    def test_resolve_rejects_tampered_key(self, default_site):
        _, raw = ApiKey.generate(default_site, "test")
        assert ApiKey.resolve(raw[:-4] + "zzzz") is None

    def test_resolve_rejects_unknown_prefix(self, default_site):
        assert ApiKey.resolve("ia_live_totallymadeupkey") is None

    def test_resolve_rejects_empty_or_short(self, default_site):
        assert ApiKey.resolve("") is None
        assert ApiKey.resolve("short") is None

    def test_resolve_rejects_revoked(self, default_site):
        api_key, raw = ApiKey.generate(default_site, "test")
        api_key.revoked_at = timezone.now()
        api_key.save()
        assert ApiKey.resolve(raw) is None

    def test_resolve_rejects_expired(self, default_site):
        api_key, raw = ApiKey.generate(default_site, "test")
        api_key.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        api_key.save()
        assert ApiKey.resolve(raw) is None

    def test_resolve_rejects_inactive_site(self, other_site):
        _, raw = ApiKey.generate(other_site, "test")
        other_site.is_active = False
        other_site.save()
        assert ApiKey.resolve(raw) is None

    def test_scopes(self, default_site):
        api_key, _ = ApiKey.generate(default_site, "test", scopes=["read:content"])
        assert api_key.has_scope("read:content")
        assert not api_key.has_scope("write:events")

    def test_touch_is_rate_limited(self, default_site):
        api_key, _ = ApiKey.generate(default_site, "test")
        api_key.touch()
        first = api_key.last_used_at
        api_key.touch()  # immediately again -- should not write
        assert api_key.last_used_at == first

    def test_install_persists_a_known_raw_key(self, default_site):
        raw = "ia_live_known-key-for-local-bootstrap-tests-xxxx"
        installed = ApiKey.install(default_site, raw, name="Frontend delivery")
        assert ApiKey.resolve(raw) == installed
        assert installed.prefix == raw[:12]
        # Calling again with the same raw key must not insert a second row.
        again = ApiKey.install(default_site, raw, name="Frontend delivery")
        assert again.pk == installed.pk

    def test_install_rejects_short_keys(self, default_site):
        with pytest.raises(ValueError):
            ApiKey.install(default_site, "short")


class TestSiteDomain:
    def test_alias_is_normalised(self, default_site):
        domain = SiteDomain.objects.create(site=default_site, domain="ALIAS.Example.COM")
        assert domain.domain == "alias.example.com"

    def test_domain_is_globally_unique(self, default_site, other_site):
        SiteDomain.objects.create(site=default_site, domain="shared.example.com")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SiteDomain.objects.create(site=other_site, domain="shared.example.com")
