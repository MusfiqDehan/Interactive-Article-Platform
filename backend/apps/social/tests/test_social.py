"""Social: counting, captions, the provider contract, and per-target publishing."""

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.social.captions import DEFAULT_TEMPLATE, fit, truncate_graphemes
from apps.social.constraints import counted_length, grapheme_length, spec_for
from apps.social.models import SocialAccount, SocialPost, SocialPostTarget
from apps.social.providers import (
    ProviderError,
    ProviderNotReady,
    PublishResult,
    SocialProvider,
    get_provider,
    register,
    registered,
)
from apps.social.tasks import idempotency_key, publish_target

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


@pytest.fixture(autouse=True)
def _credential_key(settings):
    settings.SOCIAL_CREDENTIAL_KEY = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# A scriptable provider, so publishing is testable without a network
# ---------------------------------------------------------------------------

SCRIPT: dict = {"behaviour": "ok", "calls": []}


@register
class FakeProvider(SocialProvider):
    key = "fake"
    platforms = ("x", "linkedin", "facebook", "threads")

    def begin_authorization(self, *, site, platform, redirect_uri):
        raise NotImplementedError

    def complete_authorization(self, *, site, platform, payload):
        raise NotImplementedError

    def publish(self, *, platform, caption, media, idempotency_key, state):
        SCRIPT["calls"].append(
            {"platform": platform, "key": idempotency_key, "state": dict(state or {})}
        )
        behaviour = SCRIPT["behaviour"]
        if behaviour == "not_ready_once":
            if not (state or {}).get("creation_id"):
                raise ProviderNotReady(
                    "container pending", retry_after=5, state={"creation_id": "c-1"}
                )
        elif behaviour == "transient":
            raise ProviderError("upstream hiccup")
        elif behaviour == "permanent":
            raise ProviderError("image too large", permanent=True)
        return PublishResult(external_id="ext-1", url="https://example.test/p/1")


@pytest.fixture(autouse=True)
def _reset_script():
    SCRIPT["behaviour"] = "ok"
    SCRIPT["calls"] = []


@pytest.fixture
def account_factory(db, default_site):
    counter = {"n": 0}

    def _make(platform="x", provider="fake", **kwargs):
        counter["n"] += 1
        account = SocialAccount(
            site=kwargs.pop("site", default_site),
            platform=platform,
            provider=provider,
            display_name=kwargs.pop("display_name", f"{platform} account"),
            external_id=kwargs.pop("external_id", f"ext-{counter['n']}"),
            **kwargs,
        )
        account.credentials = {"access_token": "t"}
        account.save()
        return account

    return _make


@pytest.fixture
def target_factory(db, default_site, account_factory):
    def _make(account=None, caption="Hello", media=None, **kwargs):
        account = account or account_factory()
        post = SocialPost.objects.create(
            site=default_site, article_label="Test", state="publishing"
        )
        return SocialPostTarget.objects.create(
            post=post,
            account=account,
            platform=account.platform,
            caption=caption,
            media=media or [],
            **kwargs,
        )

    return _make


# ---------------------------------------------------------------------------


class TestCounting:
    def test_x_counts_every_url_as_23(self):
        short = "See https://x.co/a"
        long = "See https://example.com/" + "a" * 300
        # The rule everyone gets wrong: a 300-character link is 23 characters.
        assert counted_length(short, "x") == counted_length(long, "x")

    def test_other_platforms_count_urls_in_full(self):
        text = "See https://example.com/" + "a" * 100
        assert counted_length(text, "linkedin") == grapheme_length(text)

    def test_a_bengali_conjunct_is_one_character(self):
        # "ক্ষ" is three code points and one grapheme; counting code points
        # would tell a Bengali author their post is a third longer than it is.
        assert grapheme_length("ক্ষ") == 1
        assert len("ক্ষ") == 3

    def test_a_zwj_emoji_sequence_is_one_character(self):
        assert grapheme_length("👨‍👩‍👧") == 1

    def test_a_long_link_leaves_room_on_x(self):
        spec = spec_for("x")
        text = "a" * 250 + " https://example.com/" + "b" * 200
        assert counted_length(text, "x") <= spec.max_length


