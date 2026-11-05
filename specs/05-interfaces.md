# 05 — Interfaces

Status: **accepted** (owner, 2026-11-05; implemented, see `implementation-status.md`)
Owner: Bernd Bischl
Last updated: 2026-11-05
Depends on: `00-requirements.md` R17, `02-ingest.md`, `06-ops.md`

How people use the brain. Open questions are marked **[U#]**.

## 1. MVP

| Interface | Who | What | Writes |
|---|---|---|---|
| **Claude Code + brain plugin** | members | ingest, query, lint, edit by command; works from any repo that has the plugin (06 § 2) | per 03 § 0 |
| **Session hooks** | automatic, in opted-in repos | digest after work sessions (02 § 2) | `raw/` only |
| **GitHub web view** | everyone with repo access | read pages; links work (root-absolute, 01 § 6); PRs and the "Brain health" issue | humans may edit |
| **Obsidian** | optional | read and edit the clone as a vault (settings in 01 § 6) | humans may edit |
| **Any editor** | optional | plain Markdown | humans may edit |

## 2. Commands

Provided by the plugin (names decided 2026-11-05, U1).

| Command | Does | `raw/` | `wiki/` |
|---|---|---|---|
| `/brain-ingest <url \| doi \| arXiv id \| file>` | ingest one source (03 § 3) | new item | writes |
| `/brain-ask <question>` (or just ask) | query (03 § 4) | nothing | nothing |
| `/brain-edit <request>` | change pages on a human's request | nothing | writes |
| `/brain-lint` | run lint, show findings (03 § 5) | nothing | safe fixes only |

## 3. Later

- **Mattermost bot** (R17): query and ingest from channels and DMs.
  Answers only from tiers that the asker and the channel may see.
- **Mattermost pings** for brain health (`parked.md` K29).
- **Web viewer** with login and search (`parked.md` K16).
- **Recorded meetings** as a source (`parked.md` K28).

## 4. Decisions

| # | Question | Decision |
|---|---|---|
| U1 | ~~Command names~~ | **decided 2026-11-05:** `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint` |
| U2 | ~~Query from any repo without a brain clone?~~ | **decided 2026-11-05: yes.** Search *and* page reads go through the server's qmd (MCP). A local clone is optional: needed only for the grep fallback, for editing by hand, and for `/brain-ingest` / `/brain-edit` (they work in a worktree, 03 § 2). Session digests need no clone (02 § 2.4) |
