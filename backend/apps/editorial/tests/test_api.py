"""Studio workflow endpoints: transitions, concurrency, revisions, audit."""

import pytest
from django.utils import timezone

BASE = "/api/v1/studio"

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(user_factory, default_site, membership_factory):
    user = user_factory(role="author")
    membership_factory(user, default_site, role="editor")
    return user


@pytest.fixture
def writer(user_factory, default_site, membership_factory):
    user = user_factory(role="author")
    membership_factory(user, default_site, role="author")
    return user


class TestTransitionEndpoint:
    def test_publishes(self, auth_client, editor, article_factory):
        article = article_factory(status="draft")
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish", "reason": "ready"},
            format="json",
        )
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.status == "published"
        assert response.json()["article"]["status"] == "published"

    def test_illegal_transition_is_409_not_400(
        self, auth_client, editor, article_factory
    ):
        """The request is well-formed; it conflicts with current state.

        A 400 would tell the client its payload was wrong, sending a developer
        to debug the request body instead of refetching the article.
        """
        article = article_factory(status="draft")
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "approve"},
            format="json",
        )
        assert response.status_code == 409
        assert response.json()["code"] == "illegal_transition"

    def test_insufficient_role_is_403(self, auth_client, writer, article_factory):
        article = article_factory(status="draft", author=writer)
        response = auth_client(writer).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )
        assert response.status_code == 403
        article.refresh_from_db()
        assert article.status == "draft"

    def test_unknown_transition_is_400(self, auth_client, editor, article_factory):
        article = article_factory(status="draft")
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "explode"},
            format="json",
        )
        assert response.status_code == 400

    def test_response_carries_next_available_actions(
        self, auth_client, editor, article_factory
    ):
        article = article_factory(status="draft")
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )
        names = {t["name"] for t in response.json()["available_transitions"]}
        assert {"unpublish", "archive"} <= names

    def test_schedule_through_the_transition_endpoint(
        self, auth_client, editor, article_factory
    ):
        article = article_factory(status="draft")
        when = timezone.now() + timezone.timedelta(hours=3)
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "schedule", "scheduled_publish_at": when.isoformat()},
            format="json",
        )
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.status == "scheduled"

    def test_publish_triggers_the_publish_chain(
        self, auth_client, editor, article_factory, stub_outbound_http,
        django_capture_on_commit_callbacks, settings,
    ):
        """The chain is deferred to commit, so the test must reach commit.

        Firing it inline would announce a publish that a rollback could undo --
        which is precisely why `django_capture_on_commit_callbacks` is needed
        here rather than the assertions just working.
        """
        settings.CMS_REVALIDATE_SECRET = "test-secret"
        article = article_factory(status="draft")

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            auth_client(editor).post(
                f"{BASE}/articles/{article.slug}/transition/",
                {"transition": "publish"},
                format="json",
            )
        assert callbacks, "publish should have queued post-commit work"

        # A revision snapshot marks the published state...
        from apps.editorial.models import Revision

        assert Revision.objects.filter(article=article, reason="published").exists()
        # ...and the frontend was asked to purge the article's path.
        assert stub_outbound_http, "expected a revalidation call"
        assert "revalidate" in stub_outbound_http[0]["url"]

    def test_nothing_is_announced_if_the_transaction_rolls_back(
        self, auth_client, editor, article_factory, stub_outbound_http
    ):
        """No on_commit hook fires without a commit -- the point of deferring."""
        article = article_factory(status="draft")
        auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )
        assert stub_outbound_http == []


class TestListTransitions:
    def test_author_is_offered_submit_only(
        self, auth_client, writer, article_factory
    ):
        article = article_factory(status="draft", author=writer)
        body = auth_client(writer).get(
            f"{BASE}/articles/{article.slug}/transitions/"
        ).json()
        names = {t["name"] for t in body["available"]}
        assert "submit" in names and "publish" not in names
        assert body["status"] == "draft"


