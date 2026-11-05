---
description: Change brain pages on request (fix, merge, deprecate, retag); commits through tools/commit-op
argument-hint: <what to change>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Skill
---

Load the `brain` skill and run its **Edit** procedure for: `$ARGUMENTS`.

Use a fresh worktree, keep citations intact, respect `locked: true` and
human-written lines (pass `--overrides` only with a newer source), and commit
with `tools/commit-op … -m "edit: <what>"`. Report the PR link.
