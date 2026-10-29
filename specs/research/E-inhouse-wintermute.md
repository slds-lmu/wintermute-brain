# Prior art E — in-house: the `wintermute` skills repo

Scope: read-only review of `/home/bischl/cos/wintermute` (local checkout at
`2ed1695`, 2026-07-04; identical to the installed marketplace copy under
`~/.claude/plugins/marketplaces/wintermute`; `git fetch` was **not** run, so
newer upstream commits may exist). Compared against
`specs/00-requirements.md` and `specs/01-data-model.md` (both draft,
2026-10-29).

Line references are `file:line` in the wintermute repo unless prefixed with
`specs/`. `attic/` is excluded: the wintermute `AGENTS.md:19` says not to bring
it up.

---

## 1. Repo overview and maturity

### 1.1 Structure

| Path | What |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace "wintermute" with 4 plugins: `slds-setup-skills`, `slds-paper-skills`, `slds-lecture-skills`, `blitzlesen` |
| `skills/setup/` | `slds-setup-{memory,paper,lecture,rpack}` |
| `skills/paper/` | `slds-paper-{review,idea-assessment,litsearch,litdownload,litbrowse-html}` |
| `skills/lecture/` | `slds-lecture-review`, `slds-lecture-notation/{check,find}` |
| `blitzlesen/` | Python CLI + 3 skills: daily arXiv crawl → parquet → keyword/rerank filter → HTML summary |
| `setup-template/` + `copier.yml` | copier templates (`rpack`, `paper`, `lecture`, `_shared/`) that scaffold and **keep in sync** project config files |
| `infrastructure/` | Notes: service wishlist (`general_notes.md`), the `mewse` Mattermost bot (`mewse.md`) |
| `AGENTS.md`, `DECISIONS.md`, `PLAN.md`, `SCRIPT_AND_CONFIG_STYLE.md`, `TODO.md` | Repo governance docs |

`CLAUDE.md` is a one-line `@AGENTS.md` shim. `README.md` only links to the
GitHub wiki (local clone: `/home/bischl/cos/wintermute.wiki`).

### 1.2 Conventions for writing skills

- **Naming**: every skill is `slds-<area>-<name>`. The wiki says this is for
  namespacing across marketplaces (`wintermute.wiki/Skills-Wintermute.md`).
- **Layout per skill**: `SKILL.md` plus optional `references/` (loaded on
  demand), `scripts/` (stdlib-only Python), `templates/`, and `evals/`
  (`evals.json` in skill-creator format, fixture trees under `evals/files/`,
  a `grade_filechecks.py` grader; run output goes to `evals/workspace/`,
  which is gitignored).
- **Frontmatter** is not uniform. Some skills use `user-invocable: true` plus
  `allowed-tools: '…'` (memory, litsearch, litdownload, litbrowse). Others use
  `tools:` plus `disable-model-invocation: true` (the setup skills for
  paper, lecture and rpack). `TODO.md:7` lists "check invocate-model=T/F for
  every skill" as open.
- **Script and config style** (`SCRIPT_AND_CONFIG_STYLE.md:1-34`): every
  script and config needs a header block, section dividers and inline
  rationale.
- **Governance**: `DECISIONS.md` holds locked ADR-style decisions, `PLAN.md`
  holds open follow-ups, and both are marked "operator does not modify"
  (`AGENTS.md:8-19`).
- **Distribution of shared config**: copier. One root `copier.yml` picks
  `setup-template/<project_type>/`. Shared files are symlinks into
  `_shared/`, and `copier update` does a 3-way merge
  (`DECISIONS.md:304-379`). Project repos enable the marketplace plugin via
  `.claude/settings.json` (`setup-template/paper/.claude/settings.json`).
  `AGENTS.d/*.md` is loaded by a SessionStart hook
  (`setup-template/_shared/hooks/load-agents-d.sh`, `DECISIONS.md:382-390`).

### 1.3 Activity and maturity

- 285 commits, 2026-02-13 → 2026-07-04, about 20 authors. The top committers
  are Bernd Bischl (151 across two identities), Sebastian Fischer (53),
  be-marc (13), Yawei Li (11), Timo Heiß (11) and giuseppec (10).
- Commits per month: Feb 11, Mar 54, Apr 78, May 116, **Jun 12, Jul 14**.
  Activity dropped sharply after May. Most of the June/July work is setup
  config and evals.
