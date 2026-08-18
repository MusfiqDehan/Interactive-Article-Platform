"""Delivery: idempotency, signing, backoff, auto-disable, and the retry sweep."""

import json

import pytest
from django.utils import timezone

from apps.syndication.delivery import enqueue, payload_fingerprint, send
from apps.syndication.models import ContentDelivery, Destination
from apps.syndication.tasks import retry_due_deliveries
from common.retry import MAX_ATTEMPTS, backoff_seconds
from common.signing import verify

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


@pytest.fixture
def destination(db, default_site):
    return Destination.objects.create(
        site=default_site,
        name="Partner",
        kind="webhook",
        endpoint_url="https://partner.example.com/hook",
    )


@pytest.fixture
def live_article(article_factory, default_site):
    from apps.syndication.models import Placement

    article = article_factory(status="published", is_live=True)
    Placement.objects.update_or_create(
        article=article,
        site=default_site,
        defaults={"is_primary": True, "is_live": True, "path_slug": article.slug},
    )
    return article


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text or json.dumps(body or {})

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class Recorder(list):
    """Captured POSTs, plus control over what the next one returns."""

    next_response = FakeResponse(200, {"ok": True})

    def respond(self, response):
        self.next_response = response


@pytest.fixture
def posts(monkeypatch):
    calls = Recorder()

    def _post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": data, "headers": headers})
        result = calls.next_response
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("apps.syndication.delivery.requests.post", _post)
    return calls


class TestIdempotency:
    def test_republishing_unchanged_content_sends_nothing_new(
        self, destination, live_article
    ):
        first = enqueue(live_article, "publish")
        second = enqueue(live_article, "publish")

        assert len(first) == 1
        # The whole point: a redelivered Celery message, a double-clicked
        # Publish button, and a retried task all land here and produce nothing.
        assert second == []
        assert ContentDelivery.objects.count() == 1

    def test_editing_the_body_produces_a_new_delivery(
        self, destination, live_article
    ):
        enqueue(live_article, "publish")
        live_article.content = {"blocks": [{"type": "paragraph", "data": {"text": "New"}}]}
        live_article.save()

        assert len(enqueue(live_article, "publish")) == 1
        assert ContentDelivery.objects.count() == 2

    def test_a_title_only_edit_also_redelivers(self, destination, live_article):
        before = payload_fingerprint(live_article)
        enqueue(live_article, "publish")

        live_article.title = "Corrected headline"
        live_article.save()

        # content_hash covers the block JSON only, so keying on it alone would
        # decide nothing had changed and leave the partner site showing the old
        # headline forever.
        assert payload_fingerprint(live_article) != before
        assert len(enqueue(live_article, "publish")) == 1

    def test_the_key_covers_the_event(self, destination, live_article):
        enqueue(live_article, "publish")
        assert len(enqueue(live_article, "unpublish")) == 1

    def test_disabled_destinations_are_not_enqueued(self, destination, live_article):
        destination.disabled_at = timezone.now()
        destination.save(update_fields=["disabled_at"])
        assert enqueue(live_article, "publish") == []

    def test_event_filter_is_respected(self, destination, live_article):
        destination.events = ["unpublish"]
        destination.save(update_fields=["events"])
        assert enqueue(live_article, "publish") == []
        assert len(enqueue(live_article, "unpublish")) == 1


class TestSigning:
    def test_the_receiver_can_verify_the_signature(
        self, destination, live_article, posts
    ):
        delivery = enqueue(live_article, "publish")[0]
        assert send(delivery) is True

        call = posts[0]
        assert verify(
            destination.secret,
            call["headers"]["X-CMS-Signature"],
            call["headers"]["X-CMS-Timestamp"],
            call["data"],
        )

    def test_a_tampered_body_fails_verification(
        self, destination, live_article, posts
    ):
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)
        call = posts[0]
        assert not verify(
            destination.secret,
            call["headers"]["X-CMS-Signature"],
            call["headers"]["X-CMS-Timestamp"],
            call["data"].replace("true", "false") + " ",
        )

    def test_an_event_id_is_sent_for_receiver_side_dedupe(
        self, destination, live_article, posts
    ):
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)
        assert posts[0]["headers"]["X-CMS-Event-Id"] == delivery.event_id

    def test_a_secret_is_generated_when_none_is_given(self, default_site):
        created = Destination.objects.create(
            site=default_site, name="Auto", kind="webhook",
            endpoint_url="https://x.example.com/h",
        )
        # Without this, signing raises and the delivery never leaves the queue
        # -- a configuration slip becomes a silent stall.
        assert created.secret


