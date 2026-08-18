"""Tags: slugs, tagging, merging, and the studio endpoints."""

import pytest

from apps.taxonomy.models import Tag, TaggedItem, set_tags, tags_for

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"


@pytest.fixture
def tag_factory(db, default_site):
    def _make(name, site=None, **kwargs):
        return Tag.objects.create(site=site or default_site, name=name, **kwargs)

    return _make


class TestModel:
    def test_slug_preserves_bengali_marks(self, tag_factory):
        tag = tag_factory("যান্ত্রিক অনুবাদ")
        # Django's own slugify would strip the vowel marks and leave "যনতরক";
        # common.slugs keeps them, which is the whole reason it exists.
        assert "যান্ত্রিক" in tag.slug

    def test_same_name_on_two_sites_is_allowed(self, tag_factory, other_site):
        tag_factory("Machine Learning")
        tag_factory("Machine Learning", site=other_site)
        assert Tag.unscoped.filter(name="Machine Learning").count() == 2

    def test_duplicate_name_on_one_site_is_rejected(self, tag_factory):
        from django.db.utils import IntegrityError

        tag_factory("Duplicate")
        with pytest.raises(IntegrityError):
            tag_factory("Duplicate")


class TestSetTags:
    def test_unknown_names_are_created(self, article_factory, default_site):
        article = article_factory()
        set_tags(article, ["Translation", "NLP"], site=default_site)
        assert [t.name for t in tags_for(article)] == ["Translation", "NLP"]

    def test_order_is_preserved(self, article_factory, default_site):
        article = article_factory()
        set_tags(article, ["c", "a", "b"], site=default_site)
        assert [t.name for t in tags_for(article)] == ["c", "a", "b"]

    def test_setting_replaces_rather_than_appends(self, article_factory, default_site):
        article = article_factory()
        set_tags(article, ["one", "two"], site=default_site)
        set_tags(article, ["two", "three"], site=default_site)
        assert {t.name for t in tags_for(article)} == {"two", "three"}

    def test_usage_count_tracks_both_directions(self, article_factory, default_site):
        article = article_factory()
        set_tags(article, ["counted"], site=default_site)
        assert Tag.unscoped.get(name="counted").usage_count == 1
        set_tags(article, [], site=default_site)
        assert Tag.unscoped.get(name="counted").usage_count == 0

    def test_an_existing_tag_is_matched_case_insensitively(
        self, article_factory, tag_factory, default_site
    ):
        existing = tag_factory("Machine Learning")
        article = article_factory()
        set_tags(article, ["machine learning"], site=default_site)
        # Typing a tag that already exists in different case must not fork the
        # taxonomy into two near-identical entries.
        assert list(tags_for(article)) == [existing]


class TestMerge:
    def test_items_move_to_the_target(
        self, article_factory, tag_factory, default_site
    ):
        keep = tag_factory("NLP")
        drop = tag_factory("Natural Language Processing")
        article = article_factory()
        set_tags(article, [drop.slug], site=default_site)

        moved = drop.merge_into(keep)

        assert moved == 1
        assert list(tags_for(article)) == [keep]
        assert not Tag.unscoped.filter(pk=drop.pk).exists()

    def test_an_item_carrying_both_tags_does_not_violate_uniqueness(
        self, article_factory, tag_factory, default_site
    ):
        keep = tag_factory("NLP")
        drop = tag_factory("NLProc")
        article = article_factory()
        set_tags(article, [keep.slug, drop.slug], site=default_site)

        # The failure this guards: a blind UPDATE of tag_id would collide on
        # (tag, content_type, object_id) for exactly the articles that carry
        # both -- which is the common case when merging synonyms.
        moved = drop.merge_into(keep)

        assert moved == 0
        assert list(tags_for(article)) == [keep]
        assert TaggedItem.unscoped.filter(tag=keep).count() == 1

    def test_usage_count_is_recomputed(self, article_factory, tag_factory, default_site):
        keep = tag_factory("Keep")
        drop = tag_factory("Drop")
        for _ in range(3):
            set_tags(article_factory(), [drop.slug], site=default_site)
        drop.merge_into(keep)
        keep.refresh_from_db()
        assert keep.usage_count == 3

    def test_cross_site_merge_is_refused(self, tag_factory, other_site):
        here = tag_factory("Here")
        there = tag_factory("There", site=other_site)
        with pytest.raises(ValueError):
            here.merge_into(there)


