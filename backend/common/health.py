"""Liveness and readiness endpoints.

The split matters operationally:

``/healthz`` (liveness) checks only the database. The site is designed to
survive a Redis outage -- ``IGNORE_EXCEPTIONS`` makes cache reads fall through
to Postgres -- so a Redis failure must NOT make the container unhealthy and
cause the orchestrator to kill a perfectly serviceable process.

``/readyz`` (readiness) additionally checks Redis, so a degraded instance can be
pulled from a load-balancer pool without being restarted.

These replace the existing healthcheck that curls ``/admin/login/`` -- which
returns 200 whenever Django can render a template, even with a dead database.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - exercised via the endpoint
        return False, str(exc)
    return True, "ok"


def _check_cache():
    from django.core.cache import cache

    try:
        # IGNORE_EXCEPTIONS makes failures return None rather than raise, so
        # assert on the round-tripped value instead of relying on an exception.
        cache.set("healthcheck", "1", 10)
        if cache.get("healthcheck") != "1":
            return False, "cache did not return the value written"
    except Exception as exc:  # pragma: no cover
        return False, str(exc)
    return True, "ok"


@never_cache
def healthz(request):
    """Liveness: is this process able to serve requests at all?"""
    ok, detail = _check_database()
    return JsonResponse(
        {"status": "ok" if ok else "error", "checks": {"database": detail}},
        status=200 if ok else 503,
    )


@never_cache
def readyz(request):
    """Readiness: are all dependencies healthy enough to take traffic?"""
    db_ok, db_detail = _check_database()
    cache_ok, cache_detail = _check_cache()
    ok = db_ok and cache_ok
    return JsonResponse(
        {
            "status": "ok" if ok else "degraded",
            "checks": {"database": db_detail, "cache": cache_detail},
        },
        status=200 if ok else 503,
    )
