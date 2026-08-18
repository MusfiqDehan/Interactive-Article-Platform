from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.social"
    label = "social"

    def ready(self):
        # Registers every provider. Done here rather than lazily so an
        # unknown-provider error surfaces at boot, not on the first publish.
        from . import providers  # noqa: F401
