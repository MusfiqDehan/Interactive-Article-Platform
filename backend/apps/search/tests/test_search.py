"""Search: indexing, drift repair, the swap rebuild, and failing soft."""

import pytest

from apps.search import client
from apps.search.models import IndexingLog
from apps.search.tasks import index_article, rebuild_index, repair_drift

pytestmark = pytest.mark.django_db

BASE = "/api/v1/studio"
PUBLIC = "/api/v1/public"


class FakeIndex:
    def __init__(self, engine, name):
        self.engine = engine
        self.name = name

    def update_settings(self, settings):
        self.engine.settings[self.name] = settings

    def add_documents(self, documents):
        if self.engine.down:
            raise RuntimeError("connection refused")
        store = self.engine.documents.setdefault(self.name, {})
        for document in documents:
            store[document["id"]] = document

    def delete_document(self, document_id):
        if self.engine.down:
            raise RuntimeError("connection refused")
        self.engine.documents.setdefault(self.name, {}).pop(document_id, None)

    def search(self, query, options):
        if self.engine.down:
            raise RuntimeError("connection refused")
        store = self.engine.documents.get(self.name, {})
        hits = [
            doc
            for doc in store.values()
            if query.lower() in f"{doc['title']} {doc['plain_text']}".lower()
            and doc.get("is_live")
        ]
        return {"hits": hits, "estimatedTotalHits": len(hits), "query": query}


class FakeEngine:
    def __init__(self):
        self.documents: dict = {}
        self.settings: dict = {}
        self.down = False
        self.swaps: list = []

    def create_index(self, name, options=None):
        self.documents.setdefault(name, {})

    def index(self, name):
        return FakeIndex(self, name)

    def delete_index(self, name):
        self.documents.pop(name, None)

    def swap_indexes(self, pairs):
        for pair in pairs:
            a, b = pair["indexes"]
            self.documents[a], self.documents[b] = (
                self.documents.get(b, {}),
                self.documents.get(a, {}),
            )
            self.swaps.append((a, b))

    def generate_tenant_token(self, **kwargs):
        return "tenant.token.signed"


