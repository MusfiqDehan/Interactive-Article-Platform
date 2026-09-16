# 2. Meilisearch over Typesense

**Status:** Accepted · **Phase:** 7

## Context

Search has to cover mixed Bengali/Latin content, index documents whose shape
changes every time a block type is added, and be tenant-scoped.

## Decision

Meilisearch, with the browser querying it **directly** using a per-API-key
tenant token.

## Why

**Tenant tokens are the deciding factor.** A Meilisearch tenant token is a
signed JWT carrying a `searchRules` filter. We mint one per API key, hand it to
the browser, and the browser talks to the engine with no Django hop. The scope
is inside the signature, so the token cannot be edited to widen it.

Every alternative puts the application server on the search path. That matters
more here than anywhere else in the system: search is *typed*, so it fires per
keystroke. A hop that is invisible on a page load is very visible at 8
requests per second per user.

Two secondary reasons, both specific to this content:

- **Schemaless.** `document_for()` grows a field whenever a block type is
  added. An engine requiring a declared schema turns that into a migration.
- **Typo tolerance on mixed scripts.** Bengali content is routinely searched in
  transliteration, where an exact-match engine turns one spelling choice into
  zero results.

## Consequences

- Two URLs in settings, not one: the backend reaches the engine over the
  container network, the browser needs a public origin.
- The signing key must be the **search-only** key, never the master key. A
  tenant token derived from the master key is a master key with a filter
  bolted on.
- Everything in `apps/search/client.py` fails soft, and the site keeps
  publishing and rendering when the engine is down. `IndexingLog` plus the
  drift-repair task is what makes that trade honest — otherwise "best effort"
  means "silently wrong forever".
