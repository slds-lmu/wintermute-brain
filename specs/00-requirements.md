# 00 — Requirements

Status: **draft**
Owner: Bernd Bischl
Last updated: 2026-10-29

## 1. Purpose

A group knowledge base for SLDS / MCML. LLM agents compile it from raw
material into an interlinked Markdown wiki and keep it maintained. The
wiki is the group's long-term memory for research, leadership/orga and
teaching. It is queried by people and agents instead of re-reading
the raw sources each time.

Baseline architecture is Karpathy's LLM Wiki pattern (raw → wiki →
schema; ingest / query / lint). See `CLAUDE.md` § Prior art.

## 2. Users and roles

| Role | Who | Can |
|---|---|---|
| Owner | Bernd | everything, all tiers, schema changes |
| Member | SLDS group members (~10–30; MCML not in scope for now) | read + write (via own agent) in tiers they have access to |
| Agent | Claude Code sessions, Mattermost bot, scheduled jobs | ingest, write, lint, answer within the tier(s) of the invoking context |

Multiple concurrent human and agent writers are expected.

## 3. Scope

In scope: **research**, **leadership / orga**, **teaching**.
Out of scope: private life (no personal/hobby/health/finance content).

## 4. Use cases (v1 must do these well)

- **UC1 — Status lookup.** "What's the state of project/grant X?",
  "Who works on Z?", "What did we decide about Y, and why?"
- **UC2 — Research synthesis.** Literature overviews, method
  comparisons, idea tracking, related-work drafts, all with citations
  back to sources.
- **UC3 — Meeting / decision memory.** Prep for a meeting: past
  discussions, open items, commitments, decisions with rationale.
- **UC4 — Onboarding / group memory.** New members find how things
  work: conventions, infrastructure, who to ask, past decisions.

## 5. Functional requirements

Priority: **M** = must (MVP), **S** = should (post-MVP), **C** = could.

### Content and structure
- **R1 (M)** Plain Markdown in git, Obsidian-compatible (root-absolute Markdown links,
  YAML frontmatter). Pages are written in **English**, whatever the
  source language.
- **R2 (M)** Raw sources are immutable and stored separately from
  agent-written wiki pages.
- **R3 (M)** Every non-trivial claim on a wiki page cites its source(s)
  (raw file, URL, DOI, or a Mattermost permalink).
- **R4 (dropped for v1, 2026-10-29)** No separate epistemic markers.
  The citation is the epistemic status: cited = sourced, uncited =
  not backed. Follows OKF v0.2.
- **R5 (M)** Outdated claims are edited in place, and git keeps the
  history. A replaced page is kept and gets OKF `status: deprecated`.
  *(Contradiction handling was dropped for v1 and supersession extras
  were deferred, both on 2026-10-29; OKF has neither.)*
- **R6 (M)** Every operation regenerates the per-folder `index.md` files (by script) and
  leaves a structured git commit, which serves as the operation log
  (see 01 D4, D5).

### Operations
- **R7 (M)** *Ingest*: a source → summary page plus updates to the
  affected entity/concept pages, index, and log.
- **R8 (M)** *Query*: answer from the wiki with citations. Good answers
  can be filed back as pages.
- **R9 (M)** *Lint*: detect contradictions, stale claims, orphans,
  broken links, missing pages, and tier violations (R14).
- **R10 (M)** Agents may write **fully autonomously**, with no human
  approval gate per change. Safety comes from git: every agent change
  is an attributable commit that can be reverted (R18).
- **R11 (S)** Scheduled unattended ingest and lint jobs.

### Ingest channels
- **R12** Supported sources:
  - (M) web pages and papers (URL, arXiv, DOI, PDF)
  - (S) Mattermost threads and DMs
  - (S) Claude Code / claude.ai session digests
  - (S) mail, Google Docs/Drive, meeting notes and transcripts

### Access and confidentiality
- **R13 (v2/v3; deferred 2026-10-29)** Content is split into three
  **confidentiality tiers**. Each tier is enforced by the hosting
  platform's access control, not by agent discipline alone. Candidate
  mechanism: one repo per tier.

  | Tier | Who | Typical content |
  |---|---|---|
  | `group` | all SLDS members | research, teaching, conventions, how-tos |
  | `leadership` | PIs + admin | grants, budgets, hiring, strategy |
  | `owner` | Bernd only | personnel matters, reviews, student evaluations |
