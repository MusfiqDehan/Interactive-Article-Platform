"""Celery application.

Queues are separated by failure mode, not by app: a rate-limited social API
retrying for hours must never block scheduled publishing.

  default   -- scheduled publish/unpublish, rollups, housekeeping
  social    -- outbound social posting (slow, rate-limited, long backoff)
  delivery  -- syndication + webhook delivery (retries for up to ~30h)
  index     -- search indexing (cheap, high volume, safe to drop and rebuild)
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("interactive_articles")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def heartbeat(self):
    """No-op task used to prove worker and beat are wired up end to end.

    Keeps its result (rather than ``ignore_result``) so that
    ``heartbeat.delay().get()`` is a usable one-liner smoke test.
    """
    return "ok"
