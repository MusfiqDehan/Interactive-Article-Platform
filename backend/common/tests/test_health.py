"""Tests for the liveness/readiness split.

The distinction is operational: the site is designed to survive a Redis outage,
so /healthz must stay green (no restart) while /readyz goes red (pull from the
load-balancer pool).
"""

import pytest

pytestmark = pytest.mark.django_db


class TestHealthz:
    def test_returns_200_when_the_database_is_up(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_does_not_check_the_cache(self, client, monkeypatch):
        # A dead Redis must not make the container look unhealthy, or the
        # orchestrator restarts a process that is serving traffic fine.
        #
        # django-redis runs with IGNORE_EXCEPTIONS, so the real failure mode is
        # "every read returns None", not "every read raises". Simulating a raise
        # would be testing a scenario production cannot produce.
        monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)
        monkeypatch.setattr("django.core.cache.cache.set", lambda *a, **k: None)

        response = client.get("/healthz")
        assert response.status_code == 200

    def test_is_not_cached(self, client):
        assert "no-cache" in client.get("/healthz").headers.get("Cache-Control", "")


class TestReadyz:
    def test_returns_200_when_everything_is_up(self, client):
        response = client.get("/readyz")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["cache"] == "ok"

    def test_reports_degraded_when_the_cache_is_down(self, client, monkeypatch):
        # django-redis IGNORE_EXCEPTIONS makes a failed get return None rather
        # than raise, so the check asserts on the round-tripped value.
        monkeypatch.setattr("django.core.cache.cache.get", lambda *a, **k: None)

        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
