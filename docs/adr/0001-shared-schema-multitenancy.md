# 1. Shared-schema multi-tenancy, not schema-per-tenant

**Status:** Accepted · **Phase:** 1

## Context

Content is owned by one site and published to many. Tenants are few (single
digits) and rows are modest (thousands of articles). The alternative on the
table was PostgreSQL schema-per-tenant, which gives isolation by default.

## Decision

One schema. Every tenant-owned table carries a `site` FK, and scoping is
enforced in three overlapping layers:

1. `TenantModel` gives a guarded default manager plus an explicit, greppable
   `unscoped` manager for genuinely cross-tenant work.
2. `TenantScopedAPIView.get_queryset()` is **final** — subclasses override
   `get_base_queryset()` and the base applies the filter. There is no hook in
   which a view author can forget.
3. A pytest fixture inspects executed SQL and fails any query touching a
   tenant table without a `site_id` predicate.

## Why not schema-per-tenant

The product thesis is *one article on many sites*. Schema isolation would make
the three things the product is built around into cross-schema joins:

- `Placement` — which article appears on which site, by definition spanning
  tenants.
- The global media library, shared across sites by design.
- Aggregate analytics across all owned sites.

Each of those would have to be rebuilt as a shared schema *alongside* the
per-tenant ones — so the end state is shared-schema plus schema plumbing, which
is strictly worse than shared-schema alone. At this row count, isolation buys
nothing that the three enforcement layers do not.

## Consequences

- A missing filter is a cross-tenant leak rather than an empty result. Hence
  three layers, not one; the SQL-level assertion is what proves the other two
  actually fired.
- `unscoped` is greppable on purpose. Every use is a place to look during a
  security review.
- If tenant count ever reaches the hundreds, this is the decision to revisit —
  not because of correctness, but because a single `articles` table becomes a
  noisy-neighbour problem.
