"""Tests for the SEO check functions and scoring."""

import pytest

from apps.seo.checks import STATUS_FAIL, STATUS_OK, STATUS_WARN, analyze_article
from apps.seo.resolver import resolve_seo

pytestmark = pytest.mark.django_db


def result_for(checks, check_id):
    return next(c for c in checks if c["id"] == check_id)


def para(text):
    return {"id": "p1", "type": "paragraph", "data": {"text": text}}


class TestScoring:
    def test_score_is_a_percentage(self, article_factory, default_site):
        score, checks, _ = analyze_article(article_factory(), site=default_site)
        assert 0 <= score <= 100
        assert len(checks) >= 10

    def test_a_good_article_outscores_a_bad_one(self, article_factory, default_site):
        bad = article_factory(title="x", excerpt="", content={"blocks": []})

        good = article_factory(
            title="A Complete Guide to Bengali Machine Translation",
            excerpt=(
                "Bengali machine translation has advanced rapidly. This guide covers "
                "the models, the datasets and the evaluation methods that matter most "
                "for practitioners working today."
            ),
            featured_image="https://cdn.example.com/cover.png",
            content={
                "blocks": [
                    {"id": "h1", "type": "header", "data": {"text": "Bengali machine translation", "level": 2}},
                    para("Bengali machine translation " + "word " * 700),
                    para('<a href="/articles/other">Related reading</a>'),
                    para('<a href="https://example.org/paper">The original paper</a>'),
                ]
            },
        )
        bad_score, _, _ = analyze_article(bad, site=default_site)
        good_score, _, _ = analyze_article(good, site=default_site)
        assert good_score > bad_score


class TestIndividualChecks:
    def test_title_length(self, article_factory, default_site):
        article = article_factory(title="Too short")
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "title_length")["status"] == STATUS_WARN

    def test_word_count_fails_when_thin(self, article_factory, default_site):
        article = article_factory(content={"blocks": [para("only a few words here")]})
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "word_count")["status"] == STATUS_FAIL

    def test_missing_alt_text_is_reported_with_anchors(
        self, article_factory, default_site
    ):
        article = article_factory(
            content={
                "blocks": [
                    {
                        "id": "img1",
                        "type": "image",
                        "data": {"file": {"url": "https://cdn/a.png"}, "caption": ""},
                    }
                ]
            }
        )
        _, checks, _ = analyze_article(article, site=default_site)
        alt = result_for(checks, "image_alt")
        assert alt["status"] == STATUS_FAIL
        # The editor uses anchors to scroll to the offending block.
        assert "img1" in alt["anchors"]

    def test_images_inside_annotations_are_checked(self, article_factory, default_site):
        # A large share of this platform's images live in annotation modals;
        # ignoring them would report a clean bill of health on a half-unlabelled
        # article.
        article = article_factory(
            content={
                "blocks": [
                    {
                        "id": "b1",
                        "type": "interactive_text",
                        "data": {
                            "text": "body",
                            "annotations": [
                                {
                                    "id": "a1",
                                    "type": "image",
                                    "image_url": "https://cdn/inside.png",
                                    "image_caption": "",
                                    "modal_title": "",
                                }
                            ],
                        },
                    }
                ]
            }
        )
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "image_alt")["status"] == STATUS_FAIL

    def test_annotated_image_with_caption_passes(self, article_factory, default_site):
        article = article_factory(
            content={
                "blocks": [
                    {
                        "id": "b1",
                        "type": "interactive_text",
                        "data": {
                            "text": "body",
                            "annotations": [
                                {
                                    "id": "a1",
                                    "type": "image",
                                    "image_url": "https://cdn/inside.png",
                                    "image_caption": "A described diagram",
                                }
                            ],
                        },
                    }
                ]
            }
        )
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "image_alt")["status"] == STATUS_OK

    def test_multiple_h1s_are_flagged(self, article_factory, default_site):
        # The page title is already the H1; another in the body competes.
        article = article_factory(
            content={
                "blocks": [
                    {"id": "h1", "type": "header", "data": {"text": "One", "level": 1}},
                    {"id": "h2", "type": "header", "data": {"text": "Two", "level": 1}},
                ]
            }
        )
        _, checks, _ = analyze_article(article, site=default_site)
        hierarchy = result_for(checks, "heading_hierarchy")
        assert hierarchy["status"] == STATUS_WARN
        assert "H1" in hierarchy["detail"]

    def test_skipped_heading_level_is_flagged(self, article_factory, default_site):
        article = article_factory(
            content={
                "blocks": [
                    {"id": "h1", "type": "header", "data": {"text": "A", "level": 2}},
                    {"id": "h2", "type": "header", "data": {"text": "B", "level": 4}},
                ]
            }
        )
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "heading_hierarchy")["status"] == STATUS_WARN

    def test_noindex_is_reported_as_a_failure(self, article_factory, default_site):
        from django.contrib.contenttypes.models import ContentType

        from apps.articles.models import Article
        from apps.seo.models import SEOMetadata

        article = article_factory()
        SEOMetadata.objects.create(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=article.pk,
            site=default_site,
            robots_index=False,
        )
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "indexable")["status"] == STATUS_FAIL

    def test_keyword_checks_use_the_focus_keyword(self, article_factory, default_site):
        from django.contrib.contenttypes.models import ContentType

        from apps.articles.models import Article
        from apps.seo.models import SEOMetadata

        article = article_factory(
            title="Bengali Translation Explained",
            content={"blocks": [para("bengali translation " + "filler " * 200)]},
        )
        SEOMetadata.objects.create(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=article.pk,
            site=default_site,
            focus_keyword="bengali translation",
        )
        _, checks, _ = analyze_article(article, site=default_site)
        assert result_for(checks, "title_keyword")["status"] == STATUS_OK
        assert result_for(checks, "keyword_opening")["status"] == STATUS_OK


class TestPersistence:
    def test_analysis_is_cached(self, article_factory, default_site):
        from apps.seo.models import SEOAnalysis

        article = article_factory()
        analyze_article(article, site=default_site)
        assert SEOAnalysis.objects.filter(article=article).exists()

    def test_draft_analysis_is_not_cached(self, article_factory, default_site):
        from apps.seo.models import SEOAnalysis

        article = article_factory()
        analyze_article(article, site=default_site, persist=False)
        assert not SEOAnalysis.objects.filter(article=article).exists()


class TestAnalyzeEndpoint:
    def test_scores_a_saved_article(self, auth_client, admin, article_factory):
        article = article_factory()
        response = auth_client(admin).post(
            f"/api/v1/studio/articles/{article.slug}/analyze-seo/", {}, format="json"
        )
        assert response.status_code == 200
        body = response.json()
        assert "score" in body and "checks" in body and body["cached"] is True

    def test_scores_unsaved_draft_content(self, auth_client, admin, article_factory):
        # The live editor sidebar depends on this: the score must reflect what
        # the author is looking at, not the last saved revision.
        article = article_factory(title="Old", content={"blocks": []})
        response = auth_client(admin).post(
            f"/api/v1/studio/articles/{article.slug}/analyze-seo/",
            {
                "title": "A Much Better Title For This Particular Article",
                "content": {"blocks": [para("word " * 800)]},
            },
            format="json",
        )
        assert response.status_code == 200
        body = response.json()
        assert body["cached"] is False
        assert result_for(body["checks"], "word_count")["status"] == STATUS_OK
        # The database row must be untouched.
        article.refresh_from_db()
        assert article.title == "Old"
