# Prior art C: retrieval and search over a local Markdown wiki

Research date: 2026-10-29. Scope: search and retrieval tools that Claude Code agents (via CLI or MCP) and humans can use over a git-hosted Markdown and YAML-frontmatter wiki that works in Obsidian, at a scale of more than 2000 sources and several thousand pages.

Method: I read READMEs and docs through the `gh` API and WebFetch, searched issue trackers with `gh search issues`, and ran several WebSearch queries. I did not install or run any tool. Star counts and push dates come from the GitHub API on 2026-10-29. Claims I could not check against primary sources are marked **[unverified]**.

---

## 1. Framing: what actually stops scaling

- **Raw grep speed does not run out.** ripgrep over 5,000 Markdown files of about 50 MB takes well under a second. The two things that do run out are **recall** (vocabulary mismatch: the page says "Gaussian process" and the query says "GP surrogate") and **context budget** (a common term returns 300 hits, and the agent reads too many files).
- **A flat `index.md` runs out first.** At about 30 to 50 tokens per one-line entry, 5,000 pages come to roughly 150k to 250k tokens, too much to load. Karpathy's own wiki is about 100 articles and 400K words, and he says the LLM navigates it "just fine" from index files alone. Our target is 30 to 50 times that size. (Source: secondary coverage of the April 2026 gist, for example [VentureBeat](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an) and [towardsai](https://pub.towardsai.net/andrej-karpathy-killed-rag-or-did-he-the-llm-wiki-pattern-7824d876e790).)
- **What we need is ranked retrieval (BM25 plus optional vectors) and hierarchical catalogs,** not a different storage format. Every serious tool below keeps the Markdown as the source of truth and builds an index that can be thrown away and rebuilt. That fits our git setup.

## 2. Claude Code native capabilities (baseline)

Source: https://code.claude.com/docs/en/memory (fetched 2026-10-29).

| Feature | Fact (quoted or paraphrased from the docs) | Relevance |
|---|---|---|
| CLAUDE.md hierarchy | Files above the working directory load at launch. "Files in subdirectories load on demand": a subdirectory's CLAUDE.md loads once Claude reads, writes or edits a file in that subdirectory. | You can put a per-folder `CLAUDE.md` (for example in `sources/` and `concepts/`) with local conventions or a mini-catalog. It costs context only when an agent works in that folder. |
| `@path` imports | Relative and absolute paths. "Imported files can recursively import other files, with a maximum depth of four hops." Imports "don't reduce its context cost". | **Do not** `@import` index.md. It would load in full every session. |
| Size guidance | "target under 200 lines per CLAUDE.md file" | Keep the CLAUDE.md for the wiki to schema and workflow. The catalog goes elsewhere. |
| `.claude/rules/*.md` with `paths:` frontmatter | A rule loads when Claude reads, writes or edits a matching file. | Good for type-specific page conventions (source pages, concept pages). |
| Auto memory | "first 200 lines or 25KB" loaded per session | Per-user and per-repo. Not a group knowledge store. |
| Skills | Load only when invoked or judged relevant | The right place for the "how to search the wiki" procedure. |
| Search | None built in beyond the Grep and Glob tools (ripgrep under the hood) | Native tools give exact search, no ranking. |

Takeaway: Claude Code has no semantic or ranked search. Grep, Glob and Read are excellent for exact lookups. Ranked search has to come from an external CLI or MCP server.

## 3. Candidate tools: details

### 3.1 qmd (tobi/qmd), the strongest fit

- **Repo:** https://github.com/tobi/qmd, MIT license, about 30.7k stars, created 2025-12-08, last push 2026-10-15, latest release v2.8.3 (2026-08-16). 241 open issues. npm package `@tobilu/qmd`. Needs Node >= 22 or Bun >= 1.0.
- **What it does:** three search modes.
  - `qmd search` is BM25 over SQLite FTS5. **No models needed.**
  - `qmd vsearch` is vector search with sqlite-vec.
  - `qmd query` is hybrid: query expansion with a fine-tuned 1.7B model, then BM25 and vector search, merged with RRF, then reranking with Qwen3-Reranker-0.6B and a position-aware blend.
  - Collections are globs over directories. **"Context"** is a tree of path-prefix descriptions returned with results, which maps naturally to wiki folders.
