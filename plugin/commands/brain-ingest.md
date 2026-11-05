---
description: Ingest one source (URL, DOI, arXiv id or file) into the brain
argument-hint: <url | doi | arXiv id | file>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, Skill
---

Load the `brain` skill and run its **Ingest** procedure for exactly this
source: `$ARGUMENTS`.

Work in a fresh operation worktree of `$BRAIN_DIR` (`tools/start-op`), write
the raw item and the pages, run `tools/check_evidence`, and commit with
`tools/commit-op --agent brain-agent-interactive --invoked-by <your person
slug>`. If it is rejected, discard the worktree and redo; after three
failures, stop and report. Finish with: disposition, pages created/updated,
and the PR link.
