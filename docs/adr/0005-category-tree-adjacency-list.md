# 5. Adjacency list for the category tree, not MPTT

**Status:** Accepted · **Phase:** 4b

## Context

Categories were two flat levels (`Category` + `SubCategory`). They needed to
become an arbitrary-depth tree.

## Decision

An adjacency list — a `parent` self-FK — plus two denormalised columns:

- `path`: zero-padded **primary keys**, e.g. `0000000003.0000000011`.
  Descendants are one indexed prefix scan.
- `url_path`: **slugs**, e.g. `technology/machine-learning`. What URLs and
  breadcrumbs use.

## Why not django-mptt or treebeard

Both replace the default manager and override `save()`. `Category.save()`
already owns Unicode-slug generation (see `common/slugs.py`, which exists
because Django's `slugify` destroys Bengali), so that logic would have to be
threaded back through their node API. Worse, the `SubCategory` backfill would
have to run row-by-row through `add_child()` instead of one bulk `RunPython`.

The tree is at most four levels and a few hundred nodes per site. A prefix scan
on an indexed column is not merely adequate there — it beats a nested-set read,
which pays for its `O(1)` subtree query with `O(n)` writes.

## Why two path columns

They look redundant and are not. A slug rename must rewrite every descendant's
URL. If descendant *lookup* also went through slugs, the rename would have to
find the rows it is about to change using the values it is changing. Keys are
stable; slugs are not.

## Consequences

- Moving a category returns **which URLs changed**, and the studio immediately
  offers 301s for them. That is the only moment anyone knows the old paths.
- The cycle guard is the load-bearing check. Making a node a child of its own
  descendant is something PostgreSQL accepts happily; the only symptom is an
  entire branch vanishing from the tree with no error anywhere.
- `_rebuild_subtree()` walks children explicitly rather than doing a SQL string
  replace on the prefix. `url_path` segments are Unicode slugs of unbounded
  content, and a substring rewrite would corrupt any descendant whose own slug
  contains the old prefix.