class TestCaptions:
    def test_a_fitting_caption_is_left_alone(self):
        caption, fits = fit(
            DEFAULT_TEMPLATE, "linkedin",
            title="Short", excerpt="Also short.", link="https://e.test/a",
        )
        assert fits and "Also short." in caption

    def test_only_the_excerpt_is_trimmed(self):
        link = "https://example.test/articles/a-long-one"
        caption, fits = fit(
            DEFAULT_TEMPLATE, "x",
            title="A perfectly reasonable headline",
            excerpt="word " * 200,
            link=link,
            hashtags=["nlp", "bangla"],
        )
        assert fits
        # The three things that must survive intact: a trimmed link is broken,
        # trimmed hashtags are lost reach, a trimmed title loses the subject.
        assert link in caption
        assert "#nlp" in caption and "#bangla" in caption
        assert "A perfectly reasonable headline" in caption
        assert "…" in caption

    def test_an_impossible_caption_is_reported_not_mangled(self):
        caption, fits = fit(
            DEFAULT_TEMPLATE, "x",
            title="T" * 400, excerpt="anything", link="https://e.test/a",
        )
        assert fits is False
        # Returned whole, for a human to shorten -- the only cuts left would
        # break the link or drop the title.
        assert "https://e.test/a" in caption

    def test_trimming_does_not_split_a_grapheme(self):
        text = "ক্ষমতা " * 40
        trimmed = truncate_graphemes(text, 20)
        # A conjunct cut in half is not a shorter word, it is a different one.
        assert "্" not in trimmed[-1]
        assert grapheme_length(trimmed) <= 20

    def test_gaps_are_collapsed_when_a_segment_is_empty(self):
        caption, _ = fit(
            DEFAULT_TEMPLATE, "linkedin", title="T", excerpt="", link="https://e.test/a"
        )
        assert "\n\n\n" not in caption


class TestProviderContract:
    def test_validation_uses_the_shared_spec_table(self, account_factory):
        account = account_factory(platform="x")
        provider = get_provider(account)
        problems = provider.validate(platform="x", caption="a" * 400, media=[])
        assert problems and "over the 280 limit" in problems[0]

    def test_oversized_media_is_named_in_the_problem(self, account_factory):
        account = account_factory(platform="x")
        problems = get_provider(account).validate(
            platform="x",
            caption="fine",
            media=[{"mime": "image/png", "bytes": 20 * 1024 * 1024, "alt": "big.png"}],
        )
        assert any("big.png" in p for p in problems)

    def test_an_unknown_provider_key_is_a_clear_lookup_error(self, account_factory):
        account = account_factory(provider="nope")
        with pytest.raises(LookupError) as exc:
            get_provider(account)
        assert "nope" in str(exc.value)

    def test_every_registered_provider_implements_the_interface(self):
        for key, cls in registered().items():
            assert issubclass(cls, SocialProvider), key
            assert cls.platforms, f"{key} declares no platforms"

    def test_direct_providers_add_no_new_concepts(self):
        """Phase 8's whole point, asserted rather than assumed.

        A direct provider must be substitutable for the aggregator: same base
        class, same method set, no extra public methods the caller would have
        to know to call.
        """
        from apps.social.providers.aggregator import AggregatorProvider
        from apps.social.providers.direct import (
            FacebookProvider,
            LinkedInProvider,
            ThreadsProvider,
            XProvider,
        )

        def surface(cls):
            return {
                name
                for name in dir(cls)
                if not name.startswith("_") and callable(getattr(cls, name, None))
            }

        baseline = surface(AggregatorProvider)
        for cls in (LinkedInProvider, XProvider, FacebookProvider, ThreadsProvider):
            assert surface(cls) <= baseline, f"{cls.key} adds public API"

    def test_swapping_the_provider_is_a_data_change(self, account_factory):
        account = account_factory(platform="linkedin", provider="fake")
        assert get_provider(account).key == "fake"
        # One UPDATE. Nothing above this call knows or cares.
        SocialAccount.objects.filter(pk=account.pk).update(provider="linkedin_direct")
        account.refresh_from_db()
        assert get_provider(account).key == "linkedin_direct"