class TestAPI:
    def test_author_may_create_but_not_rename(
        self, auth_client, author, membership_factory, default_site, tag_factory
    ):
        membership_factory(author, default_site, role="author")
        client = auth_client(author)
        assert client.post(f"{BASE}/tags/", {"name": "New"}, format="json").status_code == 201

        tag = tag_factory("Existing")
        # Renaming reshapes every URL carrying the tag; that is editor work.
        assert client.patch(
            f"{BASE}/tags/{tag.slug}/", {"name": "Renamed"}, format="json"
        ).status_code == 403

    def test_editor_may_rename(
        self, auth_client, author, membership_factory, default_site, tag_factory
    ):
        membership_factory(author, default_site, role="editor")
        tag = tag_factory("Before")
        response = auth_client(author).patch(
            f"{BASE}/tags/{tag.slug}/", {"name": "After"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["name"] == "After"

    def test_deleting_a_tag_in_use_is_refused(
        self, auth_client, admin, tag_factory, article_factory, default_site
    ):
        tag = tag_factory("Busy")
        set_tags(article_factory(), [tag.slug], site=default_site)
        response = auth_client(admin).delete(f"{BASE}/tags/{tag.slug}/")
        # Silently stripping the tag from every article would be the easy
        # implementation and the one nobody can undo.
        assert response.status_code == 409
        assert response.json()["code"] == "tag_in_use"
        assert Tag.unscoped.filter(pk=tag.pk).exists()

    def test_unused_tags_delete_cleanly(self, auth_client, admin, tag_factory):
        tag = tag_factory("Unused")
        assert auth_client(admin).delete(f"{BASE}/tags/{tag.slug}/").status_code == 204

    def test_merge_reports_per_source(
        self, auth_client, admin, tag_factory, article_factory, default_site
    ):
        keep = tag_factory("Keep")
        drop = tag_factory("Drop")
        set_tags(article_factory(), [drop.slug], site=default_site)

        response = auth_client(admin).post(
            f"{BASE}/tags/merge/",
            {"into": keep.slug, "sources": [drop.slug, "no-such-tag", keep.slug]},
            format="json",
        )
        body = response.json()
        assert response.status_code == 200
        assert body["merged"] == [drop.slug]
        assert body["items_moved"] == 1
        assert {row["slug"] for row in body["skipped"]} == {"no-such-tag", keep.slug}

    def test_article_write_accepts_tag_slugs(self, auth_client, admin):
        response = auth_client(admin).post(
            f"{BASE}/articles/",
            {
                "title": "Tagged",
                "content": {"blocks": []},
                "tag_slugs": ["Attention", "Transformers"],
            },
            format="json",
        )
        assert response.status_code == 201
        assert [t["name"] for t in response.json()["tags"]] == [
            "Attention",
            "Transformers",
        ]

    def test_article_list_filters_by_tag_conjunctively(
        self, auth_client, admin, article_factory, default_site
    ):
        both = article_factory(title="Both")
        one = article_factory(title="One")
        set_tags(both, ["alpha", "beta"], site=default_site)
        set_tags(one, ["alpha"], site=default_site)

        client = auth_client(admin)
        single = client.get(f"{BASE}/articles/?tag=alpha").json()
        assert single["count"] == 2
        # Stacked chips narrow; two filters meaning "either" would make the
        # result grow as the editor adds constraints.
        stacked = client.get(f"{BASE}/articles/?tag=alpha&tag=beta").json()
        assert [row["title"] for row in stacked["results"]] == ["Both"]

    def test_tags_are_scoped_to_the_site(
        self, auth_client, admin, tag_factory, other_site
    ):
        tag_factory("Mine")
        tag_factory("Theirs", site=other_site)
        names = {row["name"] for row in auth_client(admin).get(f"{BASE}/tags/").json()["results"]}
        assert names == {"Mine"}
