from django.db import migrations, models


class Migration(migrations.Migration):
    """Reconcile migration drift.

    ``allow_unicode=True`` was added to ``Article.slug`` in the model but never
    captured in a migration, so ``makemigrations --check`` reported a permanent
    pending change. On PostgreSQL this is metadata-only: ``allow_unicode`` only
    swaps the field's validator, it does not alter the column DDL.
    """

    dependencies = [
        ("articles", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="slug",
            field=models.SlugField(
                allow_unicode=True, blank=True, max_length=300, unique=True
            ),
        ),
    ]