class TestCredentials:
    def test_credentials_are_encrypted_at_rest(self, account_factory):
        account = account_factory()
        raw = bytes(
            SocialAccount.objects.filter(pk=account.pk)
            .values_list("encrypted_credentials", flat=True)
            .first()
        )
        assert b"access_token" not in raw
        assert account.credentials == {"access_token": "t"}

    def test_a_missing_key_refuses_rather_than_storing_plaintext(
        self, settings, default_site
    ):
        settings.SOCIAL_CREDENTIAL_KEY = ""
        account = SocialAccount(
            site=default_site, platform="x", display_name="X", external_id="e"
        )
        with pytest.raises(RuntimeError):
            account.credentials = {"access_token": "secret"}

    def test_an_undecryptable_credential_reads_as_empty(self, account_factory, settings):
        account = account_factory()
        # Key rotated without re-encrypting. The account must read as unusable,
        # not 500 every page that lists accounts.
        settings.SOCIAL_CREDENTIAL_KEY = Fernet.generate_key().decode()
        assert account.credentials == {}


class TestPublishing:
    def test_a_target_publishes_independently(self, target_factory):
        target = target_factory()
        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "published"
        assert target.external_id == "ext-1"
        assert target.post.state == "published"

    def test_one_target_failing_leaves_the_others_published(
        self, account_factory, default_site
    ):
        post = SocialPost.objects.create(
            site=default_site, article_label="Multi", state="publishing"
        )
        good = SocialPostTarget.objects.create(
            post=post, account=account_factory(platform="linkedin"),
            platform="linkedin", caption="fine",
        )
        # Over X's limit, so validation fails this target and only this one.
        bad = SocialPostTarget.objects.create(
            post=post, account=account_factory(platform="x"),
            platform="x", caption="a" * 400,
        )

        publish_target(good.pk)
        publish_target(bad.pk)

        good.refresh_from_db()
        bad.refresh_from_db()
        post.refresh_from_db()
        assert good.state == "published"
        assert bad.state == "failed"
        # `partial`, not `failed`: telling the editor "failed" would have them
        # re-post to the platform that already worked.
        assert post.state == "partial"
        assert "over the 280 limit" in bad.last_error

    def test_not_ready_retries_the_same_container(self, target_factory):
        SCRIPT["behaviour"] = "not_ready_once"
        target = target_factory(account=None, caption="threads post")

        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "retrying"
        assert target.request_snapshot["creation_id"] == "c-1"
        # Not a failure -- a slow upload must not consume the retries meant for
        # real errors.
        assert target.attempts == 0

        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "published"
        # The second call resumed the container instead of creating another,
        # which is the difference between one post and two.
        assert SCRIPT["calls"][1]["state"]["creation_id"] == "c-1"

    def test_a_transient_error_schedules_a_retry(self, target_factory):
        SCRIPT["behaviour"] = "transient"
        target = target_factory()
        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "retrying"
        assert target.attempts == 1
        assert target.next_attempt_at is not None

    def test_a_permanent_error_does_not_retry(self, target_factory):
        SCRIPT["behaviour"] = "permanent"
        target = target_factory()
        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "failed"
        assert target.next_attempt_at is None

    def test_republishing_a_published_target_is_a_no_op(self, target_factory):
        target = target_factory()
        publish_target(target.pk)
        publish_target(target.pk)
        # acks_late means this task arrives twice; one post, not two.
        assert len(SCRIPT["calls"]) == 1

    def test_the_idempotency_key_is_stable_across_retries(self, target_factory):
        target = target_factory()
        first = idempotency_key(target)
        target.refresh_from_db()
        assert idempotency_key(target) == first

    def test_editing_the_caption_changes_the_key(self, target_factory):
        target = target_factory()
        before = idempotency_key(target)
        target.caption = "Reworded"
        assert idempotency_key(target) != before

    def test_an_unusable_account_fails_the_target_clearly(self, target_factory, account_factory):
        account = account_factory()
        account.status = "expired"
        account.save(update_fields=["status"])
        target = target_factory(account=account)
        publish_target(target.pk)
        target.refresh_from_db()
        assert target.state == "failed"
        assert "reconnecting" in target.last_error


