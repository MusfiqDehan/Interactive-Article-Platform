from django.db import migrations, models


class Migration(migrations.Migration):
    """Reconcile migration drift on the category slugs.

    See ``articles.0002_alter_article_slug`` for the rationale. Metadata-only on
    PostgreSQL -- ``allow_unicode`` changes the validator, not the column.
    """

    dependencies = [
        ("categories", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(
                allow_unicode=True, blank=True, max_length=200, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="subcategory",
            name="slug",
            field=models.SlugField(allow_unicode=True, blank=True, max_length=200),
        ),
    ]
