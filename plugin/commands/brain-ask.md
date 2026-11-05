---
description: Ask the brain a question; answers from the wiki with citations, writes nothing
argument-hint: <question>
allowed-tools: Read, Glob, Grep, Bash(git log:*), Bash(grep:*), Skill
---

Load the `brain` skill and run its **Query** procedure for: `$ARGUMENTS`.

Search index → folder index → `brain-search` (qmd) → read the top pages and
follow links. Answer with `[Title](/wiki/<type>/<slug>.md)` citations, say
which parts come from wiki pages and which from raw sources, and end with
what the wiki does not cover and how recent the newest relevant source is.
Write nothing.
