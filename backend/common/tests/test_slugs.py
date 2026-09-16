"""Tests for Unicode-safe slug generation.

Django's ``slugify(allow_unicode=True)`` drops combining marks, which for Indic
scripts are the vowels. Three distinct Bengali words collapsed onto one slug,
producing unreadable URLs and real uniqueness collisions.
"""

import pytest

from common.slugs import MAX_SLUG_LENGTH, unicode_slugify


class TestAscii:
    def test_basic(self):
        assert unicode_slugify("Hello World") == "hello-world"

    def test_punctuation_removed(self):
        assert unicode_slugify("Hello, World! (2024)") == "hello-world-2024"

    def test_collapses_whitespace(self):
        assert unicode_slugify("a   b\n\tc") == "a-b-c"

    def test_strips_edges(self):
        assert unicode_slugify("  --Hello--  ") == "hello"

    def test_empty_input(self):
        assert unicode_slugify("") == ""
        assert unicode_slugify("!!!") == ""


class TestBengali:
    def test_combining_marks_are_preserved(self):
        # Django's slugify yields "যনতরক-অনবদ" here.
        assert unicode_slugify("যান্ত্রিক অনুবাদ") == "যান্ত্রিক-অনুবাদ"

    def test_distinct_words_get_distinct_slugs(self):
        # The collision that broke uniqueness: all three previously became "অনবদ".
        slugs = {unicode_slugify(w) for w in ("অনুবাদ", "অনবাদ", "অনুবদ")}
        assert len(slugs) == 3

    def test_mixed_script(self):
        assert unicode_slugify("Django এবং বাংলা") == "django-এবং-বাংলা"

    def test_normalisation_is_stable(self):
        import unicodedata

        text = "অনুবাদ"
        assert unicode_slugify(unicodedata.normalize("NFC", text)) == unicode_slugify(
            unicodedata.normalize("NFD", text)
        )


class TestLength:
    def test_capped(self):
        assert len(unicode_slugify("word " * 100)) <= MAX_SLUG_LENGTH

    def test_does_not_end_on_a_separator(self):
        slug = unicode_slugify("word " * 100)
        assert not slug.endswith("-")

    def test_short_input_untouched(self):
        assert unicode_slugify("short title") == "short-title"


@pytest.mark.django_db
class TestModelIntegration:
    def test_article_slug_keeps_marks(self, article_factory):
        assert article_factory(title="যান্ত্রিক অনুবাদ").slug == "যান্ত্রিক-অনুবাদ"

    def test_articles_with_colliding_bengali_titles_get_distinct_slugs(
        self, article_factory
    ):
        a = article_factory(title="অনুবাদ")
        b = article_factory(title="অনবাদ")
        assert a.slug != b.slug
        assert a.slug == "অনুবাদ"

    def test_identical_titles_still_get_a_suffix(self, article_factory):
        a = article_factory(title="Same Title")
        b = article_factory(title="Same Title")
        assert b.slug == f"{a.slug}-1"

    def test_category_slug_collision_does_not_raise(self, category_factory):
        # Previously Category.slug was globally unique with no collision loop.
        first = category_factory(name="অনুবাদ")
        second = category_factory(name="অনবাদ")
        assert first.slug != second.slug

    def test_child_category_slugs_are_unique_per_site(self, category_factory, default_site):
        from apps.categories.models import Category

        parent_a = category_factory(name="Parent A")
        parent_b = category_factory(name="Parent B")
        first = Category.objects.create(site=default_site, name="Shared", parent=parent_a)
        second = Category.objects.create(
            site=default_site, name="Shared B", parent=parent_b
        )
        # Uniqueness is now per *site*, not per parent -- one flat namespace
        # across the tree, because `/categories/<slug>/` has to resolve without
        # knowing the parent.
        assert first.slug != second.slug
        assert first.url_path != second.url_path