- **R14 (v2/v3, with R13)** No content flows from a higher tier into a
  lower one: no copying, summarising, or linking that reveals it. This
  applies to agents in particular. Lint checks it.
- **R15 (M)** Secrets and credentials are never ingested. An ingest
  filter strips them.
- **R16 (M)** Sending content of any tier to Anthropic cloud models is
  allowed (owner decision, 2026-10-29).

### Interfaces
- **R17** Ways to use it:
  - (M) Obsidian vault: clone the repo and browse it.
  - (M) Ask an agent: Claude Code in the repo answers questions and
    runs operations.
  - (S) Mattermost bot: query and ingest from channels or DMs. It
    answers only from tiers that both the asker and the channel are
    allowed to see.

### Collaboration
- **R18 (M)** Every change is a git commit attributed to the human or
  agent that made it (agent commits name the human who invoked them).
- **R19 (M)** Concurrent writers are supported. Conflicts are resolved
  via git, and page granularity should keep conflicts rare.
- **R20 (M)** The schema (`CLAUDE.md` plus specs) is shared. Changes
  to it go through the owner.

## 6. Non-functional requirements

- **N1** Boring, inspectable formats. No database as the source of truth.
- **N2** Works without custom tooling at MVP scale: `index.md` + grep.
  Expected scale is **>2000 sources in year one**, driven by Mattermost,
  mail and meeting ingest. A flat index won't hold at that size, so
  search is needed. **Decided 2026-10-29: the search layer is qmd**
  (see 01 § 7). It searches everything, wiki pages and raw sources.
  The wiki never depends on it: without qmd, agents use index + grep.
  The layout must allow a hierarchical or sharded index from the
  start.
- **N3** Hosted as private repos in the `slds-lmu` GitHub org, one repo per tier.
- **N4** Built on existing skills and tools where possible rather than
  reinventing them (see `prior-art.md`). The wiki is plain Markdown
  that Obsidian displays well, not an Obsidian-native vault: no
  wikilinks, embeds or callouts. Obsidian is optional.

## 7. MVP (milestone 1)

- A single tier (*group*) in one repo.
- Manual loop: ingest, query and lint run by hand via Claude Code.
- Ingest channel: web pages and papers.
- Interfaces: Obsidian and Claude Code.
- Covers R1–R10, R15, R16, R18–R20.

Done when, after ingesting ~20 real sources, UC1–UC4 can be answered
from the wiki with correct citations, and lint runs clean.

Later milestones (order to be decided):
- more tiers (R13, R14)
- Mattermost ingest and the bot
- session digests
- mail, docs and meetings
- scheduled jobs (R11)
- qmd hybrid mode (`qmd query`) on the GPU server, at the latest with
  the first high-volume channel; the bot uses the same instance (N2)
- **human verification (`verified`, OKF), marked important**: add it
  as soon as the group relies on the wiki (01 § 5.1)

## 8. Risks

- **Autonomy × multi-writer.** Several agents writing unattended can
  degrade pages silently. Mitigations: provenance (R3), lint, git
  revert, and attributable commits.
- **Tier leakage.** An agent that can read a higher tier writes into a
  lower one, or the bot answers in the wrong channel. Mitigations:
  per-tier repos, R14, and channel checks in the bot.
- **Personal data.** Orga content about people (students, staff,
  reviews). R16 allows processing it with cloud LLMs, but retention
  and deletion of personal data in git history still needs a policy.
  Deprioritized by the owner (2026-10-29); not a blocker for any
  planned milestone.
- **Guesses hardening into facts.** R4 was dropped for v1; citations
  (R3) are the only guard. Revisit if lint or users find agent
  inferences passing as facts.

## 9. Decisions (2026-10-29)

- Group = SLDS (~10–30 writers). MCML is a possible later extension.
- Three tiers: `group` / `leadership` / `owner` (R13).
- Scale: >2000 sources in year one (N2).
- Hosting: private repos in the `slds-lmu` GitHub org, one repo per
  tier (N3).
- Initial page types: person, project, grant, paper, method, concept,
  course, decision, meeting, how-to, idea (added 2026-10-29, including
  failed ones). Theses are tracked as projects.
  Details go in `01-data-model.md`.

## 10. Open questions

1. **Mattermost bot**: reuse the existing bot account or create a
   dedicated one? Decide at the bot milestone.
