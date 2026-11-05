---
description: Ingest one source (URL, DOI, arXiv id or file) into the brain
argument-hint: <url | doi | arXiv id | file>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, Skill
---

Load the `brain` skill and run its **Ingest** procedure for exactly this
source: `$ARGUMENTS`.

Work in a fresh operation worktree of `$BRAIN_DIR` (`$T/start-op`, with `$T`
the plugin's tools folder as the skill explains), write the raw item and the
pages, run `$T/check_evidence`, and commit with
`$T/commit-op --agent brain-agent-interactive --invoked-by <your person
slug>`. If it is rejected, discard the worktree and redo; after three
failures, stop and report. Finish with: disposition, pages created/updated,
and the PR link.
