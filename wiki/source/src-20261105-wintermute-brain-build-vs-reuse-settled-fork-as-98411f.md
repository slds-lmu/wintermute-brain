---
type: source
title: "Build vs. reuse settled: fork Astro-Han, drop the spike, keep Disputed"
description: "Session digest: owner decisions to fork Astro-Han/karpathy-llm-wiki, skip the v0 spike, and use edit-in-place plus Disputed blocks."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

The owner accepted building on a fork of `Astro-Han/karpathy-llm-wiki` with qmd and plain git/Markdown, because no existing product qualified as the base. The v0 spike and retrieval-only baseline were dropped, and the contradiction handling was fixed.

## Key points

- No existing product qualifies: AnythingLLM keeps data outside git, arkon has no git export and a PolyForm Internal Use licence, nashsu/llm_wiki is GPL-3.0 and auto-ingests on every machine, and team-wiki products have no wiki-maintaining AI. Ideas may be borrowed only.
- No v0 spike (owner decision, 2026-11-05): the first real check is the MVP done-criterion in `00-requirements.md` §7.
- Changed facts are overwritten in place (R5); real disagreements get a `Status: Disputed` blockquote with both sources cited; `Status: Outdated` is dropped.
- Parked research ideas go into `specs/parked.md` (K1–K16).
- Still open: 2b (qmd keyword search from the start vs. grep-only) and 2c (stale text cleanup).

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): added build-vs-reuse and contradiction decisions.
