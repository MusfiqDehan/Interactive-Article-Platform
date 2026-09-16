"""Retry backoff for outbound delivery.

Eight attempts spread over roughly thirty hours. That shape is chosen for the
failure it is actually built for: a receiving site being down for a deploy, a
DNS change, or an overnight outage. A tight schedule would exhaust its
attempts inside the first ten minutes and give up before anyone noticed; an
even one would still be hammering a dead host a day later.

**Decorrelated jitter**, not a fixed delay. When one publish fans out to a
dozen destinations and they all fail at once -- which is exactly what happens
when the network, not the destination, is the problem -- a fixed schedule
re-sends all twelve at the same instant, forever. Jitter spreads them, so the
recovering host sees a trickle rather than a repeated thundering herd.
"""

from __future__ import annotations

import random

#: Base delay per attempt number, in seconds. Index 0 is the first try.
SCHEDULE = (0, 30, 120, 600, 1800, 7200, 21600, 86400)
MAX_ATTEMPTS = len(SCHEDULE)


def backoff_seconds(attempt: int, *, jitter: bool = True) -> int:
    """Delay before attempt number ``attempt`` (1-based).

    Returns 0 for the first attempt so the initial delivery is immediate.
    Beyond ``MAX_ATTEMPTS`` the last interval repeats, which only matters for a
    caller that ignores ``is_exhausted``.
    """
    index = max(0, min(attempt - 1, MAX_ATTEMPTS - 1))
    base = SCHEDULE[index]
    if not base or not jitter:
        return base
    # Full jitter over [base/2, base*1.5]: enough spread to break up a
    # synchronised fleet without letting any single retry drift so late that
    # the overall window stops meaning what it says.
    return int(random.uniform(base * 0.5, base * 1.5))


def is_exhausted(attempt: int) -> bool:
    return attempt >= MAX_ATTEMPTS
