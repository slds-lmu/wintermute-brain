# Prior art B: team, multi-writer and at-scale LLM knowledge bases

Research date: 2026-10-29. Scope: systems that go beyond a single user (teams, several writers, scale, research groups), plus what people running them at scale report. Measured against the SLDS group-wiki requirements: Karpathy LLM Wiki pattern, Obsidian Markdown with YAML frontmatter in git, per-claim citations, epistemic markers, contradiction and supersession handling, agent-maintained index, git history as the log, concurrent human and agent writers, fully autonomous agents, three confidentiality tiers as separate repos, more than 2000 sources a year.

Method: I cloned and read the READMEs, schema files and docs of AutoSci/OmegaWiki, nashsu/llm_wiki, lucasastorian/llmwiki, obsidian-claude-pkm, llm-atomic-wiki, gbrain, basic-memory, agentmemory and iwe. Clones are under `scratchpad/clones/`, and no code was run. I pulled the rohitg00 gist and its 24 comments through the GitHub API. I pulled all 1155 comments on the Karpathy gist (`scratchpad/karpathy-comments.txt`), filtered them by keyword for team, concurrency and scale topics, and read the matches. The OKF spec comes from GitHub. Web searches covered team wikis, company brains, concurrency, Graphiti, Mem0, Letta and Basic Memory Teams. GitHub metadata was taken on 2026-10-29.

Nearly every number below is **self-reported by the project or commenter**. Claims I could not check are marked **[unverified]**.

---

## 0. TL;DR

1. **Nobody has built what we need.** No open-source system I found offers a git and Markdown, multi-writer, tiered-confidentiality, research-group LLM wiki that we could adopt whole. Most "team" implementations are personal tools with a sharing feature added later. The few that are genuinely team-oriented are either very heavy (gbrain, built on Postgres) or tiny and unproven (mcp-llm-wiki, Citadel, junbjnnn/llm-wiki, AEVYRA coordination). **Build on plain git plus Markdown, and borrow conventions and mechanisms precisely.**
2. **git plus Markdown is the right foundation.** The memory frameworks are now converging on it. Letta's newest memory (MemFS, or "context repositories") is a git-backed set of Markdown files with YAML frontmatter, and background agents write through git worktrees. gbrain treats Markdown in git as the system of record and Postgres as a rebuildable index. Basic Memory's files are the source of truth. Mem0, Zep/Graphiti and Letta's older memory blocks are built around per-user chat memory and a database. They don't provide human-readable, reviewable or citable synthesis pages, and they don't separate repos by confidentiality tier.
3. **Adopt Google's Open Knowledge Format (OKF) v0.2 as the frontmatter and provenance base.** OKF is Apache-2.0, from GoogleCloudPlatform, and its spec repo has about 1.2k stars. It is a vendor-neutral spec for corpora maintained by agents. It defines `sources[]` with stable ids, **per-claim footnote citations keyed by `sources[].id`**, `generated: {by, at}`, `verified: [{by: human:<id>, at}]` (which yields the trust tiers unverified, machine-confirmed and human-reviewed), `status: draft|stable|deprecated`, `stale_after`, the actor convention `human:` / `process:` / `agent/version`, and per-directory `index.md` and `log.md`. Basic Memory and IWE already produce or validate OKF, so adopting it gets us tooling for free. We would extend it with our own fields: epistemic markers, `supersedes` / `superseded_by`, contradictions, and confidentiality tier.
4. **Concurrency problems are semantic, not textual.** Git merges two agents' differently worded versions of the same fact without complaint (watsonrm). In one team deployment, a batch of parallel ingests produced **38% near-duplicate pages** (huachen-wang) **[unverified]**. The fixes, in order:
   - partition writers so that each writer owns a page type or layer;
   - make writes append-only where possible, such as timeline sections and one entry per line;
   - **reserve slugs in the index before generating pages** (`status: planned`, `claimed_by: [...]`);
   - use revision or ETag preconditions on page replacement;
   - use deterministic merge drivers, or better, generate the hotspot files (`index.md`) in CI instead of having agents write them;
   - keep a grep or search dedup step before every create.
5. **Separate repos per tier is the correct choice, and practitioners confirm it.** One team ran an `audience:` label as a query-time filter. A mis-derived label hid a page from the ingest step, which then created a parallel copy that contradicted the original. Their conclusion: "If an audience must never see some knowledge, the reliable guarantee is that it was never compiled into their wiki at all" (huachen-wang). PromptQL makes the same point: "if you build a company brain, it will likely leak company secrets." What we still need is a rule that no derived synthesis flows down to a lower tier.
6. **`index.md` as the main retrieval path stops working at about 100–500 pages.** Every independent report agrees. At more than 2000 sources a year we will pass that within months. Plan for these steps:
   - **index plus full-text, taking the union of both results**: BM25 or FTS5 is enough, and adding a step can never reduce recall;
   - hierarchical per-directory `index.md` files and routing;
   - optionally hybrid vector search, kept as a *derived, rebuildable* index.
7. **Ideas worth borrowing directly:**
   - gbrain's *compiled truth plus append-only timeline* page shape. It fits project and grant status pages and supersession well.
   - huachen-wang's *human-correction pins*, so autonomous re-compiles don't silently revert human fixes.
   - cablate's *two-layer lint* (deterministic first, LLM second) and the *slug pre-lock before parallel fan-out*.
   - AutoSci's typed edges with `confidence` plus `evidence`, `writers.yaml` and lifecycle state machines.
   - The `sources: [{path, etag/hash}]` provenance for detecting stale sources (mcp-llm-wiki, distorx).
   - Trust tiers that separate `agent_written` from `external_untrusted` (gbrain memory-trust) as a defence against prompt injection.

---

## 1. Per-system evaluation

### 1.1 rohitg00 "LLM Wiki v2" gist + agentmemory

