# Prior art: synthesis

Status: **draft**
Last updated: 2026-11-05
Full reports: `specs/research/A–H` (A–E on 2026-10-29: about 1900 lines,
30+ projects, repos cloned and read, no code executed). Key repos and
licenses were spot-checked with `gh`, and OKF's SPEC.md was read
directly. F–H (2026-11-05) assess AnythingLLM, arkon, nashsu/llm_wiki
and team-wiki products as candidate bases; none qualifies (§ 7). Scale and performance numbers in the reports are
self-reported by their projects unless stated otherwise.

## 1. Bottom line

1. **Nobody has built what we need.** No open-source project combines
   these four properties:
   - a git + Markdown wiki
   - several writers, human and agent
   - confidentiality tiers
   - research-group orientation

   Everything found is single-user, or a team feature bolted onto a
   personal tool. **The concurrency and tier model is ours to design.**
   No documented case of a research group running a shared
   LLM-maintained wiki turned up.
2. **Git + Markdown is the right system of record.** Memory frameworks
   are converging on it: Letta's MemFS, and gbrain's "Markdown in git,
   Postgres as a rebuildable index". The database-centred options
   (Mem0, Zep/Graphiti, Basic Memory) are chat memory, not citable
   synthesis pages. Search gets added later as a **derived, rebuildable
   index** that never owns the data.
3. **Most of the parts exist.** Reuse them:

| What | Use | License | Verdict |
|---|---|---|---|
| `kepano/obsidian-skills` (50k★) | Obsidian syntax, Bases, `defuddle` web→MD | MIT | **not a dependency** (2026-10-29): its `obsidian-markdown` prescribes wikilinks, which conflicts with our links; use the `defuddle` tool directly; `obsidian-bases` optional later |
| `Astro-Han/karpathy-llm-wiki` (2.6k★) | skeleton of our wiki skill + evidence checker | MIT | **fork** |
| Open Knowledge Format v0.2 (Google Cloud) | frontmatter/provenance vocabulary | Apache-2.0 | **adopt + extend** (P1) |
| `PKU-DAIR/AutoSci` (1.7k★) | ML-research ontology, typed edges with evidence, writer rules | MIT | **borrow schema** |
| `tobi/qmd` (31k★) | local hybrid search, CLI + MCP | MIT | **adopted (2026-10-29)** as the search layer: BM25 from the start, hybrid on the GPU server later; grep fallback |
| `iwe-org/iwe` (1.8k★) | schema validation of frontmatter + sections in CI | Apache-2.0 | **evaluate as lint layer** |
| wintermute `slds-paper-litdownload` | paper metadata + arXiv TeX download | in-house | **reuse** (via staging dir) |
| wintermute `setup-template` / Copier | keep 3 tier repos in sync | in-house | **reuse** |
| wintermute `slds-setup-memory` lint + evals | secret/injection checks, eval harness | in-house | **reuse parts** |
| gitleaks | secret filter before writing `raw/` + pre-commit | MIT | **adopt** |

## 2. Ideas to borrow (mapped to our specs)

**Ingest (→ 03-agent-ops)**, mostly from Astro-Han and claude-obsidian:
- **Grounding invariant**: every number, date and quote must appear
  in the source. A script checks this later (Astro-Han's
  `check_evidence.py`, extended to read our `raw/`).
- **Triage before writing**: classify each source as New, Update,
  Disputed or No-material. Skip it if it adds nothing.
- **Cascade updates**: after the main page, search the wiki for other
  pages the source touches.
- **Source text is untrusted data**: it can never carry instructions,
  which defends against prompt injection.
- **One source at a time**, with an explicit change budget.
- **A changed upstream source** becomes a new raw revision, plus a
  `retract` operation (nvk).

**Data model (→ 01)**:
- OKF field names; see P1.
- **Status-type pages** (project, grant, person, decision) use a
  compiled current-state section on top and an **append-only dated
  timeline** below (gbrain). This replaces our `## History` section and
  merges cleanly.
- `generated: {by, at}` (agent) is kept separate from
  `verified: [{by: human:…, at}]`. **Only humans set `verified`**
  (OKF, nvk).
- `stale_after` / `valid_until` mark facts that expire (OKF, Graphiti).
- **Typed relations with an evidence quote** (`builds_on`,
  `challenges`, `contradicts`, `supersedes`) (AutoSci).
- **Risky claims need two independent sources** (claude-obsidian).
- A source-summary page stores the raw content **hash**, so lint can
  detect drift (mcp-llm-wiki).

**Concurrency (→ 03; our own design, informed by)**:
- Each operation runs on its own branch or worktree, then rebases and
  fast-forwards. On conflict the agent **re-reads and redoes the
  operation, never overwrites**, and **LLMs never resolve merge
  conflicts** (claude-obsidian, praneybehl, B report).
- **The real failure is duplicates, not conflicts.** One team reports
  38% near-duplicate pages after parallel ingest. Mitigations:
  - search before every create
  - reserve slugs before generating pages
  - append-only timelines
