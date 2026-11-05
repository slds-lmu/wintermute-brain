# Prior art G: nashsu/llm_wiki as a candidate base

Research date: 2026-11-05. Scope: judge **nashsu/llm_wiki** as a possible *base* for the brain, not only as a source of ideas. B §1.3 covered it briefly ("single-user, GPL, won't reuse"). This report compares it with the current plan: a fork of the Astro-Han/karpathy-llm-wiki Claude Code skill, plus qmd, plus plain git and Markdown, with many concurrent human and agent writers and Claude Code as the agent (`v0-foundation.md`, `01-data-model.md`).

Method: I shallow-cloned the repo at commit `e08cfce` (2026-10-21, release v0.6.13) into `scratchpad/clones/llm_wiki` and read the code. That covered the ingest pipeline and prompts (`src/lib/ingest.ts`), page merging, the cache, the queue and the file watcher, the state files under `.llm-wiki/`, the Rust HTTP API (`src-tauri/src/api_server.rs`), the MCP server (`mcp-server/`), LLM providers, graph and link parsing, lint, dedup and project creation. I diffed `LICENSE` against the stock GPL-3.0 text. GitHub metadata, releases, contributors and issues come from `gh api` on 2026-11-05. I ran web searches for independent reviews and for team use or forks. **I did not build, install or run the app.** Behaviour described below comes from reading the code. Where I infer runtime behaviour I say so. Claims I could not check are marked **[unverified]**.

File references are `path:line` in the llm_wiki repo at `e08cfce`.

---

## 0. TL;DR

1. **Verdict: borrow ideas. Don't adopt it, don't fork it, and don't recommend it as a viewer.** It is a polished, fast-moving desktop app for one person. Its data model and its operating model both conflict with ours at the root: wikilinks, `log.md`, LLM-maintained aggregates, `created`/`updated` stamps, filename `sources[]`, and app state outside git. It has no git support and no headless mode.
2. **Using it as-is with 10–30 people on a git-synced folder breaks quickly:**
   - Every member's app auto-ingests any new file in `raw/sources/` that arrives through `git pull`. The source watcher is on by default with `autoIngest: true` (`src/lib/source-watch-defaults.json:2-3`). So N machines ingest the same source N times and rewrite shared pages.
   - `wiki/log.md` (append), `wiki/index.md` and `wiki/overview.md` ("Recently Updated" sections) change on every ingest. These are the merge hotspots we already ruled out (01 §7, §8).
   - Locks exist only inside one process (`src/lib/project-mutex.ts`). There is no coordination across machines.
   - Several kinds of state exist only in `.llm-wiki/`: the ingest cache, review items, the "not duplicates" decisions, chats and page backups. If that folder is committed, it becomes a set of JSON conflict hotspots. If it is ignored, each machine has a different view.
   - It cannot run autonomous agents on a server. Ingest is orchestrated in the webview's TypeScript. Headless mode is an open request (#231, #762, #777).
3. **As an optional viewer on our repo it adds little and carries risk.**
   - It refuses to open a folder that has no root `schema.md` (`src-tauri/src/commands/project.rs:350`).
   - Its graph, backlinks, orphan lint and link cleanup only understand `[[wikilinks]]` and the frontmatter `related:` field (`src/lib/wiki-graph.ts:74,114`). On our root-absolute Markdown links the graph would be empty and every page would look orphaned.
   - One stray click on Ingest, Lint-fix or Save-to-Wiki writes the app's conventions into our repo.
   - Obsidian and GitHub already do the viewer job without any of this.
