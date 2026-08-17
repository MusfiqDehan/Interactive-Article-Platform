"""End-to-end proof that content survives a real create -> fetch round trip.

Exercises the full HTTP path (serializer validation, sanitization, model save)
rather than the helpers in isolation, because that is where the two confirmed
corruption bugs actually bit: multi-parameter URLs were HTML-escaped and rich
annotation bodies were flattened on every save.
"""

import pytest

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/studio/articles/"


@pytest.fixture
def created(auth_client, author, default_site, membership_factory):
    # `default_site` is requested explicitly rather than relying on the row that
    # tenancy.0002 seeds. Depending on migration-created data makes a test
    # silently order-dependent: any transactional test elsewhere in the suite
    # truncates that row and this one starts failing for reasons that have
    # nothing to do with it.
    membership_factory(author, default_site, role="author")
    client = auth_client(author)
    payload = {
        # No `status`: it is read-only on this surface, so articles are always
        # created as drafts and moved by transitions.
        "title": "যান্ত্রিক অনুবাদ",
        "content": {
            "blocks": [
                {
                    "type": "interactive_youtube",
                    "data": {
                        "source": "https://youtu.be/abc?a=1&t=5",
                        "caption": "Watch this",
                        "chapters": [
                            {
                                "id": "c1",
                                "time": 30,
                                "label": "Intro",
                                "modal_title": "Opening",
                                "modal_content": "<h3>Notes</h3><ul><li>one</li><li>two</li></ul>",
                            }
                        ],
                    },
                },
                {
                    "type": "paragraph",
                    "data": {"text": "Body <script>alert(1)</script> text"},
                },
            ]
        },
    }
    response = client.post(LIST_URL, payload, format="json")
    assert response.status_code == 201, response.content
    article_id = response.json()["id"]

    from apps.articles.models import Article

    slug = Article.objects.get(pk=article_id).slug
    return client, client.get(f"{LIST_URL}{slug}/").json()


class TestRoundTrip:
    def test_unicode_slug_survives(self, created):
        _, data = created
        assert data["slug"] == "যান্ত্রিক-অনুবাদ"

    def test_multi_param_url_is_not_escaped(self, created):
        _, data = created
        source = data["content"]["blocks"][0]["data"]["source"]
        assert source == "https://youtu.be/abc?a=1&t=5"
        assert "&amp;" not in source

    def test_rich_annotation_body_keeps_its_structure(self, created):
        _, data = created
        body = data["content"]["blocks"][0]["data"]["chapters"][0]["modal_content"]
        assert "<h3>Notes</h3>" in body
        assert "<li>one</li>" in body

    def test_script_tags_are_still_stripped(self, created):
        _, data = created
        text = data["content"]["blocks"][1]["data"]["text"]
        assert "<script" not in text
        assert "Body" in text and "text" in text

    def test_every_block_has_an_id(self, created):
        _, data = created
        assert all(block.get("id") for block in data["content"]["blocks"])

    def test_reading_time_counts_annotation_prose(self, created):
        _, data = created
        assert data["reading_time"] >= 1

    def test_detail_response_shape_is_pinned(self, created):
        _, data = created
        # Pinned exactly, because the generated TypeScript client is typed off
        # this shape: a field quietly appearing or vanishing is a compile error
        # for the studio rather than something anyone notices at runtime.
        assert set(data) == {
            "id", "title", "slug", "author", "category",
            "content", "excerpt", "featured_image", "status", "is_live",
            "is_featured", "reading_time", "word_count", "views_count",
            "content_hash", "published_at", "last_published_at",
            "unpublished_at", "scheduled_publish_at", "scheduled_unpublish_at",
            "locale", "created_at", "updated_at",
            "placements", "available_transitions", "tags",
        }

    def test_editing_preserves_block_ids(self, created):
        client, data = created
        original_ids = [b["id"] for b in data["content"]["blocks"]]

        # No `status` in the payload: publication is a transition now, and an
        # author sending one here is correctly refused. These tests are about
        # content surviving a round trip, so they stay out of the workflow.
        response = client.put(
            f"{LIST_URL}{data['slug']}/",
            {"title": data["title"], "content": data["content"]},
            format="json",
        )
        assert response.status_code == 200

        refetched = client.get(f"{LIST_URL}{data['slug']}/").json()
        assert [b["id"] for b in refetched["content"]["blocks"]] == original_ids

    def test_urls_survive_repeated_saves(self, created):
        client, data = created
        for _ in range(3):
            client.put(
                f"{LIST_URL}{data['slug']}/",
                {"title": data["title"], "content": data["content"]},
                format="json",
            )
            data = client.get(f"{LIST_URL}{data['slug']}/").json()

        assert (
            data["content"]["blocks"][0]["data"]["source"]
            == "https://youtu.be/abc?a=1&t=5"
        )
