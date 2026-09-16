"""HMAC request signing.

One implementation, two consumers: the Next.js revalidation endpoint
(``POST /api/revalidate``) and, from Phase 5, outbound syndication webhooks.
Keeping them on the same scheme means there is a single thing to get right and
a single thing to audit.

Scheme (Stripe-style)::

    X-CMS-Timestamp: 1699999999
    X-CMS-Signature: v1=<hex hmac_sha256(secret, "{timestamp}.{body}")>

The timestamp is *inside* the signed payload, which is what makes it useful:
signing only the body would let an attacker replay a captured request forever,
because the signature would stay valid. Binding the timestamp means a replay is
only accepted inside ``tolerance`` seconds.

The receiving side lives in
``frontend/src/app/api/revalidate/route.ts`` and must stay byte-compatible with
``signature_payload`` below.
"""

from __future__ import annotations

import hashlib
import hmac
import time

TOLERANCE_SECONDS = 300
SIGNATURE_PREFIX = "v1="


def signature_payload(timestamp: int | str, body: str) -> bytes:
    """The exact bytes that get signed."""
    return f"{timestamp}.{body}".encode("utf-8")


def sign(secret: str, body: str, timestamp: int | None = None) -> tuple[str, str]:
    """Return ``(signature, timestamp)`` for a request body.

    The timestamp is returned rather than only stamped internally because the
    caller must send the *same* value in the header -- recomputing it would
    produce a signature over a payload the receiver cannot reconstruct.
    """
    if not secret:
        raise ValueError("A signing secret is required.")
    ts = str(timestamp if timestamp is not None else int(time.time()))
    digest = hmac.new(
        secret.encode("utf-8"), signature_payload(ts, body), hashlib.sha256
    ).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}", ts


def verify(
    secret: str,
    signature: str,
    timestamp: str,
    body: str,
    tolerance: int = TOLERANCE_SECONDS,
) -> bool:
    """Constant-time signature check with a replay window."""
    if not secret or not signature or not timestamp:
        return False

    try:
        skew = abs(time.time() - float(timestamp))
    except (TypeError, ValueError):
        return False
    if skew > tolerance:
        return False

    expected, _ = sign(secret, body, timestamp)
    # compare_digest is constant-time only across equal-length inputs, but it
    # does not leak length here: both sides are fixed-width sha256 hex.
    return hmac.compare_digest(signature.strip(), expected)