- **`slds-setup-memory` is young and has never been used in practice:**
  - It has 2 commits. Philip Boustani created it on 2026-05-26 (`ab869bd`,
    "slds-paper-context-anchor to slds-setup-memory", +1733 lines in one
    commit). be-marc added evals on 2026-06-29 (`9aab645`).
  - Its predecessor `slds-paper-context-anchor` dates from April 2026. The
    GitHub wiki page `Skills-Wintermute.md:62` still describes that old
    skill.
  - No `memory/`, `.context/`, `memory.ignore` or `literature/papers.json`
    exists in any of the ~70 repos under `/home/bischl/cos/`.
  - No copier template wires memory in (`grep memory setup-template` finds
    nothing).
- Conclusion: the conventions are solid (copier, evals, naming), but the
  memory and literature data models are **unvalidated designs, not
  entrenched formats**. Diverging from them is cheap today.

---

## 2. `skills/setup/slds-setup-memory` in detail

### 2.1 Purpose and positioning

This is a **project-local** memory that lives *inside* an existing project repo
(paper, R package, lecture). "The project repository is the source of truth.
Obsidian vaults are optional generated browsing or aggregation targets"
(`SKILL.md:29-30`). It has two layers (`SKILL.md:19-27`):

- `.context/`: a tiny always-loaded layer. `MEMORY.md` has a budget of 2,500
  characters, `USER.md` 500, and `users/<key>.md` 1,500
  (`references/schema.md:55-60`).
- `memory/`: canonical, versioned project memory.

### 2.2 Directory layout (`references/schema.md:8-33`; `scripts/lint_project_memory.py:15-34`)

```
.context/MEMORY.md  .context/USER.md  .context/users/<user-key>.md
memory.ignore                       # gitignore-style; excludes for "contextualize"
memory/
  index.md  log.md  overview.md  scratchpad.md
  repository/index.md  repository/folders/  repository/files/
  sources/  entities/  concepts/  decisions/  experiments/  findings/  analyses/
```

There is **no raw layer**. The project repo's own files are the "raw"
material, and pages point to them via `source_paths`. URL or web sources are
not stored; `allowed-tools` has no WebFetch (`SKILL.md:14`).

### 2.3 Page types and frontmatter

The standard contract is in `references/schema.md:170-194`, and the lint
script enforces the fields in `scripts/lint_project_memory.py:40-49`:
`title, type, status, provenance, canonical_home, source_paths, related,
created, updated`. `tags` is added on most templates.

| type | dir | extra fields | `status` enum | `provenance` enum | body sections |
|---|---|---|---|---|---|
| `source` | `sources/` | `authors, year, venue, ingested` (`templates/source.md:12-15`) | active | source-backed | Summary · Key Findings · Methods · Limitations · Project Relevance · Connections |
| `entity` | `entities/` | `entity_type: author\|institution\|dataset\|method\|model\|software\|other` (`templates/entity.md:11`) | active | source-backed\|human-confirmed\|agent-inferred | Overview · Contributions · Project Relevance · Notes |
| `concept` | `concepts/` | `aliases` | active | 4 values | Definition · How It Works · Project Use · Key Sources · Debates / Open Questions · Related Concepts |
| `decision` | `decisions/` | `date` | proposed\|accepted\|superseded\|rejected | human-confirmed\|agent-inferred | Decision · Context · Rationale · Alternatives Considered · Consequences · Links |
| `experiment` | `experiments/` | `date` | planned\|running\|completed\|failed\|abandoned | experiment-backed | Question · Setup · Result · Interpretation · Follow-Up · Links |
| `finding` | `findings/` | `date`, `finding_type: insight\|caveat\|failure\|open-question` | active\|superseded\|open | 4 values | Finding · Evidence · Implications · Links |
| `analysis` | `analyses/` | `date`, `analysis_type: comparison\|synthesis\|open-question\|query-answer` | active\|superseded\|draft | 4 values | Summary · Content · Sources Used · Follow-Up |
| `repository-file` / `-folder` / `-index` | `repository/…` | `path`, `kind` | active | agent-generated | Role/Purpose · Contents · … |
| `overview`, `scratchpad`, `index`, `log` | `memory/` root | — | active | agent-generated | singleton pages |

Further rules:

- `provenance` is a **page-level** enum. Its values are `source-backed |
  experiment-backed | human-confirmed | agent-inferred`, plus
  `agent-generated` for bookkeeping pages.
