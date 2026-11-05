---
description: Run the brain's lint (mechanical with safe fixes, grounding check, LLM judgment report)
allowed-tools: Bash, Read, Glob, Grep, Skill
---

Load the `brain` skill and run its **Lint** procedure. Commit safe fixes
(if any) with `-m "lint: safe fixes"`; present all other findings as a list
with page links. Never fix facts automatically. Scope: `$ARGUMENTS` (empty
= the whole wiki).