- **One git identity per agent**, so commits are attributable and
  access can be revoked (mcp-llm-wiki).
- **Merge-safe human corrections**: an `audit/` inbox with one file
  per comment, which agents resolve (lewislulu; idea only, no
  license). Human fixes are stored as **pins** that every later
  regeneration must respect, or the page is marked `locked: true`.
  Otherwise autonomous agents silently undo human fixes (gist
  comments, Basic Memory).

**Lint (→ 03)**, in two layers (cablate, B report):
- **Deterministic, in CI on every push**: schema, broken links,
  orphans, uncited claims, source-hash drift, `stale_after`, index
  consistency, tier violations.
- **LLM, scheduled**: contradictions (sample sources in random
  order), stale claims, near-duplicate pages.
- Tune for precision: under about 15% noise, or people stop reading
  the reports.
- Tests: a known-good fixture wiki plus one broken copy per lint rule
  (nvk).

**Tiers (→ 03/06)**: compile each wiki only from sources at its tier or
below. Enforce "no downward flow" with hooks and CI path checks, not
only prompt instructions. A team that used labels inside one repo
leaked content (B report).

**Retrieval (→ 04)**:
- MVP: index + ripgrep. Grep is not the bottleneck; the context size
  of the index is.
- More than 2000 sources: add `qmd`, with all models local (~2 GB).
  - Index is a SQLite file outside git; a post-merge hook keeps it
    incremental.
  - Default to `qmd search` (BM25, no models needed). Pin the version.
  - Known CPU-only bugs: run the bot's instance on a GPU machine.
- Query order: index → area index → ranked search → read the top 3–5
  pages and follow links. Keep a ledger of unanswered queries.
- Use **no external embeddings API**. Anthropic has none, and Voyage
  would be a third party seeing the text.

## 3. Ingest tooling (→ 02/03)

