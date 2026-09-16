# Architecture decision records

One file per decision that was **contested** — where a reasonable engineer
would have picked differently, and where the reasoning is not recoverable from
the code alone. Decisions that are obvious in hindsight are not recorded here;
they are just the code.

Each record states the alternative that was rejected and *what it would have
cost*, because that is the part nobody can reconstruct a year later. "We chose
Meilisearch" is not useful. "We chose Meilisearch because Typesense would have
put Django on the per-keystroke search path" is.

| # | Decision | Status |
|---|---|---|
| [0001](0001-shared-schema-multitenancy.md) | Shared-schema multi-tenancy, not schema-per-tenant | Accepted |
| [0002](0002-meilisearch-over-typesense.md) | Meilisearch over Typesense | Accepted |
| [0003](0003-custom-revisions.md) | A custom `Revision` model, not django-reversion | Accepted |
| [0004](0004-apiviews-not-viewsets.md) | Plain APIViews with explicit URLs, not routers | Accepted |
| [0005](0005-category-tree-adjacency-list.md) | Adjacency list for the category tree, not MPTT | Accepted |
| [0006](0006-social-provider-abstraction.md) | Provider abstraction with the aggregator first | Accepted |
| [0007](0007-details-appendix-for-annotations.md) | `<details>` appendix for annotation SEO | Accepted |
| [0008](0008-buffered-analytics-ingest.md) | Buffer analytics in Redis, never write on the read path | Accepted |
