---
type: source
title: "LLM Wiki (Karpathy gist)"
description: "Karpathy's idea file: an LLM incrementally compiles raw sources into a persistent, interlinked Markdown wiki."
resource: "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
tags: [knowledge-management, agents, llm-wiki]
---

A source page is the summary page of exactly one raw item
(`raw/web/2026/src-20261105-karpathy-llm-wiki/`).

## Summary

An "idea file" by Andrej Karpathy describing a pattern for personal
knowledge bases: instead of retrieving chunks from raw documents at query
time (RAG), an LLM incrementally builds and maintains a persistent wiki of
Markdown files between the user and the raw sources. The author calls the
wiki "a persistent, compounding artifact"
[LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

## Key points

- **Three layers:** raw sources (immutable, the source of truth), the wiki
  (LLM-generated Markdown the LLM owns entirely), and the schema (e.g.
  CLAUDE.md) that tells the LLM the structure and workflows
  [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).
- **Three operations:** ingest (summarise a source, update index and
  related pages; "A single source might touch 10-15 wiki pages"), query
  (answer with citations; good answers can be filed back as pages) and
  lint (contradictions, stale claims, orphans, missing pages and links)
  [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).
- **Navigation:** `index.md` as a content catalog read first on every
  query, said to work "at moderate scale (~100 sources, ~hundreds of
  pages)", and `log.md` as an append-only timeline
  [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).
- **Tooling:** Obsidian as the viewer ("Obsidian is the IDE; the LLM is
  the programmer; the wiki is the codebase"); qmd suggested as local
  hybrid search once the index stops sufficing; git gives history and
  collaboration [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).
- **Why it works:** maintenance is the burden that makes humans abandon
  wikis; LLMs "can touch 15 files in one pass". The idea is linked to
  Vannevar Bush's Memex (1945)
  [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).
- The document is intentionally abstract and leaves structure and tooling
  to each implementation [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

## Pages updated

- [LLM Wiki](/wiki/page/llm-wiki.md): created.
