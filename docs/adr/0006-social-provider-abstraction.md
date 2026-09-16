# 6. Provider abstraction, with the aggregator first

**Status:** Accepted · **Phases:** 6, 8

## Context

Publishing to X, LinkedIn, Facebook and Threads. Going direct means four OAuth
app reviews before anything ships; an aggregator means one integration and a
dependency.

## Decision

Ship the aggregator behind a `SocialProvider` ABC, then add direct providers
later without changing anything above `get_provider()`.

The success criterion, asserted in `test_swapping_the_provider_is_a_data_change`
and `test_direct_providers_add_no_new_concepts`: flipping one
`SocialAccount.provider` value and re-authenticating changes **nothing** in the
composer, the scheduler, or the dispatch task.

## Two decisions that make the swap actually work

**We do not use the aggregator's scheduling.** `SocialPost.scheduled_at` is
honoured by our own beat task, which calls `publish()` at the due moment. The
aggregator offers scheduling and `capabilities()` reports it — and we ignore it.
A direct integration has no scheduling API at all, so leaning on the
aggregator's would mean the semantics silently changed on swap day. That is
exactly the coupling the abstraction exists to prevent, and it is invisible
until it breaks.

**"Not ready" is a typed answer, not an error.** Threads uploads media to a
container and publishes it a moment later. Modelling that as a two-phase method
on the interface would push one platform's quirk onto three providers that do
not have it. Instead the provider raises `ProviderNotReady(retry_after=...)`
carrying its `creation_id`, and the retry resumes the same container. Without
that state, a retry creates a *second* container and the account posts twice.

## Consequences

- The attempt counter does not advance on `ProviderNotReady`. A slow upload
  must not consume the retries meant for real failures.
- Per-platform limits live in one declarative table (`constraints.py`) that is
  **served over the API**, so the composer's counters and the server's
  validation cannot disagree through a stale copy.
- Publishing is per `SocialPostTarget`, not per post. An oversized image on X
  fails that target and leaves LinkedIn published — impossible if a post had a
  single state.
