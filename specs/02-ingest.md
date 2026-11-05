# 02 — Ingest channels

Status: **accepted** (owner, 2026-11-05; implemented, see `implementation-status.md`)
Owner: Bernd Bischl
Last updated: 2026-11-05
Depends on: `00-requirements.md`, `01-data-model.md`, `03-agent-ops.md`

How material gets into `raw/`, per channel. What the agent does with a
raw item afterwards (triage, pages, citations) is `03-agent-ops.md`
§ 3. Open questions are marked **[I#]**.

## 1. Channels

| Channel | Trigger | Tool | Status |
|---|---|---|---|
| `web` | human: "ingest <url>" | `defuddle` (I10) | MVP |
| `paper` | human: "ingest <doi / arXiv / pdf>" | `slds-paper-litdownload`; PDF converter from the 10-paper benchmark (I11, I12) | MVP |
| `session` | **automatic**, Claude Code hooks in project repos (§ 2) | digest agent | **MVP** (owner, 2026-11-05) |
| `meeting` | recorded oral meetings | transcription with timestamps (e.g. whisperX) | very high priority, later (`parked.md` K28) |
| `mattermost`, `mail`, `doc` | later | see proposals I13, I15 | later |

## 2. Session channel: Claude Code work sessions

Decided 2026-11-05 (owner). Knowledge and decisions are created while
group members work with Claude Code on their projects. They should
reach the brain **automatically, with no human reading or confirming
anything**. The idea is similar to claude-mem, but the target is the
shared wiki.

### 2.1 Setup: once per project repo

A small Claude Code plugin / hook configuration is committed into the
**project repo** (not the brain repo). Everyone who works in that repo
with Claude Code is covered. Projects opt in by adding it. **The brain
repo itself opts in**, so new knowledge from query conversations is
captured (03 § 4).

### 2.2 When digests are made

Session end alone is not reliable: sessions stay open for days,
terminals get closed, machines crash. So digests are made in pieces:

1. **During the session.** After each agent reply, a hook runs a
   cheap check: is there enough new material since the last digest
   (e.g. 20+ turns or 30+ minutes)? If so, it starts a **background**
   digest of only the new part. The user notices nothing.
2. **At the next session start in that repo.** A hook finds older
   sessions of the repo with an undigested tail (closed window, crash)
   and digests it.
3. **At session end**, if the hook fires, flush the last piece. Not
   relied upon.

**Checkpoint without local state.** Each digest's `source.yaml`
records the session id and the message range it covers. "Where did I
stop" is derived from the brain repo, so no local state must survive.

**Accepted gap:** a crashed session's tail in a repo where nobody
starts Claude Code again is never digested. Closing it would need a
scheduled job per machine, which breaks "configured once in the
repo".

### 2.3 What the digest agent keeps

The digest agent reads the new part of the transcript and **decides on
its own**.

- **Default: keep nothing.** Most sessions are routine coding and
  debugging.
- **Keep** what a group member would want to know later:
  - decisions and their rationale;
  - findings and results;
  - failed approaches and why they failed;
  - conventions and how-tos;
  - open questions.
- **Never keep:** code details (git has them), chatter, dead ends
  without a lesson, personal remarks, secrets, and **personal machine or
  tool setup** (someone's tokens, sandbox, shell, editor configuration;
  2026-11-05). Group conventions for tools stay.
- **Mark the assistant's contributions** (owner, 2026-11-05). Only
  what the human said, decided or reported counts as the group's.
  Anything the assistant added on its own (calculations, tests,
  analyses, advice, judgments) is kept only if useful and always marked
  as such on its line ("the assistant's calculation, not checked by the
  group"); never in the title. Live test: an unmarked sign test computed
  by the assistant ended up as a project "result".
- **Never re-ingest the wiki.** Anything that merely restates brain
  pages (e.g. an answer the agent built from the wiki) is skipped;
  only what is new in the conversation is kept: information the human
  added, decisions, corrections. Otherwise the wiki copies itself and
  creates duplicates and circular citations.
- Transcript text is untrusted data (A3), like any source.
- `gitleaks` runs over the digest before it leaves the machine (R15).

Output: a short Markdown digest in English plus `source.yaml`:

```yaml
id: src-20261105-mlr3-tuning-session
channel: session
title: "mlr3tuning: switched default resampling to 5-fold CV"
repo: https://github.com/mlr-org/mlr3tuning
commit: 3f2a9c1           # HEAD at digest time
session: 7b1e…            # Claude Code session id
messages: [412, 538]      # range covered by this digest
person: jane-doe          # who ran the session
retrieved: 2026-11-05
files: [digest.md]
```

The full transcript is **not** stored in the brain; it stays local
with Claude Code. The digest is the raw source.

### 2.4 Transport: raw-only PR, server-side compile

1. **Member's machine:** the digest agent opens a pull request that
   adds **only** `raw/session/<YYYY>/<id>/`. It does this through the
   GitHub API (`gh`), so no local clone of the brain repo is needed
   (05 U2). A new folder per digest
   means these PRs never conflict.
2. **Server (GPU server):** **one** ingest worker processes new raw
   items that have no summary page yet, one at a time and **oldest
   first** (when the item reached the repo, then session and message
   range; 2026-11-05), with the normal
   ingest rules (`03-agent-ops.md` § 3): triage, update the project
   page, cascade, citations, PR with the required check.
3. **The queue is derived:** raw items without a summary page. The
   worker keeps no state of its own.

Why: only the member's machine has the transcript, so the digest is
made there. A single writer compiles the wiki, so this channel causes
almost no conflicts or duplicates (C4, K22). Safety comes from lint,
locks, protected human lines and git revert, not from human review.

### 2.5 Costs and risks

- One extra model call per digest, on the member's account.
- Every participating machine needs a git identity that may open PRs
  on the brain repo (O4 in 03).
- Personal data in digests: see `parked.md` K27 (priority).
- Digest quality can only be judged in use. Safeguard: the LLM lint
  regularly samples digests against the pages built from them.
- Volume: 10–30 people × several sessions a day. The "keep nothing by
  default" rule is what keeps the wiki from flooding.

## 3. Decisions

| # | Question | Decision (owner, 2026-11-05) |
|---|---|---|
| I1 | Session channel in the MVP? | **yes** (00 R12, § 7 updated) |
| I2 | Thresholds for an in-session digest | **20 turns or 30 minutes** to start; tune in use |
| I3 | Model for the digest agent | **a small, cheap model** (Haiku class); escalate only if quality is poor |
