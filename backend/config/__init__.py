"""Ensure the Celery app is loaded whenever Django starts.

Without this import, ``@shared_task`` decorators bind to no app and tasks
silently fail to register.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
