---
type: page
title: "LLM Wiki"
description: "Pattern where an LLM compiles raw sources into a maintained, interlinked Markdown wiki; the basis of this brain."
aliases: [llm-wiki, karpathy wiki]
tags: [concept, knowledge-management, agents]
---

## Definition

An LLM wiki is a knowledge base in which an LLM incrementally compiles
immutable raw sources into a persistent, interlinked collection of
Markdown pages that it writes and maintains; humans curate sources and ask
questions [LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

## How it differs from RAG

In RAG the LLM retrieves chunks from raw documents at query time and
rediscovers knowledge on every question. In an LLM wiki the knowledge is
compiled once at ingest and kept current, so cross-references and flagged
contradictions already exist when a question is asked
[LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

## Structure and operations

The pattern has three layers (raw sources, wiki, schema) and three
operations (ingest, query, lint). An index file is read first on every
query; Karpathy reports this works "at moderate scale (~100 sources,
~hundreds of pages)", after which proper search such as qmd helps
[LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

## Extensions from practice

LLM Wiki v2 keeps the three layers and three operations and adds what
its author found missing when running the pattern at scale: a memory
lifecycle (confidence scores, supersession, forgetting, consolidation
tiers), a typed knowledge graph on top of the pages, hybrid search, and
event-driven automation such as compressing each session into
observations at session end
[LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).

It puts the limit of a single `index.md` at "maybe 100-200 pages",
consistent with the original's "moderate scale"
[LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md),
[LLM Wiki](/wiki/source/src-20261105-karpathy-llm-wiki.md).

For multiple agents it proposes "Last-write-wins" for most cases, with
timestamp-based resolution and manual override for conflicts
[LLM Wiki v2](/wiki/source/src-20261105-rohitg00-llm-wiki-v2.md).

## Related

The SLDS brain implements this pattern for a research group, with
multi-writer git workflow, minimal page types and automatic session
digests; see the repo's `specs/`. It deliberately does not adopt numeric
confidence scores, forgetting curves or last-write-wins (see
`specs/proposals.md`, "Avoid").