- **Models:** all local GGUF via node-llama-cpp, downloaded from HuggingFace to `~/.cache/qmd/models/`:
  - embeddinggemma-300M (about 300 MB)
  - qwen3-reranker-0.6b (about 640 MB)
  - qmd-query-expansion-1.7B (about 1.1 GB)

  The embedding model can be swapped (for example Qwen3-Embedding-0.6B for multilingual or German content) via `QMD_EMBED_MODEL` or `index.yml`. **No API embeddings are supported. Everything is local**, so nothing leaves the machine. Chunks are 900 tokens with 15% overlap.
- **Index storage:** `~/.cache/qmd/index.sqlite`, config at `~/.config/qmd/index.yml`. Alternatively, `qmd init` creates a project-local `.qmd/index.yml` and `index.sqlite`. Commit the yml and gitignore the sqlite. A project-local config that travels with `git clone` is "trust-gated" (`qmd trust`) for update hooks.
  - Open issue #1077 says `qmd mcp` bypasses that trust gate.
- **Incremental updates:**
  - `qmd update` rescans and content-hashes files, and reports indexed, updated, unchanged and removed counts.
  - `qmd embed` embeds only pending chunks.
  - A per-collection `update:` hook (for example `git pull --ff-only`) runs before re-indexing.
  - So "pull, then `qmd update && qmd embed`" is the whole sync story. It fits a git post-merge hook. Each user keeps a private, derived index.
- **MCP:** tools `query`, `get`, `multi_get`, `status` and `metadata`. Transport is stdio, or HTTP with `qmd mcp --http --daemon` (default port 8181) to keep models loaded. The HTTP endpoint also offers plain `POST /query`, which suits a Mattermost bot.
- **Frontmatter awareness:** partial and opinionated.
  - Typed metadata filtering exists, but only for a **namespaced `qmd: metadata:` frontmatter block**. Ordinary frontmatter keys are **not** filterable.
  - Frontmatter is otherwise indexed as body text. Open issue #975 reports that frontmatter gets embedded and becomes the top hit.
  - Our options are to mirror selected keys under `qmd.metadata` or to accept text-only matching.
