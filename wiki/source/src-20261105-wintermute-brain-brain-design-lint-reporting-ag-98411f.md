---
type: source
title: "Brain design: lint reporting, agent commit identity, ops decisions Q1–Q9"
description: "Session digest: owner decisions on lint reporting, agent commit identity, merge method and ops questions Q1–Q9 for the brain."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

The owner decided how unattended failures are reported, how agent commits are attributed, and the operating setup of the brain (what runs where, search, distribution, server, cost, large files, backups, access).

## Key points

- Lint and failure reports: no report files in the repo; one standing GitHub issue, "Brain health", with one comment per event.
- Agent commits use a dedicated author per agent kind, listed in `agents.txt`; the triggering human goes into an `Invoked-by:` trailer.
- Merge method: rebase-and-merge as a trial; merge commits are the fallback.
- Server: the worker polls every 5 minutes and authenticates as a GitHub App; qmd runs centrally.
- Open checks: LFS limits of the `slds-lmu` plan, GitHub Actions minutes for a private repo, and who administers the server worker and the API key.

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): created with the design and ops decisions.
