"""The editorial state machine.

Hand-rolled rather than ``django-fsm``, which is unmaintained for Django 5.x.
What is actually needed is small: a legality table, a role guard, side effects,
and an audit entry -- and writing it out keeps the rules greppable in one file
instead of scattered across decorators.

Two invariants the rest of the system leans on:

1. **A state change and its audit entry commit together.** ``perform`` runs both
   inside one ``atomic`` block, so there is no window in which an article is
   published with no record of who published it.
2. **Visibility is derived, never assigned.** Nothing here sets ``is_live``;
   ``Article.save()`` computes it from ``status`` via ``LIVE_STATES``. A
   transition that forgot to update it would otherwise leave an article
   publicly visible while showing as archived in the studio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from django.db import transaction
from django.utils import timezone

from .states import (
    APPROVED,
    ARCHIVED,
    DRAFT,
    IN_REVIEW,
    PUBLISHED,
    SCHEDULED,
)

# Ordered weakest to strongest; mirrors common.permissions.HasSiteRole.
ROLE_ORDER = {"viewer": 0, "author": 1, "editor": 2, "owner": 3}


class TransitionError(Exception):
    """The requested transition is not legal from the article's current state."""


class TransitionPermissionDenied(Exception):
    """The actor is not allowed to perform this (otherwise legal) transition."""


def effective_site_role(user, site) -> str | None:
    """The actor's role on ``site``, or None if they have no access.

    A global admin is treated as ``owner`` everywhere. This is the single place
    that fusion happens -- callers should never test ``user.role`` directly, or
    the two role systems drift apart.
    """
    from common.permissions import is_admin

    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if is_admin(user):
        return "owner"
    if site is None:
        return None

    from apps.tenancy.models import SiteMembership

    membership = SiteMembership.objects.filter(site=site, user=user).first()
    return membership.role if membership else None


def _requires_schedule(article, **kwargs):
    when = kwargs.get("scheduled_publish_at") or article.scheduled_publish_at
    if when is None:
        raise TransitionError("A scheduled publish time is required.")
    if when <= timezone.now():
        raise TransitionError("The scheduled time must be in the future.")


@dataclass(frozen=True)
class Transition:
    name: str
    sources: frozenset[str]
    target: str
    #: Minimum site role. Authors additionally must own the article (below).
    min_role: str = "editor"
    #: If True, an actor whose role is exactly ``author`` may run this only on
    #: articles they wrote. Editors and above are unrestricted.
    author_owns_only: bool = True
    guard: Callable | None = None
    label: str = ""
    #: Applied to the article before saving. Receives (article, **kwargs).
    apply: Callable | None = None
    #: Field names touched by ``apply``, so the save can stay narrow.
    touches: tuple[str, ...] = field(default_factory=tuple)


def _apply_publish(article, **kwargs):
    now = timezone.now()
    # published_at is the *first* publication and is never rewritten -- it is
    # datePublished in JSON-LD, and resetting it on a republish would falsify
    # the article's age. last_published_at tracks the most recent one.
    if article.published_at is None:
        article.published_at = now
    article.last_published_at = now
    article.unpublished_at = None
    # A scheduled publish that has fired must not remain due, or the next sweep
    # would pick it up again.
    article.scheduled_publish_at = None


def _apply_unpublish(article, **kwargs):
    article.unpublished_at = timezone.now()


def _apply_schedule(article, **kwargs):
    when = kwargs.get("scheduled_publish_at")
    if when is not None:
        article.scheduled_publish_at = when


def _apply_unschedule(article, **kwargs):
    article.scheduled_publish_at = None


