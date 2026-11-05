# Prior art F: AnythingLLM and arkon as a possible base

Research date: 2026-11-05. Question: should we adopt an existing product as the **base** of the brain, instead of our own thin layer (fork of `Astro-Han/karpathy-llm-wiki` + qmd + git/Markdown)? Two candidates not covered by reports A–E: **AnythingLLM** and **arkon**.

Method: shallow clones of both repos under `scratchpad/clones/`. I read the READMEs, docs, data models (`server/prisma/schema.prisma` in AnythingLLM; `app/database/models.py` in arkon), permission code, ingest connectors and the arkon wiki pipeline (`app/ai/mrp/`). GitHub metadata via `gh api` on 2026-11-05. Web search and fetch for official docs and independent reviews. **No code was installed or run.** Star counts and feature claims are self-reported unless I say I checked the code. Claims I could not check are marked **[unverified]**.

The URL `https://github.com/nduckmink/arkon` is correct: the repo exists and is the project meant (an "Enterprise AI Knowledge Hub & MCP Server" that compiles documents into a wiki).

---

## 0. TL;DR

1. **Neither product should be our base.** Both keep the system of record in a database (SQLite + LanceDB for AnythingLLM; Postgres + pgvector + MinIO for arkon). Neither can be rebuilt from a git repo of Markdown, and neither writes to one. That breaks our hard rules: *the repo is complete*, *derive, don't store*, R1, R18, R19, N1.
2. **AnythingLLM is a RAG chat workspace, not a wiki.** It chunks documents, embeds them and answers questions with a list of source chunks. No agent writes or maintains pages. It is mature, MIT-licensed and very active (68k stars, 291 contributors, release v1.19.0 on 2026-10-26).
   **Verdict: ignore as a base; at most an optional, disposable Q&A front end later**, and only if the Mattermost bot plus Claude Code turn out not to be enough. It duplicates qmd, and its per-workspace permissions are too coarse to add anything.
3. **arkon is conceptually close to us**: an LLM compiles sources into an interlinked wiki with index, log, revisions, scopes and an MCP server. But:
   - pages live only in Postgres, with `[[wikilinks]]` and no git or Markdown export;
   - the license is **PolyForm Internal Use 1.0.0** (source-available, not open source; no redistribution);
   - it is a one-person project (168 of ~178 commits by one author), with **no push since 2026-06-03** and a backlog of unanswered bug reports;
   - its docs promise per-claim citation verification that the **code does not implement** (§2.4).

   **Verdict: borrow ideas, do not adopt or fork.**
