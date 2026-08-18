"""The editorial state machine's vocabulary.

Kept in its own module because both ``apps.articles.models`` (for the field
choices) and ``apps.editorial.transitions`` (for the legality table) need it,
and importing the latter from the former would be circular.
"""

from __future__ import annotations

DRAFT = "draft"
IN_REVIEW = "in_review"
APPROVED = "approved"
SCHEDULED = "scheduled"
PUBLISHED = "published"
ARCHIVED = "archived"

STATUS_CHOICES = (
    (DRAFT, "Draft"),
    (IN_REVIEW, "In review"),
    (APPROVED, "Approved"),
    (SCHEDULED, "Scheduled"),
    (PUBLISHED, "Published"),
    (ARCHIVED, "Archived"),
)

ALL_STATES = frozenset(state for state, _ in STATUS_CHOICES)

#: The only state in which the public can see an article.
#:
#: ``Article.is_live`` is derived from this rather than tested inline, so that
#: "visible" has exactly one definition. Note that ``published`` is the only
#: live state: ``archived`` content stays reachable by URL only if a redirect
#: says so, and ``scheduled`` is explicitly not yet live.
LIVE_STATES = frozenset({PUBLISHED})
