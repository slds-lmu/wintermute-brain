# Parked ideas

Status: **parking lot, nothing decided.**
Last updated: 2026-11-05

Ideas from research that are not needed for v1. They are kept here so
they don't get lost. **Revisit after v1 or v2** is running: re-check
each one against real usage, then accept it (move it into a spec),
reject it, or keep it parked.

Each row names its origin (a report in `specs/research/`) and the spec
it would affect. Add new parked ideas here, not in other files.

Ideas already marked DEFERRED in `proposals.md` (M4, M5 `verified`,
M6, M7) stay there for now.

## Priority items

Look at these first when v1 runs.

| # | Idea | Origin | Affects |
|---|---|---|---|
| K17 | **PRIORITY. Workflow to resolve disputes.** `Status: Disputed` blocks are visible (01 § 6), so they need an owner and a path to resolution, or they pile up. Open points: who gets notified (page owner, a person linked from the page); how a human resolves one (edit the page, file an `audit/` item, comment in Mattermost); whether an agent may propose a resolution (e.g. a newer or stronger source); how resolution is recorded (commit message); and a lint report of disputes older than N weeks | owner, 2026-11-05 | 01 § 6, 03 lint, P7 |

| K27 | **PRIORITY. Personal-data policy.** For now (test phase) humans decide what gets ingested, with no policy. Before wider use: what may be ingested; how deletion requests (GDPR) are handled; how data is removed from git history, LFS and backups (painful, gets worse with time); whether sensitive raw sources stay out of git | owner, 2026-11-05; 00 § 8 | 00, 02, 06 |
| K28 | **PRIORITY (very high). Recorded oral meetings as a source.** Record → transcribe with timestamps (e.g. whisperX on the GPU server, proposals I15) → raw `meeting` item → `meeting` page with decisions and action items, citing transcript timestamps. Open: consent of participants, what is kept (audio or only the transcript), K27 personal data | owner, 2026-11-05 | 00 R12, 02, 06 |
| K30 | **PRIORITY. Backup outside GitHub.** For now GitHub only, plus branch protection on `main`. Candidate: the server keeps a full mirror (incl. all LFS files) on a disk covered by the university backup; it already pulls every 5 minutes | owner, 2026-11-05 (06-Q8) | 06 |
| K31 | **Enforce "nobody pushes directly to `main`" for admins.** The ruleset still lets repository admins bypass (direct pushes skip lint and the concurrency precondition). Lenient during the test phase (owner, 2026-11-05). Before wider use: switch the admin bypass to "pull requests only" (escape hatch for a broken check) or remove it | owner, 2026-11-05; live test problem 3 | 03 § 2.1 |

## From the O3 decision (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K29 | **Mattermost pings for brain health.** Mirror the "Brain health" GitHub issue (lint reports, failed operations) to Mattermost, so people get pinged where they already talk; ideally the person concerned (e.g. the one whose session or page is affected) gets a direct ping. Needs the Mattermost bot (00 R17) | owner, 2026-11-05 | 03 § 5.3, 05 |
| K32 | **DECIDED (2026-11-05), see 01 § 1: code repo `wintermute-brain` + content repo `wintermute-brain-content-slds`; schema with the content; pinned code version; fresh start; no digests of code work. Implementation pending.** **PRIORITY (very high). Separate code from content.** Today brain content (`raw/`, `wiki/`) and code (`tools/`, `plugin/`, `server/`, specs, tests) live in one repo (`wintermute-brain`; implementation decision 1). The owner considers this bad; to be discussed and solved right after the implementation-decision review | owner, 2026-11-05 | 01 § 1–2, 06 |

## From the P7 decision (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K18 | **`audit/` inbox.** People who don't want to edit file a short comment file; an agent applies it. Parked because people can edit directly or tell an agent in chat | lewislulu (A), proposals C9 | 03 |