4. **Ideas worth borrowing** (all from arkon unless noted):
   - a **compilation plan** before writing (which pages to create or update), reviewable or auto-approved. This is our triage step made explicit (→ 03);
   - **map → reduce → write** for large sources: extract claims with byte offsets per chunk, dedup entities against existing pages, then write one page per plan entry (→ 03, for long PDFs and meeting transcripts);
   - **reconcile against the existing wiki by similarity thresholds** before creating a page, as an anti-duplicate rule (→ 03; matches the B report's main concurrency finding);
   - an **orphaned flag** when all of a page's sources are deleted (→ lint);
   - **`preserve_verbatim` sources**: index high-fidelity documents (regulations, contracts, exam rules) for search without compiling them into wiki prose (→ 02);
   - a **layered cheap-first pre-check** on agent edits: regex (secrets, PII), then structure (broken links), then near-duplicates, then LLM (→ our two-layer lint);
   - a small **MCP tool surface** for a wiki: `search_wiki`, `read_wiki_page`, `read_wiki_index`, `get_source`, `get_source_pages` (→ 04/05, if we ever expose the brain over MCP);
   - from AnythingLLM: **query mode with a fixed refusal message** when retrieval finds nothing, which is a clean "not in the wiki" answer for the bot (→ 04/05).

---

## 1. AnythingLLM (Mintplex-Labs/anything-llm)

### 1.1 Facts

| Item | Value |
|---|---|
| Repo | https://github.com/Mintplex-Labs/anything-llm |
| License | MIT. Self-hosted terms file adds privacy statements, no extra restrictions |
| Stars / forks | 67,961 / 7,668 (gh, 2026-11-05) |
| Contributors | 291 (gh, incl. anonymous); lead author ~1,540 commits |
| Commits | ~2,650 |
| Last push | 2026-11-05; releases v1.17–v1.19 in Oct 2026 |
| Open issues | 349 |
| Stack | Node/Express server, React frontend, separate "collector" service, Prisma on SQLite, LanceDB default vector store |
| Editions | Desktop app (single user) and Docker (multi-user) |
| Telemetry | On by default (PostHog, anonymous events); opt-out by env var |

### 1.2 What it is

An all-in-one **"chat with your documents"** app. You create workspaces, upload or connect documents, and they are chunked and embedded. A chat then retrieves the top N chunks (default 4, similarity threshold 0.25) and answers. Extras: agents with tools, MCP client support, scheduled prompt jobs, memories, a Telegram bot, an embeddable chat widget, a browser extension and a developer API.

**No agent writes or maintains knowledge pages.** The closest features:
- a *filesystem* agent plugin that can read and write text files, but only inside a sandbox directory in Docker (`storage/anythingllm-fs` by default);
- *memories*: short per-user or per-workspace facts in a DB table.

Neither is a compiled, cited and linted wiki. AnythingLLM answers questions; it doesn't build anything.

### 1.3 Against our requirements

| Requirement | AnythingLLM | Fit |
|---|---|---|
| Compiled, maintained wiki (R7, R8, R9) | No. RAG over chunks only | ✗ |
| Plain Markdown in git as source of truth (R1, N1) | No. Parsed docs are JSON in `server/storage/documents/` (the docs call it a "temporary cache"); metadata in SQLite; vectors in LanceDB | ✗ |
| Rebuildable from git | The vector index can be rebuilt by re-importing. Chats, threads, memories, users and workspace settings live only in SQLite | partly |
| Citations per claim (R3) | No. The answer gets a list of source chunks (title, URL, first ~1,000 chars); claims are not tied to sources | ✗ |
| Multi-user and roles | Docker only. 3 global roles: `admin` (everything), `manager` (all workspaces, no model settings), `default` (chat only in workspaces they were added to). Access is per workspace, no per-document permissions | coarse |
| Tiers (R13, R14) | One workspace per tier, with members, could separate `group` / `leadership` / `owner` for *reading*. But every `manager` sees every workspace, and nothing stops content flowing down a tier | weak |
| Attributed commits, concurrent writers (R18, R19) | Not applicable: no git, no page writes | ✗ |
| Git integration | A GitHub/GitLab/Gitea **repo loader** imports files (branch, ignore paths, token for private repos). "Watched" documents re-sync hourly, but **only individual files, not directories**, so new wiki pages would need re-import via API or UI. Live sync is a beta feature, and the docs warn of possible DB corruption | weak |
| Ingest: web, PDF (R12 M) | Yes: URL scraper, website crawler, PDF/DOCX/TXT, OCR, YouTube, audio transcription | ✓ |
| Ingest: Mattermost, mail, Drive (R12 S) | No Mattermost or Slack connector found in code. Gmail and Outlook exist as *agent tools*, not ingest connectors. Confluence, Obsidian vault upload, Paperless-ngx, DrupalWiki | partly |
| Claude support (R16) | Yes, Anthropic provider | ✓ |
| Local embeddings | Yes: built-in native embedder (default `Xenova/all-MiniLM-L6-v2`), Ollama, LM Studio and others | ✓ |
| MCP | **MCP client** (its agents call MCP servers). I found no MCP *server* exposing its workspaces | — |
| Self-hosting cost | One Docker container (server + collector + SQLite + LanceDB). Light, apart from the embedder | ✓ |

### 1.4 Could it sit on top of our repo?

Technically yes. Import each tier repo into its own workspace with the repo loader, and let members chat with it. That would be a **derived, rebuildable index**, which satisfies "the repo is complete" as long as we treat its chats and settings as disposable.

But it adds little and costs a lot:
- It duplicates qmd (already decided as the search layer, N2) with a weaker retriever. It is pure embedding top-k by default, with reranking only on LanceDB. Our pages are short and interlinked, and an agent that follows links does better than top-4 chunks.
- Its answers cite chunks, not wiki pages with their inline citations, so R3 is lost at query time.
- Keeping it in sync needs our own glue: the API plus a post-merge hook to re-import changed and new files.
- It is a second user database, login system and permission model next to GitHub's, and must be kept in step with the repo-per-tier access.
- The Mattermost bot (R17 S) and Claude Code (R17 M) already cover the "ask the wiki" use case.

An independent hands-on review found its RAG and agent features "superficial and too rigid" (one user's opinion, on Medium). I found no systematic evaluation.

### 1.5 Verdict

**Ignore as a base. Optional layer: not now.** Reconsider only if non-technical members need a web chat UI and the Mattermost bot doesn't serve them. Even then, run it read-only on a git checkout, with telemetry off and local embeddings. **Borrow:** query mode with a fixed refusal message ("not in the wiki") instead of a guessed answer.

---

## 2. arkon (nduckmink/arkon)

### 2.1 Facts

| Item | Value |
|---|---|
| Repo | https://github.com/nduckmink/arkon (exists; URL as given is correct) |
| Owner | Minh Nguyen / BITSNESS Technology and Solutions Co., Vietnam |
| License | **PolyForm Internal Use 1.0.0**. Source-available, **not OSI open source**. Use and modify for "internal business operations"; **no distribution**. The README nonetheless calls it "Open-Source". Whether a university group's use counts as "internal business operations" is **[unverified]**; ask LMU legal if it ever matters |
| Stars / forks | 1,519 / 305 (gh, 2026-11-05). Third-party listings show 15 to 1.4k at various dates. Unusually high for a 6-month-old, 3-contributor repo; treat as **[unverified]** popularity |
| Contributors | 3; the main author has 168 of ~178 commits |
| Created / last push | 2026-04-30 / **2026-06-03** (5 months idle) |
| Releases | v0.9.1 on 2026-06-01 (pre-1.0) |
| Open issues | 22. A run of detailed bug reports from July–August 2026 (ingest stuck at 55%, empty dashboard, login 500, LLM refusal saved as page body, NUL-byte crash) has no visible fix. One open issue is a request for a private channel to report a security problem |
| Stack | FastAPI, PostgreSQL + pgvector, Redis (arq workers), MinIO, Next.js. 7 containers |
| Server sizing (self-reported) | 2 vCPU / 4 GB RAM / 40 GB SSD for 1–20 users. No GPU; all inference goes to external APIs |

### 2.2 What it is

A **compiled wiki**, close to the Karpathy pattern, packaged as a team server. An admin or contributor uploads a document. A worker runs the "MRP" pipeline, and the LLM writes or updates interlinked wiki pages. People read them in a web UI or through Claude via MCP. So, unlike AnythingLLM, **an agent does write and maintain pages.**

The pipeline (`docs/WIKI.md`, `app/ai/mrp/`):
1. **Triage** by size: single pass, standard, or hierarchical.
2. **Map**: chunk along headings (~20k chars). Per chunk, the LLM extracts entities, concepts, claims and relations as JSON, with byte offsets into the source. Results are saved per chunk so a crash can resume.
3. **Reduce**: dedup entities (exact, then embedding similarity >0.90 auto-merge, 0.75–0.90 LLM decides). Reconcile against existing pages (≥0.85 update, 0.60–0.85 LLM decides, <0.60 create). One LLM call writes a **compilation plan**: pages to create or update, entities covered, link targets.
4. **Plan review**: an editor approves, edits or rejects the plan. `MRP_AUTO_APPROVE_PLAN=true` skips this step.
5. **Refine**: one writer per planned page, up to 4 in parallel. Large pages get a small agent loop with `read_kb_page` and `read_source_excerpt`.
6. **Verify**: coverage check plus a contradiction check against similar pages. A detected contradiction is prepended as a callout. Non-blocking.
7. **Commit**: one DB transaction. Then the index (`_index`) is regenerated and a log entry is appended (`_log`).

Human edits: editors edit directly. Contributors propose drafts that go through a review queue, with optimistic version checks (`base_version`), a Postgres advisory lock on approve, and notifications to other draft authors. Every change creates an immutable revision row, so rollback is possible.

### 2.3 Against our requirements

| Requirement | arkon | Fit |
|---|---|---|
| Compiled, maintained wiki (R7) | Yes: ingest → plan → page writes, index and log | ✓ |
| Query with citations, file answers back (R8) | Query via MCP or UI. No "file the answer as a page" step found | partly |
| Lint (R9) | Orphan detection, a "wiki linter" UI, contradiction check at ingest. No scheduled lint for stale claims | partly |
| Plain Markdown in git (R1, N1) | **No.** `wiki_pages.content_md` in Postgres. Sources (`full_text`) in Postgres, files in MinIO. **No git integration and no Markdown export in the code** (grep finds only a CSV export of usage stats) | ✗ |
| Rebuildable from git | No. Postgres is the system of record; revisions, drafts, scopes and users exist only there | ✗ |
| Link syntax | `[[slug]]` wikilinks and Obsidian callouts. We decided against both (N4) | ✗ |
| Citations per claim (R3) | Page-level only: `source_ids[]` per page. The docs say every claim gets a `[^N]` footnote that a verify phase checks (SUPPORTED / PARTIAL / NOT_SUPPORTED / CONTRADICTED). **The code at HEAD does the opposite.** The writer prompt says "Do NOT use [^N] footnote markers" and "Do NOT include a Citations or Footnotes section". `verifier.py` contains only the coverage and conflict checks, with no citation check. The map phase does keep claim offsets internally | ✗ (docs ≠ code) |
| Attributed changes (R18) | Revision rows with `changed_by_id`; agent compiles have a null author. Not git commits | partly |
| Concurrent writers (R19) | Handled in the DB: advisory locks, version checks, a draft queue. Sound design, but not git | n/a for us |
| Autonomous agents (R10) | Default is a human plan gate; auto-approve is an env flag. Agent edits via MCP need editor role, else they become drafts | ✓ configurable |
| Tiers (R13, R14) | "Global" plus department or workspace scopes, enforced at API, MCP and search ("hard scope enforcement", **[unverified]** beyond the code paths I read in `app/mcp/permissions.py`). Fine-grained RBAC `{resource}:{action}:{scope}` with roles Viewer / Contributor / Editor / Admin, plus an audit log. Could model `group` / `leadership` / `owner` as scopes. But all tiers share one database, and nothing stops downward flow: the same "labels in one store" model the B report warns against | partly |
| Ingest (R12) | PDF, DOCX, DOC, text, URLs, images (vision captions). No arXiv/DOI handling, no Mattermost, no mail. Drive/SharePoint/Notion connectors are on the roadmap | partly |
| Claude support (R16) | Yes: Anthropic LLMs; OAuth 2.1 MCP server that works with Claude Desktop and claude.ai connectors | ✓ |
| Local embeddings | **No.** Embeddings only via Google or OpenAI APIs; an open issue (#19) asks for self-hosted models. That would send all text to a second provider, which we ruled out (prior-art §2, retrieval) | ✗ |
| Maturity | Pre-1.0, one main author, idle for 5 months, open crash bugs | ✗ |
| Self-hosting cost | 7 containers (Postgres, Redis, MinIO, API, 2 workers, frontend). Small on hardware, heavy on operations | ✗ |

### 2.4 The documentation gap

The README and `docs/WIKI.md` describe per-claim footnotes and an LLM citation check. Checked against the code at the cloned HEAD (`app/ai/mrp/writer.py` around line 220; `app/ai/mrp/verifier.py`), neither exists. The writer prompt explicitly forbids footnotes, and the verify phase has no citation check. Either the feature was removed or it was never shipped. This matters for us because per-claim citations (R3) are our main guard against guesses hardening into facts. It also lowers trust in the project's other documentation claims.

### 2.5 Could it sit on top of our repo?

No. It has no import path that treats a git repo as truth. Its pipeline wants to *own* the wiki pages and rewrite them from uploaded sources, so pointing it at our repo would create a second, competing wiki. Its MCP server only serves its own Postgres content.

### 2.6 Verdict

**Borrow ideas. Do not adopt, fork or run it.** Reasons:
- its state lives in a database, not git;
- the license forbids distribution, which rules out a fork in `slds-lmu`;
- it is effectively unmaintained;
- it uses wikilinks;
- it has no local embeddings;
- its documented citation guarantee is not in the code.

The *design* is the most useful team-oriented compiled-wiki design I have seen so far. Ideas for our specs, with a target and a cost note:

| Idea | Where it goes | Note |
|---|---|---|
| Compilation plan before writing: list of pages to create or update, with entities and links | 03 ingest | Our triage step, made into a written artifact. Can go in the commit message. Auto-approve by default (R10) |
| Map → reduce for long sources: chunk, extract claims with byte offsets, then write per page | 03 ingest | Only for long sources (theses, transcripts, long PDFs). Offsets support our grounding check |
| Similarity-threshold reconciliation against existing pages before create | 03 ingest | Our "search before every create" rule, with explicit bands. We can do it with qmd, no embeddings needed at first |
| `orphaned` when all of a page's sources are gone | lint | Derivable from citations, so a lint rule, not a field (derive, don't store) |
| `preserve_verbatim`: search a source without compiling it | 02 ingest | E.g. exam regulations, contracts: keep in `raw/`, index in qmd, no summary page |
| Layered pre-check on edits: regex → structure → near-duplicate → LLM | lint | Matches our two-layer lint; adds the cheap-first order |
| Resume-safe ingest: save per-chunk extracts | 03 | Only if we automate big ingests (R11); not v1 |
| MCP tool set: `search_wiki`, `read_wiki_page`, `read_wiki_index`, `get_source`, `get_source_pages` | 04/05 | If we ever expose the brain over MCP. qmd already has an MCP server; this list is a guide to naming |
| Draft review queue with `base_version` conflict check | — | Not needed: git branches and PRs already do this. Note only |

---

## 3. Comparison

| | AnythingLLM | arkon | Our plan |
|---|---|---|---|
| Kind | RAG chat over chunks | Compiled wiki, team server | Compiled wiki, git repo + agent skill |
| Agent writes pages | No | Yes | Yes |
| System of record | SQLite + LanceDB + JSON cache | Postgres + MinIO | git (Markdown + YAML) |
| Rebuildable from git | Index only | No | By definition |
| Citations | Chunk list per answer | Page-level `source_ids` (claim-level promised, not in code) | Inline per claim (R3) |
| Access model | Workspace membership, 3 roles | Scopes + fine RBAC + audit | One repo per tier (GitHub) |
| Local embeddings | Yes | No | qmd, local |
| License | MIT | PolyForm Internal Use | ours (MIT deps) |
| Maintenance | Very active | Idle since 2026-06 | — |
| Verdict | Ignore; maybe optional chat UI later | Borrow ideas | — |

Bottom line for P4 (implementation base): **nothing here changes the recommendation.** The thin layer (Astro-Han fork + qmd + git) remains the right base. This confirms the A–E finding that no existing product combines git + Markdown, several writers, tiers and per-claim citations.

---

## 4. Not verified

- AnythingLLM: I did not test retrieval quality or the repo loader on a private `slds-lmu` repo. Per-workspace isolation was read from docs and `workspace.js`, not tested.
- AnythingLLM: whether any community MCP *server* for AnythingLLM exists, so that Claude Code could query its workspaces. I found none in the repo.
- arkon: scope enforcement was read only in `app/mcp/permissions.py` and the docs, not audited. The open security report (#23) is not public.
- arkon: whether the citation verification exists on another branch or in an earlier commit. Only the shallow HEAD was read.
- arkon: star history looks inorganic for its age and contributor count; not investigated further.
- PolyForm Internal Use: applicability to a public university is not checked legally.

## 5. Sources

- AnythingLLM repo: https://github.com/Mintplex-Labs/anything-llm (README, `server/prisma/schema.prisma`, `server/utils/middleware/multiUserProtected.js`, `server/utils/agents/aibitat/plugins/filesystem/`, `collector/utils/extensions/`, `collector/extensions/resync/`, `server/utils/chats/stream.js`, `server/storage/documents/DOCUMENTS.md`, `TERMS_SELF_HOSTED.md`)
- AnythingLLM docs: https://docs.anythingllm.com ; security and roles: https://docs.anythingllm.com/features/security-and-access ; live document sync: https://docs.anythingllm.com/beta-preview/active-features/live-document-sync ; chatting with documents: https://docs.anythingllm.com/chatting-with-documents/introduction ; MCP: https://docs.anythingllm.com/mcp-compatibility/overview
- Independent review (one user): https://medium.com/@pamperherself/hands-on-experience-with-anythingllm-rag-tools-seem-superficial-and-too-rigid-e904e3ceab4c
- arkon repo: https://github.com/nduckmink/arkon (README, `LICENSE`, `docs/WIKI.md`, `docs/ACCESS-CONTROL.md`, `docs/MCP.md`, `app/database/models.py`, `app/ai/mrp/writer.py`, `app/ai/mrp/verifier.py`, `app/mcp/permissions.py`, issues #4–#36)
- arkon third-party listings (inconsistent star counts): https://awesome.ecosyste.ms/projects/github.com%2Fnduckmink%2Farkon ; https://gittrend.io/repo/nduckmink/arkon
- PolyForm Internal Use 1.0.0: https://polyformproject.org/licenses/internal-use/1.0.0
