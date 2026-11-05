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

Storage: PDFs stay in git LFS; member clones skip LFS downloads and only the server fetches PDFs. Backups are GitHub only, plus branch protection on `main`; an off-GitHub backup is parked as priority K30 [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

## Reporting and commit identity

No report files in the repo: failures of unattended operations and scheduled lint runs go to one standing GitHub issue, "Brain health", with one comment per event. A Mattermost ping mirror is parked as K29 [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

Agent commits use a dedicated author per agent kind (e.g. `brain-agent-compile`), listed in `agents.txt`; every other author counts as human, and the triggering human goes into an `Invoked-by:` trailer [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

## Merge method

The owner chose rebase-and-merge as a trial, to keep one commit per operation in a linear history; merge commits are the fallback [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).

## Open checks

LFS limits of the `slds-lmu` plan, GitHub Actions minutes for a private repo, and who administers the server worker and the API key [Brain design digest](/wiki/source/src-20261105-wintermute-brain-brain-design-lint-reporting-ag-98411f.md).