- **Wikilink awareness:** none found. No backlink or graph features (searched the README and issues).
- **Maturity and risks** (from open issues):
  - #1088: on CPU-only hosts the MCP server's 5-minute idle model unload causes 5 to 27 minute queries or empty results. A user patched the dist files.
  - #942: concurrent invocations each load the models, which exhausts RAM.
  - #763: embedding fails on x86 CPUs without AVX.
  - #897: silent garbage vectors at 512-token batch boundaries.
  - #673: embed has a hardcoded 30-minute session limit on large corpora.
  - #935: embed fails with DisposedError but exits 0.
  - Overall: very active and popular, but a fast-moving, sharp-edged v2. **The BM25 path (`qmd search`) avoids all of the model issues.**
  - Resident memory with all three models is about 3 to 4 GiB (#1088). A query takes 0.3 to 9 s once the models are warm on CPU.
- **Scale:** no published numbers for thousands of documents (none found **[unverified]**). An old issue (#219) mentions a 4.6 GB index. Our corpus, a few thousand pages plus sources, is small for SQLite FTS5 and sqlite-vec. Expect the first embed of the sources on CPU to take a while (the order of an hour is plausible **[unverified]**).
- **Ecosystem:** Karpathy and the LLM-wiki community use it as the de facto search layer ([VentureBeat](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an) and others). A "qmd search" Obsidian community plugin exists (https://community.obsidian.md/plugins/qmd-search, **not examined**).

### 3.2 Basic Memory (basicmachines-co/basic-memory)

- **Repo:** AGPL-3.0, about 4.4k stars, very active (push 2026-10-29, v0.24.1 on 2026-10-23). Python, installed with `uv tool install`. Has a commercial cloud offering.
- **What it does:**
  - An MCP server with tools `bm_write`, `bm_read`, `bm_edit`, `bm_move`, `bm_delete`, `bm_search`, `bm_list`, `bm_find`, `bm_context` (graph traversal) and `bm_schema`.
  - Markdown with a **specific grammar**: "Observations" (`- [category] fact #tag`) and "Relations" (`- relation_type [[Target]]`). Bare `[[links]]` index as `links_to`.
  - SQLite index locally (Postgres in the cloud). A file watcher keeps it in sync.
  - Hybrid FTS and vector search with optional cross-encoder rerank.
- **Embeddings:**
  - The default is FastEmbed (local ONNX) with `BAAI/bge-small-en-v1.5`, 384 dimensions.
  - OpenAI is "recommended" in the docs. LiteLLM support is experimental. Any OpenAI-compatible endpoint works, so Voyage via LiteLLM is likely possible **[unverified]**.
- **Wikilinks and frontmatter:** yes. This is the most graph-aware option.
- **Blocking concerns for us:**
  1. **It writes to your files.** "Basic Memory writes a `permalink` into any Markdown note that arrives without one the next time it's indexed", and "as of v0.24 there is no setting to turn permalinks off" ([docs](https://docs.basicmemory.com/concepts/knowledge-format)). With 10 to 30 people each running it against their own clone, this produces git churn and merge conflicts unless every page already has a `permalink:`.
  2. It imposes its own page grammar, which competes with our own wiki schema.
  3. AGPL. Fine for internal use, but it constrains redistributing a modified bot.
  4. Its write tools would bypass our agent workflow and conventions. We would want read-only use only.
- **Index location:** probably `~/.basic-memory/` **[unverified]**. Outside the repo either way.
- **Verdict:** good ideas to borrow (typed relations, graph context tool, schema validation), but don't adopt it as the engine.

### 3.3 Obsidian-native search and the Obsidian CLI (human side)

- **Official Obsidian CLI**, shipped in 1.12 (February 2026). Docs: https://obsidian.md/help/cli.
  - Commands include `search`, `search:context` (grep-style, JSON output), `backlinks`, `links`, `unresolved`, `orphans`, `deadends`, `tags`, `properties` and `property:read/set`.
  - **Requires the Obsidian desktop app to be running.** That rules it out for headless servers and the bot.
  - Useful for a human's local Claude Code session. kepano/obsidian-skills (about 50k stars, MIT) ships an agent skill for it.
- **Omnisearch** (scambier, GPL-3.0, about 2.2k stars, active).
  - BM25 via MiniSearch, plus PDF and OCR text through Text Extractor.
  - An **opt-in local HTTP server** lets external tools query it. cyanheads' MCP server uses it as a backend.
  - Index lives in Obsidian's cache. Recommended plugin for humans.
- **Smart Connections** (brianpetro, about 5.5k stars, "source available", license NOASSERTION, so check it).
  - A local embedding model, reportedly `TaylorAI/bge-micro-v2` with 384 dimensions **[unverified]**.
  - Stores embeddings in **`.smart-env/` inside the vault**. That folder **must be gitignored**, since it is reportedly platform-specific and regenerated per device **[unverified]**.
  - Some features are Pro-only.
  - Third-party MCP bridges (for example msdanyg/smart-connections-mcp) read `.smart-env`. Fragile.
  - Nice for humans ("related notes"). Not an agent backend.
- **Obsidian Copilot** (logancyang, AGPL-3.0, about 7.9k stars). Has evolved toward running agents inside Obsidian. Vault QA uses API or Ollama embeddings **[not re-verified for 2026]**. Not relevant as agent infrastructure.

### 3.4 Obsidian MCP servers

| Server | Needs Obsidian running? | Search | License / activity |
|---|---|---|---|
| bitbonsai/mcpvault | No (works directly on files) | `search_notes` with BM25 rerank. Frontmatter and tag tools. | MIT, about 1.7k stars, active |
| cyanheads/obsidian-mcp-server | Yes (Local REST API plugin) | Text, JSONLogic over frontmatter, links and backlinks, Omnisearch BM25 | Apache-2.0, about 700 stars, active |
| MarkusPfundstein/mcp-obsidian | Yes (Local REST API plugin) | Simple and JsonLogic search | MIT, about 4.5k stars |
| coddingtonbear/obsidian-local-rest-api | Yes (it is the plugin; now also MCP) | Same as the REST API | MIT, about 3.1k stars |
| aaronsb/obsidian-mcp-plugin | Yes (plugin) | Semantic operations, HTTP | MIT, about 470 stars |
| jacksteamdev/obsidian-mcp-tools | Yes | Semantic search via Smart Connections | **Archived** (MIT) |

Assessment: for Claude Code, which already has Read, Grep, Glob and Edit on the repo, these servers add little. Their value is for clients that have no filesystem (Claude Desktop, a bot without a checkout). The ones that need Obsidian running are unsuitable for servers.

### 3.5 Other local options

| Tool | What it is | Embeddings | Notes for us |
|---|---|---|---|
| **ripgrep** (BurntSushi, Unlicense, about 70k stars) | Regex search that respects `.gitignore` | none | Already what Claude Code's Grep uses. The MVP engine. |
| **zk** (zk-org/zk, GPL-3.0, about 2.9k stars, active) | Go CLI for plain-text notebooks. SQLite full-text index with boolean, phrase and `title:` syntax. **`[[wikilinks]]` and YAML frontmatter aware.** Has `--link-to` (backlinks), `--linked-by`, `--recursive --max-distance`, `--related`, `--orphan`, `--broken-links`, `--tag` boolean and glob filters, and an LSP. | none | The best fit for *graph and catalog queries* from the CLI with no Obsidian. Index location (`.zk/`) and incremental behaviour were not confirmed **[unverified]**. Needs a `.zk/config.toml` in the repo. |
| **marksman** (MIT, about 3.4k stars) | Markdown LSP with wikilink completion, go-to-definition and references | none | Editor-side link integrity for non-Obsidian users. |
| **SQLite FTS5 + sqlite-vec (DIY)** | sqlite-vec: Apache-2.0, about 8.2k stars, last push 2026-05 (slower cadence) | Any: local (sentence-transformers, FastEmbed, Ollama) or API (Voyage, OpenAI) | The roughly 200-line Python "build your own qmd" route. Full control over frontmatter fields as columns and over a wikilink edge table. Several small MCP servers do exactly this (DimonSmart LocalVectorSearchMcp, sqlite-rag-mcp, QFS, knowledge-rag), all immature **[not examined in depth]**. |
| **LanceDB** (Apache-2.0, about 11.8k stars, very active) | Embedded vector database with full-text and hybrid search | Bring your own | A library, not a tool. Only for DIY. |
| **txtai** (neuml, Apache-2.0, about 13k stars, active) | All-in-one embeddings index (SQLite plus Faiss/HNSW), hybrid BM25, workflows, an API and an MCP option **[unverified]** | Local HF models by default | Capable but Python-framework-heavy. DIY glue needed for frontmatter and links. |
| **semtools** (run-llama, MIT, about 1.9k stars, last push 2026-03) | Rust CLI. `search` does local semantic matching per line, with workspaces for large collections. | Static model2vec `potion-multilingual-128M` (fast, CPU, multilingual). `parse` uses the LlamaParse API and `ask` uses OpenAI. | Interesting as a dependency-light `semantic grep`. Maintenance cadence has slowed. |
| **Khoj** (AGPL-3.0, about 38k stars, last push 2026-08) | Self-hosted "AI second brain" server with Obsidian plugin, chat and agents | Local sentence-transformers by default **[unverified]** | A whole app with its own UX and a Postgres-backed server. Overlaps our design. Reports say the hosted cloud was sunset in 2026 **[unverified]**. Not recommended. |
| **GraphRAG** (Microsoft, MIT, about 36k stars) and **LightRAG** (HKUDS, MIT, about 40k stars) | LLM-extracted entity and relation graphs plus community summaries | Need an embedding provider and many LLM calls at index time | Expensive to index, an opaque derived store, and redundant: **the LLM wiki itself *is* the curated graph and summary layer.** Not recommended. |
| **Orama, Tantivy** | Embeddable full-text and hybrid engines | Optional | Only relevant if building a web UI or search service. |

### 3.6 Embedding providers (Anthropic has none)

- Anthropic's docs state it offers no embedding model and recommend **Voyage AI** (`voyage-3.5`, `voyage-3.5-lite`, `voyage-3-large`) ([docs](https://docs.claude.com/en/docs/build-with-claude/embeddings)). Using Voyage means sending wiki text to a third party, which is a separate data-governance decision.
- Local options that need no data egress:
  - embeddinggemma-300M (qmd default, English-focused)
  - Qwen3-Embedding-0.6B (qmd option, multilingual)
  - bge-small-en-v1.5 (Basic Memory default)
  - bge-micro-v2 (Smart Connections)
  - potion-multilingual-128M static model (semtools, CPU-trivial)
- For an ML group with GPUs, local embeddings are the obvious choice. Also, with a curated wiki of good titles and summaries, **BM25 captures most of the value**. Vectors mainly help with raw sources and synonyms.

## 4. Comparison table

Legend: ✅ yes, ⚠️ partial or caveat, ❌ no.

| Tool | Local on Linux and laptops | Embeddings | Index outside git, rebuildable | Incremental after `git pull` | Wikilinks | Frontmatter | MCP | CLI | Humans | License | Maturity / activity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ripgrep / Claude Grep | ✅ | none | ✅ (no index) | ✅ trivially | ⚠️ regex only | ⚠️ regex only | n/a (built in) | ✅ | ✅ | Unlicense | Rock solid |
| **qmd** | ✅ (Node 22 or Bun; GPU optional; CPU has rough edges) | Local GGUF only (about 2 GB for 3 models) | ✅ `~/.cache/qmd` or gitignored `.qmd/` | ✅ content-hash `update` plus `embed`, git-pull hook | ❌ | ⚠️ filtering only via `qmd.metadata` namespace | ✅ stdio and HTTP | ✅ | ⚠️ CLI, plus third-party Obsidian plugin | MIT | Very popular and active; v2 has many open bugs |
| Basic Memory | ✅ (Python) | FastEmbed local, or OpenAI / LiteLLM | ✅ SQLite outside repo | ✅ file watcher | ✅ (typed relations) | ✅ | ✅ | ✅ | ⚠️ via Obsidian | AGPL-3.0 | Active, commercial backing; **writes `permalink:` into files** |
| zk | ✅ (Go binary) | none | ✅ `.zk/` (gitignore DB **[unverified]**) | ✅ **[unverified]** | ✅ backlinks, recursive | ✅ | ❌ (LSP only) | ✅ | ✅ (LSP / editor) | GPL-3.0 | Mature, active |
| Obsidian CLI | ⚠️ needs desktop app running | none | ✅ (Obsidian cache) | ✅ | ✅ | ✅ | ❌ (skills exist) | ✅ | ✅ | Proprietary app | Official, new (Feb 2026) |
| Omnisearch | ⚠️ inside Obsidian | none (BM25) | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ via HTTP and cyanheads MCP | ❌ | ✅ | GPL-3.0 | Mature |
| Smart Connections | ⚠️ inside Obsidian | Local bge-micro | ❌ by default in `.smart-env/` (gitignore it) | ✅ | ⚠️ | ⚠️ | ⚠️ third-party | ❌ | ✅ | Source-available | Active; partly Pro |
| mcpvault | ✅ (Node) | none (BM25) | ✅ | ✅ | ⚠️ | ✅ | ✅ | ❌ | ❌ | MIT | Young, active |
| cyanheads obsidian-mcp | ⚠️ needs Obsidian and REST plugin | none | ✅ | ✅ | ✅ (via plugin) | ✅ | ✅ | ❌ | ❌ | Apache-2.0 | Active |
| DIY FTS5 + sqlite-vec | ✅ | Any | ✅ | ✅ (our own hashing) | ✅ (our own parser) | ✅ (our own schema) | ✅ (we write it) | ✅ | ❌ | Ours | We maintain it |
| txtai / LanceDB | ✅ | Any | ✅ | ⚠️ DIY | ❌ DIY | ❌ DIY | ⚠️ | ⚠️ | ❌ | Apache-2.0 | Mature libraries |
| semtools | ✅ (Rust) | Static model2vec (CPU) | ✅ | ⚠️ | ❌ | ❌ | ❌ | ✅ | ❌ | MIT | Slowing (last push March 2026) |
| Khoj | ✅ server | Local or API | ✅ | ✅ | ❌ | ⚠️ | ⚠️ | ❌ | ✅ web and Obsidian | AGPL-3.0 | Large; direction uncertain |
| GraphRAG / LightRAG | ✅ | API or local, plus heavy LLM indexing | ✅ | ⚠️ costly | ❌ (builds its own graph) | ❌ | ⚠️ community | ⚠️ | ❌ | MIT | Research-grade, active |

## 5. Recommendation

### MVP (now, up to a few hundred sources): no search engine, but design for one

1. **Engine: ripgrep, through Claude Code's Grep and Glob.** Nothing to install, and nothing goes stale.
2. **Make the catalog hierarchical from day one.**
   - `index.md` holds top-level sections plus links to per-area catalogs (`sources/_index.md`, `concepts/_index.md`, `people/_index.md` and so on).
   - Each catalog entry is one line: `[[page]]: one-line summary #tags`.
   - Agents maintain these. That keeps every catalog under a few thousand tokens as the wiki grows.
3. **Make pages search-friendly.** These conventions pay off later with any engine:
   - Required frontmatter `title`, `type`, `tags`, `aliases`, and a one-sentence `summary`. A grep for `^summary:` gives a cheap ranked-free catalog.
   - Stable kebab-case filenames.
   - Wikilinks by filename.
   - Avoid giant pages; split by heading. Search tools chunk by around 900 tokens.
4. **A tiny repo script** (in our own repo, no install) that emits backlinks and orphans from `rg -o '\[\[[^]|#]+'` is enough for link maintenance. Humans get backlinks free in Obsidian.
5. **For humans:** Obsidian plus Omnisearch is optional. If anyone uses Smart Connections, add `.smart-env/` to `.gitignore` up front. Also gitignore `.obsidian/workspace*`.

### At the >2000-sources milestone: adopt qmd, with zk as an optional graph helper

- **qmd is the closest off-the-shelf match.** MIT, built for exactly this pattern, CLI and MCP, local models with no egress, a derived SQLite index outside git, and content-hash incremental `update` with a built-in `git pull` hook. The folder "context" feature maps to wiki areas.
- **How to deploy it:**
  - Each user: `qmd collection add <repo> --name wiki --mask "**/*.md"` (plus `qmd context add` per top-level folder). Add a `post-merge` git hook running `qmd update && qmd embed`.
  - Alternatively, commit a project-local `.qmd/index.yml`, gitignore `.qmd/*.sqlite`, and have each user run `qmd trust` once.
  - Server or bot: one long-running `qmd mcp --http --daemon` on a machine with a GPU. Pin the version and keep the models resident; see issue #1088.
  - **Default agents to `qmd search` (BM25, no models).** Use `qmd query` (hybrid with rerank) when the BM25 results are poor or the question is conceptual. This sidesteps most of qmd's open model and CPU bugs.
  - Mirror 2 or 3 frontmatter keys (`type`, `tags`, `status`) into the `qmd: metadata:` block only if filtered search turns out to be needed. Otherwise rely on folder collections and contexts.
  - Pin the qmd version, because v2 changes fast.
- **zk** for graph questions (backlinks, related, orphans, broken links), if the home-grown backlink script isn't enough. Don't use it as the main search.
- **Fallback if qmd proves too flaky:** a roughly 200-line in-repo Python indexer using SQLite FTS5 (frontmatter as columns, a wikilink edge table) with optional sqlite-vec and a local embedding model, exposed as a CLI plus a minimal MCP server. qmd's design (RRF, context tree, content hashes) is the blueprint.
- **Do not adopt:**
  - Basic Memory: it rewrites files with permalinks and has its own grammar. Borrow its ideas.
  - GraphRAG and LightRAG: redundant with the wiki, and expensive.
  - Khoj: a whole competing app.
  - Obsidian-REST-based MCP servers: they need the app running.

### How agents should query: catalog first, then search, then follow links

Put this in a wiki-search skill:

1. **Exact identifiers** (paper ID, arXiv number, person, filename): use Glob or Grep directly.
2. **Orientation or "what do we know about X":**
   - Read `index.md`, then the relevant area `_index.md` (cheap, curated, high precision).
   - Then run a ranked search: `qmd search` or `qmd query`, or `rg -l` plus a `summary:` grep before qmd exists. Use it for anything the catalog misses.
   - Merge the results and read the top 3 to 5 pages.
3. **Expand along `[[links]]` and backlinks** from those pages (graph hop). Wiki pages are the synthesized layer, so follow them to `sources/` pages only when evidence is needed.
4. **Before creating a page, always search** (catalog plus ranked search on title and aliases) to avoid duplicates.

Rationale: curated catalogs give precision and the editorial "map", while search gives recall over thousands of pages. Catalog-first stays cheap only while catalogs are kept hierarchical. Once a single catalog exceeds about 300 to 500 lines, split it.

## 6. Unverified or open items to check before adopting

- qmd: no public benchmarks for corpora of 5k to 20k files. Do a trial index of a realistic corpus on our own hardware (CPU laptop and a GPU box) and time `update`, `embed` and queries. Check whether frontmatter noise (#975) hurts ranking for our page format.
- qmd: issue #1077 (`qmd mcp` bypasses the trust gate). Matters only if the config is committed to the repo.
- Smart Connections: default model name, `.smart-env` portability, and license terms (NOASSERTION).
- zk: index location and whether its re-index after `git pull` is incremental.
- Basic Memory: index path, and whether pre-populating `permalink:` frontmatter fully avoids rewrites.
- Khoj: the hosted-cloud sunset (single 2026 review) and the default embedding model.
- txtai MCP support.
- The small sqlite-vec MCP servers (DimonSmart, sqlite-rag-mcp, QFS, knowledge-rag) were not examined.

## Sources

- qmd: https://github.com/tobi/qmd (README; issues #1088, #942, #763, #897, #673, #935, #975, #1077, #219)
- Basic Memory: https://github.com/basicmachines-co/basic-memory, `docs/semantic-search.md`, https://docs.basicmemory.com/concepts/knowledge-format
- Claude Code memory: https://code.claude.com/docs/en/memory
- Obsidian CLI: https://obsidian.md/cli, https://obsidian.md/help/cli
- Omnisearch: https://github.com/scambier/obsidian-omnisearch
- Smart Connections: https://github.com/brianpetro/obsidian-smart-connections, https://github.com/msdanyg/smart-connections-mcp
- MCP servers: https://github.com/bitbonsai/mcpvault, https://github.com/cyanheads/obsidian-mcp-server, https://github.com/MarkusPfundstein/mcp-obsidian, https://github.com/coddingtonbear/obsidian-local-rest-api
- zk: https://github.com/zk-org/zk, https://zk-org.github.io/zk/notes/note-filtering.html
- semtools: https://github.com/run-llama/semtools
- Embeddings: https://docs.claude.com/en/docs/build-with-claude/embeddings
- Karpathy LLM wiki coverage: https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an, https://pub.towardsai.net/andrej-karpathy-killed-rag-or-did-he-the-llm-wiki-pattern-7824d876e790
- Khoj: https://github.com/khoj-ai/khoj, https://www.promptquorum.com/power-local-llm/khoj-ai-second-brain-review
- Small sqlite-vec MCP servers: https://www.nuget.org/packages/DimonSmart.LocalVectorSearchMcp, https://mcpservers.org/servers/lyonzin/knowledge-rag
