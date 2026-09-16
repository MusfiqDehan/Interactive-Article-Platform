"""Optimistic concurrency for editing endpoints.

Editor.js autosaves. Two tabs open on the same article therefore do not produce
a merge conflict an author can see -- they produce a silent last-write-wins
race in which one tab's work disappears with no error anywhere. This mixin
turns that into a visible 409.

The client sends the content hash it started from::

    PATCH /api/v1/studio/articles/my-post/
    If-Match: "9f2c...e1"

and gets 409 if the stored article has moved on since. Every response carries
the current hash as an ``ETag``, so a client can adopt the protocol simply by
echoing back whatever it last received.

**On the status code.** Strict HTTP says a failed ``If-Match`` is 412
Precondition Failed. This returns 409 Conflict deliberately: 412 is also
emitted by caches and proxies for reasons unrelated to editing, whereas 409
here always means exactly one thing -- somebody else changed this article --
and the body carries what the UI needs to offer "keep mine / take theirs / show
diff". The precondition header keeps the standard spelling; only the failure
code differs.

The header is **optional**. Requiring it would break the legacy client, which
predates this protocol; a client that omits it gets the old last-write-wins
behaviour and no false sense of safety.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response


def _normalise_etag(value: str) -> str:
    """Strip quoting and weak-validator syntax so comparison is on content."""
    value = (value or "").strip()
    if value.startswith("W/"):
        value = value[2:].strip()
    return value.strip('"')


class OptimisticConcurrencyMixin:
    """``If-Match`` checking and ``ETag`` emission for an APIView.

    Two explicit calls rather than method overrides: a view calls
    ``check_precondition()`` before writing and ``tag_response()`` on the way
    out. The previous version wrapped `update`/`retrieve`/`create`, which only
    worked because a ViewSet happened to name its handlers that way -- and
    silently did nothing on any view that did not.
    """

    #: Model field holding the version token.
    concurrency_field = "content_hash"

    def _current_token(self, instance) -> str:
        return str(getattr(instance, self.concurrency_field, "") or "")

    def check_precondition(self, instance):
        """Return a 409 Response if ``If-Match`` does not match, else None."""
        supplied = self.request.headers.get("If-Match")
        if not supplied:
            return None

        # `If-Match: *` means "any existing representation", which is satisfied
        # by the object simply existing -- we only reach here if it does.
        if supplied.strip() == "*":
            return None

        current = self._current_token(instance)
        # A comma-separated list is legal in If-Match; any member matching wins.
        candidates = {_normalise_etag(part) for part in supplied.split(",")}
        if current in candidates:
            return None

        return Response(
            {
                "detail": (
                    "This article was modified by someone else since you loaded "
                    "it. Reload, or choose which version to keep."
                ),
                "code": "stale_content",
                "current_version": current,
                "your_version": sorted(candidates)[0] if candidates else "",
                "modified_at": getattr(instance, "updated_at", None),
            },
            status=status.HTTP_409_CONFLICT,
        )

    def tag_response(self, response, instance=None):
        """Attach the current version as an ``ETag``.

        Prefers the instance over the response body: a serializer that omits
        ``content_hash`` would otherwise silently produce untagged responses,
        and a client with no ETag to echo back gets no concurrency protection
        at all -- failing open, invisibly.
        """
        token = ""
        if instance is not None:
            token = self._current_token(instance)
        if not token:
            data = getattr(response, "data", None)
            if isinstance(data, dict):
                token = str(data.get(self.concurrency_field) or "")
        if token:
            response["ETag"] = f'"{token}"'
        return response