- No per-claim citation syntax is defined. The schema only says "Distinguish
  human-confirmed facts, source-backed claims, experiment-backed findings,
  and agent inference. Label or phrase agent inference so it cannot be
  mistaken for evidence" (`references/schema.md:136-138`).
- **Orthogonality**: "one canonical home, links elsewhere"
  (`references/schema.md:131-134`). This is enforced by a `canonical_home:`
  field that holds the page's own path.
- **Links**: `[[slug]]` or `[[slug|Text]]`, lowercase kebab-case slugs
  (`references/schema.md:184-185`). In practice the index uses
  **path-qualified** links, e.g. `[[decisions/license-lgpl]]`
  (`evals/files/clean_memory/memory/index.md:43`). Filenames are *not*
  unique across the tree: `memory/index.md` and `memory/repository/index.md`
  both exist.

### 2.4 Index and log

- **`memory/index.md`** (`templates/index.md:1-95`) is a page with
  frontmatter and **one Markdown table per type**. The column sets differ by
  section, e.g. Sources `| Page | Title | Date | Status | Provenance | Tags |`
  and Decisions `| Page | Status | Date | Provenance |`. There is **no
  one-line summary column** for most types. `SKILL.md:62-63` requires an
  update after every substantive edit.
- **`memory/log.md`** (`templates/log.md:1-32`) is append-only, in
  Karpathy's format: `## [YYYY-MM-DD] <operation> | <title>`. The operations
  are `init, load, contextualize, ingest, capture, query, lint, export,
  edit`. The skill appends to it on every substantive edit
  (`SKILL.md:62-63`, `references/schema.md:168`).
- `overview.md` is an opinionated current synthesis, not a page list
  (`references/schema.md:193`). `scratchpad.md` is a promotion queue for
  uncertain or unclassified notes (`references/schema.md:149-151, 164-165`).

### 2.5 Operations (`SKILL.md:70-196`)

| op | what |
|---|---|
| `init` | Creates `.context/`, `memory/` and `memory.ignore` from templates. Never overwrites. Logs `init`. |
| `load` | Reads `.context`, `index`, `overview`, `repository/index`, `scratchpad` and recent log entries, then returns a state summary. |
| `contextualize` | Maps the non-ignored repo into `memory/repository/` (selectively). |
| `ingest` | Writes `memory/sources/<slug>.md` and updates entities, concepts, findings and overview. "Never invent bibliographic metadata; mark uncertain fields as `unknown` or `TO CHECK`" (`SKILL.md:132-136`). |
| `capture` | Routes a decision, experiment, finding, concept or note to its canonical home (`references/schema.md:140-168`). |
| `query` | Reads `.context` → `index` → relevant pages and answers with links. **Offers** to file the answer as an analysis, finding etc. (`SKILL.md:149-159`). |
| `lint` | Runs the script, then applies safe autofixes. Asks before changing substantive claims (`references/lint.md:73-91`). |
| `export` | Mirrors `memory/` into `<vault>/projects/<name>/` with `.export.json` (`references/export.md:22-55`). |

**Write policy**: the skill asks before overwriting, exposing private data,
duplicating memory or changing substantive claims (`SKILL.md:85-86`,
`references/lint.md:85-91`). **It never commits to git.** There is no
attribution and no tier concept.

### 2.6 Scripts

**`scripts/lint_project_memory.py`** (286 lines, stdlib only):

- **Output**: an `Issue(severity, code, path, message)` record, with
  `--json` and `--strict` flags. Exit code 1 on errors.
- **Checks**:
  - required dirs and files
  - `.context` character budgets
  - `USER.md` pointer validity
  - mandatory ignores
  - frontmatter presence and standard fields (naive line-based key parse,
    no YAML parser: `:84-92`)
  - index coverage, as a **substring test** of `[[stem]]` or the relative
    path inside `index.md` (`:225-226`)
  - broken wikilinks, resolved by stem *or* memory-relative path (`:233-236`)
  - duplicate titles
  - stale `.context` routes
  - **security patterns**: private keys, `api_key|secret|token|password = …`,
    and prompt-injection phrasing (`:50-55`), plus invisible Unicode
    (`:56, 103-104`)
- **Gaps compared to its own `references/lint.md`**:
  - **orphan detection** is listed (`lint.md:49`) but not implemented
  - stem collisions are not checked
  - contradictions, provenance and stale claims are left to the LLM
