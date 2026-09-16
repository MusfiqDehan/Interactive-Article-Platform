# 7. `<details>` appendix for annotation SEO

**Status:** Accepted · **Phase:** 2

## Context

The product's differentiator is interactive annotations. Its implementation was
`if (!isOpen) return null` — so annotation bodies were **absent from the DOM
entirely** until clicked. On an article where 40% of the substance lives in
annotations, a crawler saw 60%; and since pages were client-rendered, closer to
0%.

## Decision

Server-render every annotation into a native `<details>` disclosure in an
anchored "Notes & annotations" appendix, then progressively enhance to the
modal on hydration.

## Alternatives rejected

- **`<template>`** — inert by specification and explicitly not indexed.
- **`<noscript>`** — largely ignored, and duplicating body content there is a
  cloaking signal.
- **`display:none`** — indexed, but discounted, and it is the pattern search
  engines specifically look for.
- **`.sr-only`** — abuses a screen-reader affordance and leaves no-JS readers
  with nothing.

`<details>` is fully indexed under mobile-first indexing, native, keyboard
accessible, works with zero JavaScript, and is semantically *exactly* what an
annotation is.

## The cloaking question

Identical HTML is served to Googlebot and to readers. The client island hides
the disclosure **on hydration**, which is a progressive enhancement, not a
substitution. Nothing is served conditionally on user agent.

## Consequences

- Annotations became deep-linkable (`#annotation-x`), and print and no-JS
  reading got genuinely better as a side effect.
- `plain_text` now includes annotation prose, so `word_count`, `reading_time`,
  keyword density and the search index all stopped under-counting interactive
  articles.
- That last point is why a phrase appearing **only** inside an annotation is
  findable in search — see ADR 2.