TRANSITIONS: dict[str, Transition] = {
    t.name: t
    for t in [
        Transition(
            name="submit",
            label="Submit for review",
            sources=frozenset({DRAFT}),
            target=IN_REVIEW,
            min_role="author",
        ),
        Transition(
            name="withdraw",
            label="Withdraw from review",
            sources=frozenset({IN_REVIEW}),
            target=DRAFT,
            min_role="author",
        ),
        Transition(
            name="approve",
            label="Approve",
            sources=frozenset({IN_REVIEW}),
            target=APPROVED,
            min_role="editor",
        ),
        Transition(
            name="request_changes",
            label="Request changes",
            sources=frozenset({IN_REVIEW}),
            target=DRAFT,
            min_role="editor",
        ),
        Transition(
            name="schedule",
            label="Schedule",
            sources=frozenset({DRAFT, APPROVED, SCHEDULED}),
            target=SCHEDULED,
            min_role="editor",
            guard=_requires_schedule,
            apply=_apply_schedule,
            touches=("scheduled_publish_at",),
        ),
        Transition(
            name="unschedule",
            label="Cancel schedule",
            sources=frozenset({SCHEDULED}),
            target=APPROVED,
            min_role="editor",
            apply=_apply_unschedule,
            touches=("scheduled_publish_at",),
        ),
        Transition(
            name="publish",
            label="Publish",
            sources=frozenset({DRAFT, IN_REVIEW, APPROVED, SCHEDULED, ARCHIVED}),
            target=PUBLISHED,
            min_role="editor",
            apply=_apply_publish,
            touches=(
                "published_at",
                "last_published_at",
                "unpublished_at",
                "scheduled_publish_at",
            ),
        ),
        Transition(
            name="unpublish",
            label="Unpublish",
            sources=frozenset({PUBLISHED}),
            target=DRAFT,
            min_role="editor",
            apply=_apply_unpublish,
            touches=("unpublished_at",),
        ),
        Transition(
            name="archive",
            label="Archive",
            sources=frozenset({DRAFT, IN_REVIEW, APPROVED, SCHEDULED, PUBLISHED}),
            target=ARCHIVED,
            min_role="editor",
            apply=_apply_unpublish,
            touches=("unpublished_at",),
        ),
        Transition(
            name="restore",
            label="Restore to draft",
            sources=frozenset({ARCHIVED}),
            target=DRAFT,
            min_role="editor",
        ),
    ]
}


def can_perform(article, name: str, user, site=None) -> bool:
    """True if ``user`` may run ``name`` on ``article`` right now.

    Argument guards are **not** run. They answer "would this succeed with the
    arguments I have", which is a different question from "may this person do
    this at all" -- and conflating them hides the Schedule action precisely
    when no date has been picked yet, which is when it needs offering.
    """
    try:
        check(article, name, user, site=site, run_guard=False)
    except (TransitionError, TransitionPermissionDenied):
        return False
    return True


def check(
    article,
    name: str,
    user,
    site=None,
    system: bool = False,
    run_guard: bool = True,
    **kwargs,
) -> Transition:
    """Validate a transition, raising on the first problem. Returns the rule.

    ``system=True`` skips only the *role* checks, for the scheduler publishing
    on nobody's behalf. State legality and guards still apply -- a scheduled
    publish whose article was archived in the meantime must still fail, and the
    audit entry is written either way with a ``system`` actor label.
    """
    rule = TRANSITIONS.get(name)
    if rule is None:
        raise TransitionError(f"Unknown transition {name!r}.")

    if article.status not in rule.sources:
        raise TransitionError(
            f"Cannot {name} an article that is {article.status!r}; "
            f"expected one of {sorted(rule.sources)}."
        )

    if system:
        if run_guard and rule.guard is not None:
            rule.guard(article, **kwargs)
        return rule

    site = site if site is not None else article.site
    role = effective_site_role(user, site)
    if role is None:
        raise TransitionPermissionDenied("You do not have access to this site.")

    if ROLE_ORDER.get(role, -1) < ROLE_ORDER.get(rule.min_role, 0):
        raise TransitionPermissionDenied(
            f"{name!r} requires the {rule.min_role} role or above."
        )

    # Authors are confined to their own work; editors and above are not.
    if (
        rule.author_owns_only
        and role == "author"
        and article.author_id != getattr(user, "pk", None)
    ):
        raise TransitionPermissionDenied("Authors may only act on their own articles.")

    if run_guard and rule.guard is not None:
        rule.guard(article, **kwargs)

    return rule