@pytest.fixture
def engine(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(client, "get_client", lambda: fake)
    return fake


@pytest.fixture
def live_article(article_factory, default_site):
    article = article_factory(status="published", is_live=True, title="Attention is all")
    article.plain_text = "The decoder learns to weigh every source token."
    article.save()
    return article


class TestIndexing:
    def test_a_live_article_is_indexed(self, engine, live_article):
        index_article(live_article.pk)
        store = engine.documents[client.index_name(live_article.site_id)]
        assert store[live_article.pk]["title"] == "Attention is all"

    def test_annotation_prose_is_searchable(self, engine, article_factory, default_site):
        from apps.articles.models import Article

        article = article_factory(
            status="published",
            is_live=True,
            title="Neural translation",
            content={
                "blocks": [
                    {
                        "type": "interactive_text",
                        "data": {
                            "text": "Visible body.",
                            "annotations": [
                                {
                                    "id": "a1",
                                    "modal_title": "How attention works",
                                    "modal_content": "<p>যান্ত্রিক অনুবাদ explained</p>",
                                }
                            ],
                        },
                    }
                ]
            },
        )
        index_article(article.pk)
        document = engine.documents[client.index_name(article.site_id)][article.pk]
        # The whole reason plain_text includes annotation text: on this platform
        # a large share of the substance lives inside annotations, and a search
        # that cannot see it misses most of the article.
        assert "যান্ত্রিক" in document["plain_text"]

    def test_a_draft_is_removed_rather_than_skipped(self, engine, live_article):
        index_article(live_article.pk)
        # `is_live` is derived from `status` in Article.save(), so setting it
        # directly is silently undone -- the status is the thing to change.
        live_article.status = "draft"
        live_article.save()
        index_article(live_article.pk)
        # Skipping would leave an unpublished article findable, which is the
        # more dangerous half of the same bug.
        assert live_article.pk not in engine.documents[
            client.index_name(live_article.site_id)
        ]

    def test_indexing_records_the_content_hash(self, engine, live_article):
        index_article(live_article.pk)
        log = IndexingLog.unscoped.get(article_pk=live_article.pk, action="upsert")
        assert log.state == "indexed"
        assert log.content_hash == live_article.content_hash


class TestFailsSoft:
    def test_an_outage_does_not_break_saving(self, engine, article_factory):
        engine.down = True
        # The property the whole design turns on: publishing must not depend on
        # a separate process being up.
        article = article_factory(status="published", is_live=True)
        index_article(article.pk)
        log = IndexingLog.unscoped.get(article_pk=article.pk, action="upsert")
        assert log.state == "failed"

    def test_an_unconfigured_engine_returns_empty_results(self, monkeypatch):
        monkeypatch.setattr(client, "get_client", lambda: None)
        result = client.search(1, "anything")
        # `available: False`, not zero hits. "Search is down" and "nothing
        # matched" are very different messages to a reader.
        assert result["available"] is False
        assert result["hits"] == []

    def test_search_survives_the_engine_falling_over(self, engine):
        engine.down = True
        assert client.search(1, "anything")["available"] is False


class TestDriftRepair:
    def test_a_failed_index_is_retried_when_the_engine_returns(
        self, engine, article_factory
    ):
        engine.down = True
        article = article_factory(status="published", is_live=True)
        index_article(article.pk)
        assert IndexingLog.unscoped.get(article_pk=article.pk).state == "failed"

        engine.down = False
        repair_drift()

        assert IndexingLog.unscoped.get(article_pk=article.pk).state == "indexed"
        assert article.pk in engine.documents[client.index_name(article.site_id)]

    def test_a_stale_entry_is_reindexed(self, engine, live_article):
        index_article(live_article.pk)
        # Indexed successfully, then edited with the reindex lost -- the second
        # kind of drift, invisible without the recorded hash.
        live_article.title = "Rewritten headline"
        live_article.save()
        IndexingLog.unscoped.filter(article_pk=live_article.pk).update(
            content_hash="stale"
        )

        result = repair_drift()

        assert result["stale"] >= 1
        document = engine.documents[client.index_name(live_article.site_id)][
            live_article.pk
        ]
        assert document["title"] == "Rewritten headline"

    def test_a_never_indexed_article_is_picked_up(self, engine, article_factory):
        article = article_factory(status="published", is_live=True)
        IndexingLog.unscoped.all().delete()
        engine.documents.clear()

        result = repair_drift()

        assert result["unindexed"] >= 1
        assert article.pk in engine.documents[client.index_name(article.site_id)]


class TestRebuild:
    def test_the_old_index_serves_until_the_swap(self, engine, live_article):
        index_article(live_article.pk)
        target = client.index_name(live_article.site_id)
        assert engine.documents[target]

        rebuild_index(live_article.site_id)

        # A clear-then-refill would leave the site looking empty for the whole
        # rebuild; the swap has no such window.
        assert engine.swaps
        assert live_article.pk in engine.documents[target]

    def test_the_scratch_index_is_cleaned_up(self, engine, live_article):
        rebuild_index(live_article.site_id)
        scratch = f"{client.index_name(live_article.site_id)}_rebuild"
        assert scratch not in engine.documents

    def test_drafts_are_not_rebuilt_into_the_index(
        self, engine, article_factory, live_article
    ):
        draft = article_factory(status="draft")
        rebuild_index(live_article.site_id)
        store = engine.documents[client.index_name(live_article.site_id)]
        assert draft.pk not in store


class TestPublicAPI:
    def test_search_finds_a_phrase_only_inside_an_annotation(
        self, engine, public_client, article_factory
    ):
        article = article_factory(
            status="published",
            is_live=True,
            title="Machine translation",
            content={
                "blocks": [
                    {
                        "type": "interactive_text",
                        "data": {
                            "text": "Body text.",
                            "annotations": [
                                {
                                    "id": "a1",
                                    "modal_title": "Note",
                                    "modal_content": "<p>beam search decoding</p>",
                                }
                            ],
                        },
                    }
                ]
            },
        )
        index_article(article.pk)

        body = public_client().get(f"{PUBLIC}/search/?q=beam search decoding").json()
        assert body["total"] == 1
        assert body["hits"][0]["title"] == "Machine translation"

    def test_an_empty_query_returns_nothing_without_calling_the_engine(
        self, engine, public_client
    ):
        body = public_client().get(f"{PUBLIC}/search/?q=").json()
        assert body["hits"] == [] and body["available"] is True

    def test_a_tenant_token_is_scoped_and_minted(self, engine, public_client):
        body = public_client().get(f"{PUBLIC}/search/token/").json()
        assert body["token"] == "tenant.token.signed"
        assert body["index"].startswith("articles_")

    def test_rebuild_requires_an_owner(
        self, auth_client, author, membership_factory, default_site
    ):
        membership_factory(author, default_site, role="editor")
        assert auth_client(author).post(f"{BASE}/search/rebuild/").status_code == 403

    def test_health_reports_the_index_state(self, engine, auth_client, admin, live_article):
        index_article(live_article.pk)
        body = auth_client(admin).get(f"{BASE}/search/health/").json()
        assert body["available"] is True
        assert body["indexed"] >= 1