- Verified: it reports "No issues" on `evals/files/clean_memory` and 5
  warnings on `broken_memory`.

**`scripts/export_project_memory.py`** (159 lines):

- Validates the vault path and project name.
- **Deletes** the target and copies `memory/` contents into
  `<vault>/projects/<name>/` (`:110-114`).
- Optionally adds `.context/MEMORY.md` under `_context/`.
- Writes `.export.json` with `schema_version:
  "slds-chair-vault-project-export/v1"`, `canonical: false` and
  `generated: true`.

**Evals** (`evals/evals.json`, 8 cases) cover init, contextualize, capture
of a decision, **capture with a planted secret and prompt injection** (#4),
lint autofix, export, ingest with missing bibliographic data (#7), and a
query. `evals/grade_filechecks.py` (345 lines) grades from files and re-runs
the lint script.

### 2.7 Notable: the "chair vault" concept

`references/export.md:22-55` defines a **"chair-vault v1 project export
contract"**. The target is `<obsidian-vault>/projects/<project-name>/`, and
the contract states: "Do not create or manage vault-level `bases/`,
`canvases/`, `people/`, `groups/`, or `topics/` … Those are future or manual
chair-vault layers". So wintermute already **anticipates a chair-level
Obsidian vault** that aggregates project memories. That is conceptually the
same thing as `brain-group`, and the two need to be reconciled (§ 5).

---

## 3. Literature skills

### 3.1 `slds-paper-litdownload`

- **Input**: `.bib`, markdown tables, Deep Research output, DOIs or arXiv IDs
  (`SKILL.md:20-32`). Identifier regexes are at `SKILL.md:29-31`.
- **Metadata resolution**: Semantic Scholar → OpenAlex → Crossref → arXiv →
  DBLP, then canonical pages, cross-validated across ≥2 APIs
  (`references/apis.md:6-27`). "Never LLM-infer abstracts, keywords, or
  venues" (`SKILL.md:36`).
- **Dedupe order**: DOI → canonical URL → fuzzy title+author+year. Updates
  are widen-only (`SKILL.md:55-58`, `references/papers-json-schema.md:41-46`).
- **PDF fallback chain**: arXiv → S2 `openAccessPdf` → DOI landing OA →
  bioRxiv, medRxiv or PMC. On total failure it records
  `download_status: "failed: …"` and continues
  (`references/apis.md:37-50`).
- **TeX**: `arxiv.org/e-print/{id}` → extract to `source/`, delete the tar
  (`references/apis.md:52-61`).
- **Non-arXiv PDFs**: nougat → `paper.mmd`, after one user prompt. The
  install path is `pip install nougat-ocr` (`references/nougat-conversion.md:20-27`).
- **BibTeX**: must come only from authoritative online exports (arXiv
  `/bibtex/`, Crossref content negotiation, DBLP, OpenReview, publisher).
  Only the cite-key may be changed (`references/citekey-and-bibtex.md:38-77`).
- **Layout produced** (`SKILL.md:108-119`):
  ```
  references.bib                 # regenerated, sorted by key
  literature/papers.json         # canonical metadata, array, rewritten whole every run
  literature/{citekey}/paper.pdf | source/ | paper.mmd
  ```
- **`papers.json` record** (`references/papers-json-schema.md:8-27`):
  `citation_key, title, authors ["Last, First"], year (int), venue, abstract,
  doi, arxiv_id, canonical_url, keywords[], local_files{pdf,tex_dir,mmd},
  download_status`.
- **Cite-keys** use the form `firstauthorYEARtitleword` (`vaswani2017attention`).
  Collisions get `a, b, …` suffixes (`references/citekey-and-bibtex.md:5-26`).
- **Implementation**: there are **no scripts**. All steps are agent prose
  executed with WebFetch, curl and bibtexparser. The output root is fixed to
  the project root; there is no target-directory parameter.
- **Internal inconsistencies** (minor):
  - `bibtex_status` is used (`citekey-and-bibtex.md:83-84`) but missing from
    the schema.
  - The nougat-declined status is `"ok (no markdown: nougat declined)"` in
    `nougat-conversion.md:27` but `"failed: nougat declined"` in
    `papers-json-schema.md:25-26`.
  - `litsearch/SKILL.md:18` hands off to a non-existent
    `slds-paper-litreport`.

### 3.2 `slds-paper-litsearch`

Topic prompt → multi-query search over the same APIs until results saturate.
It prefers the published version over the preprint and the latest arXiv
version (`SKILL.md:41-59`). It writes one GFM table to
`./literature-search-YYYY-MM-DD-HHMM.md` with the columns `title | authors |
year | venue | links | keywords | abstract` (`SKILL.md:61-96`), then offers a
handoff to litdownload.

### 3.3 `slds-paper-litbrowse-html`

Renders `papers.json` or a litsearch table into one offline HTML file with
embedded JSON (`references/html-template-*.md`, token `__PAPERS_JSON__`).
`scripts/parse_litsearch_md.py` turns the table into JSON.

### 3.4 Other relevant pieces

- **`blitzlesen/`**: daily arXiv crawl into `saved/papers.parquet`, keyed by
  `arxiv_id_base` (`blitzlesen/src/blitzlesen/models.py:13-36`), with a
  relevance filter and an HTML digest. It could become a future ingest feed
  ("relevant new papers → raw/paper").
- **Knowledge management, Mattermost, meetings, notes**: no other skill in
  the repo covers these.
  - `infrastructure/general_notes.md:46,64-65` lists knowledge management,
    a vector DB and Mattermost integration as wishes.
  - `infrastructure/mewse.md` describes an existing agentic Mattermost bot
    "mewse". This is relevant to our open question 00 § 10.1.
  - The sibling repo `/home/bischl/cos/wintermute-mattermost` (not part of
    wintermute) provides the Mattermost MCP server (a bot-token REST client
    with 20 tools). It is the natural base for R12 Mattermost ingest and the
    R17 bot.
- `slds-paper-idea-assessment` mentions meetings only as prep memos. It is
  not relevant.

---

## 4. Conflicts with our data model

Each row is a precise point where adopting wintermute as-is would contradict
`specs/01-data-model.md` (or 00).

### 4.1 slds-setup-memory vs our spec

| # | Topic | slds-setup-memory | Our spec | Severity |
|---|---|---|---|---|
| C1 | Raw layer | None. `source_paths` point at live project files (`templates/source.md:7-8`); URLs are not stored | `raw/<channel>/<YYYY>/<id>/source.yaml` + immutable files (01 § 2 l.39-53, § 4 l.87-112; R2) | high |
| C2 | Root and dir names | `memory/` with **plural** dirs `sources/ entities/ concepts/ decisions/ experiments/ findings/ analyses/ repository/` | `wiki/` with **singular** dirs `hub/ person/ project/ grant/ course/ paper/ method/ concept/ decision/ meeting/ howto/ source/` (01 l.46-49) | medium (naming only) |
| C3 | Page types | `source, entity(entity_type), concept, decision, experiment, finding, analysis, repository-*, overview, scratchpad` | `hub, person, project, grant, course, paper, method, concept, decision, meeting, howto, source` (01 § 5.2 l.145-158) | high (see mapping below) |
| C4 | Paper vs source | One `source` type for papers and everything else, with `authors/year/venue/ingested` | Separate `paper` type (`authors, year, venue, doi, arxiv`) and `source` type (`channel, url`) (01 l.152, 158) | medium |
| C5 | Required frontmatter | `title, type, status, provenance, canonical_home, source_paths, related, created, updated` (lint `:40-49`) | `type, title, summary, aliases, tier, status, superseded_by, created, updated, sources, tags` (01 l.119-131) | high: our pages would fail their lint and vice versa |
| C6 | `summary` | Absent; the index has no summary column for most types | Required, ≤140 chars, copied into `index.md` (01 l.134) | high for the index |
| C7 | `status` enum | Per type: decision `proposed\|accepted\|superseded\|rejected`, experiment `planned\|running\|completed\|failed\|abandoned`, finding `active\|superseded\|open`, analysis `active\|superseded\|draft` | Uniform `draft\|active\|superseded\|archived` plus `superseded_by` (01 l.125-126) | medium |
| C8 | Provenance model | **Page-level** `provenance:` enum (source-backed / experiment-backed / human-confirmed / agent-inferred / agent-generated) | **Per-claim** `[[summary-page]]` citations plus inline `*(inference)*`, `*(hypothesis)*`, `*(opinion: who)*` and callouts. An uncited, unmarked claim is a lint error (01 § 6 l.170-199; R3, R4) | high: different axis. Their enum mixes *evidence type* with *epistemic status* |
| C9 | Source references | `source_paths:` = file paths; `related:` = list | `sources:` = **slugs** of summary pages (01 l.129); related pages are body wikilinks | medium |
| C10 | `canonical_home` | Self-path field | Not needed: location is given by type folder plus repo-unique slug | low (drop it) |
| C11 | Tier | None | `tier:` on every page and source (01 l.124, 102; R13, R14) | high for multi-tier |
| C12 | Link and slug uniqueness | `[[slug]]` **and** `[[dir/slug]]`; duplicate stems allowed (`index.md` ×2); no type prefixes | Filenames unique across the whole repo, bare `[[slug]]`; prefixes `src-`, `mtg-`, `dec-` with dates (01 l.58-60, § 3 l.67-85) | medium |
| C13 | Index format | `memory/index.md` with frontmatter and per-type **tables** (`Page \| Status \| Date \| Provenance …`) | Root `index.md`: `- [[slug]] — <summary>` one line per page, grouped by type; split per type at scale (01 § 7 l.226-250) | medium. Our one-line form is also more merge-friendly |
| C14 | Log | Append-only `memory/log.md`, `## [YYYY-MM-DD] op \| title` | **No `log.md`**: git history with commit convention `ingest(<channel>): <slug>` plus `Source:`, `Pages:`, `Invoked-by:` and `Agent:` trailers (01 § 8 l.252-270, D5) | high: direct contradiction of D5 |
| C15 | Git and attribution | The skill never commits | Every operation is one attributed commit (R18), and the commit *is* the log | high |
| C16 | Autonomy | "Ask first" for substantive claim changes, deletions and reclassification (`references/lint.md:85-91`); query only *offers* to file | Fully autonomous writes, with git revert as the safety net (R10) | medium (policy) |
| C17 | Contradictions and supersession | "Debates / Open Questions" in concepts only; finding status `superseded`; no History section | `## Disagreements` with `> [!conflict]`, `## History` for superseded claims, page `status: superseded` + `superseded_by` (01 § 6 l.201-219) | medium |
| C18 | Obsidian role | The repo is canonical and the vault is a **generated copy**. Export mirror-deletes into `<vault>/projects/<name>/` (`references/export.md:22-55`) | The repo **is** the vault (R17) | high if the export were pointed at brain-group: it would bring in many `index.md`, `log.md`, `overview.md` files (breaks C12 uniqueness), plural dirs and non-conforming frontmatter, and it bypasses ingest, citations and tier checks |
| C19 | `.context/` layer and user profiles | `MEMORY.md`, `USER.md` and `users/<key>.md` with character budgets | Schema lives in `CLAUDE.md`; people are `person` pages (no preferences; evaluations go to the owner tier) | low: not needed in a shared group repo, and per-user preference files are a privacy/tier hazard |
| C20 | Bookkeeping singletons | `overview.md`, `scratchpad.md` | Not in our model. `hub` pages play the overview role; there is no scratchpad | low |

**Page type mapping** (needed if we ever ingest a project's `memory/`):

| Theirs | Ours |
|---|---|
| `source` | `paper` or `source` |
| `entity(author)` | `person` |
| `entity(method\|model)` | `method` |
| `entity(software)` | `project` or `method` |
| `entity(dataset\|institution\|other)` | **no home** |
| `concept` | `concept` |
| `decision` | `decision` (status `accepted` → `active`, `rejected` → `archived`?) |
| `experiment`, `finding` | **no home**. Closest is the project page sections "Outputs / Open items" |
| `analysis` (incl. `query-answer`) | **no home** |
| `overview` | `hub` or `project` |

**Gap in our own spec revealed by this comparison:** R8 says "Good answers can
be filed back as pages", but 01 § 5.2 has no page type for a filed
query answer or synthesis (their `analysis`, with `analysis_type:
comparison|synthesis|query-answer`). UC2 (literature overviews, method
comparisons, related-work drafts) needs one too. Consider adding a `synthesis`
or `analysis` type.

**Internal inconsistency in our own specs:** `specs/00-requirements.md:62-63`
(R6) still says "`index.md` (catalog) and `log.md` (append-only operation
log) are maintained by every operation". `specs/01-data-model.md` D5
(l.252-270, 317) abolishes `log.md`. R6 should be amended to "index.md
+ git-history log per 01 § 8".

### 4.2 Literature skills vs our spec

| # | Topic | litdownload | Our spec |
|---|---|---|---|
| L1 | Storage root | `literature/{citekey}/` + central `literature/papers.json` + root `references.bib` | `raw/paper/<YYYY>/<id>/` + per-item `source.yaml` (01 § 2, § 4) |
| L2 | Metadata store | One JSON array, **rewritten as a whole on every run** (`papers-json-schema.md:47`), plus a regenerated, sorted `references.bib` | Per-source `source.yaml`. Two central files rewritten wholesale would conflict on nearly every concurrent ingest (R19), the same reasoning that dropped `log.md` (D5) |
| L3 | Identifier | Cite-key `vaswani2017attention` (no separators, `a/b` collision suffix) | Slug `vaswani-2017-attention` (kebab, `-2` suffix) (01 l.74, 81-82) |
| L4 | Field names | `citation_key, arxiv_id, canonical_url, keywords, local_files{pdf,tex_dir,mmd}, download_status` | `source.yaml`: `id, channel, title, url, doi, authors, published, retrieved, ingested_by, tier, files`. Page: `doi, arxiv, year, venue` (01 l.92-104, 152) |
| L5 | Author format | `"Last, First"` | `[Andrej Karpathy]` (01 l.98). Pick one and document it |
| L6 | File names | `paper.pdf`, `source/` (TeX tree), `paper.mmd` | `paper.pdf`, `main.tex`, … (01 l.44). Compatible in spirit; `source/` and `paper.mmd` are fine as "original files" |
| L7 | Mutation | Existing entries are extended in place (widen-only) | Nothing in `raw/` changes after ingest; a newer version is a new source (01 l.107-108). Widen-only metadata enrichment would violate immutability unless enrichment lands on the wiki `paper` page, not in `source.yaml` |
| L8 | LFS | Not considered | PDFs in git LFS (D2) |
| L9 | Installs | `pip install nougat-ocr` inline (`nougat-conversion.md:23-24`) | The user's global CLAUDE.md requires manifest-tracked out-of-project installs. A brain ingest pipeline should not shell out to an ad-hoc `pip install` |

---

## 5. What to reuse, and how

### 5.1 Reuse directly (as dependency, invocation, or copied code with attribution)

1. **Copier distribution of the schema across the three tier repos.** 01 § 1
   requires that "All three repos share the same layout and the same schema
   files". Wintermute already solves this for paper, lecture and rpack. Add
   `setup-template/brain/` (CLAUDE.md, `templates/<type>.md`, `tools/`,
   `.claude/settings.json` enabling the brain plugin, the `load-agents-d.sh`
   hook, `.gitattributes` with LFS rules). `copier update` then keeps
   `brain-group`, `brain-leadership` and `brain-owner` in sync with a 3-way
   merge, and tier-specific rules go in `AGENTS.d/`.
   Ref: `DECISIONS.md:304-379`, `copier.yml`.
2. **The paper resolution and download procedure from `slds-paper-litdownload`.**
   This covers identifier regexes, the API cascade, the PDF fallback chain,
   the arXiv e-print TeX download, authoritative BibTeX, and the
   "never infer metadata" rule. It is exactly what R12 (M) "papers (URL,
   arXiv, DOI, PDF)" needs.
   - **MVP**: call it into a scratch dir, then adapt its outputs:
     `literature/{key}/*` → `raw/paper/<YYYY>/<slug>/`, and the
     `papers.json` record → `source.yaml` plus `paper` page frontmatter.
   - **Better, as an upstream PR**: add an output-layout or target parameter,
     or factor the resolver into a stdlib script (e.g. `resolve_paper.py
     <id> → JSON`) that both skills call.
   - Do **not** adopt `papers.json` or `references.bib` as the brain's
     source of truth (L2). A generated `references.bib` or `papers.json`
     export under `tools/` is fine and would make `slds-paper-litbrowse-html`
     work on the brain for free.
3. **Security and prompt-injection patterns and the invisible-Unicode check**
   from `lint_project_memory.py:50-56, 103-104`. These are the seed for the
   R15 secret filter and for lint.
4. **Lint script skeleton**: the `Issue` dataclass, severity ordering,
   `--json` and `--strict`, wikilink extraction regex (`:233`). Fix its
   weaknesses: use a real YAML parse, an exact index-entry match, implement
   orphans, check stem uniqueness, and add our checks (uncited claims, tier
   markers, `summary` ↔ index agreement).
5. **The eval harness pattern**: `evals/evals.json` plus fixture trees plus
   `grade_filechecks.py` that re-runs the deterministic lint. Eval #4
   (secret plus injection during capture) and #7 (no fabricated
   bibliographic data) can be ported almost verbatim as brain ingest evals.