| Source | Tool | Notes |
|---|---|---|
| Web | `defuddle parse <url> --md` | call the tool directly from our ingest skill (how it is installed on the brain's machines is a deployment question, `06-ops.md`). Fallback: trafilatura. Avoid hosted Jina Reader |
| arXiv | LaTeX source + arXiv HTML → MD | via litdownload. No PDF OCR needed |
| Other PDFs | MinerU 4.x or Marker 2 (balanced) | run a 10-paper benchmark on our own papers first. Heavy torch dependencies → project venv or a conversion box. Replaces nougat (abandoned) |
| Mattermost | own small script on the REST API / existing MCP | no mature tool. Cite as `https://<server>/<team>/pl/<post_id>` |
| Claude sessions | `claude-code-log --format md` + agent distillation | transcripts in `~/.claude/projects/…`, auto-deleted after a cleanup period |
| Google Docs | Drive API export `text/markdown` | cite by revision ID |
| Mail | opt-in `.eml` → markitdown | cite by Message-ID |
| Meetings | whisperX / faster-whisper | timestamped lines so claims can be cited |
| Secrets/PII | gitleaks (all); Presidio (chat/mail/meetings only) | trufflehog: AGPL and sends candidate secrets out to verify them |

## 4. Relationship to wintermute

`slds-setup-memory` overlaps heavily but is barely used: 2 commits,
and no repo under `~/cos` uses it. Its design conflicts with ours on
several points:
- no immutable `raw/`
- page-level provenance only
- an append-only `log.md`
- no commits
- table-style index and plural folder names

**Recommendation:** ship the brain as a **new plugin group in the
wintermute marketplace** that shares wintermute's conventions, not as
an extension of `slds-setup-memory`. Agree with its authors (Philip
Boustani, be-marc) that project memories feed the brain through an
ingest channel, so there are not two competing group knowledge stores.
The existing `mewse` Mattermost bot and the `wintermute-mattermost`
MCP server are candidates for the bot milestone.

## 5. Proposed changes to our specs (need owner decisions)

> **IMPORTANT, REVISIT ASAP.** All P1–P8 are **open**. The owner wants
> to read and discuss the prior art first (2026-10-29) before deciding.
> Nothing here changes 00/01 until decided.
> Leaning so far: P3, a generated per-directory index (owner's first
> answer; confirm after the discussion).

| # | Proposal | Recommendation |
|---|---|---|
| P1 | **DECIDED (2026-10-29): OKF v0.2 field names (`type`, `title`, `description`, `tags`, `status`) + optional `aliases`. Git is provenance (no `generated`, `created`, `updated`). Deferred: `verified` (important), `stale_after`. No `sources` list, no `tier`, no epistemic or contradiction fields.** Base frontmatter on **OKF v0.2**. Rename `summary` → `description`, status `draft\|stable\|deprecated`, add `generated`, `verified`, `stale_after`, `sources[{id, resource, …}]`. Our fields (`tier`, `superseded_by`, epistemic markers) become extensions. OKF requires only `type`, so the cost is renames | **yes**: free interop with IWE, Basic Memory and future tools |
| P2 | **DECIDED (2026-10-29): inline citations as root-absolute Markdown links `[text](/wiki/<type>/<slug>.md)`, no `sources` list.** Per-claim citation syntax: OKF footnote `…claim.[^slug]` whose definition is `[^slug]: [[slug]]` | **yes**: OKF-conformant, and Obsidian backlinks still work |
| P3 | **DECIDED (2026-10-29): generated per-folder indexes (script, OKF § 8).** **Index: reconsider D4.** Three of five reports independently found an agent-edited `index.md` to be the #1 merge hotspot and context sink. Alternative: **per-directory `index.md` (OKF §8), generated by a script** from `description`, run in the same commit as each operation or in CI | **switch to generated per-directory indexes**. Agents still *read* `index.md` first; they just don't hand-edit it |
| P4 | **DECIDED (2026-10-29, v0-foundation accepted; confirmed 2026-11-05 after research F–H).** Implementation base: fork Astro-Han's skill into a wintermute plugin group (kepano/obsidian-skills dropped, 2026-10-29) | yes |
| P5 | **DECIDED (2026-11-05): no ontology. Only indisputable types (person, meeting, paper, grant, source) + untyped `page`; tags for the rest (01 § 5.2).** Ontology: add `idea`, `experiment`, `topic` (AutoSci) and `synthesis` (filed query answers; currently missing for R8/UC2); typed relations with evidence | yes, `synthesis` in the MVP; the others when research ingest starts |
| P6 | **DEFERRED (2026-10-29, see M4).** Status pages: compiled state + append-only timeline instead of `## History` | yes |
| P7 | **DECIDED (2026-11-05): `locked: true` + protected human lines, enforced in `tools/commit-op` and a GitHub check (01 § 5.3); `audit/` inbox parked.** Human-correction channel: `audit/` inbox + `locked`/pins | yes, in the MVP: autonomy without it erodes trust |
| P8 | **DECIDED (2026-11-05): two layers (00 R9); no IWE, own validator script.** Two-layer lint; evaluate IWE as the deterministic validator (we use root-absolute Markdown links, which are OKF-native) | yes |

## 6. Open / unverified

- No independent benchmark of PDF converters on math-heavy ML papers;
  we need our own 10-paper test.
- qmd has no published numbers at 5000+ files; we need a trial on our
  hardware.
- IWE's handling of Obsidian wikilinks is unchecked.
- Star counts of some projects look inflated (A report § 12).
- GPU: **a group GPU server is available** (owner, 2026-10-29). It can
  host PDF conversion (MinerU/Marker) and the bot's qmd instance.

## 7. Build vs. reuse (owner, 2026-11-05)

**Decision: no existing product as the base; the plan stands** (fork of
Astro-Han's skill + qmd + plain git/Markdown). Reports F–H.

What the plan reuses: Claude Code as the agent loop, the Astro-Han skill
(prompts plus one checker), qmd, defuddle, litdownload, gitleaks, OKF
field names. Our own code is a few hundred lines of scripts.

| Candidate | What it is | Why not as the base | Verdict |
|---|---|---|---|
| AnythingLLM (MIT, very active) | chat with your documents (RAG), no wiki | state in SQLite/LanceDB; chunk citations only; roles too coarse for tiers; duplicates qmd | ignore; at most an optional web chat later |
| arkon | close to our design: compiled pages, revisions, roles, MCP | Postgres only, no git or Markdown export; PolyForm Internal Use license (not open source); one author, inactive; per-claim citations promised but not in the code | borrow ideas |
| nashsu/llm_wiki (GPL-3.0) | desktop app for one user | every member's app would re-ingest each pulled source; no headless mode; state in `.llm-wiki/`; wikilinks only; ~92k lines | borrow ideas, in our own words (GPL) |
| Team wikis (Notion, Confluence/Rovo, Glean, Outline, GitBook, Wiki.js, BookStack, Docmost) | humans write, AI answers or drafts | no AI maintains a wiki; only git-backed ones pass "repo is complete", and even Wiki.js 3 drops our OKF fields on web edits | git stays the record; optional viewer later (K16) |
| Memory frameworks (Mem0, Zep, Basic Memory) | chat memory | not citable pages; Basic Memory is AGPL and writes into every file | ignore |

- **Caveat (H report):** if git ever stops being the record, self-hosted
  Outline would beat our plan for a human-edited team wiki. Our plan
  wins because the main writer is the agent, git is the provenance, lint
  runs on files, and qmd searches `raw/` too.
- **Real risk:** our custom parts are the unproven ones: concurrent
  autonomous writers, duplicates, human corrections being overwritten,
  tiers. The open question is whether a compiled wiki beats plain
  retrieval over `raw/`.
- **No spike** (owner): a 15-source test can't show whether the wiki
  helps; only real use by the group can. The MVP done-criterion (00 § 7)
  is the first check (`v0-foundation.md`).
- New ideas from F–H are parked as K1–K16 (`parked.md`).
