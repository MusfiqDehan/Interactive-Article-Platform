from django.apps import AppConfig


class EditorialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.editorial"
    label = "editorial"
    verbose_name = "Editorial workflow"
