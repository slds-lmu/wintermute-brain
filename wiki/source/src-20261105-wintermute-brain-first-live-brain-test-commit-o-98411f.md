---
type: source
title: "First live brain test: commit-op, index Action, HTTPS clones"
description: "Session digest: two live ingests exposed four problems (commit-op outcome, index push, admin bypass, HTTPS clones); fixes and open gaps."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

Two live ingests on 2026-11-05 ran through the full pipeline (PRs #2 and #4 merged). They exposed four problems, which were fixed or parked.

## Key points

- Test 1 (Karpathy's LLM Wiki gist) and test 2 (LLM Wiki v2, update path) passed; the evidence checker caught a non-verbatim quote in test 2.
- `commit-op` reported a merged PR as failed because the `slds-write` token gets 403 on check runs and commit statuses. It now uses the PR state plus the Actions workflow run, waits 10 minutes, and has a new exit code 4 ("outcome unknown"): the PR stays open and the agent must not redo.
- The index Action could not push to `main` under the ruleset; the brain GitHub App is now the only bypass actor, and the workflow mints an App token per run from two repo secrets.
- Parked as K31: repository admins can still push directly to `main`; before wider use the exception should become "pull requests only" or be removed.
- Members and the server clone over HTTPS. The host's shared clone stays on SSH: changing its remote broke the host's pushes until reverted.
- Open gap: the author's full name was filled in from memory although the source gave only a handle; no check covers `source.yaml` metadata (candidate new check).
- Member machines need gitleaks and defuddle; Marc will add them to the slds docker image.
- Temporary `today.md` was folded into `specs/implementation-status.md`; `prior-art.md` §7 got a "Build vs. reuse" section.

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): merge method, implementation status, open checks.
