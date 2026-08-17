"""Tests for Article save-time derivation and the publish/visibility split."""

import pytest

pytestmark = pytest.mark.django_db


def doc(*blocks):
    return {"blocks": list(blocks)}


class TestSlugGeneration:
    def test_slug_generated_from_title(self, article_factory):
        assert article_factory(title="Hello World").slug == "hello-world"

    def test_slug_collisions_get_a_suffix(self, article_factory):
        first = article_factory(title="Same Title")
        second = article_factory(title="Same Title")
        assert first.slug != second.slug

    def test_unicode_slug_is_preserved(self, article_factory):
        # allow_unicode=True: Bengali titles must not be transliterated away.
        article = article_factory(title="যান্ত্রিক অনুবাদ")
        assert article.slug == "যান্ত্রিক-অনুবাদ"

    def test_untitled_falls_back_to_a_uuid(self, article_factory):
        assert article_factory(title="!!!").slug


class TestContentMetrics:
    def test_reading_time_rounds_up(self, article_factory):
        # 250 words at 200 wpm is 2 minutes, not 1. The old floor division
        # under-reported every article.
        text = " ".join(["word"] * 250)
        article = article_factory(content=doc({"type": "paragraph", "data": {"text": text}}))
        assert article.word_count == 250
        assert article.reading_time == 2

    def test_reading_time_is_at_least_one(self, article_factory):
        article = article_factory(content=doc({"type": "paragraph", "data": {"text": "hi"}}))
        assert article.reading_time == 1

    def test_word_count_includes_annotation_bodies(self, article_factory):
        # The regression: annotations carry much of an interactive article's
        # prose but were excluded from the count entirely.
        article = article_factory(
            content=doc(
                {
                    "type": "interactive_text",
                    "data": {
                        "text": "one two three",
                        "annotations": [
                            {"id": "a", "modal_content": " ".join(["x"] * 100)}
                        ],
                    },
                }
            )
        )
        assert article.word_count == 103

    def test_headers_and_lists_are_counted(self, article_factory):
        article = article_factory(
            content=doc(
                {"type": "header", "data": {"text": "A Heading Here", "level": 2}},
                {"type": "list", "data": {"items": ["alpha beta", "gamma"]}},
            )
        )
        assert article.word_count == 6

    def test_plain_text_is_populated(self, article_factory):
        article = article_factory(
            content=doc({"type": "paragraph", "data": {"text": "<b>Bold</b> text"}})
        )
        assert article.plain_text == "Bold text"

    def test_urls_do_not_inflate_the_word_count(self, article_factory):
        article = article_factory(
            content=doc(
                {
                    "type": "image",
                    "data": {
                        "file": {"url": "https://cdn.example.com/a/b/c.png"},
                        "caption": "Two words",
                    },
                }
            )
        )
        assert article.word_count == 2

    def test_empty_content_is_safe(self, article_factory):
        article = article_factory(content={})
        assert article.word_count == 0
        assert article.plain_text == ""
        assert article.reading_time == 1


class TestContentHash:
    def test_hash_is_set(self, article_factory):
        article = article_factory(content=doc({"type": "paragraph", "data": {"text": "a"}}))
        assert len(article.content_hash) == 64

    def test_hash_is_stable_for_equal_content(self, article_factory):
        content = doc({"type": "paragraph", "data": {"text": "same"}})
        assert article_factory(content=content).content_hash == (
            article_factory(content=content).content_hash
        )

    def test_hash_changes_with_content(self, article_factory):
        a = article_factory(content=doc({"type": "paragraph", "data": {"text": "one"}}))
        b = article_factory(content=doc({"type": "paragraph", "data": {"text": "two"}}))
        assert a.content_hash != b.content_hash

    def test_hash_ignores_key_order(self, article_factory):
        a = article_factory(content={"blocks": [], "version": "2.0", "time": 1})
        b = article_factory(content={"time": 1, "version": "2.0", "blocks": []})
        assert a.content_hash == b.content_hash


class TestPublishVisibility:
    def test_publishing_stamps_published_at_and_sets_live(self, article_factory):
        article = article_factory(status="published")
        assert article.published_at is not None
        assert article.is_live is True

    def test_draft_is_not_live(self, article_factory):
        article = article_factory(status="draft")
        assert article.is_live is False
        assert article.published_at is None

    def test_unpublishing_clears_is_live_but_keeps_published_at(self, article_factory):
        article = article_factory(status="published")
        original = article.published_at

        article.status = "draft"
        article.save()
        article.refresh_from_db()

        # published_at is datePublished in JSON-LD -- rewriting it on unpublish
        # would falsify the article's publication history.
        assert article.published_at == original
        assert article.is_live is False

    def test_republishing_keeps_the_original_published_at(self, article_factory):
        article = article_factory(status="published")
        original = article.published_at

        article.status = "draft"
        article.save()
        article.status = "published"
        article.save()
        article.refresh_from_db()

        assert article.published_at == original
        assert article.is_live is True

    def test_archiving_clears_is_live(self, article_factory):
        article = article_factory(status="published")
        article.status = "archived"
        article.save()
        article.refresh_from_db()
        assert article.is_live is False

    def test_is_live_and_status_never_disagree(self, article_factory):
        for status_value, expected in [
            ("draft", False),
            ("published", True),
            ("archived", False),
        ]:
            article = article_factory(status=status_value)
            assert article.is_live is expected