- **What it is.** A design essay that extends Karpathy's pattern with a memory lifecycle (confidence scores, supersession, Ebbinghaus forgetting, consolidation tiers working → episodic → semantic → procedural), a typed knowledge graph, hybrid search (BM25 + vector + graph, fused with RRF), event-driven hooks, quality scoring, multi-agent "mesh sync" (last-write-wins plus timestamp resolution), shared versus private scoping, and filter-on-ingest privacy. Its implementation is **agentmemory**.
- **Maturity.** The gist has 24 comments and was last updated 2026-10-25. agentmemory has 30.0k stars, an Apache-2.0 licence, and was pushed 2026-10-29. It runs as a memory server on iii-engine and captures coding-agent sessions through hooks and MCP.
- **Data model.** agentmemory stores observations and memories in its own server store, not in curated Markdown pages. It has per-agent scoping (`agentId`), write-time provenance labels (user, agent, tool, import or shared), "team memory" (shared plus private namespaces), `memory_lease` (exclusive action leases) and `memory_mesh_sync` (P2P).
- **Multi-user.** Namespaced team sharing and leases exist, but this is a session memory for coding agents, not a curated wiki.
- **Provenance and contradictions.** The gist says to supersede rather than annotate, and to resolve contradictions by recency, authority and support count.
- **Scale.** The gist says `index.md` "works up to maybe 100–200 pages" and that you need hybrid search beyond that. The 95.2% LongMemEval-S result is **[unverified]** and self-reported.
- **Criticism in the comments, which is worth more than the gist itself:**
  - An anonymous commenter, apparently the same person as "gnusupport" on the Karpathy gist, lists 25 gaps. Among them: confidence is never defined; nothing records provenance (which agent wrote a fact, from which source); there is no consistency model, no access control, no rollback of a bad crystallization, no evaluation; and "LLMs are treated as reliable — they'll silently corrupt the graph". Their verdict: "Steal the ideas, not the plan."
  - Another anonymous practitioner (2026-05-04) argues: **forgetting curves applied to errors and superseded decisions are how you repeat mistakes**; use explicit supersession instead. **Numeric confidence scores are false precision**; the evidence is the chain of links. **Event-driven auto-ingest assumes reliable LLMs.** "Filter in ingestion, not in retention; supersession instead of decay; git as audit; manual before automated."
  - Firsgith lists five degradation modes:
    - cross-entity inference pollution, so facts need an evidence-scope tag;
    - conjectures hardening into facts, so we need discrete epistemic states `fact | verified_inference | hypothesis | speculation` with confidence as a secondary signal;
    - contradictions that get resolved away instead of becoming research tasks;
    - decisions stored without their reasoning, so we need decision memory with rejected alternatives;
    - no router or timeline, so point-in-time queries can't be answered.
  - HagaiHen: **tell supersession (facts) apart from disagreement (opinions)**. A "Disagreements & open questions" section became the most useful part of their wiki. A frontmatter `sources: N` count gives most of the value of a confidence score. Headless scheduled runs failed because the permission rule `Edit(wiki/**)` was relative and stopped matching after `cd wiki`, so **use absolute paths in permission rules for unattended agents**.
  - dqm07 asks how a team would share confidence scores in one repo. Nobody answered.