4. **Forking instead of Astro-Han would be far more work.** It is about 92k lines of non-test TypeScript and Rust, compared with a skill plus one checker script. One maintainer wrote 778 of the commits. It releases about every one to two weeks. It is GPL-3.0, and it brings its own LLM pipeline and agent runtime, which compete with Claude Code. We would have to replace the link model, the frontmatter, the aggregates and the write path, then add git and a headless mode. That is a rewrite that would also inherit a GPL licence.
5. **Licence:** the `LICENSE` file is the **verbatim GPL-3.0 text with one line prepended**: `LLM Wiki — Copyright (C) 2024-2026 Yong Su`. There are no extra terms, exceptions or commercial clauses. The prepended line is probably why GitHub reports `NOASSERTION` **[inference]**.
   - Running it or changing it privately carries no obligations.
   - Pages it generates are not covered by the GPL.
   - A distributed fork must stay GPL-3.0.
   - Copying its prompt text verbatim into our MIT skill is risky. Re-express the ideas in our own words.
6. **Ideas worth borrowing, beyond B §1.3** (details in §6):
   - page-worthiness threshold rules for entity pages;
   - subject-boundary rules ("don't transfer claims between entities");
   - canonical-name reuse;
   - verbatim preservation of structured data;
   - merge safeguards: a body-shrink check and locked fields;
   - "a page owned by one source only is replaced on re-ingest, not merged";
   - an LLM dedup detector with an embedding pre-filter and a persistent "not duplicates" list;
   - auto-sweeping of resolved review items;
   - chunked analysis of long sources with a global digest;
   - a guard against false-positive "missing page" findings in lint.

---

## 1. What it is, and how mature

| Item | Value (2026-11-05) |
|---|---|
| What | Cross-platform desktop app (Tauri v2: a Rust backend plus a React 19 / TypeScript webview) implementing Karpathy's pattern |
| Stars / forks | 21,397 / 2,435 (B reported 21.1k on 2026-10-29) |
| Created / last push | 2026-04-08 / 2026-10-21 |
| Releases | 62, from v0.3.0 (2026-04-12) to v0.6.13 (2026-10-22). Roughly weekly from April to August, then 09-28 and 10-22 |
| Commits | 90 in August 2026, 44 since 2026-09-01 |
| Contributors | 43. `nashsu` has 778 commits; the next has 22. **Bus factor: 1** |
| Issues / PRs | 190 open and 362 closed issues; 259 PRs; 26 new issues since 2026-10-01 |
| Code size | about 92k lines of non-test `.ts`/`.tsx`/`.rs` (including vendored Readability/Turndown), plus about 36k lines of tests |
| Licence | GPL-3.0 plus a copyright line (§5). GitHub API: `NOASSERTION` |

Independent reviews: I found none that went beyond a summary of the README. The hits were aggregators, news pages and a community "guide" site, all repeating README claims such as the vector-recall gain from 58.2% to 71.4% **[unverified]**. One aggregator calls it MIT-licensed, which is wrong. I found **no first-hand report of a team using it as a shared knowledge base**.

---

## 2. How it works (from the code)

### 2.1 Project layout and state

```
<project>/
  schema.md  purpose.md          # required; schema.md is parsed for a type→dir routing table
  raw/sources/                   # watched; new or changed files are auto-ingested
  wiki/index.md log.md overview.md
  wiki/{entities,concepts,sources,queries,synthesis,comparisons}/
  .obsidian/                     # written on project creation
  .llm-wiki/                     # app state, see below
```

The app keeps this state outside the Markdown. I classify each file by whether it can be rebuilt from the Markdown folder:

| File under `.llm-wiki/` | What it holds | Rebuildable from Markdown? |
|---|---|---|
| `project.json` | project UUID | yes (it is just an id) |
| `ingest-cache.json` | SHA-256 per source → files written. This is how the app decides "already ingested" | **partly**: the `sources:` field shows which sources have pages, but not the hash |
| `ingest-queue.json`, `ingest-progress/`, `ingest-generation/` | queue and checkpoints | transient; can be lost |
| `review.json` | LLM-generated review items and the user's resolutions | **no** |
| `dedup-not-duplicates.json` | human decisions "these pages are not duplicates" | **no** |
| `lint.json`, `lint-config.json` | lint results and ignore lists | results yes; the ignore config **no** |
| `chats/*.json`, `conversations.json` | chat history | **no**. Answers saved to `wiki/queries/` are in Markdown |
| `page-history/` | backups made before LLM merges | **no**. This is a second, non-git history |
| `history/` (`file_history.rs`) | optional per-file version store, capped at 30 versions | **no**. Off by default |
| `lancedb/`, `embedding-revisions` | vector index | yes; it is re-embedded from pages |
| `image-caption-cache.json` | captions from a vision LLM | yes, at LLM cost |
| `skills/` | project skills for the in-app agent | config |