6. **Template body sections**: their `decision.md` sections (Decision ·
   Context · Rationale · Alternatives Considered · Consequences) match our
   decision type almost exactly. Their concept, experiment and finding
   sections are good drafts if we add a synthesis or analysis type.
7. **Wintermute conventions**: `slds-` naming, the
   `references/`, `scripts/`, `templates/`, `evals/` layout, stdlib-only
   Python, `SCRIPT_AND_CONFIG_STYLE.md` headers, and DECISIONS/PLAN docs.
8. **Later channels**: blitzlesen (arXiv feed → paper ingest),
   `wintermute-mattermost` MCP (Mattermost ingest and bot), and the existing
   `mewse` bot (00 § 10.1).

### 5.2 Borrow ideas (not code)

- The capture-routing table (`references/schema.md:140-168`) as a model for
  **session digests** (R12 S): decision → `decision`, result → project page,
  uncertain → hold.
- `memory.ignore` and gitignore-style excludes for ingesting code or doc
  repos.
- The `unknown` / `TO CHECK` convention for missing metadata.
- `overview.md` as an "opinionated current synthesis". This maps onto our
  `hub` pages' Overview section.

### 5.3 Do not reuse

- The `.context/` layer and per-user profiles (C19).
- `log.md` (C14).
- Page-level `provenance:` as a substitute for per-claim citations (C8).
- `canonical_home` (C10).
- Per-type status enums (C7).
- Table-format index (C13).
- The chair-vault export mirror (C18).

