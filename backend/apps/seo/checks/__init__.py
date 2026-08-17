"""SEO check runner."""

from __future__ import annotations

from common.blocks import blocks_to_plaintext, extract_annotations

from . import content  # noqa: F401  (importing registers the checks)
from .base import (  # noqa: F401
    REGISTRY,
    STATUS_FAIL,
    STATUS_OK,
    STATUS_WARN,
    CheckContext,
    CheckResult,
)


def run_checks(article, seo, site=None) -> tuple[int, list[dict]]:
    """Run every registered check; return ``(score, results)``.

    The score is the weighted percentage earned, so adding a new check
    re-balances the scale automatically instead of shifting every article's
    score by an arbitrary amount.
    """
    ctx = CheckContext(
        article=article,
        seo=seo,
        plain_text=article.plain_text or blocks_to_plaintext(article.content),
        annotations=extract_annotations(article.content),
        site=site,
    )

    results = [check(ctx) for check in REGISTRY]
    total_weight = sum(r.weight for r in results) or 1
    earned = sum(r.earned for r in results)
    score = round(earned / total_weight * 100)

    return score, [
        {
            "id": r.id,
            "label": r.label,
            "status": r.status,
            "weight": r.weight,
            "detail": r.detail,
            "anchors": r.anchors,
        }
        for r in results
    ]


def analyze_article(article, site=None, placement=None, persist=True):
    """Resolve SEO, run the checks, and optionally cache the result.

    ``persist=False`` is what the editor's live sidebar uses: the checks run
    against an unsaved draft so the score reflects what the author is looking
    at, not the last saved revision.
    """
    from apps.seo.models import SEOAnalysis
    from apps.seo.resolver import resolve_seo

    site = site or getattr(article, "site", None)
    seo = resolve_seo(article, site=site, placement=placement)
    score, results = run_checks(article, seo, site=site)

    if persist and article.pk:
        SEOAnalysis.objects.update_or_create(
            article=article,
            defaults={
                "site": site,
                "score": score,
                "checks": results,
                "content_hash": article.content_hash,
            },
        )
    return score, results, seo