Global settings live in the Tauri store `app-state.json` in each user's app-data directory (`src/lib/project-identity.ts:13`, `src-tauri/src/server_bind.rs:24`). These include the LLM provider and keys, source-watch rules, API config and the project registry. **They are per machine, not in the repo.**

So the app fails our "the repo is complete" test for review decisions, dedup decisions and page backups. It also keeps a second history beside git.

### 2.2 Ingest pipeline (`src/lib/ingest.ts`)

1. **Analysis call** (`buildAnalysisPrompt`, `:2434`). The prompt covers entities with a `Page-worthy: yes/no` verdict, concepts, claims with evidence strength, connections, contradictions and recommendations. It sets hard output limits (`:2408`). Inputs are `purpose.md`, `schema.md` and the index, capped at 32k characters.
2. **Generation call** (`buildGenerationPrompt`, `:2498`). The model emits `---FILE: path--- … ---END FILE---` blocks and optional `---REVIEW:` blocks. **The model writes whole files.** It is told to use `[[wikilinks]]` in the body and frontmatter `type, title, created, updated, tags, related (slugs), sources (filenames)`. It must **not** write `index.md` or `overview.md`; the app maintains those (`:2564`, `isAppManagedAggregatePath` `:1646`).
3. **An optional third call** proposes review items when the output is large (`buildReviewSuggestionPrompt`, `:2673`).
4. **Write** (`writeFileBlocks`, `:2095`):
   - It sanitises the frontmatter. A code comment says about 45% of generated entity pages used to have unparseable frontmatter (`:2152`) **[self-reported]**.
   - It stamps `created`/`updated`, canonicalises `sources`, and checks schema routing and language.
   - **If the page exists**, `mergePageContent` (`src/lib/page-merge.ts`) unions `sources/tags/related`, then asks the LLM to merge the two bodies (prompt at `ingest.ts:3454`).
   - The merge is rejected if the merged body is under 70% of the longer input (`page-merge.ts:BODY_SHRINK_THRESHOLD`).
   - `type/title/created` are forced back to their old values.
   - On fallback, the old page is backed up to `.llm-wiki/page-history/`.
   - A page whose `sources` lists **only** the current source is replaced, not merged (`:2266`).
5. **Aggregates.** The app appends `- [[slug]] — title` lines to a "Recently Updated" section in `wiki/index.md` and `wiki/overview.md` (`:1700-1820`) and appends to `wiki/log.md` (`:2236`).
6. **Long sources** are chunked semantically with a rolling "global digest", and they get checkpoints (`:3176-3240`). Truncated FILE blocks get a dedicated repair call (`:2741`).
7. **Concurrency.** Parsing may run in parallel, but commits are serialised in task order (`ingest-commit-coordinator.ts`) under a per-project promise lock (`project-mutex.ts`). All of this happens **inside one app process**.

### 2.3 Retrieval, lint, dedup

- **Search**: a tokenised search with CJK bigrams and a title bonus over `wiki/` and `raw/sources/`, optionally fused with LanceDB vectors (RRF, `search-rrf`). Then a 2-hop graph expansion and a token budget, as described in B §1.3.
- **Graph**: edges come only from `[[wikilinks]]` and the frontmatter `related:` field (`wiki-graph.ts:74,114`; Rust `api_server.rs:2819-2865`). Standard Markdown links are not edges.
- **Lint**:
  - Structural checks: orphan, broken link and no-outlinks, all based on wikilinks (`lint-structural-core.ts`).
  - Semantic checks: **one** LLM prompt with the first 500 characters of **every** page (`lint.ts:232-290`). This can't scale to thousands of pages.
