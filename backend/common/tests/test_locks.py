"""Advisory locks -- including the deliberate fail-open behaviour."""

import pytest
from django.core.cache import cache

from common.locks import advisory_lock


@pytest.fixture(autouse=True)
def _clean():
    cache.delete("lock:t")
    yield
    cache.delete("lock:t")


class TestAcquire:
    def test_first_caller_wins(self):
        with advisory_lock("t") as acquired:
            assert acquired is True

    def test_second_caller_is_told_to_skip(self):
        with advisory_lock("t") as first:
            assert first is True
            with advisory_lock("t") as second:
                assert second is False

    def test_lock_is_released_on_exit(self):
        with advisory_lock("t"):
            pass
        with advisory_lock("t") as acquired:
            assert acquired is True

    def test_lock_is_released_even_if_the_body_raises(self):
        with pytest.raises(RuntimeError):
            with advisory_lock("t"):
                raise RuntimeError("boom")
        with advisory_lock("t") as acquired:
            assert acquired is True


class TestFailOpen:
    def test_cache_outage_proceeds_rather_than_blocking(self, monkeypatch):
        """The distinction this module exists to make.

        With IGNORE_EXCEPTIONS a dead Redis returns None from `add`, while a
        genuinely contended lock returns False. Treating them alike would mean a
        Redis outage silently halts every scheduled publish -- a much worse
        failure than the duplicate work the database rejects anyway.
        """
        monkeypatch.setattr("common.locks.cache.add", lambda *a, **kw: None)
        with advisory_lock("t") as acquired:
            assert acquired is True

    def test_contention_still_skips(self, monkeypatch):
        monkeypatch.setattr("common.locks.cache.add", lambda *a, **kw: False)
        with advisory_lock("t") as acquired:
            assert acquired is False


class TestOwnership:
    def test_does_not_release_a_lock_taken_over_by_someone_else(self):
        """If our lock expired and another process took it, deleting on exit
        would free *their* lock and let a third process in."""
        with advisory_lock("t"):
            # Simulate expiry followed by another holder.
            cache.set("lock:t", "somebody-else", 60)
        assert cache.get("lock:t") == "somebody-else"
