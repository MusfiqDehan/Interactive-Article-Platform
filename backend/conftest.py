"""Shared pytest fixtures.

Kept at the repo root of ``backend/`` so every app package can rely on the same
factories without importing across app boundaries.
"""

import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Clear the cache around every test.

    Tests run against the real Redis (worth it -- it exercises INCR semantics
    and the IGNORE_EXCEPTIONS path that LocMem cannot). The cost is that cached
    responses survive between tests unless explicitly cleared, which silently
    turns test order into a dependency.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Run tasks inline instead of dispatching them to the real broker.

    Without this, ``.delay()`` in a test enqueues onto the development Redis and
    the running worker picks it up -- against the *development* database, where
    the test's objects do not exist. That is both a silent no-op and a way for a
    test run to disturb a live environment.

    Set through Django settings, not ``celery_app.conf``. The app is configured
    with ``config_from_object("django.conf:settings")``, which re-reads the
    Django settings on every access, so a direct assignment to ``conf`` is
    silently discarded on the next read -- it looks like it worked and does
    nothing.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    # False so a failing side-effect task surfaces in its result rather than
    # propagating into the caller, which is how a real worker behaves.
    settings.CELERY_TASK_EAGER_PROPAGATES = False


@pytest.fixture(autouse=True)
def _no_live_search(settings):
    """Point the search client at nothing for the whole suite.

    Two reasons, both discovered the hard way. A configured `MEILISEARCH_URL`
    makes every `Article.save()` in every test index against a real engine --
    slow, and it pollutes a development index with thousands of fixture rows.
    And Meilisearch's client uses `requests`, so it collides with the
    outbound-HTTP stub below and fails with an error about `raise_for_status`
    that says nothing about search.

    Everything degrades to "search unavailable", which is a supported state by
    design. Tests that exercise search monkeypatch `client.get_client`
    directly with a fake engine.
    """
    settings.MEILISEARCH_URL = ""
    settings.MEILISEARCH_PUBLIC_URL = ""


@pytest.fixture(autouse=True)
def stub_outbound_http(monkeypatch):
    """Record outbound POSTs instead of making them.

    Publishing calls the frontend's revalidation endpoint. A test suite that
    actually issues those requests is slow, order-dependent, and purges a real
    site's cache. Yields the recorded call list so tests can assert on it.
    """

    calls = []

    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {}

    def _record(url, *args, **kwargs):
        calls.append({"url": url, **kwargs})
        return _Response()

    monkeypatch.setattr("requests.post", _record)
    return calls


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def default_site(db):
    """The site created by tenancy.0002_bootstrap_default_site.

    Recreated defensively: --reuse-db or a squashed migration history could
    leave a test database without it.
    """
    from apps.tenancy.models import Site, SiteSettings

    site = Site.objects.filter(is_default=True).first()
    if site is None:
        site = Site.objects.create(
            name="Test Site",
            slug="default",
            primary_domain="testserver",
            base_url="http://testserver",
            is_default=True,
        )
    SiteSettings.objects.get_or_create(site=site, defaults={"site_title": site.name})
    return site


@pytest.fixture(autouse=True)
def _ensure_default_site(request):
    """Guarantee a default Site for every test that touches the database.

    Tests used to inherit the row seeded by ``tenancy.0002``, which made the
    whole suite quietly order-dependent: a single ``transaction=True`` test
    truncates every table on teardown, taking migration-created data with it,
    and with ``--reuse-db`` that damage survives into later runs. The symptom is
    a NOT NULL violation on ``site_id`` in tests that have nothing to do with
    the one that caused it.

    Recreating it per test is cheap (one SELECT, occasionally one INSERT),
    self-heals after a truncation, and matches production, where a default site
    always exists.
    """
    uses_db = request.node.get_closest_marker("django_db") is not None or bool(
        {"db", "transactional_db", "django_db_setup"} & set(request.fixturenames)
    )
    if uses_db:
        request.getfixturevalue("default_site")


@pytest.fixture
def other_site(db):
    """A second tenant, for asserting isolation."""
    from apps.tenancy.models import Site, SiteSettings

    site = Site.objects.create(
        name="Partner Site",
        slug="partner",
        primary_domain="partner.example.com",
        base_url="https://partner.example.com",
        locale="bn",
    )
    SiteSettings.objects.create(site=site, site_title=site.name)
    return site


