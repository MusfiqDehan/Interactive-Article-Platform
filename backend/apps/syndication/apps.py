from django.apps import AppConfig


class SyndicationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.syndication"
    label = "syndication"
    verbose_name = "Syndication"

    def ready(self):
        from . import signals  # noqa: F401