class TestOptimisticConcurrency:
    def test_matching_if_match_succeeds(self, auth_client, editor, article_factory):
        article = article_factory(content={"blocks": []})
        response = auth_client(editor).patch(
            f"{BASE}/articles/{article.slug}/",
            {"title": "Renamed"},
            format="json",
            HTTP_IF_MATCH=f'"{article.content_hash}"',
        )
        assert response.status_code == 200

    def test_two_tabs_conflict_instead_of_clobbering(
        self, auth_client, editor, article_factory
    ):
        """The Phase 3 acceptance case.

        Both tabs loaded the same version. Tab A saves; tab B must be told its
        base is stale rather than silently overwriting A's paragraph.
        """
        article = article_factory(content={"blocks": []})
        client = auth_client(editor)
        shared_version = article.content_hash

        first = client.patch(
            f"{BASE}/articles/{article.slug}/",
            {"content": {"blocks": [{"id": "a", "type": "paragraph",
                                     "data": {"text": "tab A"}}]}},
            format="json",
            HTTP_IF_MATCH=f'"{shared_version}"',
        )
        assert first.status_code == 200

        second = client.patch(
            f"{BASE}/articles/{article.slug}/",
            {"content": {"blocks": [{"id": "b", "type": "paragraph",
                                     "data": {"text": "tab B"}}]}},
            format="json",
            HTTP_IF_MATCH=f'"{shared_version}"',
        )
        assert second.status_code == 409
        assert second.json()["code"] == "stale_content"

        # Tab A's work is intact.
        article.refresh_from_db()
        assert article.content["blocks"][0]["data"]["text"] == "tab A"

    def test_conflict_body_carries_what_the_ui_needs(
        self, auth_client, editor, article_factory
    ):
        article = article_factory(content={"blocks": []})
        response = auth_client(editor).patch(
            f"{BASE}/articles/{article.slug}/",
            {"title": "x"},
            format="json",
            HTTP_IF_MATCH='"deadbeef"',
        )
        body = response.json()
        assert response.status_code == 409
        assert body["current_version"] == article.content_hash
        assert body["your_version"] == "deadbeef"

    def test_omitting_if_match_is_allowed(self, auth_client, editor, article_factory):
        """The legacy client predates this protocol and must keep working."""
        article = article_factory()
        response = auth_client(editor).patch(
            f"{BASE}/articles/{article.slug}/", {"title": "No Header"}, format="json"
        )
        assert response.status_code == 200

    def test_star_matches_any_version(self, auth_client, editor, article_factory):
        article = article_factory()
        response = auth_client(editor).patch(
            f"{BASE}/articles/{article.slug}/",
            {"title": "Star"},
            format="json",
            HTTP_IF_MATCH="*",
        )
        assert response.status_code == 200

    def test_weak_and_quoted_forms_are_accepted(
        self, auth_client, editor, article_factory
    ):
        article = article_factory()
        response = auth_client(editor).patch(
            f"{BASE}/articles/{article.slug}/",
            {"title": "Weak"},
            format="json",
            HTTP_IF_MATCH=f'W/"{article.content_hash}"',
        )
        assert response.status_code == 200

    def test_responses_carry_an_etag(self, auth_client, editor, article_factory):
        article = article_factory()
        response = auth_client(editor).get(f"{BASE}/articles/{article.slug}/")
        assert response["ETag"] == f'"{article.content_hash}"'


