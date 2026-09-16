"""Advisory distributed locks.

**These locks are an optimisation, not a correctness guarantee.** Exactly-once
scheduled publishing is enforced by the database: the sweep selects due rows
``FOR UPDATE SKIP LOCKED`` and the transition itself moves them out of the due
set, so a second worker either skips the locked row or finds nothing left to do
after the first commits. This lock exists so that N workers waking on the same
beat tick do not all run the same sweep and perform N-1 units of wasted work.

That distinction drives the one non-obvious behaviour here. The cache is
configured with ``IGNORE_EXCEPTIONS``, so when Redis is unreachable
``cache.add`` returns ``None`` instead of raising, whereas a genuinely
contended lock returns ``False``. Those two cases must not be treated alike:

* ``False`` -- another worker holds it. Skip; it is doing the work.
* ``None``  -- Redis is down. **Proceed anyway.** Refusing would mean a Redis
  outage silently halts all scheduled publishing, which is far worse than
  duplicated effort that the database will reject regardless.

Failing open is only safe *because* the database is the real guard. Do not
reuse this lock where it is the only thing standing between you and a double
side effect.
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import uuid

from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300


def _owner_token() -> str:
    """Identify the holder, so a stuck lock can be traced to a process."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@contextlib.contextmanager
def advisory_lock(name: str, timeout: int = DEFAULT_TIMEOUT):
    """Yield True if this process should do the work, False if it should skip.

    ``timeout`` bounds how long the lock survives if the holder dies mid-task;
    it should comfortably exceed the expected work duration, because expiring
    early lets a second worker start while the first is still running.
    """
    key = f"lock:{name}"
    token = _owner_token()

    # add() is atomic SETNX: only one caller can win.
    acquired = cache.add(key, token, timeout)

    if acquired is None:
        logger.warning(
            "Advisory lock %r unavailable (cache backend down); proceeding "
            "without it and relying on database-level guards.",
            name,
        )
        yield True
        return

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        # Only release a lock we still own. If it expired and another worker
        # took it, deleting here would free *their* lock and let a third in.
        try:
            if cache.get(key) == token:
                cache.delete(key)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to release advisory lock %r", name)
