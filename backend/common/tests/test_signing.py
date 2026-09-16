"""HMAC request signing -- the scheme shared by revalidation and webhooks."""

import time

import pytest

from common.signing import sign, signature_payload, verify

SECRET = "shared-secret-for-tests"


class TestSign:
    def test_round_trips(self):
        body = '{"tags":["articles"]}'
        signature, timestamp = sign(SECRET, body)
        assert verify(SECRET, signature, timestamp, body)

    def test_signature_is_prefixed_for_versioning(self):
        signature, _ = sign(SECRET, "{}")
        assert signature.startswith("v1=")

    def test_empty_secret_is_rejected_loudly(self):
        """Silently signing with "" would produce a valid-looking signature
        that anyone could forge."""
        with pytest.raises(ValueError):
            sign("", "{}")

    def test_payload_binds_timestamp_to_body(self):
        assert signature_payload(123, "abc") == b"123.abc"


class TestVerify:
    def test_rejects_a_tampered_body(self):
        signature, timestamp = sign(SECRET, '{"tags":["articles"]}')
        assert not verify(SECRET, signature, timestamp, '{"tags":["evil"]}')

    def test_rejects_a_wrong_secret(self):
        signature, timestamp = sign(SECRET, "{}")
        assert not verify("other-secret", signature, timestamp, "{}")

    def test_rejects_a_replayed_request(self):
        """The timestamp is inside the signed payload precisely so that a
        captured request expires. Without that binding it stays valid forever.
        """
        old = int(time.time()) - 600
        signature, timestamp = sign(SECRET, "{}", timestamp=old)
        # The signature itself is genuine...
        assert signature == sign(SECRET, "{}", timestamp=old)[0]
        # ...and still refused, because it is outside the replay window.
        assert not verify(SECRET, signature, timestamp, "{}")

    def test_accepts_within_the_tolerance(self):
        recent = int(time.time()) - 60
        signature, timestamp = sign(SECRET, "{}", timestamp=recent)
        assert verify(SECRET, signature, timestamp, "{}")

    def test_rejects_a_future_timestamp_beyond_tolerance(self):
        ahead = int(time.time()) + 600
        signature, timestamp = sign(SECRET, "{}", timestamp=ahead)
        assert not verify(SECRET, signature, timestamp, "{}")

    @pytest.mark.parametrize(
        "signature,timestamp",
        [("", "123"), ("v1=abc", ""), ("", "")],
    )
    def test_missing_pieces_are_rejected(self, signature, timestamp):
        assert not verify(SECRET, signature, timestamp, "{}")

    def test_non_numeric_timestamp_does_not_raise(self):
        """A malformed header must be a rejection, not a 500."""
        assert not verify(SECRET, "v1=abc", "not-a-number", "{}")

    def test_no_secret_configured_rejects_everything(self):
        signature, timestamp = sign(SECRET, "{}")
        assert not verify("", signature, timestamp, "{}")