@pytest.fixture
def api_key_factory(db):
    """Return ``(ApiKey, raw_key)`` for a site."""
    from apps.tenancy.models import ApiKey

    def _make(site, name="test-key", scopes=None, **kwargs):
        return ApiKey.generate(site=site, name=name, scopes=scopes, **kwargs)

    return _make


@pytest.fixture
def public_client(api_client, api_key_factory, default_site):
    """APIClient pre-authenticated against a site's public delivery API."""

    def _for(site=None):
        site = site or default_site
        _, raw_key = api_key_factory(
            site,
            scopes=["read:content", "read:taxonomy", "read:media", "write:events"],
        )
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=raw_key)
        return client

    return _for


@pytest.fixture
def membership_factory(db):
    from apps.tenancy.models import SiteMembership

    def _make(user, site, role="editor"):
        return SiteMembership.objects.create(user=user, site=site, role=role)

    return _make


# Tables holding tenant-owned rows. A SELECT against any of these that carries
# no site_id predicate is a potential cross-tenant leak.
TENANT_TABLES = (
    "articles_article",
    "categories_category",
    "categories_subcategory",
    "media_library_mediafile",
)


@pytest.fixture
def assert_queries_scoped(db):
    """Fail if any SELECT touches a tenant table without filtering on site_id.

    The third enforcement layer behind ``TenantModel`` and
    ``TenantScopedViewSetMixin``: those make scoping easy and hard to skip
    respectively, while this proves it actually happened at the SQL level.

    Usage::

        with assert_queries_scoped():
            client.get("/api/v1/public/articles/")
    """
    import contextlib
    import re

    from django.db import connection

    @contextlib.contextmanager
    def _checker(allow_tables=()):
        offenders = []

        def wrapper(execute, sql, params, many, context):
            lowered = sql.lower()
            if lowered.lstrip().startswith("select"):
                for table in TENANT_TABLES:
                    if table in allow_tables:
                        continue
                    # Only inspect queries that actually read the table.
                    if re.search(rf'\b(from|join)\s+"?{table}"?', lowered):
                        # Look for site_id in the predicate, not the whole
                        # statement -- ``site`` is a concrete column, so it
                        # appears in every SELECT list and a naive substring
                        # check would pass unconditionally.
                        _, _, predicate = lowered.partition(" where ")
                        if "site_id" not in predicate:
                            offenders.append(sql)
                        break
            return execute(sql, params, many, context)

        with connection.execute_wrapper(wrapper):
            yield

        if offenders:
            joined = "\n\n".join(offenders[:5])
            raise AssertionError(
                f"{len(offenders)} unscoped quer{'y' if len(offenders) == 1 else 'ies'} "
                f"against tenant tables:\n\n{joined}"
            )

    return _checker


@pytest.fixture
def user_factory(db):
    """Create users without going through the (slow) default password hasher."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    counter = {"n": 0}

    def _make(role="reader", password="pw-testing-only", **kwargs):
        counter["n"] += 1
        n = counter["n"]
        kwargs.setdefault("email", f"user{n}@example.com")
        kwargs.setdefault("username", f"user{n}")
        user = User.objects.create_user(password=password, role=role, **kwargs)
        return user

    return _make


@pytest.fixture
def reader(user_factory):
    return user_factory(role="reader")


@pytest.fixture
def author(user_factory):
    return user_factory(role="author")


@pytest.fixture
def admin(user_factory):
    return user_factory(role="admin")


@pytest.fixture
def auth_client(api_client):
    """Return a callable that authenticates the shared APIClient as ``user``."""

    def _as(user):
        api_client.force_authenticate(user=user)
        return api_client

    return _as


@pytest.fixture
def article_factory(db, author, default_site):
    from apps.articles.models import Article

    counter = {"n": 0}

    def _make(**kwargs):
        counter["n"] += 1
        n = counter["n"]
        kwargs.setdefault("title", f"Test Article {n}")
        kwargs.setdefault("author", author)
        kwargs.setdefault("content", {"blocks": []})
        kwargs.setdefault("site", default_site)
        return Article.objects.create(**kwargs)

    return _make


@pytest.fixture
def category_factory(db, default_site):
    from apps.categories.models import Category

    counter = {"n": 0}

    def _make(**kwargs):
        counter["n"] += 1
        kwargs.setdefault("name", f"Category {counter['n']}")
        kwargs.setdefault("site", default_site)
        return Category.objects.create(**kwargs)

    return _make
