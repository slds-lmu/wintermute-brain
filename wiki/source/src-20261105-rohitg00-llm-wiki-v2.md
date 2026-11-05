---
type: source
title: "LLM Wiki v2 (rohitg00 gist)"
description: "Extension of Karpathy's LLM Wiki with lessons from production: lifecycle, knowledge graph, hybrid search, automation, multi-agent."
resource: "https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2"
tags: [knowledge-management, agents, llm-wiki]
---

A source page is the summary page of exactly one raw item
(`raw/web/2026/src-20261105-rohitg00-llm-wiki-v2/`).

## Summary

An extension of [Karpathy's LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md)
by the author of agentmemory, a persistent memory engine for AI coding
agents. It keeps the original's core ("stop re-deriving, start compiling")
and adds what the author found "after building and running this pattern
across thousands of sessions"
[LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).

## Key points

- **Memory lifecycle:** confidence scores per fact (e.g. "confidence
  0.85"), explicit supersession of outdated claims, forgetting via a
  retention curve, and consolidation tiers (working, episodic, semantic,
  procedural memory)
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).
- **Knowledge graph:** entity extraction, typed relationships ("uses",
  "depends on", "contradicts", "supersedes") and graph traversal for
  queries, on top of the pages
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).
- **Search:** `index.md` "works up to maybe 100-200 pages"; beyond that,
  hybrid search (BM25, vectors, graph) fused with reciprocal rank fusion
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).
- **Automation:** event hooks on new source, session start and end,
  query, memory write and schedule; at session end, the session is
  compressed into observations and insights are filed
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).
- **Quality and collaboration:** quality scores, self-healing lint,
  proposed contradiction resolution; multi-agent sync with
  "Last-write-wins" for most cases; shared vs. private scoping; filtering
  secrets and PII on ingest; an audit trail
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).
- **Schema:** "the schema document (CLAUDE.md, AGENTS.md) is the most
  important file in the system"; features can be adopted step by step
  from a minimal viable wiki upwards
  [LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).

## Pages updated

- [LLM Wiki](/wiki/page/llm-wiki.md): added extensions from practice and
  a scaling limit for `index.md`.