class TestOutcomes:
    def test_success_marks_delivered_and_clears_the_failure_count(
        self, destination, live_article, posts
    ):
        destination.consecutive_failures = 3
        destination.save(update_fields=["consecutive_failures"])

        delivery = enqueue(live_article, "publish")[0]
        assert send(delivery) is True

        delivery.refresh_from_db()
        destination.refresh_from_db()
        assert delivery.state == "delivered"
        assert delivery.response_status == 200
        assert delivery.delivered_at is not None
        assert destination.consecutive_failures == 0

    def test_a_500_schedules_a_retry(self, destination, live_article, posts):
        posts.respond(FakeResponse(500, text="boom"))
        delivery = enqueue(live_article, "publish")[0]

        assert send(delivery) is False
        delivery.refresh_from_db()
        assert delivery.state == "failed"
        assert delivery.attempts == 1
        assert delivery.next_attempt_at > timezone.now()

    def test_a_404_is_abandoned_immediately(self, destination, live_article, posts):
        posts.respond(FakeResponse(404, text="no such hook"))
        delivery = enqueue(live_article, "publish")[0]

        assert send(delivery) is False
        delivery.refresh_from_db()
        # Eight retries over thirty hours against a URL with a typo in it helps
        # nobody; the operator needs to know now.
        assert delivery.state == "abandoned"
        assert delivery.attempts == 1
        assert delivery.next_attempt_at is None

    def test_a_connection_error_is_retried(self, destination, live_article, posts):
        import requests

        posts.respond(requests.ConnectionError("refused"))
        delivery = enqueue(live_article, "publish")[0]

        assert send(delivery) is False
        delivery.refresh_from_db()
        assert delivery.state == "failed"
        assert "ConnectionError" in delivery.last_error

    def test_retries_are_exhausted_rather_than_infinite(
        self, destination, live_article, posts
    ):
        posts.respond(FakeResponse(503))
        delivery = enqueue(live_article, "publish")[0]
        for _ in range(MAX_ATTEMPTS):
            delivery.refresh_from_db()
            if delivery.state == "abandoned":
                break
            delivery.state = "failed"
            send(delivery)

        delivery.refresh_from_db()
        assert delivery.state == "abandoned"
        assert delivery.attempts == MAX_ATTEMPTS


class TestAutoDisable:
    def test_a_destination_switches_itself_off_after_repeated_failures(
        self, destination, live_article, posts
    ):
        posts.respond(FakeResponse(503))
        for index in range(Destination.FAILURE_LIMIT):
            article = live_article
            article.title = f"Version {index}"
            article.save()
            delivery = enqueue(article, "publish")[0]
            send(delivery)

        destination.refresh_from_db()
        assert destination.disabled_at is not None
        assert destination.is_deliverable is False
        assert "consecutive failures" in destination.disabled_reason

    def test_one_success_resets_the_counter(self, destination, live_article, posts):
        posts.respond(FakeResponse(503))
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)
        destination.refresh_from_db()
        assert destination.consecutive_failures == 1

        posts.respond(FakeResponse(200, {"ok": True}))
        live_article.title = "Now working"
        live_article.save()
        send(enqueue(live_article, "publish")[0])

        destination.refresh_from_db()
        assert destination.consecutive_failures == 0


class TestBackoff:
    def test_the_first_attempt_is_immediate(self):
        assert backoff_seconds(1) == 0

    def test_delays_grow(self):
        delays = [backoff_seconds(n, jitter=False) for n in range(1, MAX_ATTEMPTS + 1)]
        assert delays == sorted(delays)
        assert delays[-1] == 86400

    def test_jitter_spreads_a_synchronised_fleet(self):
        # Twelve destinations failing at the same instant must not all retry at
        # the same instant, or the recovering host sees the same herd again.
        samples = {backoff_seconds(4) for _ in range(12)}
        assert len(samples) > 1

    def test_beyond_the_schedule_the_last_interval_repeats(self):
        assert backoff_seconds(MAX_ATTEMPTS + 5, jitter=False) == 86400