def available(article, user, site=None) -> list[dict]:
    """Every transition the actor could run right now, for the UI.

    The studio's split Publish button reads this to decide its primary action,
    which is why it returns labels rather than bare names.
    """
    return [
        {"name": rule.name, "label": rule.label, "target": rule.target}
        for rule in TRANSITIONS.values()
        if can_perform(article, rule.name, user, site=site)
    ]


@transaction.atomic
def perform(
    article,
    name: str,
    user,
    site=None,
    reason: str = "",
    metadata: dict | None = None,
    system: bool = False,
    **kwargs,
):
    """Run a transition, writing the audit entry in the same transaction.

    Returns the updated article. Callers that need side effects outside the
    database (cache busting, webhooks, revalidation) should hook
    ``transaction.on_commit`` -- firing them here would publish notifications
    for a transaction that may still roll back.
    """
    from .models import AuditLogEntry

    rule = check(article, name, user, site=site, system=system, **kwargs)
    from_state = article.status

    if rule.apply is not None:
        rule.apply(article, **kwargs)
    article.status = rule.target

    # A targeted update_fields list, not a blanket save: a full save would write
    # back every field this request happened to load, silently clobbering a
    # concurrent edit to a column the transition never touched. Article.save()
    # unions in the columns it derives, so they do not need listing here.
    article.save(update_fields=sorted({"status", *rule.touches}))

    AuditLogEntry.objects.create(
        site=article.site,
        actor=user if getattr(user, "is_authenticated", False) else None,
        actor_label=_label_for(user),
        action="transition",
        article=article,
        target_label=article.title[:300],
        from_state=from_state,
        to_state=article.status,
        metadata={"transition": name, "reason": reason, **(metadata or {})},
    )

    return article


def _label_for(user) -> str:
    if user is None or not getattr(user, "is_authenticated", False):
        return "system"
    return getattr(user, "email", "") or getattr(user, "username", "") or str(user.pk)


def record(
    *,
    site,
    action: str,
    user=None,
    article=None,
    metadata: dict | None = None,
    from_state: str = "",
    to_state: str = "",
):
    """Write a non-transition audit entry (create, update, restore, ...)."""
    from .models import AuditLogEntry

    return AuditLogEntry.objects.create(
        site=site,
        actor=user if getattr(user, "is_authenticated", False) else None,
        actor_label=_label_for(user),
        action=action,
        article=article,
        target_label=(getattr(article, "title", "") or "")[:300],
        from_state=from_state,
        to_state=to_state,
        metadata=metadata or {},
    )


def legal_targets(status: str) -> Iterable[str]:
    """Every state reachable from ``status``, ignoring permissions."""
    return {rule.target for rule in TRANSITIONS.values() if status in rule.sources}


def transition_for(article, target: str, user=None, site=None) -> str | None:
    """Name the transition that moves ``article`` to ``target``, or None.

    Bridges a state *assignment* (what the legacy API and any status dropdown
    speak) onto the state machine. Some targets are reachable by more than one
    route -- ``in_review -> draft`` is both ``withdraw`` (the author giving up
    on it) and ``request_changes`` (an editor sending it back) -- so the actor's
    permissions break the tie. That keeps the audit trail meaningful: the entry
    records which of the two actually happened rather than always the first.
    """
    candidates = [
        rule
        for rule in TRANSITIONS.values()
        if rule.target == target and article.status in rule.sources
    ]
    if not candidates:
        return None
    permitted = [
        rule for rule in candidates if can_perform(article, rule.name, user, site=site)
    ]
    return (permitted or candidates)[0].name
