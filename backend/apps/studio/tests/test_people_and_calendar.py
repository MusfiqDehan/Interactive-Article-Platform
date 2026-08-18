"""Sites, memberships and the publishing calendar."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tenancy.models import SiteMembership

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


class TestSiteList:
    def test_lists_only_sites_you_belong_to(
        self, auth_client, author, membership_factory, default_site, other_site
    ):
        membership_factory(author, default_site, role="author")
        body = auth_client(author).get(f"{BASE}/sites/").json()
        # The switcher must not advertise a tenant the user cannot open --
        # picking it would produce a shell of 403s with no way back.
        assert [site["slug"] for site in body] == [default_site.slug]

    def test_admins_see_every_active_site(
        self, auth_client, admin, default_site, other_site
    ):
        body = auth_client(admin).get(f"{BASE}/sites/").json()
        assert {site["slug"] for site in body} == {default_site.slug, other_site.slug}

    def test_anonymous_is_rejected(self, api_client):
        assert api_client.get(f"{BASE}/sites/").status_code in (401, 403)


class TestPeople:
    def test_owner_can_invite_by_email(
        self, auth_client, author, user_factory, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        colleague = user_factory(role="author")

        response = auth_client(author).post(
            f"{BASE}/people/",
            {"email": colleague.email, "role": "editor"},
            format="json",
        )
        assert response.status_code == 201
        assert SiteMembership.objects.get(
            site=default_site, user=colleague
        ).role == "editor"

    def test_inviting_an_existing_member_changes_their_role(
        self, auth_client, author, user_factory, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        colleague = user_factory(role="author")
        membership_factory(colleague, default_site, role="viewer")

        response = auth_client(author).post(
            f"{BASE}/people/", {"email": colleague.email, "role": "editor"}, format="json"
        )
        # Re-inviting is the natural gesture for "give them more access"; a
        # duplicate-key error would be a correct database answer and a useless
        # product one.
        assert response.status_code == 201
        assert SiteMembership.objects.get(
            site=default_site, user=colleague
        ).role == "editor"

    def test_unknown_email_is_a_field_error(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="owner")
        response = auth_client(author).post(
            f"{BASE}/people/", {"email": "nobody@example.com", "role": "editor"},
            format="json",
        )
        assert response.status_code == 400
        assert "email" in response.json()

    def test_editors_cannot_manage_people(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="editor")
        assert auth_client(author).get(f"{BASE}/people/").status_code == 403

    def test_the_last_owner_cannot_be_removed(
        self, auth_client, author, membership_factory, default_site
    ):
        membership = membership_factory(author, default_site, role="owner")
        response = auth_client(author).delete(f"{BASE}/people/{membership.pk}/")
        # Handing a site over by removing yourself first is the natural order
        # to do it in, and it locks everyone out of the screen that could undo
        # it -- including the person who did it.
        assert response.status_code == 409
        assert response.json()["code"] == "last_owner"

    def test_the_last_owner_cannot_be_demoted(
        self, auth_client, author, membership_factory, default_site
    ):
        membership = membership_factory(author, default_site, role="owner")
        response = auth_client(author).patch(
            f"{BASE}/people/{membership.pk}/", {"role": "editor"}, format="json"
        )
        assert response.status_code == 409

    def test_an_owner_can_leave_once_another_exists(
        self, auth_client, author, user_factory, membership_factory, default_site
    ):
        membership = membership_factory(author, default_site, role="owner")
        membership_factory(user_factory(role="author"), default_site, role="owner")
        assert auth_client(author).delete(f"{BASE}/people/{membership.pk}/").status_code == 204

    def test_people_are_scoped_to_the_current_site(
        self, auth_client, admin, user_factory, membership_factory,
        default_site, other_site,
    ):
        here = user_factory(role="author")
        there = user_factory(role="author")
        membership_factory(here, default_site, role="editor")
        membership_factory(there, other_site, role="editor")

        emails = {
            row["user"]["email"]
            for row in auth_client(admin).get(f"{BASE}/people/").json()["results"]
        }
        assert here.email in emails and there.email not in emails


class TestCalendar:
    def test_window_requires_both_bounds(self, auth_client, admin):
        assert auth_client(admin).get(f"{BASE}/calendar/").status_code == 400

    def test_entries_are_bucketed_by_kind(self, auth_client, admin, article_factory):
        now = timezone.now()
        article_factory(
            title="Going live",
            status="scheduled",
            scheduled_publish_at=now + timedelta(days=1),
        )
        article_factory(
            title="Already out",
            status="published",
            is_live=True,
            published_at=now - timedelta(days=1),
        )

        start = (now - timedelta(days=7)).isoformat()
        end = (now + timedelta(days=7)).isoformat()
        body = auth_client(admin).get(f"{BASE}/calendar/?from={start}&to={end}").json()

        by_title = {row["title"]: row for row in body["entries"]}
        assert by_title["Going live"]["kind"] == "scheduled_publish"
        assert by_title["Already out"]["kind"] == "published"
        # `at` is the single date the calendar sorts and places on; without it
        # every consumer re-derives the same branch and one gets it wrong.
        assert all(row["at"] for row in body["entries"])

    def test_articles_outside_the_window_are_excluded(
        self, auth_client, admin, article_factory
    ):
        now = timezone.now()
        article_factory(
            title="Far future",
            status="scheduled",
            scheduled_publish_at=now + timedelta(days=90),
        )
        start = now.isoformat()
        end = (now + timedelta(days=7)).isoformat()
        body = auth_client(admin).get(f"{BASE}/calendar/?from={start}&to={end}").json()
        assert body["entries"] == []

    def test_unscheduled_drafts_are_returned_for_the_side_rail(
        self, auth_client, admin, article_factory
    ):
        article_factory(title="Waiting", status="draft")
        now = timezone.now()
        body = auth_client(admin).get(
            f"{BASE}/calendar/?from={now.isoformat()}"
            f"&to={(now + timedelta(days=7)).isoformat()}"
        ).json()
        assert "Waiting" in {row["title"] for row in body["unscheduled"]}