class TestSweep:
    def test_due_deliveries_are_dispatched(self, destination, live_article, posts):
        posts.respond(FakeResponse(500))
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)

        delivery.refresh_from_db()
        delivery.next_attempt_at = timezone.now() - timezone.timedelta(seconds=1)
        delivery.save(update_fields=["next_attempt_at"])

        posts.respond(FakeResponse(200, {"ok": True}))
        result = retry_due_deliveries()
        assert result["dispatched"] == 1

    def test_a_delivery_not_yet_due_is_left_alone(
        self, destination, live_article, posts
    ):
        posts.respond(FakeResponse(500))
        send(enqueue(live_article, "publish")[0])
        assert retry_due_deliveries()["dispatched"] == 0

    def test_rows_stuck_in_delivering_are_reclaimed(self, destination, live_article):
        delivery = enqueue(live_article, "publish")[0]
        ContentDelivery.objects.filter(pk=delivery.pk).update(
            state="delivering",
            updated_at=timezone.now() - timezone.timedelta(hours=1),
        )
        # A worker that dies mid-POST leaves the row here; without reclaim it
        # is invisible to every later sweep and never retried at all.
        assert retry_due_deliveries()["reclaimed"] == 1


class TestPublishChain:
    def test_publishing_fans_out(self, destination, live_article, posts):
        from apps.editorial.tasks import after_publish

        result = after_publish(live_article.pk)
        assert result["deliveries"] == 1
        assert ContentDelivery.objects.filter(article=live_article).exists()

    def test_a_second_publish_of_the_same_content_does_not_duplicate(
        self, destination, live_article, posts
    ):
        from apps.editorial.tasks import after_publish

        after_publish(live_article.pk)
        assert after_publish(live_article.pk)["deliveries"] == 0


class TestAPI:
    def test_creating_a_destination_returns_the_secret_once(
        self, auth_client, admin, default_site
    ):
        response = auth_client(admin).post(
            f"{BASE}/destinations/",
            {"name": "New", "kind": "webhook", "endpoint_url": "https://x.test/h"},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["secret"]

        listed = auth_client(admin).get(f"{BASE}/destinations/").json()["results"][0]
        # And never again -- the list exposes only whether one exists.
        assert "secret" not in listed
        assert listed["has_secret"] is True

    def test_a_site_destination_requires_a_target(self, auth_client, admin):
        response = auth_client(admin).post(
            f"{BASE}/destinations/", {"name": "Bad", "kind": "site"}, format="json"
        )
        assert response.status_code == 400
        assert "target_site" in response.json()

    def test_enable_clears_both_the_flag_and_the_stamp(
        self, auth_client, admin, destination
    ):
        destination.is_active = False
        destination.disabled_at = timezone.now()
        destination.consecutive_failures = 20
        destination.save()

        response = auth_client(admin).post(
            f"{BASE}/destinations/{destination.pk}/enable/"
        )
        assert response.status_code == 200
        destination.refresh_from_db()
        # Setting is_active alone would leave a destination that reads as on
        # and delivers nothing.
        assert destination.is_deliverable is True
        assert destination.consecutive_failures == 0

    def test_the_delivery_log_is_read_only(
        self, auth_client, admin, destination, live_article
    ):
        enqueue(live_article, "publish")
        client = auth_client(admin)
        assert client.get(f"{BASE}/deliveries/").json()["count"] == 1
        assert client.post(f"{BASE}/deliveries/", {}, format="json").status_code == 405

    def test_retry_resets_the_backoff(
        self, auth_client, admin, destination, live_article, posts
    ):
        posts.respond(FakeResponse(404))
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)
        delivery.refresh_from_db()
        assert delivery.state == "abandoned"

        posts.respond(FakeResponse(200, {"ok": True}))
        response = auth_client(admin).post(f"{BASE}/deliveries/{delivery.pk}/retry/")
        assert response.status_code == 200
        delivery.refresh_from_db()
        # "I fixed the receiver, try now" has to work on an abandoned row --
        # that is the only state anyone opens this screen to act on.
        assert delivery.state == "delivered"

    def test_retrying_a_delivered_row_is_refused(
        self, auth_client, admin, destination, live_article, posts
    ):
        delivery = enqueue(live_article, "publish")[0]
        send(delivery)
        response = auth_client(admin).post(f"{BASE}/deliveries/{delivery.pk}/retry/")
        assert response.status_code == 409
        assert response.json()["code"] == "already_delivered"

    def test_deliveries_are_scoped_to_the_current_site(
        self, auth_client, admin, destination, live_article, other_site
    ):
        enqueue(live_article, "publish")
        elsewhere = Destination.objects.create(
            site=other_site, name="Theirs", kind="webhook",
            endpoint_url="https://theirs.test/h",
        )
        ContentDelivery.objects.create(
            destination=elsewhere,
            article_label="Not ours",
            event="publish",
            idempotency_key="deadbeef",
            event_id="x",
        )
        rows = auth_client(admin).get(f"{BASE}/deliveries/").json()["results"]
        assert [row["article_label"] for row in rows] == [live_article.title]
