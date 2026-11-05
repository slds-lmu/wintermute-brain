---
type: page
title: "Wintermute brain"
description: "Project page for the SLDS brain repo (wintermute-brain): design and operations decisions."
aliases: [wintermute-brain, brain repo]
tags: [project, brain, decision]
---

Project repo: git@github.com:slds-lmu/wintermute-brain.git. It implements the [LLM Wiki](/wiki/page/llm-wiki.md) pattern for the group.

## Operations decisions

Members' machines run Claude Code with the brain plugin (commands, session hooks, digest agent); the GPU server runs the compile worker, qmd, PDF conversion, and later the Mattermost bot; GitHub is the gate and the record [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Search: qmd runs centrally on the server, not on each member's machine. If it is unreachable, agents fall back to the indexes plus grep on the local clone. Access is per person: only people with read access to the brain repo may query it, checked against their GitHub token through an auth proxy; the owner rejected a shared token [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Distribution: the brain ships as a Claude Code plugin from the wintermute marketplace, declared in each project repo's committed `.claude/settings.json`. gitleaks must scan before anything leaves the machine [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Server: the worker polls every 5 minutes (pull, compile new raw items, re-index qmd), so no inbound access is needed. It authenticates as a GitHub App installed on the brain repo only, with short-lived tokens. Members use their own Claude accounts; the server uses a group Anthropic API key with a monthly spending limit, to be set after measuring the first weeks [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Storage: PDFs stay in git LFS; member clones skip LFS downloads and only the server fetches PDFs. Backups are GitHub only, plus branch protection on `main` (planned; the ruleset is deferred, see Merge method); an off-GitHub backup is parked as priority K30 [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Retrieval and commands: search is hybrid from the MVP, not keyword-only first, because session digests are worded differently from later questions. Answers use both wiki pages and raw sources and say which parts come from which. The `wiki/page/` index is split by first letter. Commands are `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint`. Querying works from any repo with the plugin through the server's qmd; a local clone is optional (offline fallback, editing), while ingest and edit use a local working copy [Brain MVP digest](/wiki/source/src-20261105-wintermute-brain-brain-mvp-retrieval-and-comman-98411f.md).

## Build vs. reuse and contradictions

The owner accepted the plan to fork `Astro-Han/karpathy-llm-wiki` with qmd and plain git/Markdown; no existing product qualifies as the base. AnythingLLM keeps its data in SQLite/LanceDB, not in git; arkon has no git export and its PolyForm Internal Use licence rules out a fork in `slds-lmu`; nashsu/llm_wiki is GPL-3.0 and auto-ingests on every machine that pulls a shared repo. Team-wiki products have no AI that maintains the wiki. Ideas may be borrowed from arkon and nashsu/llm_wiki, nothing more [Build vs. reuse digest](/wiki/source/src-20261105-wintermute-brain-build-vs-reuse-settled-fork-as-98411f.md).

There is no v0 spike and no retrieval-only baseline (owner decision, 2026-11-05): the first real check is the MVP done-criterion in `00-requirements.md` §7 [Build vs. reuse digest](/wiki/source/src-20261105-wintermute-brain-build-vs-reuse-settled-fork-as-98411f.md).

Changed facts are overwritten in place and git keeps the old version (R5). Real disagreements get a `Status: Disputed` blockquote with both sources cited; lint lists them but does not hunt for contradictions. `Status: Outdated` was dropped because it conflicts with edit-in-place [Build vs. reuse digest](/wiki/source/src-20261105-wintermute-brain-build-vs-reuse-settled-fork-as-98411f.md). Research ideas not needed for v1 go into `specs/parked.md` [Build vs. reuse digest](/wiki/source/src-20261105-wintermute-brain-build-vs-reuse-settled-fork-as-98411f.md).

## Reporting and commit identity

No report files in the repo: failures of unattended operations and scheduled lint runs go to one standing GitHub issue, "Brain health", with one comment per event. A Mattermost ping mirror is parked as K29 [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Agent commits use a dedicated author per agent kind (e.g. `brain-agent-compile`), listed in `agents.txt`; every other author counts as human, and the triggering human goes into an `Invoked-by:` trailer [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

## Merge method

The owner chose rebase-and-merge as a trial, to keep one commit per operation in a linear history; merge commits are the fallback [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Nobody pushes directly to `main`, humans included; everyone uses PRs. The only exception is the index Action, which needs the brain GitHub App (not created yet). The ruleset was first deferred [Brain MVP digest](/wiki/source/src-20261105-wintermute-brain-brain-mvp-retrieval-and-comman-98411f.md); it is now active, and the brain GitHub App is its only bypass actor: the index Action mints an App token per run from two repo secrets. Repository admins can still push directly to `main`, accepted during the test phase; before wider use this should become "pull requests only" or be removed (parked as K31) [First live test digest](/wiki/source/src-20261105-wintermute-brain-first-live-brain-test-commit-o-98411f.md).

## Implementation status

Marc's PR #1 (`d0cd9e1`) implemented the MVP from specs 00–06; 38 tests pass and lint reports 0 errors and 0 warnings. The `check` and `index` workflows ran green on GitHub. Not done: branch protection or ruleset, the GitHub App, qmd pinning, and a real-transcript test of the session hook [Brain MVP digest](/wiki/source/src-20261105-wintermute-brain-brain-mvp-retrieval-and-comman-98411f.md).

## First live test

Two live ingests on 2026-11-05 passed (PRs #2 and #4 merged). `commit-op` first reported a merged PR as failed because the `slds-write` token gets 403 on check runs; it now uses the PR state plus the Actions workflow run, waits 10 minutes, and returns exit code 4 ("outcome unknown") without closing the PR, so agents must not redo the operation. Members and the server clone over HTTPS; the host's shared clone stays on SSH, because changing its remote broke the host's pushes. Open gap: no check covers `source.yaml` metadata, after an author's full name was filled in from memory. Members need gitleaks and defuddle (to be added to the slds docker image) [First live test digest](/wiki/source/src-20261105-wintermute-brain-first-live-brain-test-commit-o-98411f.md).

## GitHub tokens

A fine-grained PAT has one resource owner, so each owner needs its own token. Tokens live in `~/.gh-tokens/<name>` and are mounted read-only into yolobox; `ghr <name> …` and `gitr <name> …` run `gh` or `git` with that token. For this repo a token needs Actions read; `slds-write` is scoped to this repo [Brain MVP digest](/wiki/source/src-20261105-wintermute-brain-brain-mvp-retrieval-and-comman-98411f.md).

## Open checks

LFS limits of the `slds-lmu` plan, GitHub Actions minutes for a private repo, and who administers the server worker and the API key [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md). Also open: the PDF converter benchmark, qmd at scale, and the Obsidian link check [Brain MVP digest](/wiki/source/src-20261105-wintermute-brain-brain-mvp-retrieval-and-comman-98411f.md). Still open: qmd keyword search from the start versus grep-only wording, and cleanup of stale spec text [Build vs. reuse digest](/wiki/source/src-20261105-wintermute-brain-build-vs-reuse-settled-fork-as-98411f.md).