class TestRevisionEndpoints:
    def test_list_and_detail(self, auth_client, editor, article_factory):
        from apps.editorial.revisions import create_revision

        article = article_factory(content={"blocks": []})
        create_revision(article, user=editor, reason="one")
        client = auth_client(editor)

        listing = client.get(f"{BASE}/articles/{article.slug}/revisions/").json()
        rows = listing["results"] if isinstance(listing, dict) else listing
        assert rows[0]["number"] == 1
        # The list must stay cheap: no full snapshots.
        assert "snapshot" not in rows[0]

        detail = client.get(f"{BASE}/articles/{article.slug}/revisions/1/").json()
        assert "snapshot" in detail

    def test_diff_against_current(self, auth_client, editor, article_factory):
        from apps.editorial.revisions import create_revision

        article = article_factory(
            content={"blocks": [{"id": "a", "type": "paragraph",
                                 "data": {"text": "before"}}]}
        )
        create_revision(article, user=editor)
        article.content = {
            "blocks": [{"id": "a", "type": "paragraph", "data": {"text": "after"}}]
        }
        article.save()

        body = auth_client(editor).get(
            f"{BASE}/articles/{article.slug}/revisions/1/diff/"
        ).json()
        assert body["diff"]["blocks"]["changed"] == ["a"]

    def test_restore(self, auth_client, editor, article_factory):
        from apps.editorial.revisions import create_revision

        article = article_factory(
            content={"blocks": [{"id": "a", "type": "paragraph",
                                 "data": {"text": "original"}}]}
        )
        create_revision(article, user=editor)
        article.content = {"blocks": []}
        article.save()

        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/revisions/1/restore/", format="json"
        )
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.content["blocks"][0]["data"]["text"] == "original"

    def test_missing_revision_is_404(self, auth_client, editor, article_factory):
        article = article_factory()
        response = auth_client(editor).get(
            f"{BASE}/articles/{article.slug}/revisions/99/"
        )
        assert response.status_code == 404

    def test_manual_snapshot(self, auth_client, editor, article_factory):
        article = article_factory()
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/snapshot/",
            {"reason": "before big edit"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["reason"] == "before big edit"


class TestScheduleEndpoint:
    def test_sets_the_time(self, auth_client, editor, article_factory):
        article = article_factory(status="draft")
        when = timezone.now() + timezone.timedelta(days=1)
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/schedule/",
            {"scheduled_publish_at": when.isoformat()},
            format="json",
        )
        assert response.status_code == 200
        article.refresh_from_db()
        assert article.scheduled_publish_at is not None

    def test_rejects_a_past_time(self, auth_client, editor, article_factory):
        article = article_factory(status="draft")
        past = timezone.now() - timezone.timedelta(days=1)
        response = auth_client(editor).post(
            f"{BASE}/articles/{article.slug}/schedule/",
            {"scheduled_publish_at": past.isoformat()},
            format="json",
        )
        assert response.status_code == 400


class TestAuditEndpoints:
    def test_per_article_trail(self, auth_client, editor, article_factory):
        article = article_factory(status="draft")
        client = auth_client(editor)
        client.post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "publish"},
            format="json",
        )
        body = client.get(f"{BASE}/articles/{article.slug}/audit/").json()
        rows = body["results"] if isinstance(body, dict) else body
        assert any(r["to_state"] == "published" for r in rows)

    def test_site_wide_log_is_read_only(self, auth_client, editor, article_factory):
        article_factory()
        client = auth_client(editor)
        assert client.get(f"{BASE}/audit-log/").status_code == 200
        # No write endpoint exists -- an editable audit log is not an audit log.
        assert client.post(f"{BASE}/audit-log/", {}, format="json").status_code == 405

    def test_log_is_tenant_scoped(
        self, auth_client, editor, article_factory, other_site, user_factory,
        membership_factory
    ):
        from apps.editorial.transitions import record

        article = article_factory()
        record(site=other_site, action="update", user=None, article=None,
               metadata={"secret": "other tenant"})
        record(site=article.site, action="update", user=None, article=article)

        body = auth_client(editor).get(f"{BASE}/audit-log/").json()
        rows = body["results"] if isinstance(body, dict) else body
        assert all(r["metadata"].get("secret") is None for r in rows)


class TestReviewWorkflow:
    def test_assign_and_resolve(
        self, auth_client, editor, writer, article_factory
    ):
        article = article_factory(status="draft", author=writer)
        client = auth_client(editor)

        created = client.post(
            f"{BASE}/reviews/",
            {"article": article.pk, "assignee": editor.pk, "note": "please look"},
            format="json",
        )
        assert created.status_code == 201
        review_id = created.json()["id"]

        resolved = client.post(
            f"{BASE}/reviews/{review_id}/resolve/",
            {"state": "approved"},
            format="json",
        )
        assert resolved.status_code == 200
        assert resolved.json()["state"] == "approved"

    def test_block_anchored_comment(self, auth_client, editor, article_factory):
        article = article_factory()
        response = auth_client(editor).post(
            f"{BASE}/comments/",
            {"article": article.pk, "block_id": "abc123", "body": "tighten this"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["block_id"] == "abc123"

    def test_inbox_lists_articles_in_review(
        self, auth_client, editor, writer, article_factory
    ):
        article = article_factory(status="draft", author=writer)
        auth_client(writer).post(
            f"{BASE}/articles/{article.slug}/transition/",
            {"transition": "submit"},
            format="json",
        )
        body = auth_client(editor).get(f"{BASE}/review-inbox/").json()
        rows = body["results"] if isinstance(body, dict) else body
        assert any(r["slug"] == article.slug for r in rows)
