---
type: source
title: "Brain MVP: retrieval and command decisions, no direct pushes to main, token setup"
description: "Session digest: retrieval, command and push-policy decisions for the brain MVP, implementation status, and the per-owner token convention."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

The owner decided on hybrid search from the start, on answers that draw on both wiki pages and raw sources, on the command names, and on a no-direct-push policy for `main`. The digest also records the MVP implementation status and the token convention for `slds-lmu`.

## Key points

- Hybrid search from the MVP, not keyword-only first; the `wiki/page/` index is split by first letter.
- Commands: `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint`.
- Querying works from any repo with the plugin through the server's qmd; a local clone is optional (offline fallback, editing). Ingest and edit use a local working copy.
- Nobody pushes directly to `main`, humans included; the only exception is the index Action, which needs the brain GitHub App (not created yet).
- Status: Marc's PR #1 (`d0cd9e1`) implemented the MVP; 38 tests pass; lint reports 0 errors and 0 warnings. Not done: branch protection or ruleset, the GitHub App, qmd pinning, a real-transcript test of the session hook.
- Tokens: one fine-grained PAT per resource owner, stored in `~/.gh-tokens/<name>`; `ghr` and `gitr` run `gh` and `git` with a named token.

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): added the retrieval, command and push decisions, status and token convention.