---

## 6. Extension, sibling, or independent?

**Recommendation: build the brain as a sibling.** That means separate skills
(e.g. `slds-brain-ingest`, `-query`, `-lint`, or one `slds-brain` skill with
operations) that share wintermute conventions and infrastructure. Do not
extend `slds-setup-memory`.

Why not extend `slds-setup-memory`:

- **The unit differs.** It is memory *inside* a project repo, with the repo
  itself as raw. Ours is a standalone, multi-writer repo per tier with an
  immutable `raw/`. C1, C11, C14, C15 and C16 are architectural
  contradictions, not field renames.
- Merging both into one skill would make `SKILL.md` carry two schemas,
  contradict its own evals (e.g. eval 1 expects `log.md`), and blow the
  ≤500-line guidance.
- Its data model is young and unused (§ 1.3). There is no installed base
  that forces compatibility on us.

Why not fully independent:

- Copier distribution, the litdownload resolver, the security patterns, the
  eval harness and the marketplace plugin wiring are directly reusable.
- Wintermute's `references/export.md:53-55` already reserves a "chair vault"
  with `people/`, `groups/` and `topics/` layers. That **is** our
  `brain-group`. Building independently would create two competing
  chair-level knowledge stores.

How the two should relate (proposal, owner to decide):

1. **Packaging.** Put the brain skills in the wintermute marketplace as a new
   plugin group (`slds-brain-skills`). Put the per-tier repo scaffold in
   `setup-template/brain/`. Alternative: keep the skills in the brain repo
   itself, since 01 says the schema lives in the repo. Copier gives both: the
   source of truth stays in wintermute, and each tier repo carries a
   materialized copy.
2. **Bridge project memory to the brain via an ingest channel, not the
   export.** Add `<channel> = project-memory` (or reuse `doc`). Ingesting a
   project's `memory/decisions/*` and `findings/*` creates `source` pages
   with citations and updates the `project`/`decision` pages in the brain.
   Then deprecate or retarget `slds-setup-memory`'s chair-vault `export`
   (C18), in coordination with Philip Boustani (author) and be-marc (evals).
3. **Align the shared core frontmatter upstream where it is cheap.** Propose
   that `slds-setup-memory` add `summary:` and `aliases:`, adopt the uniform
   status enum plus `superseded_by:`, and accept per-claim
   `[[source-slug]]` citations. Project memories would then ingest with
   little transformation. This is optional and does not block the MVP.
4. **Fix our own specs:**
   - Amend R6 (00 l.62-63) to match D5.
   - Add a `synthesis`/`analysis` page type for filed query answers (R8,
     UC2).
   - Decide the author name format (L5).
   - State that metadata enrichment of papers goes on the wiki `paper` page,
     not in `source.yaml` (L7).