- **Verdict: borrow ideas, ignore the implementation.**
  - Borrow supersession links, epistemic states (from Firsgith's comment), the opinion-versus-fact distinction, decision records with rejected alternatives, and filter-on-ingest privacy.
  - Reject the decay and forgetting curves and the numeric confidence floats. Use discrete epistemic markers and evidence counts.
  - Ignore agentmemory: it is coding-session memory, not a curated wiki.

### 1.2 OmegaWiki, now PKU-DAIR/AutoSci

- **What it is.** `skyllwt/OmegaWiki` now redirects to **PKU-DAIR/AutoSci** (Peking University, Bin Cui's group; arXiv 2605.31468, "AutoSci: A Memory-Centric Agentic System for the Full Scientific Research Lifecycle"). It is a Claude Code skill suite covering the full research lifecycle: ingest papers, ideate, design and run experiments, write papers, posters and rebuttals. The wiki is the memory layer ("SciMem").
- **Maturity.** 1.7k stars, MIT licence, pushed 2026-10-21. The status is "internal beta". It has a stable Claude Code branch plus Codex and OpenCode preview branches.
- **Data model.** This is the most rigorous schema I found:
  - `runtime/schema/entities.yaml` defines typed page kinds (papers, concepts, topics, people, ideas, methods, experiments, Summary, foundations) with typed fields, enums, required-when rules and **lifecycle state machines**. Ideas go proposed → in_progress → tested → validated/failed, and `failure_reason` is required when status is failed. Experiments go planned → running → completed/abandoned.
  - `edges.yaml` defines typed edges (`same_problem_as`, `builds_on`, `challenges`, `introduces_concept`, `critiques_concept`, `supports`, `contradicts`, `invalidates`, `tested_by` and others). Each edge carries `confidence: high|medium|low` and a required `evidence` string.
  - `xref.yaml` holds the rules for writing the reverse link of every forward link.
  - Edges are stored in `wiki/graph/edges.jsonl` and change only through a tool (`tools/research_wiki.py`).
  - `wiki/log.md` is append-only.
  - `raw/{papers,notes,web}` are owned by the user and read-only.
- **Multi-user, concurrency and access control.** None. It is single-user and single-agent. `runtime/policy/writers.yaml` declares, field by field, which skill may write which field (for example, `ideas.status` is writable by `[ideate, exp-eval, ...]`). The file states plainly: **"SPEC, NOT A RUNTIME GATE … Enforcement is at the prompt level"**.
- **Provenance and contradictions.** Provenance lives on typed edges with evidence and confidence. `contradicts` and `invalidates` edges exist, and failed ideas must state a reason, which counts as negative knowledge.
- **Scale.** Not discussed. The README reports three papers produced end to end.
- **Verdict: borrow ideas, don't reuse or fork.** It is too opinionated about automating research (experiments, rebuttals) and assumes one user. Borrow:
  - the YAML entity and edge schema as the shape of our schema, kept outside the CLAUDE.md prose;
  - `confidence` plus a required `evidence` on every typed relation;
  - lifecycle state machines with required failure reasons, for projects, grants, ideas and experiments;
  - the per-field writer policy, though we would enforce it in CI, which they don't;
  - reverse-link symmetry lint.
  - Don't copy the append-only `log.md`. It becomes a merge-conflict hotspot when several people write, and git history replaces it.

### 1.3 nashsu/llm_wiki

- **What it is.** A cross-platform desktop app (Tauri, Rust, React) implementing the pattern. It has `purpose.md` (the wiki's goal and thesis, separate from the schema), a two-step chain-of-thought ingest (analyse, then generate), a SHA256 incremental cache, a persistent serial ingest queue, a watcher on the source folder, Louvain community detection, "surprising connections" and knowledge-gap insights, an asynchronous human review queue, cascade deletion, a local HTTP API on `127.0.0.1:19828` plus an MCP server, and a web clipper.
- **Maturity.** 21.1k stars, pushed 2026-10-21. The licence is **GPL-3.0** with a custom copyright header; the GitHub API reports NOASSERTION.
- **Data model.** Markdown with frontmatter `sources: []`. The app regenerates `index.md`, `log.md` and `overview.md`. LanceDB vectors are optional.
- **Multi-user and concurrency.** None. Ingest is deliberately serial: "serial processing prevents concurrent LLM calls".
- **Provenance and contradictions.** Page-level `sources[]`. The analysis step flags "contradictions & tensions". The review queue only offers fixed action types (Create Page, Deep Research, Skip) "to prevent LLM hallucination of arbitrary actions".
- **Scale.** A multi-phase retrieval pipeline: tokenised search over wiki and raw, then optional vectors, then 2-hop graph expansion with decay, then a token budget (60% pages, 20% history, 5% index, 15% system). The self-reported benchmark says recall rose from 58.2% to 71.4% with vectors **[unverified]**.
- **Verdict: borrow ideas.**
  - The `purpose.md` / schema split.
  - The two-pass ingest, analysis then write.
  - Content-hash skip of unchanged sources.
  - Review-queue items limited to a closed action set.
  - Cascade deletion that removes only the deleted source from shared entity pages' `sources[]`.
  - It is a single-user app with a GPL licence, so we won't reuse it.

### 1.4 lucasastorian/llmwiki

- **What it is.** An MCP server plus a Next.js web app plus a Chrome clipper. Claude, over MCP, writes the wiki through tools: `guide`, `search` (including a citation-graph mode), `read`, `create`, `edit` (exact find-and-replace), `append`, `delete`, `lint`. The intended mode is fully autonomous: a nightly Claude Routine folds in new sources. The README explicitly pitches "for your organization … institutional knowledge layer".
- **Maturity.** 1.7k stars, Apache-2.0, pushed 2026-10-27. Local mode uses SQLite plus the filesystem; hosted mode (llmwiki.app) uses Supabase Postgres plus S3.
- **Data model.** `wiki/` Markdown plus `.llmwiki/index.db`. The guide makes citations mandatory: "Every factual claim MUST cite its source via markdown footnotes … `[^1]: attention-paper.pdf, p.3` … One citation per claim". Each write parses citations and cross-references into graph edges. Lint checks citation resolution, footnote hygiene, dangling links, orphans, **uncited sources** and **stale pages**. Contradiction checking is left to manual semantic review. One weakness: highlights, comments and agent replies live **only** in `index.db`.
- **Multi-user and access control.** The hosted version has per-user row-level security, and migration `006_kb_sharing.sql` adds **visibility `private | shared (token URL) | public`**. That is read sharing only: there is no multi-writer support, roles or merge story. Local mode binds only to loopback.
- **Verdict: borrow ideas.**
  - Footnote citations with page locators, one per claim.
  - The "uncited source" and "stale page" lints.
  - Citation graph edges derived automatically on write.
  - The idea of a nightly autonomous routine.
  - Note its anti-pattern: keeping user annotations outside git.
  - It doesn't fit our multi-writer git model.

### 1.5 ballred/obsidian-claude-pkm

- **What it is.** A personal productivity and accountability vault (goals → projects → daily notes) driven by Claude Code skills, agents, rules and hooks. It is not a knowledge wiki.
- **Maturity.** 1.9k stars, MIT, last pushed 2026-02-18, so it is going stale.
- **Interesting mechanics:**
  - a PostToolUse **auto-commit hook** that commits on every write;
  - path-scoped `Write(...)` / `Edit(...)` allow rules plus `deny Edit(.claude/**)`;
  - a separate `CLAUDE.md` per project folder;
  - a `/push` skill;
  - a GitHub Action (`claude.yml`) triggered by issues, PRs and dispatch.
- **Multi-user.** None.
- **Verdict: borrow small ideas.**
  - Permission allowlists scoped by path that stop agents editing the schema and `.claude/` (but use absolute paths, per HagaiHen).
  - A per-directory `CLAUDE.md` for project subtrees.
  - An Action-triggered agent on issues, usable as an input channel for "please ingest / fix this".
  - Avoid auto-commit on every tool call when several writers share the repo. Commit once per logical operation instead.

### 1.6 cablate/llm-atomic-wiki

- **What it is.** Methodology plus schema plus three shell scripts. The flow is raw → **atoms**, one claim per file with frontmatter (source, type, depth, tags, date) organised in topic-branch folders → wiki pages compiled from atoms. Atoms are the source of truth and the wiki is a rebuildable cache.
- **Maturity.** 151 stars, **no licence** (so only the ideas are reusable), last pushed 2026-04-20.
- **Scale data [unverified].** 584 posts plus 8,668 replies produced 630 atoms, 11 branches and 83 pages. Replies were about 87% noise.
- **Lessons:**
  - **Two-layer lint.** Deterministic checks (ghost links, orphans, format) run first in seconds, then the LLM checks semantics (contradictions, expired claims): "so the LLM doesn't waste attention on format issues".
  - **Lint signal-to-noise.** A loose regex for temporal words gave 47 warnings, about 85% of them noise. "A report that's 85% noise gets opened three times, then ignored forever." After tightening it to temporal words paired with a date or version, it gave 16 warnings, all real.
  - **Parallel-compile naming collision.** With 11 parallel agents, the same content got different filenames (`mcp-plus-skills.md` and `mcp-plus-skills-architecture.md`). The fix was to **pre-lock the slug namespace before fan-out**: "Agents fill content into pre-named slots; they do not name files."
  - The author's conditions for the pattern to work: fewer than about 200 pages, stable knowledge, a **single owner with a point of view**, and quality over coverage. Our setting breaks the third and probably the first.
- **Verdict: borrow ideas.** Two-layer lint, slug pre-allocation, tuning lint precision, and possibly an atom (claim) layer. Our per-source summary pages already act as a coarse atom layer.

### 1.7 garrytan/gbrain (found via the comments, the most relevant team system)

- **What it is.** "Garry's opinionated OpenClaw/Hermes agent brain." It is a large TypeScript/Bun memory system with a Markdown-repo system of record and a Postgres (or PGLite) derived index, hybrid search, a typed graph, a synthesis command (`gbrain think`) that reports gaps, a nightly "dream" consolidation, about 66 cron jobs, a job queue, and MCP over HTTP with OAuth. It ships a **company-brain tutorial aimed at 10–50 people** and a hosted version (gbrain.io).
- **Maturity.** 31.3k stars, MIT, created 2026-04-05, version **0.60.488**. That is an extremely fast release cadence, so expect API churn. It has 30 contributors and 755 open issues. The scale figures (155,795 pages, 24,589 people) are **self-reported [unverified]**.
- **Data model:**
  - The schema comes from "schema packs", 15 canonical types by default.
  - Pages follow a **compiled truth plus timeline** structure. The synthesis zone is rewritten as evidence changes. The `## Timeline` zone is **append-only**, with entries like `- **YYYY-MM-DD** | Source — Summary [Source: who, channel, date]`.
  - Fenced machine tables `## Facts` and `## Takes` sit inside the Markdown. Takes include hunches and bets, and can be superseded.
  - The `system-of-record.md` contract states that Markdown is canonical and the DB is derived. But some state is **DB-only**: page revision history, the withdrawal ledger, the belief ledger, receipts. **Markdown export is therefore not a full backup.**
- **Multi-user, concurrency and access control:**
  - A brain is a database. A *source* is a git repo inside a brain.
  - Per-user OAuth clients get source grants plus `--federated-read`, and isolation is enforced at the SQL layer.
  - Within a shared source, writes can be confined with `--bound-slug-prefixes partners/alice/`.
  - Concurrency uses revision preconditions (`expected_revision`, create-only when the precondition is omitted), durable request receipts, one designated publishing host per worktree, and per-source sync locks.
  - The docs are honest about limits: "The authorization tests exercise specific access paths, not a universal no-leak guarantee"; "Local files and shared database credentials are a different trust boundary". The tutorial's "zero leaks" in fuzz testing is **[unverified]**.
- **Provenance and contradictions:**
  - **Trust tiers** on every fact, page and timeline entry: `user_confirmed`, `operator_curated`, `tool_observed`, `agent_written`, `external_untrusted`, `unknown`. There is also an instruction-detection gate, and "nothing becomes confirmed without a human typing a token at the brain host".
  - Contradictions are handled through compiled truth, source-tier boosts and `takes.active`, plus an **evaluation probe** (`gbrain eval suspected-contradictions`). The probe has an LLM judge compare retrieved chunk pairs, using a cache keyed on content hashes and Wilson confidence intervals, and reports how often unmarked contradictions surface. Contradiction rates are measured, not assumed.
- **Scale.** PGLite up to about 50k pages, Postgres plus pgvector beyond that. Hybrid search uses vectors, keywords, RRF, a source-tier boost and a reranker.
- **Verdict: borrow ideas heavily. Optionally evaluate it later as a read-only retrieval and MCP layer over our repos; don't build on it.**
  - Reasons against using it as the foundation:
    - an operational burden (Postgres, a daemon, OAuth server, crons);
    - DB-only state that breaks "git is the log";
    - a personal-CRM taxonomy;
    - extreme version churn;
    - it is designed around one fat agent per brain.
  - Borrow:
    - the **compiled truth plus append-only timeline** page layout, ideal for project, grant and person pages and for supersession;
    - **trust-tier labels** on agent-written versus external content;
    - **revision preconditions** on replace;
    - **source equals repo**, which matches our separate tier repos;
    - the **contradiction-rate evaluation probe** as a lint metric;
    - the `system-of-record` discipline: every derived table must be rebuildable from Markdown, enforced by a CI script.

### 1.8 basicmachines-co/basic-memory

- **What it is.** A local-first MCP memory server. Markdown files are the source of truth, synced two ways with an SQLite or Postgres index and optional semantic search. Notes carry `## Observations` (`- [category] fact #tag (context)`) and `## Relations` (`- relates_to [[X]]`, typed wikilinks).
- **Maturity.** 4.4k stars, **AGPL-3.0** with a CLA, pushed 2026-10-29, version 0.23 (depends on a FastMCP pre-release). **Basic Memory Teams is a paid cloud product**: shared workspace, roles, invite-only projects, a version per save and an activity feed. Its sync uses rclone, not git. Self-hosting Teams isn't documented.
- **Provenance.** A recent feature (`docs/DOCUMENT_CITATIONS.md`) adds per-observation PDF page locators that emit **OKF-compatible `sources` entries plus footnotes keyed by `sources[].id`**. `locked: true` frontmatter makes the API reject agent edits with HTTP 423. That is API-only and filesystem edits bypass it, but it is a useful convention.
- **Verdict: borrow ideas. Possibly use it as an optional MCP read and search layer for individuals; not as the foundation.**
  - Reasons: AGPL, team features cloud-only and not git-based, and its observation-list format clashes with prose synthesis pages.
  - Borrow the `[category]` observation syntax, which works as an inline epistemic marker, the typed relation lines, and `locked: true` for human-owned pages.

### 1.9 iwe-org/iwe

- **What it is.** A Rust Markdown knowledge-graph tool: LSP for editors, CLI and MCP. It contains no LLM. Its distinctive feature is **machine-checked document schemas** (`.iwe/schemas/*.yaml`): JSON Schema for frontmatter plus a body schema (required sections, order, max tokens per section) checked by `iwe schema validate`, bound to paths with globs. It has an `iwe init --okf` scaffold with OKF conformance schemas.
- **Maturity.** 1.8k stars, Apache-2.0, pushed 2026-10-29.
- **Verdict: borrow, and probably use as a CI validator.** It is a candidate for the deterministic layer of our two-layer lint: frontmatter validity, required sections such as `## Sources` and `## Contradictions`, and page size budgets. Before adopting it we should check that it handles Obsidian `[[wikilinks]]`, because OKF prefers standard Markdown links.

### 1.10 Google Cloud Open Knowledge Format (OKF) v0.2

- **What it is.** A vendor-neutral spec, Apache-2.0, at `GoogleCloudPlatform/open-knowledge-format` (1.2k stars, created 2026-08). The copy under `knowledge-catalog/okf/` is frozen. It defines knowledge as "a directory of markdown files with YAML frontmatter", is designed for corpora "continuously written and maintained by agents", and recommends distributing it as a git repo.
- **Contents:**
  - required `type`;
  - `sources[]` with `id`, `resource`, `title`, `author`, `last_modified`;
  - **per-claim attribution through footnotes whose label is a `sources[].id`**, keyed rather than positional "because agents constantly rewrite these documents";
  - `generated {by, at}` and `verified [{by, at}]`, giving trust tiers unverified, machine-confirmed and human-reviewed;
  - `status draft|stable|deprecated` and `stale_after` (an absolute instant);
  - an actor convention;
  - per-directory `index.md` with no frontmatter, listing entries with descriptions for progressive disclosure;
  - date-grouped `log.md`;
  - lenient conformance: consumers must tolerate unknown keys and broken links.
- **What it leaves out.** OKF deliberately leaves link types to prose: "the specific kind … is conveyed by the surrounding prose", so links are untyped. It has no contradiction or supersession fields and no confidentiality model.
- **Verdict: adopt as the base frontmatter vocabulary and extend it.** Our extension namespace would cover epistemic status, `supersedes` / `superseded_by`, `contradicts`, `tier`, and typed relations if we want them. Using OKF names instead of inventing our own gives us interoperability with Basic Memory, IWE and future tools.

### 1.11 Graphiti / Zep

- **What it is.** A temporal context-graph library: episodes (raw input, the provenance) → entities and fact edges with **bi-temporal validity** (`valid_at`/`invalid_at` for when a fact was true, `created_at`/`expired_at` for when the system recorded it). Contradicted facts are **invalidated, not deleted**. Ontologies can be prescribed (Pydantic) or learned. It needs Neo4j, FalkorDB or Neptune; Kuzu is deprecated. Zep's own engine, Konig, is proprietary.
- **Maturity.** 32.3k stars, Apache-2.0, pushed 2026-10-28. Thoughtworks Radar places it at "Trial". Benchmarks are vendor-reported, and I found **no independent reports of contradiction-handling failures at scale** [gap].
- **Fit.** Poor as a foundation. It has no human-readable synthesis pages, no git review, no Obsidian, and its access model is multi-tenant `group_id` partitioning in a graph DB. Contradiction detection is an LLM judgment made at write time with no human-visible diff.
- **Verdict: borrow the bi-temporal fields as frontmatter or timeline conventions** (`valid_from` / `valid_until` on a claim or status, separate from the git commit time, which is our transaction time) and the idea of invalidating rather than deleting. Ignore it as infrastructure.

### 1.12 Mem0, Letta

- **Mem0.** 68k stars, Apache-2.0. A vector-first extracted-memory layer keyed by `user_id` / `agent_id`, for personalisation in chat apps. It doesn't support temporal reasoning natively, according to third-party comparisons. **Ignore**: wrong problem (user preferences, not a curated research corpus), and its memory can't be reviewed in a git diff.
- **Letta.** 25k stars, Apache-2.0. A stateful-agent runtime. Notably, **Letta Code's MemFS (since 0.15, "context repositories") is a git-backed set of Markdown files with YAML descriptions. Every memory edit is a commit, background "dreaming" and "memory doctor" subagents write through git worktrees, and several agents can share one repo** (per docs.letta.com). That is independent confirmation of our architecture. It is aimed at an agent's own memory, not a group wiki, and hosted repos are a cloud feature. **Borrow** the idea of background maintenance agents working in separate worktrees. **Ignore** it as a platform.

### 1.13 Smaller team-oriented projects (all tiny, all **[unverified]** claims)

| Project | Stars | Licence | Idea worth noting | Verdict |
|---|---|---|---|---|
| np6126/mcp-llm-wiki | 3 | MIT | Git-backed MCP server. **ETag optimistic concurrency** on `wiki_save` (atomic write, commit, push). **Custom git merge drivers** for the two hotspots `index.md` and `log.md`. `sources: [{path, etag}]` per page, so lint flags `source_missing`/changed with a graded message. Lint never mutates. Multi-VM end-to-end tests. | Borrow: ETag/hash-pinned sources, merge drivers for hotspots |
| redmizt multi-agent toolkit (gist now 404; repo missing) | – | – | 6 parallel Claude Code agents plus 50 subagents: 5 domain wikis instead of 1; YYYYMMDDNN ids; **file-based capability tokens** ("env vars don't persist between Claude Code Bash calls"); **8 PreToolUse hooks for access control ("Rules-as-text fail under cognitive load; hooks don't")**; file-pattern locks with TTL; a "Twice Rule" (anything fixed twice gets automated). | Borrow: enforce with hooks and CI, not prose |
| AEVYRA/llm-wiki-coordination | 12 | MIT | Six multi-agent failure modes (see §2). A `wiki/agents/` folder: stale invalidation, "soft canonical", `rev:` tracking, an async dialogue thread, an honest back-channel kept apart from the canonical voice, open questions that persist across sessions. | Borrow: open-questions file, one shared entry file for all agents |
| masumi-network/Citadel | 16 | Apache-2.0 | One "seat" per human, a distinct seat-bound token per agent process. Agents capture into a private seat space; **reaching shared org memory takes an explicit promotion step**; "Knowledge Conflicts" are opened instead of silently merged. | Borrow: promotion gate as an optional pattern for raw personal captures |
| junbjnnn/llm-wiki | 13 | none | Team wiki inside the project repo; PRDs, ADRs, runbooks; AGENTS.md is tool-agnostic. | Ignore (inactive since 2026-04) |
| vitalii-ivanov-rakuten (comment only) | – | – | Team wiki as a **git submodule** in each personal vault; each developer forks and Claude opens PRs upstream; `@import index.md` in `~/.claude/CLAUDE.md`; path-scoped `~/.claude/rules`; frontmatter `confidence: high/medium/speculative`, `status: active/superseded/archived`, `contradictions: [...]`, `open-questions: [...]`. | Borrow: frontmatter fields, submodule distribution |
| AgriciDaniel/claude-obsidian | 16k | MIT | `[!contradiction]` callouts instead of overwriting; **per-file locking added after "two agents ingesting at once could corrupt a page mid-write"**; the lock only covers cooperating local writers. | Borrow: contradiction callout syntax (Obsidian-native) |
| atomicstrata/llm-wiki-compiler | 2.2k | MIT | Roadmap: "evals, and rollback/audit". | Watch |
| open-gitagent/gitagent | 739 | MIT | Git-native agent definitions with an llm-wiki template. | Ignore |
| Pratiyush/llm-wiki | 401 | MIT | Synthesis prompt structure Summary → Key Claims (falsifiable) → Connections → Contradictions. | Borrow the page template |

---

## 2. Failure modes and lessons from people running these at scale or in teams

Sources are commenters on the Karpathy gist (K) or the rohitg00 gist (R), or the named project. Almost all of it is anecdotal and self-reported.

### Concurrency and multiple writers

1. **Concurrent ingest silently forks the wiki.** Parallel plan steps read the same index snapshot and each *create* a page for the same concept (`eori` and `eori-number`). In one backfill, 38% of pages were semantic near-duplicates. Putting the LLM call behind a lock starved the queue. **The fix: reason outside any lock, then claim slugs with an atomic conditional write** (`status: planned`, `claimed_by` as a *set*). If the claim fails, the create becomes an update. Duplicates dropped to about 0. (huachen-wang, K)
2. **Git merge ≠ correct merge.** Two agents write the same decision in different words, and git merges both cleanly into a duplicate. **Make concurrent writes commute** (append-only, one entry per line, one writer per file or section). Use a deterministic merge driver for genuine collisions, **never an LLM resolver**. Keep a grep dedup before writing, permanently. Locks are a symptom; partitioning removes the contention. (watsonrm, K)
3. **Parallel compile: naming collisions.** Pre-lock slugs before fan-out. (cablate)
4. **Mid-write corruption** when two agents ingest at once, fixed with per-file locks (claude-obsidian v1.7). LLM daemons writing to the same files as human editors caused race conditions and data loss, fixed with block-level OCC on Logseq (MarcoPorcellato, K). Last-write-wins "destroys context" with three or more concurrent agents (plundrpunk, K).
5. **Hidden parallel work across agents.** Agent A writes a concept page on Tuesday, B writes a similar one on Friday, and both end up in the index. Per-agent entry files (CLAUDE.md, CODEX.md, GEMINI.md) drift apart. One agent's `lifecycle: canonical` is just that agent's self-attribution. Open questions die in chat. (AEVYRA, K)
6. **One writer per layer; all writes via PR; publishing is a tag fast-forward by an operator.** "Two agents never contend for the same page because no two roles share a page type." (pradocabreroalejandro, K, production ERP wiki with several operators)
7. **Sync conflicts** (iCloud, Obsidian Sync) at scale: define in the schema which files the LLM owns and which humans own. (aadjadj-bit, K)

### Trust, errors and autonomy

8. **Errors persist and compound.** "A bad wiki article becomes a prior that poisons future generations." (plundrpunk) "False coherence": errors spread through integration and become internally consistent (dhruvil-1990, K). "Conjectures solidify into facts" (Firsgith, R).
9. **Human corrections get reverted by re-compilation.** Store each human edit as a *pin* (claim, section anchor, `provenance: human`) and re-check it after every regeneration. If a newer source contradicts it, show it to a human; if its section is gone, flag it as orphaned. "Never let source retirement purge human-added content." (huachen-wang, K)
10. **Reviewing the plan catches less than reviewing the diff.** "Review the generated artifact, not the plan." (huachen-wang, K)
11. **Rules written as prompt text fail under cognitive load; hooks don't.** Enforce access and invariants with PreToolUse hooks and CI. (redmizt, K) AutoSci's `writers.yaml` is honestly labelled "not a runtime gate".
12. **Headless runs fail silently on permission rules**, because relative paths stopped matching after `cd`. (HagaiHen, R)
13. **The enterprise view.** "A hallucinated fact isn't a personal inconvenience, it's an audit finding." Some argue for a human validation gate before every wiki update (pnakamura, jurajskuska, K). The DokuWiki founder (cosmocode newsletter 2026-04-15, quoted in K) asks how this works with several users, how anyone can trust the content, and **who an edit is attributed to** when agents rewrite whole sections. Our requirement that agents be fully autonomous goes against this advice. We need strong compensating controls: attribution in commits and frontmatter, CI lint gates, pins, trust tiers, easy revert.
14. **Prompt injection through ingested sources.** gbrain labels connector, web and transcript content `external_untrusted` and flags text that reads like instructions. Nobody in the gists reports an incident, but this is a real risk for autonomous agents ingesting email and web pages.

### Retrieval and scale

15. **`index.md` stops working as the main lookup** at about 100–200 pages (rohitg00, skynet), at about 200–500 (rohitg00 comment), or "in the low thousands" with a well-made index (sturlese). One person had 161 pages from 1,602 sources and the graph view replaced the index around 150 pages (kdsz001) **[unverified]**.
16. **Index one-liners can't surface facts buried in page bodies.** **Union** the index-selected pages with BM25 top-k. No embeddings were needed, and it fixed every recall failure in their eval (huachen-wang).
17. **Production setups at thousands of pages:** about 4,000 concepts (distorx) and about 7,500 notes with a derived SQLite FTS5 trigram index plus 1024-d local embeddings. Integrity guards: a content hash rather than mtime decides real change, a model swap forces a full re-embed, FTS commits independently of embeddings, and deletions are reconciled. Keyword search takes about 0.07 s. "Vault = truth; index = throwaway." **Biggest failure mode: drift, the agent under-updating cross-references on ingest.** "The lint pass is not optional; we run it on a timer." Team sharing is "just a private git repo … Git history doubles as the log.md audit trail." (distorx, K)
18. **Routing by topic branch** (a ROUTING.md mapping branches to pages, with BM25 only over 1–2 selected branches) keeps latency flat as the wiki grows: 24 ms against 191 ms p95 at 10k pages (paulmchen/Synthadoc, K) **[unverified]**.
19. **Per-domain sub-schemas.** One CLAUDE.md broke after the second domain. Use a top-level file plus per-domain context files loaded on demand. (mpt.solutions, "Cloud Codex", Aug 2026)
20. **Changelog/reference drift.** The agent appends a dated changelog entry but leaves the reference section describing the old state. "A migration isn't done when the changelog says so." A **drift linter for retired terms** runs pre-commit and on cron, and caught 9 stale files after one migration. Silent contradictions came from two entity pages with different names, which led to double counting; fixed with **one file per entity named by its canonical link text**. Orphans outpaced "occasional" lint at about 300 pages, so lint weekly. (mpt.solutions) This is directly relevant to project and grant status pages.
21. **Ingestion-order bias.** The wiki leans toward early sources. Lint in batches with a persistent scratchpad and a **randomised source order** to surface contradictions that ordered passes miss. (brtrx, K)
22. **Decisions consumed most of the LLM tokens.** Choosing a folder, deciding whether a note is the same subject, merge or not, what to link took about 72% of ingest tokens. A small typed classifier for those decisions plus the LLM for prose raised correct-note recall from 62% to 89% on 525 documents and halved ingest time (sassarini-marco, K; zenodo 22898752) **[unverified, single corpus]**.
23. **Write-time entity resolution** (dedup against existing entities) "is where the pattern either compounds or sprawls" (simontaurus, K). "If each write greps for the claim's citation first, you reject the duplicate at write time" (watsonrm).
24. **Lossy compression.** Wiki pages drop caveats, dates, minority views and exact wording. "'Ask the LLM to maintain it' is not an engineering solution unless there are validators, source hashes, span-level citations, regression tests, and human review." (a-a-k, K) This is the sharpest sceptical summary and doubles as a checklist.
25. **Wiki plus RAG beats either alone.** In 7 "tournaments" on a 50k-LOC codebase, the wiki won on deleted or archived logic (institutional memory), a "mostly finished" wiki scored 17% worse than a fully compiled one, and wiki-for-context plus RAG-for-verification never lost (Eyaldavid7, K) **[unverified]**.

### Confidentiality

26. **Visibility labels filtered at query time eventually betray you.** Separate by construction and compile a separate wiki from only the permitted sources. (huachen-wang, K)
27. **A consolidated store leaks across roles** (the example: an intern sees compensation details). Mitigations: per-user credential injection so the agent acts as the individual, human-approved and attributed writes, and enforcement at read and write time rather than through audits. The open gap: **synthesised answers that combine pages with different scopes** (PromptQL). Our tier repos solve storage, but we still need a rule that a higher-tier agent may not write derived content into a lower-tier repo.
28. **Sensitive material in institutional or HE settings** (NDA, student data, grant reviews). One researcher runs a local model for sensitive folders and Claude for the rest, with `.claudeignore` exclusions (trox, K). This is relevant to our owner and leadership tiers, which may need a policy on which LLM provider may read them.

### Lifecycle and maintenance

29. **Forgetting or decay is the wrong primitive for research and decision memory.** Use explicit supersession: the old page stays with a header pointing to its replacement (anonymous, R). **Tell supersession (facts) apart from disagreement (opinions or results)**: keep both sides in a Disagreements section (HagaiHen, R). **Contradictions are research opportunities.** Turn high-confidence conflicts into open-question tasks (Firsgith, R).
30. **Lint noise kills lint.** At 85% false positives nobody reads it (cablate). **The bookkeeping backlog should write itself.** Log every unanswered query to a miss log and fold it into a demand-ranked ledger (pradocabreroalejandro). This is useful for onboarding and FAQ coverage.
31. **The schema needs an owner and an amendment process.** Agents propose changes with evidence, humans approve, and the schema's git history is the changelog. "'Co-evolved by the whole team' without this decays into 'describes nothing.'" (pradocabreroalejandro)
32. **Different readers value different parts of a source.** "A PM … doesn't need 80% of the technical documentation." (devsarangi2, K) This argues for per-audience views or queries over one shared compiled wiki, not separate ingests per person.

---

## 3. Is any system a better foundation than git plus Markdown?

| Requirement | git+MD (own) | gbrain | Basic Memory | Graphiti/Zep | Mem0 | Letta MemFS |
|---|---|---|---|---|---|---|
| Obsidian MD+YAML in git | ✔ | ✔ (canonical) + DB-only state | ✔ files; sync via rclone | ✘ | ✘ | ✔ (agent memory) |
| Per-claim citations | own convention (OKF footnotes) | timeline `[Source: …]`, facts | OKF footnotes (new) | episode provenance per edge | ✘ | ✘ |
| Contradiction/supersession | own convention | compiled truth, takes supersede, eval probe | ✘ | ✔ bi-temporal invalidation | partial | ✘ |
| Git history as log | ✔ | partial (DB revision history) | ✘ (version per save in cloud) | ✘ | ✘ | ✔ |
| Concurrent human+agent writers | needs conventions + CI | ✔ revision preconditions (DB-mediated) | cloud Teams (paid) | DB | DB | worktrees |
| 3 tiers as separate repos | ✔ trivially | ✔ sources + OAuth grants | workspaces (cloud) | group_id | user_id | per-agent repos |
| >2000 sources/yr retrieval | needs added FTS/hybrid | ✔ | ✔ | ✔ | ✔ | n/a |
| Ops burden | lowest | high | medium | high (graph DB) | medium | medium/cloud |
| Licence | – | MIT | AGPL | Apache | Apache | Apache |

**Conclusion.** None of these beats a git and Markdown wiki as the *system of record* for our requirements. The one capability we can't get from git and Markdown alone is retrieval at scale. Add it as a **derived, rebuildable index**: ripgrep first, then SQLite FTS5 or BM25, then optional local embeddings. Expose it as a CLI and possibly an MCP tool. gbrain or Basic Memory could serve as that read-only layer later, but neither should own the data.

---

## 4. Concrete recommendations for our design

1. **Frontmatter base: OKF v0.2.** Use `type`, `title`, `description`, `sources[{id, resource, title, author, last_modified, hash}]`, `generated{by: agent/model, at}`, `verified[{by: human:<id>, at}]`, `status`, `stale_after`. Add our extension fields: `epistemic: fact|reported|inferred|hypothesis|speculation|disputed`, `supersedes` / `superseded_by`, `contradicts: [...]`, `tier`, `owner`, `valid_from` / `valid_until` (Graphiti-style valid time), `open_questions`.
2. **Per-claim citations.** Use footnotes whose label is a source-summary page id or `sources[].id`, following OKF §5.1, lucasastorian and Basic Memory. Add page or section locators. A source-summary page records the raw file's content hash (mcp-llm-wiki, distorx), so lint can flag changed or missing sources.
3. **Page shape for status-type pages** (projects, grants, people, decisions): **compiled truth above, append-only dated timeline below** (gbrain). Supersession happens by rewriting the compiled truth and appending a timeline entry. Old decisions get `status: deprecated` with `superseded_by`; never delete them.
4. **Contradictions.** Use Obsidian `> [!contradiction]` callouts on the page plus a `contradicts` field (claude-obsidian, vitalii). Separate *supersession* (facts) from *disagreement* (results and opinions); disagreements stay visible (HagaiHen). Each unresolved contradiction becomes an open-question entry (Firsgith, AEVYRA).
5. **Concurrency model:**
   - each agent run works on a branch or worktree;
   - writes are partitioned by page type or role (pradocabreroalejandro);
   - timelines are append-only;
   - **slugs are reserved before generation** (huachen-wang, cablate);
   - search dedup runs before every create (watsonrm);
   - rebase-and-retry on push, with optimistic checks of the expected blob SHA (mcp-llm-wiki, gbrain);
   - **`index.md` is generated deterministically by a script or CI from frontmatter `description`**, not hand-edited by agents, which removes the main hotspot;
   - no `log.md`, since git history is the log; commit messages carry structured trailers such as op, sources and agent.
6. **Tiers.** Use three repos, as planned. The rule, from huachen-wang and PromptQL: **a wiki is compiled only from sources at its tier or below**. Higher tiers may link down to lower-tier pages, never the reverse. An agent session holding a higher tier must not write derived prose into a lower-tier repo. Enforce this with hooks and CI path checks, not prose (redmizt). Decide per tier which LLM provider may read the content (trox).
7. **Human edits.** Use `locked: true` (Basic Memory) for human-owned pages. Store human corrections as **pins** that every re-generation must satisfy (huachen-wang).
8. **Lint.** Two layers (cablate):
   - Deterministic, in CI on every push: schema validation (IWE `schema validate` or a custom script; frontmatter JSON Schema plus required sections), broken links, orphans, uncited claims, uncited sources, changed source hashes, stale_after expiry, retired-term drift (mpt.solutions), reverse-link symmetry (AutoSci).
   - LLM, scheduled: contradictions sampled in **random source order** (brtrx), stale claims, near-duplicate pages, and a contradiction-rate probe (gbrain).
   - Tune for precision: no more than about 15% noise.
9. **Retrieval roadmap:** per-directory `index.md` (OKF §8), then **index ∪ ripgrep/BM25** (huachen-wang), then FTS5 plus local embeddings as a rebuildable derived index (distorx), then optional routing by domain (paulmchen). Log unanswered queries to a miss ledger (pradocabreroalejandro). It feeds onboarding coverage.
10. **Schema governance.** Schema files (YAML entities, edges, writers) are separate from the CLAUDE.md prose (AutoSci). The schema has a named owner and an amendment-by-PR rule (pradocabreroalejandro). Use one shared AGENTS.md/CLAUDE.md for all agent harnesses to avoid per-agent drift (AEVYRA), plus per-domain sub-files loaded on demand (mpt.solutions).
11. **Trust labels.** Separate `generated.by` (agent) from `verified` (human). Mark ingested external content such as email and web as untrusted input that can't issue instructions (gbrain memory-trust).
12. **Things not to adopt:** numeric confidence floats, Ebbinghaus forgetting or decay, LLM-resolved merge conflicts, an append-only `log.md` with many writers, auto-commit per tool call, query-time visibility filtering inside one repo.

---

## 5. Gaps and unverified items

- Every performance and scale number from the gist comments and READMEs is self-reported: gbrain's 155k pages and "zero leaks", agentmemory's 95.2% LongMemEval, nashsu's 58→71% recall, huachen-wang's 38% duplicates, sassarini's 62→89%, paulmchen's latency figures, Eyaldavid7's tournament results. I ran no code.
- I found **no documented case of an ML research group running a shared LLM-maintained wiki**. The closest are a single-user research tool (AutoSci), an HE researcher's personal setup (trox), and company or ops deployments (huachen-wang, pradocabreroalejandro, distorx). We would be early.
- The redmizt multi-agent toolkit gist and repo now return 404, so I have only the comment summary.
- "Karpathy's LLM Wiki Doesn't Work for Teams" (YouTube, linked in K) was not viewed.
- I didn't check IWE's support for Obsidian `[[wikilinks]]` (OKF prefers `.md` links).
- I didn't read Basic Memory Teams' roles and permissions page or its self-hosting status in full. It appears to be cloud-only.
- Graphiti: I found no independent evidence of how well it handles contradictions at scale.

## 6. Key links

- rohitg00 gist: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2 ; agentmemory: https://github.com/rohitg00/agentmemory
- Karpathy gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (key comments: huachen-wang 2026-08-17, watsonrm 2026-06-05, pradocabreroalejandro 2026-07-12, distorx 2026-06-21/30, AEVYRA 2026-04-29, vitalii-ivanov-rakuten 2026-04-10, redmizt 2026-04-12, a-a-k 2026-05-02, brtrx 2026-05-28, sassarini-marco 2026-10-15)
- AutoSci (ex-OmegaWiki): https://github.com/PKU-DAIR/AutoSci ; paper https://arxiv.org/abs/2605.31468
- nashsu/llm_wiki: https://github.com/nashsu/llm_wiki
- lucasastorian/llmwiki: https://github.com/lucasastorian/llmwiki
- obsidian-claude-pkm: https://github.com/ballred/obsidian-claude-pkm
- llm-atomic-wiki: https://github.com/cablate/llm-atomic-wiki
- gbrain: https://github.com/garrytan/gbrain (docs/tutorials/company-brain.md, docs/architecture/system-of-record.md, docs/guides/compiled-truth.md, docs/guides/memory-trust.md, docs/guides/concurrent-writes.md, docs/contradictions.md)
- Basic Memory: https://github.com/basicmachines-co/basic-memory ; Teams: https://docs.basicmemory.com/teams/about
- IWE: https://github.com/iwe-org/iwe (docs/document-schema.md, docs/okf.md)
- OKF: https://github.com/GoogleCloudPlatform/open-knowledge-format (SPEC.md v0.2)
- Graphiti: https://github.com/getzep/graphiti ; Mem0: https://github.com/mem0ai/mem0 ; Letta MemFS: https://docs.letta.com/concepts/memfs
- mcp-llm-wiki: https://github.com/np6126/mcp-llm-wiki ; Citadel: https://github.com/masumi-network/Citadel ; AEVYRA: https://github.com/AEVYRA/llm-wiki-coordination ; claude-obsidian: https://github.com/AgriciDaniel/claude-obsidian
- mpt.solutions write-up: https://www.mpt.solutions/karpathys-llm-wiki-works-heres-what-broke-when-i-ran-it-at-real-scale/
- PromptQL company-brain leaks: https://www.sean-weldon.com/blog/2026-09-08-your-company-brain-will-leak-secrets-how-we-stopped-it-for-big-banks-tanmai-gopal-promptql