## From the P8 decision (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K19 | **Revisit IWE** (iwe-org/iwe, schema validation) as soon as our own validator script starts to duplicate what IWE does (richer schemas, section checks, many field rules). Until then: own script | owner, 2026-11-05; proposals L5 | 03 lint |

## From the concurrency batch (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K20 | **Reserve slugs before generating pages**, so parallel agents don't create the same page. Today A2 rejects creating a page that already exists upstream | proposals C4 | 03 |
| K21 | **Partition write rights by role or page type** (e.g. only the meeting agent writes meeting pages). Revisit if duplicates or conflicts show up in practice | proposals C5 | 03 |
| K22 | **Parallel helpers draft, one writer commits.** Only relevant once agents run in parallel | proposals C8 | 03 |

## From the ingest batch (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K23 | **Two independent sources for risky claims.** Needs a workable definition of "risky" first | proposals I7 | 03 ingest |
| K24 | **`retract` operation** for a source that turns out wrong or must be removed (affects all pages citing it) | proposals I8 | 03 |

## From the lint batch (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K25 | **Automatic contradiction hunting** in LLM lint: read sources in random order (L3) and track the contradiction rate as a health metric (L7). Relevant once the dispute workflow (K17) exists | proposals L3, L7 | 03 lint |

## From the query batch (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K26 | **Miss ledger:** record questions the wiki couldn't answer, to show thin coverage (e.g. onboarding). Needs a merge-safe design (no shared append file) | proposals Q4 | 03 query |

## From reports F–H (2026-11-05)

| # | Idea | Origin | Affects |
|---|---|---|---|
| K1 | **MOVED INTO v1 (owner, 2026-11-05; 03 § 3, § 6).** **Reason per edit.** Every write carries a short reason that becomes the commit message | H (Wiki.js 3) | 03 |
| K2 | **Refuse duplicate creates.** Creating a page fails if a page with that title or slug already exists (partly covered by A2) | H (Wiki.js 3) | 03 |
| K3 | **MOVED INTO v1 (owner, 2026-11-05; 03 § 3, § 6).** **Plan before writing.** Ingest first lists the pages it will create or update, then writes them | F (arkon) | 03 ingest |
| K4 | **Chunked analysis of long sources.** Extract claims chunk by chunk with source offsets, then write pages | F (arkon), G (nashsu) | 03 ingest |
| K5 | **Copy structured data verbatim** (tables, schemas, configs) | G (nashsu) | 03 ingest |
| K6 | **Page-worthiness rule.** Only important subjects get their own page; reuse existing page names instead of inventing new ones | G (nashsu) | 03 ingest |
| K7 | **No claim migration.** Never move a claim from one entity's page to another's | G (nashsu) | 03 ingest |
| K8 | **Similarity check before create.** Compare a new page with existing ones using similarity thresholds | F (arkon) | 03, 04 |
| K9 | **LLM duplicate finder.** Scheduled; "not duplicates" decisions are kept in git so they aren't re-flagged | G (nashsu) | 03 lint |
| K10 | **Shrink guard on merges.** Reject a merged page shorter than 70% of the longer input | G (nashsu) | 03 |
| K11 | **Cheap-first lint order:** regex → structure → near-duplicates → LLM | F (arkon) | 03 lint |
| K12 | **Orphaned-sources lint.** Flag pages whose cited sources were all removed | F (arkon) | 03 lint |
| K13 | **Filter false "missing page" findings** in lint | G (nashsu) | 03 lint |
| K14 | **Fixed "not in the wiki" answer** when query finds nothing (fits A1) | F (AnythingLLM) | 03 query |
| K15 | **Search-only sources.** Some sources (e.g. regulations) are indexed for search but not summarised into pages | F (arkon) | 02, 04 |
| K16 | **Web viewer with login and search.** Pull-only Wiki.js 3 on the group server (one site per tier repo; spike first) or Quartz (static). v1 = GitHub + Obsidian | H | 05, R17 |