class TestAPI:
    def test_platform_specs_are_served(self, auth_client, admin):
        body = auth_client(admin).get(f"{BASE}/social/platform-specs/").json()
        by_key = {row["key"]: row for row in body}
        assert by_key["x"]["url_length"] == 23
        assert by_key["threads"]["two_step_publish"] is True

    def test_accounts_never_expose_credentials(self, auth_client, admin, account_factory):
        account_factory()
        row = auth_client(admin).get(f"{BASE}/social/accounts/").json()["results"][0]
        assert "encrypted_credentials" not in row
        assert "credentials" not in row

    def test_caption_preview_reports_fit_per_platform(
        self, auth_client, admin, article_factory
    ):
        article = article_factory(title="A headline", excerpt="word " * 200)
        response = auth_client(admin).post(
            f"{BASE}/social/captions/",
            {"article": article.pk, "platforms": ["x", "linkedin"]},
            format="json",
        )
        assert response.status_code == 200
        by_platform = {row["platform"]: row for row in response.json()}
        assert by_platform["x"]["counted_length"] <= 280
        assert by_platform["linkedin"]["fits"] is True

    def test_creating_a_post_fans_out_one_target_per_account(
        self, auth_client, admin, account_factory
    ):
        x = account_factory(platform="x")
        linkedin = account_factory(platform="linkedin")
        response = auth_client(admin).post(
            f"{BASE}/social/posts/",
            {
                "targets": [
                    {"account": x.pk, "caption": "Short one"},
                    {"account": linkedin.pk, "caption": "A longer one"},
                ]
            },
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert {t["platform"] for t in body["targets"]} == {"x", "linkedin"}

    def test_the_same_account_twice_is_rejected(
        self, auth_client, admin, account_factory
    ):
        account = account_factory()
        response = auth_client(admin).post(
            f"{BASE}/social/posts/",
            {
                "targets": [
                    {"account": account.pk, "caption": "a"},
                    {"account": account.pk, "caption": "b"},
                ]
            },
            format="json",
        )
        assert response.status_code == 400

    def test_scheduling_does_not_publish_immediately(
        self, auth_client, admin, account_factory
    ):
        account = account_factory()
        when = (timezone.now() + timezone.timedelta(hours=2)).isoformat()
        response = auth_client(admin).post(
            f"{BASE}/social/posts/",
            {"scheduled_at": when, "targets": [{"account": account.pk, "caption": "x"}]},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["state"] == "scheduled"
        # Our beat task owns the schedule, not the provider's -- so nothing has
        # been handed to a platform yet.
        assert SCRIPT["calls"] == []

    def test_the_dispatch_sweep_publishes_due_posts(
        self, auth_client, admin, account_factory
    ):
        from apps.social.tasks import dispatch_due_posts

        account = account_factory()
        post = SocialPost.objects.create(
            site=account.site,
            state="scheduled",
            scheduled_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        SocialPostTarget.objects.create(
            post=post, account=account, platform=account.platform, caption="due"
        )
        result = dispatch_due_posts()
        assert result["dispatched"] == 1

    def test_retrying_one_target_does_not_touch_the_others(
        self, auth_client, admin, account_factory, default_site
    ):
        post = SocialPost.objects.create(site=default_site, state="partial")
        done = SocialPostTarget.objects.create(
            post=post, account=account_factory(platform="linkedin"),
            platform="linkedin", caption="ok", state="published", external_id="e1",
        )
        broken = SocialPostTarget.objects.create(
            post=post, account=account_factory(platform="x"),
            platform="x", caption="ok", state="failed",
        )
        response = auth_client(admin).post(f"{BASE}/social/targets/{broken.pk}/retry/")
        assert response.status_code == 200
        done.refresh_from_db()
        # Re-sending the whole post would duplicate the one that worked.
        assert done.state == "published" and done.external_id == "e1"

    def test_retrying_a_published_target_is_refused(
        self, auth_client, admin, target_factory
    ):
        target = target_factory()
        publish_target(target.pk)
        response = auth_client(admin).post(f"{BASE}/social/targets/{target.pk}/retry/")
        assert response.status_code == 409

    def test_accounts_are_scoped_to_the_site(
        self, auth_client, admin, account_factory, other_site
    ):
        account_factory(display_name="Ours")
        account_factory(display_name="Theirs", site=other_site)
        names = {
            row["display_name"]
            for row in auth_client(admin).get(f"{BASE}/social/accounts/").json()["results"]
        }
        assert names == {"Ours"}