- **Dedup** (`dedup.ts`):
  - It pre-filters candidates with embeddings (`dedup_embedding.ts`).
  - An LLM groups slugs that name the same thing, with a reason and a confidence of high/medium/low.
  - The user confirms each group. The app then merges the pages and rewrites every wikilink.
  - Rejected groups are stored so they aren't suggested again.

### 2.4 HTTP API, MCP and headless

- **HTTP API** (`api_server.rs:360-392`, default `127.0.0.1:19828`, token-protected):
  - `projects`, `files`, `files/content`;
  - `reviews` (list, resolve, patch, delete);
  - `search`, `graph`, `sources/rescan`, `pages/embed`;
  - **`pages/write`** (writes a page; `allowOverwrite` is required to replace one);
  - `chat` (the Rust agent runtime).
  - There is **no ingest endpoint**: `rescan` only triggers the source watcher.
  - LAN binding is possible through `LLM_WIKI_BIND_HOST` or a setting (`server_bind.rs`).
- **MCP server** (`mcp-server/`, Node): a thin wrapper around the HTTP API. **It needs the desktop app running.** Its tools: status, projects, set_project, files, read_file, reviews, search, chat, graph, rescan_sources. A separate read-only Claude Code skill, `nashsu/llm_wiki_skill` (153 stars), talks to it.
- **Headless: not supported.** Ingest, lint, review and deep-research orchestration live in the webview's TypeScript (#777: "the frontend … owns significant core logic such as ingest orchestration, prompt construction, LLM provider routing"). There are open requests for headless or server mode: #231 (May), #762 (September), #194 (closed after the API shipped, though it isn't a server mode).
- **Community forks**:
  - `hfwittmann/llm_wiki` is a browser/LAN multi-user fork (axum, argon2 sessions, per-user chat and LLM config, shared project state on disk). It was last pushed 2026-06-16, has 0 stars, and is an alpha.
  - `luoshuhui/llm-wiki-headless` is a "vibe-coded" read-only headless HTTP API (1 star).
  - Upstream is designing a read-only external harness, "Pi" (#818–#821, October 2026), with write tools explicitly out of scope.

### 2.5 LLM providers

The providers are OpenAI, Anthropic, Google, Azure, Ollama, MiniMax, custom endpoints (OpenAI or Anthropic API mode), and two **subprocess transports**: `claude-code` and `codex-cli` (`llm-providers.ts:941-1080`).

The Claude Code transport spawns `claude -p --output-format stream-json …` and uses Claude Code only as a **text-completion backend** (`claude-cli-transport.ts`, `commands/claude_cli.rs`). Claude Code doesn't drive the wiki here; the app's prompts and parser do. Claude is therefore supported, through the API key or a Claude Code login. That fits R16, but Claude Code still isn't the agent in the sense of our plan.

---

## 3. Could the group use it as-is?

Setup: each member runs the desktop app on a clone of a shared git repo.

| Problem | Why it breaks with 10–30 writers and autonomous agents | Code |
|---|---|---|
| **Duplicate ingest on pull** | A source added by Alice arrives in Bob's `raw/sources/` through `git pull`. Bob's watcher sees a created file and auto-ingests it, as does every other running instance. Each one rewrites the shared entity pages with a different LLM merge. The ingest cache is local, so it doesn't prevent this **[inferred from code]** | `project-file-sync.ts:enqueueRawSourceChanges`, `source-watch-defaults.json` |
| **Aggregate hotspots** | Every ingest appends to `log.md` and prepends to the "Recently Updated" sections of `index.md` and `overview.md`. Concurrent ingests conflict on nearly every merge. This is exactly what 01 §7 and §8 decided against | `ingest.ts:1700-1820, 2236` |
| **Whole-page LLM rewrites** | Pages are regenerated and LLM-merged as whole files. Two writers who touched one entity page conflict textually, or merge cleanly but semantically wrong (B TL;DR 4). There is no revision precondition like our A2 | `ingest.ts:2250-2290` |
| **Date stamps** | `created`/`updated` are written or bumped on every generated write. That adds frontmatter churn and needless conflicts, and it duplicates git dates | `ingest.ts:2049-2058` |
| **No cross-machine coordination** | The mutex and the commit coordinator are in-process promises. Nothing reserves slugs, nothing does search-before-create across writers, and nothing rebases | `project-mutex.ts` |
| **State split** | Review queue, dedup decisions, page backups and chats are per machine unless `.llm-wiki/` is committed. Committing it turns `review.json` and `ingest-cache.json` into JSON conflict hotspots | §2.1 |
| **Per-machine config drift** | Provider, model, source-watch rules and output language live in each user's app store. Thirty members means thirty pipeline configurations writing one wiki | `app-state.json` |
| **No git attribution (R18)** | The app never runs git. Commits, messages and the "invoked by" trailer are left to the user | `grep git` finds only `.git` exclusions |
| **No autonomous or server agents (R10, R11)** | Ingest needs the GUI. Scheduled imports exist but run inside the desktop app (`scheduled-import.ts`). There is no ingest API | §2.4 |
| **Scale of lint and index** | Semantic lint sends every page preview in one prompt. The index prompt is capped at 32k characters | `lint.ts:232`, `ingest.ts:66` |
| **Operations** | Installing and updating a desktop app on 10–30 machines with weekly releases. Recent open bugs include a Linux startup panic (#847), sustained CPU load from periodic full rescans on Windows (#812), and a UI hang (#810) | issues |

**Answer: no.** It could only work with **one** designated ingest machine, with source watch disabled everywhere else and everyone else read-only. That is a personal wiki with readers, not R10/R19.

---

## 4. Could it be an optional viewer or client on our repo?

Our conventions (01) against what the app expects:

| Our convention | App expectation | Effect |
|---|---|---|
| Root-absolute Markdown links `/wiki/<type>/<slug>.md` | `[[wikilinks]]` and `related:` slugs | Empty graph, no backlinks, every page flagged orphan or no-outlinks. In the reader, only `#`-anchored wikilinks are handled in-app (`wiki-reader.tsx:90-130`). Whether a `/wiki/...` link navigates in the webview is **[unverified]**, and it probably doesn't work |
| No `sources` field; citations inline; source list derived | `sources: [filename]` on every page. Graph "source overlap" weight ×4 | Source-overlap relevance and cascade delete do nothing |
| No `created`/`updated` (git has them) | Stamped on every write | Any write from the app adds them |
| Generated root `index.md` and `wiki/<type>/index.md`; agents never edit them | App-maintained `wiki/index.md` with `[[…]]` lines | Any ingest creates a second, wikilink index at `wiki/index.md` |
| No `log.md` | Appends `wiki/log.md` | Any ingest re-creates it |
| `raw/<channel>/<YYYY>/<id>/source.yaml` | `raw/sources/` (watched) | Our raw files are invisible to the app. That is harmless, but source search and source views are empty |
| `CLAUDE.md` plus specs as the single schema | Root `schema.md` (required to open the project) with a type→directory table, plus `purpose.md` | We would keep a second schema file that can drift (against R20) |
| OKF `description` required | Not used. Index lines use `title` | Lower-quality app index |
| English only (R1) | Supports a configurable output language | fine |

What would work in read-only use: file browsing, rendering with frontmatter as a panel, plain-text editing (edit mode bypasses the Milkdown serializer, `wiki-editor.tsx:69-71`), keyword search over `wiki/`, optional vector search, and chat over the wiki through the Rust agent.

Opening our repo would require:

- adding `schema.md` and `purpose.md` at the root;
- git-ignoring `.llm-wiki/`;
- every user remembering never to press Ingest, Lint-fix, Dedup-merge or Save-to-Wiki.

Pre-commit lint would catch wikilinks, `log.md` and stray fields, but that is friction for little gain. Obsidian (graph and backlinks work on our links, per 01 §6) and GitHub already cover viewing, and qmd covers search.

**Answer: technically possible, but not recommended.** Don't list it as a supported client. If someone wants it personally, the rules are: read-only, `.llm-wiki/` ignored, and no app writes committed.

---

## 5. Licence, exactly

- `LICENSE` line 1: `LLM Wiki — Copyright (C) 2024-2026 Yong Su`. Line 2 is blank. From line 3 on, the text is **identical to the stock GPL-3.0** (`diff -w` against `/usr/share/common-licenses/GPL-3` shows no differences).
- No additional permissions or restrictions under GPL §7. No "non-commercial" clause and no CLA. The README says "licensed under the GNU General Public License v3.0".
- Inconsistency: `mcp-server/package.json` declares `"license": "MIT"`, but there is no separate licence file in `mcp-server/`. Treat the whole repo as GPL-3.0 unless the author clarifies. `src-tauri/Cargo.toml` declares no licence.
- GitHub reports `NOASSERTION`, most likely because the prepended line defeats licence detection **[inference]**.

What this means (not legal advice):

| Use | Consequence |
|---|---|
| Members run the unmodified app | No obligations. The GPL doesn't restrict running it |
| Wiki pages the app generates | Not a derivative work of the program. Our Markdown stays under whatever licence we choose |
| Private, modified build used only by its author | No obligations |
| A fork published in `slds-lmu` or handed to group members | Must stay GPL-3.0 with source available. Whether passing it inside one university group counts as "conveying" is a grey area **[unverified]** |
| Copying prompt text or code into our MIT skill fork | Makes those parts a derivative of GPL code, which isn't compatible with releasing our skill as MIT. **Re-express the ideas in our own words; ideas and conventions aren't copyrightable** |
| Talking to the app over HTTP or MCP from our tools | Separate programs communicating at arm's length. Generally not a derivative **[unverified]** |

---

## 6. Mechanisms worth borrowing (beyond B §1.3)

B §1.3 already lists: the `purpose.md`/schema split, two-pass ingest, the content-hash skip, a closed set of review actions, and cascade removal from `sources[]`. New items:

| # | Mechanism | Where | How it would fit us |
|---|---|---|---|
| N1 | **Page-worthiness threshold.** Mark each candidate `Page-worthy: yes/no` with a one-line reason. No pages for passing mentions, generic roles or workflow artefacts. In long sources, decide only after accumulating across chunks | `ingest.ts:2401-2431` | Ingest triage rule in the forked SKILL.md: fewer stub person or concept pages. Matters for Mattermost and meeting ingest |
| N2 | **Subject-boundary rule.** Never move a claim, limit or benchmark from one entity, model or method to another because they share keywords. Comparisons must be explicit and cited | `ingest.ts:2463, 2600-2602`, merge prompt `:3463` | Add to the grounding rules and the G2 LLM support check. This is the cross-entity contamination failure B §1.1 (Firsgith) describes |
| N3 | **Canonical naming.** Reuse an existing page's exact title first, otherwise keep the source's spelling. Localised names become aliases. Never invent or phonetically guess names | `ingest.ts:2406, 2419` | Combine with our `aliases:` and search-before-create |
| N4 | **Identity sentence and background label.** An entity page opens with *what the subject is*. Any non-source background must be labelled as such, and if identity is unclear, no page is created | `ingest.ts:2420-2421` | Fits "uncited = not sourced": background stays visibly uncited |
| N5 | **Preserve structured data verbatim.** DDL, API signatures, configs and tables go into code blocks or tables, never prose | `ingest.ts:2465, 2604` | Useful for howto and infrastructure pages (UC4) |
| N6 | **Merge safeguards.** Reject an LLM merge whose body shrinks below 70% of the longer input. Lock identity fields (`type`, `title`). Union list fields deterministically | `page-merge.ts` | Add as a deterministic check in `tools/commit-op`: flag big shrinks on agent edits. Git replaces their `page-history/` backup |
| N7 | **Sole-owner replace.** If a page cites only the re-ingested source, regenerate it instead of merging, so retracted wording doesn't survive | `ingest.ts:2266-2272` | Relevant when a source gets a corrected version. In our model that is a new source id, so this becomes a lint hint ("page cites only a superseded source") |
| N8 | **LLM dedup with an embedding pre-filter and a persistent "not duplicates" list.** Prompt lists plural/singular, abbreviation, synonym, other language and spelling variants. Output is JSON groups with reason and confidence | `dedup.ts:171-210`, `dedup_embedding.ts`, `dedup-storage.ts` | Near-duplicate check in scheduled lint (B §4.8). **Keep the rejection list in git**, e.g. a `not-duplicates.yaml`, not in tool state |
| N9 | **Sweep resolved reviews.** After the queue drains, auto-close review items whose condition is now met: first by rules (page exists, matching title), then by an LLM check. Contradictions and suggestions are kept for humans | `sweep-reviews.ts` | Housekeeping for our `audit/` inbox (G6) |
| N10 | **Lint false-positive guard.** Drop "missing page" findings whose title matches an existing slug or title | `lint.ts:320-330` (#537) | Cheap precision gain (B: keep lint noise under about 15%) |
| N11 | **Chunked long-source analysis.** Semantic chunks with heading paths, a rolling global digest, entity decisions made only on the final digest, and resumable checkpoints | `ingest.ts:2962-3240` | Theses, books and long grant documents. Claude Code can do this in the prompt, but the digest rule is worth writing down |
| N12 | **Model never writes aggregates.** Index and overview are app-maintained so "large wikis are never rewritten through model output" | `ingest.ts:2564, 1646` | Independent confirmation of our P3 decision. Nothing to add |

Also worth remembering as **anti-patterns** (what not to copy):

- human decisions kept only in `.llm-wiki/*.json`;
- a second page history beside git;
- `created`/`updated` stamping;
- an append-only `log.md`;
- one prompt over every page for semantic lint;
- core orchestration inside the GUI layer, which upstream itself is now trying to undo (#777).

---

## 7. Forking it instead of Astro-Han

| | Astro-Han fork (current plan) | nashsu/llm_wiki fork |
|---|---|---|
| Size | One SKILL.md plus `check_evidence.py` | About 92k lines of TS and Rust, plus 36k lines of tests, a Tauri build chain, pdfium binaries and a Chrome extension |
| Agent | Claude Code itself (tools, permissions, hooks, worktrees) | Own prompt and parse pipeline (FILE blocks) and own Rust agent runtime. Claude Code is only a text backend |
| Licence | MIT | GPL-3.0 |
| Upstream | Dormant since July. We own it | Very active, one maintainer, frequent releases. A fork drifts within weeks |
| Link model | Standard Markdown (G8) | Wikilinks throughout: prompts, graph (TS and Rust), cleanup, index, dedup rewrite, reader |
| Multi-writer | Has to be added (G1), and our design does it with git | Has to be added, and the architecture is single-process |
| Headless or server | Native: Claude Code runs anywhere | Needs a refactor (#777) or a third-party fork |

To make a fork fit our specs we would have to:

1. replace the link model everywhere;
2. replace the frontmatter and page types;
3. remove `log.md`, the overview and the app index, and call our index generator instead;
4. put all writes through git with A2-style preconditions;
5. move ingest out of the webview into a headless service;
6. move review and dedup state into the repo;
7. maintain a GUI we don't need.

That amounts to a rewrite. It would bring a GPL licence and a large maintenance surface, against KISS and N4. **Effort: weeks to months, compared with days. Risk: high.** Not recommended.

---

## 8. Verdict

**Borrow ideas. Don't adopt it as a base, don't fork it, and don't support it as a client.**

Reasons:

1. It is a single-user desktop application by design. Collaboration is an open, unspecified wish upstream (#194: "Collaboration functionality is quite complex, so we're still working on the design").
2. Its on-disk conventions contradict decided parts of 01 (§6 links, §5.1 no dates or `sources`, §7 generated indexes, §8 no `log.md`).
3. It fails "the repo is complete" for review and dedup decisions.
4. It can't run autonomous server-side agents.
5. GPL-3.0 makes code reuse awkward for an MIT skill.

The value is in its prompts and safeguards, which have been hardened against real ingest failures. N1–N11 should go into the `03-agent-ops.md` drafting, written in our own words.

Optional follow-up: none needed. If a member wants a GUI with chat over the wiki, check later whether upstream gains a headless, read-only mode (#818–#821) that can index a plain Markdown folder with standard links.

---

## 9. Open or unverified items

- I never ran the app. The duplicate-ingest-on-pull behaviour and link navigation in the reader are inferred from code.
- The self-reported numbers (58.2% → 71.4% recall; "~45% unparseable frontmatter" before sanitising) are unverified.
- The GPL "conveying" question for distribution inside one university group is unverified and not legal advice.
- The MIT declaration in `mcp-server/package.json` hasn't been clarified by the author.
- I didn't evaluate the quality of the `hfwittmann/llm_wiki` LAN fork beyond its README and issue #400.

## 10. Sources

- Repo: https://github.com/nashsu/llm_wiki (read at `e08cfce`, v0.6.13). Key files: `src/lib/ingest.ts`, `src/lib/page-merge.ts`, `src/lib/dedup.ts`, `src/lib/dedup_embedding.ts`, `src/lib/dedup-storage.ts`, `src/lib/sweep-reviews.ts`, `src/lib/lint.ts`, `src/lib/lint-structural-core.ts`, `src/lib/wiki-graph.ts`, `src/lib/project-file-sync.ts`, `src/lib/source-lifecycle.ts`, `src/lib/ingest-cache.ts`, `src/lib/project-mutex.ts`, `src/lib/ingest-commit-coordinator.ts`, `src/lib/project-identity.ts`, `src/lib/llm-providers.ts`, `src/lib/claude-cli-transport.ts`, `src/lib/source-watch-defaults.json`, `src-tauri/src/api_server.rs`, `src-tauri/src/server_bind.rs`, `src-tauri/src/commands/project.rs`, `src-tauri/src/commands/file_history.rs`, `src-tauri/src/agent/tools.rs`, `mcp-server/README.md`, `mcp-server/package.json`, `LICENSE`, `README.md`
- Issues: #194 (server mode), #231 (headless or 0.0.0.0), #253 (enterprise practice), #400 (browser/LAN fork), #762 (headless Linux), #777 (frontend/backend boundary), #810, #811, #812, #818–#821 (Pi harness), #847
- Forks: https://github.com/hfwittmann/llm_wiki ; https://github.com/luoshuhui/llm-wiki-headless ; agent skill: https://github.com/nashsu/llm_wiki_skill
- Secondary (README restatements, no independent testing): https://llm-wiki-guide.pages.dev/ ; https://hublens.pages.dev/en/nashsu-llm_wiki/ ; https://ai-news-site-1ih.pages.dev/en/news/llm-wiki-karpathy-knowledge-base-app-en ; https://www.besthub.dev/articles/llm-wiki-a-karpathy-inspired-personal-knowledge-base-now-available-as-a-desktop-app-fa9513d00d69 ; https://aitoolly.com/de/ai-news/article/2026-09-13-llm-wiki-emerges-as-an-open-source-desktop-alternative-to-traditional-retrieval-augmented-generation
- Our specs: `specs/00-requirements.md`, `specs/01-data-model.md`, `specs/v0-foundation.md`, `specs/research/B-team-and-scale.md` §1.3
