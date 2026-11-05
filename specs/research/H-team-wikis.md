# Prior art H: team wikis and knowledge products with AI features

Research date: 2026-11-05. Scope: existing team wiki and knowledge products, hosted and self-hostable, that could replace our own thin layer (Claude Code skill + git/Markdown repo + qmd), or sit on top of it as a viewer/editor. Earlier reports (A–E) did not assess this class.

Method: official docs, pricing pages and changelogs fetched with WebFetch; web searches for pricing and data residency where official pages were incomplete. For open-source projects, GitHub metadata via `gh api` (license, stars, last push, releases). For Wiki.js 3 I read the source and design docs on the `scarlett` branch via `gh api` (`backend/modules/storage/git/`, `backend/helpers/storageFiles.ts`, `backend/models/pages.ts`, `dev/specs/mcp.md`, `.claude/rules/{mcp,storage}.md`). Nothing was installed or run. Third-party pricing figures disagree in places; I give ranges and mark them. Claims I could not check are marked **[unverified]**.

Measured against: `00-requirements.md` (R1 Markdown+YAML in git, R3 per-claim citations, R10 autonomous agent writes, R13 three tiers `group` / `leadership` / `owner`, R18 attributable commits, R19 concurrent writers, N1 no DB as source of truth) and the CLAUDE.md principles (KISS, tool independence, derive-don't-store, the repo is complete, standards over inventions).

---

## 0. TL;DR

1. **No product's AI compiles and maintains a wiki the way our ingest/lint loop does.** Every hosted AI feature (Notion AI, Rovo, Glean, Slite, Guru, GitBook Assistant, Outline "AI answers") is **answer/summarise/draft over human-written pages**. GitBook's Agent comes closest: it flags stale docs and proposes edits. The Karpathy loop (read a source, update 10–15 pages, cite every claim, lint) would still be *our* agent, talking to the product through an API or MCP server. So a product replaces the storage, UI and permissions, not the brain.
2. **External-agent writing is now solved by several products.** Official MCP servers with write tools exist for Notion, Confluence (Atlassian Rovo MCP, GA), Outline (built in, since 2026-02-18), Docmost (built in, paid tiers) and **Wiki.js 3** (built in, released 2026-11-01). Wiki.js 3's design is the best fit for an agent: required "reason" per write (becomes the git commit message), optimistic concurrency (`baseVersionId`), str_replace-style edits, an "AI" badge on agent versions, and a suggest-for-review path.
3. **Only git-backed products pass "the repo is complete".** Notion, Confluence, Glean, Slite, Guru, Docmost and BookStack keep content in their own database; export is one-way and lossy. Outline added an **OKF export** (2026-09-04), which is notable because we adopted OKF, but it is still an export, not a round-trip. GitBook Git Sync and Wiki.js 3's git storage are true two-way syncs, but **both rewrite our front matter**: Wiki.js 3 writes a fixed key set (`title, description, published, date, tags, editor, dateCreated`) and drops unknown keys such as OKF `type`, `status`, `aliases`; GitBook adds its own syntax (`{% hint %}`, `SUMMARY.md`, `.gitbook.yaml`).
4. **Permissions fit the tiers well in several products**, often better than "one repo per tier" in UX terms (Outline collections + groups, Confluence spaces, Wiki.js sites/page rules, Docmost spaces). But the core leak risk (R14) is unchanged: an agent acting with Bernd's token reads all tiers either way. Products enforce *who reads*, not *what an agent may copy downward*.
5. **Data protection.** Self-hosting on LMU infrastructure is possible for Outline, Wiki.js, BookStack, Docmost, SilverBullet, Otter Wiki. Among hosted products, EU data residency for Notion is **Enterprise only**; Glean has a ~100-seat minimum. Cost for 30 users ranges from €0 (self-hosted OSS) to ~€585/month (Notion Business) and beyond.
6. **Recommendation: option (2).** Keep the git repo as the source of truth. Do not adopt a product for v1. GitHub's own web UI (already part of N3) plus Obsidian are the v1 viewers. When the group needs a web reader with search and SSO, the best candidate is **Wiki.js 3 in "pull only" git mode, one Wiki.js site per tier repo**: read-only mirror, rebuildable from git, no front-matter rewriting. Reconsider two-way editing only after a spike shows that Wiki.js leaves our files intact. Option (1) would be defensible only if the group drops git-as-provenance; the honest best "replace" pick is **self-hosted Outline**, and §4 says when that would be the better choice.

---

## 1. Comparison

Legend: ✓ yes, ~ partly, ✗ no. "AI maintains" = the product's own AI compiles or updates pages unprompted. "Ext. agent writes" = an external agent (Claude Code) can create/update pages via an official API or MCP server.

| Product | Type / license | AI maintains pages? | Ext. agent writes | Content lives in | Lossless git round-trip | Perms vs 3 tiers | Agent attribution / revert | EU / self-host | ~Cost, 30 users/month |
|---|---|---|---|---|---|---|---|---|---|
| **Notion** (AI, Agents) | hosted, proprietary | ~ (Custom Agents can write on triggers; not a citation-compiling wiki loop) | ✓ official MCP | Notion DB | ✗ (export only) | ✓ teamspaces/pages | ~ page history 90 d on Business; edits under integration/user [unverified] | EU residency **Enterprise only** | €585 (Business €19.50) |
| **Confluence + Rovo** | hosted, proprietary | ~ (Rovo agents draft/update on request) | ✓ Rovo MCP (GA), OAuth, uses Rovo credits | Atlassian cloud | ✗ | ✓ spaces + page restrictions | ✓ page versions; audit log | data residency on paid tiers [unverified]; Data Center being retired [unverified] | ~$165–190 (Standard) + credit overage |
| **Glean** | hosted enterprise search | ✗ (answers over connected sources) | ✗ (not a wiki) | your sources | n/a | inherits sources | n/a | [unverified] | ~100-seat minimum, $50+/user → not viable |
| **Slite** (+ Super) | hosted | ✗ (Ask/answers; stale-doc flags) | ~ API [unverified] | Slite | ✗ | ~ channels | ~ | [unverified] | ~$300–600 |
| **Guru** | hosted | ✗ (answers; verification workflow) | ~ API [unverified] | Guru | ✗ | ✓ collections | ✓ verifier per card | [unverified] | ~$750 ($25/user) |
| **GitBook** | hosted, proprietary (old OSS CLI is GPL, abandoned) | ~ Agent flags stale content, proposes edits | ✓ via git (and API) | GitBook + **Git Sync** repo | ~ two-way, but GitBook syntax + `SUMMARY.md` | ~ space-level; public-docs oriented | ✓ via git commits | US vendor hosting [unverified] | $425 (Essential $65 + $12/user) – $609 (Ultimate) |
| **Outline** | BSL 1.1 → Apache-2.0 in 2030; 41k★; pushed 2026-11-05 | ✗ (AI question answering) | ✓ built-in MCP (read/write, comments) + full API | Postgres | ~ **OKF export** (one-way) | ✓ collections + groups + doc sharing | ✓ revision history; agent = token's user | ✓ self-host (Docker) | cloud $79 flat; self-host CE €0, Business $120 ($4/user, AI via OpenAI) |
| **Wiki.js 3** | AGPL-3.0; 29k★; 3.0.1 stable 2026-11-01, 3.1.0 on 2026-11-05 | ✗ (explicit non-goal) | ✓ built-in MCP: create/update/suggest/comment, history tools | Postgres **+ git storage target** (commit per change) | ~ two-way, **drops unknown front matter** | ✓ sites, groups, page rules, approvals | ✓ per-user commit author; `reason` = commit msg; "AI" badge | ✓ self-host | €0 |
| **Docmost** | AGPL-3.0 + EE dirs; 22k★ | ✗ (AI features in paid tiers) | ✓ built-in MCP (Business/Enterprise) | Postgres | ✗ (Markdown export; no git) | ✓ spaces; page-level perms in Business | ✓ page history + restore | ✓ self-host | CE €0 (no AI/MCP); Business $180 ($6/seat) |
| **BookStack** | MIT; 19k★ | ✗ (no built-in AI found) | ~ REST API; only community MCP servers | MySQL | ✗ | ✓ fine-grained roles | ✓ revisions | ✓ self-host | €0 |
| **Otter Wiki** | MIT; 1.6k★ | ✗ | ~ git push (experimental git HTTP server) | **git repo** | ✓ (it *is* git + Markdown) | ✗ coarse (read/write/admin) | ✓ git commits | ✓ self-host | €0 |
| **Gollum** | MIT; 14k★; last release 2024-12 | ✗ | ✓ via git | **git repo** | ✓ | ✗ none built in | ✓ git | ✓ self-host | €0 (stagnating) |
| **SilverBullet** | MIT; 6.5k★ | ✗ | ~ files on disk / HTTP API | Markdown files | ✓ files (git is up to you) | ✗ "personal knowledge database" | ✗ | ✓ self-host | €0 |
| **Obsidian Sync (shared vault)** | proprietary | ✗ | ✓ files | E2E-encrypted sync + local files | ✓ files | ✗ all collaborators = owner perms; **max 20** | ✗ (own version history, not git) | EU region (Frankfurt) | ~$120–150, but 20-user cap |
| **Logseq** | AGPL-3.0; 45k★ | ✗ | ~ | files (DB version in progress) | ~ outliner syntax | ✗ | ✗ | ✓ | €0 |
| **Quartz** | MIT; 13.5k★ | n/a (static site generator) | n/a (reads repo) | **git repo** | ✓ read-only render | via hosting (one site per tier) | git | ✓ self-host | €0 |
| *GitHub web UI (baseline, already in N3)* | — | ✗ | ✓ git | git | ✓ | ✓ one repo per tier | ✓ commits, blame, revert | US (GitHub) | already paid/free for org |

---

## 2. What each product's AI actually does

The question that matters for us: does the AI *compile and maintain* pages, or only read them?

- **Answer-only** (the large majority): Glean, Guru, Slite, Outline ("AI question answering"), Confluence Rovo search/chat, Notion Q&A, GitBook Assistant. They are RAG over human-written pages. Answers cite *pages*, not the raw sources behind them.
- **Drafts and edits on request**: Notion AI, Rovo, Docmost AI. A human asks, the AI writes in the editor. No source-to-page compilation loop.
- **Proactive, but suggestion-only**: GitBook Agent detects stale content and proposes changes. Notion Custom Agents can run on triggers and write to databases/pages (Business plan, metered by Notion Credits). Neither implements ingest → update affected pages → cite → lint.
- **No AI by design**: Wiki.js 3 (its MCP spec lists "An AI feature in the wiki itself" as a non-goal: it makes the wiki "a source and a destination for somebody else's agent"), BookStack, Otter Wiki, Gollum, SilverBullet, Quartz.

**Consequence.** Whatever we pick, the Karpathy loop is our agent. A product only changes *where* it writes. The AI features we would pay for (Notion, Rovo, Guru) duplicate what Claude Code already does over our repo.

**Per-claim citations (R3).** All products can hold Markdown links or footnotes in page text, so our citation syntax survives as text. None enforces or checks it. Only Wiki.js 3's MCP spec makes citability a stated goal, and it means *the agent citing wiki pages*, not pages citing sources.

---

## 3. Per-product notes

### 3.1 Notion (Notion AI, Agents, MCP)

- Plans (official pricing page, EUR): Plus €9.50, **Business €19.50/member/month** (includes Notion Agent, AI Meeting Notes, Enterprise Search beta, SAML SSO, **90 days** page history), Enterprise custom (adds zero data retention at LLM providers, audit log).
- **Data residency is Enterprise-only** (official help page). EU region is Frankfurt (backup Ireland). It covers data at rest only; processing, including by LLM providers, can happen outside the EU. Business-plan content is stored in the US.
- Official MCP server (`makenotion/notion-mcp-server`, MIT, 4.7k★; plus a hosted remote server) can create and update pages, databases and comments.
- Custom Agents need Business and consume Notion Credits ($10 per 1,000 since May 2026, per third-party sources) **[unverified]**.
- **Fit:** fails R1, N1 and "the repo is complete". Export is Markdown/HTML/CSV, one-way, and loses database properties and links in practice **[unverified for 2026 exporter]**. History is limited by plan, not permanent like git. For a German university, US hosting on Business is a hard sell; Enterprise pricing is custom.

### 3.2 Confluence Cloud + Atlassian Rovo

- Rovo is now bundled into all paid Confluence Cloud plans, metered by credits: 25 / 70 / 150 credits per user per month on Standard / Premium / Enterprise, pooled across the org. Overage billing from December 2026 (Atlassian licensing page via search).
- Per-user prices disagree across sources: Standard ~$5.4–6.4, Premium ~$10.4–12.3 **[unverified, check atlassian.com]**.
- **Atlassian Rovo MCP server** (GA; `atlassian/atlassian-mcp-server`, Apache-2.0) supports Claude Code, creates and updates Confluence pages, uses OAuth 2.1 (API tokens optional), respects user permissions, and **consumes Rovo credits**. An autonomous ingest agent touching 10–15 pages per source would burn credits quickly **[unverified: per-call credit cost]**.
- Permissions: spaces plus page restrictions map cleanly to three tiers.
- Atlassian is retiring Data Center (self-managed) in favour of cloud **[unverified: dates]**. So no long-term self-hosting.
- **Fit:** strong permissions and agent API, but DB-held content, Atlassian-specific storage format, credit-metered agent use. Fails "the repo is complete". Many universities already run Confluence; LMU's status is **[unverified]**.

### 3.3 Glean, Slite, Guru (AI knowledge/answer products)

- **Glean**: enterprise search across connected apps. No public pricing; third-party estimates $50–75/user/month with ~100-seat minimum, median contract ~$99k/year. Not a wiki, not viable at 30 users.
- **Slite**: team docs with AI "Ask"; ~$10–20/user/month (third-party). Its enterprise-search product "Super" was not checked **[unverified]**.
- **Guru**: verified "cards" with an owner and verification interval; AI answers. ~$25/user/month (Feb 2026 price change, third-party). The verification workflow is a nice idea (compare our deferred OKF `verified`), nothing more.
- **Fit:** all three are answer layers over human-written content in a vendor DB. None compiles pages. Ignore.

### 3.4 GitBook (Git Sync + AI)

- Pricing (official): Free (1 user), **Essential $65/site + $12/user**, Ultimate $249/site + $12/user, Enterprise custom. Git Sync on all plans. Assistant and Agent on Essential and above, with $20/$100 monthly AI credits.
- Git Sync is two-way with GitHub/GitLab. Pages are Markdown files with YAML front matter (`title`, `description`, `icon`). Navigation is `SUMMARY.md`; config is `.gitbook.yaml`. GitBook-specific blocks such as `{% hint style="warning" %}` and `{% code %}` are written into the files. Editing `README.md` in GitBook can create conflicts or duplicates (official docs).
- The **GitBook Agent** detects stale or outdated content and proposes edits; it does not compile from sources.
- GitBook ships a `skill.md` so local coding agents learn GitBook syntax: the product expects agents to write *through git*.
- **Fit:** the most "docs-as-code" hosted product. But it is built for **published product documentation**, not a private, tiered knowledge base. Its syntax (`{% hint %}`, `SUMMARY.md`) violates tool independence if its editor writes it into our repo. Hosting location **[unverified]**; SSO beyond Google/email domain needs Enterprise. Not a fit.

### 3.5 Outline (self-hostable)

- License: **BSL 1.1** (not open source today; converts to Apache-2.0 on 2030-10-23). The grant allows internal use; it forbids offering Outline as a "Document Service" to third parties. Fine for a research group. 41k★, very active.
- Pricing (official): cloud Starter $10 (1–10 users), **Team $79/month flat (11–100 users)**; on-prem Community €0 (no AI), **Business $4/user/month** (10-user minimum; AI answers via an OpenAI integration), Enterprise $5/user (100 min).
- **Built-in MCP server per workspace** (changelog 2026-02-18): search, read, create, edit documents; find, create and resolve comments. Availability on self-hosted Community **[unverified]**. Full REST API on all plans.
- **OKF export** (changelog 2026-09-04): collections or the whole workspace as Markdown + YAML front matter (`title`, `type`, `description`, generated time) plus a root `index.md` declaring the OKF version. Link format, attachments and re-import are not documented **[unverified]**. This is the closest any DB-backed product gets to our format, but it is a snapshot, not a sync.
- Permissions: collections with group and per-user access, plus per-document sharing. Three tiers = three private collections with three groups. Good UX.
- Content in Postgres; attachments on disk or S3. History per document; agent edits are attributed to the API-token owner (no separate "agent" marker) **[unverified]**.
- **Fit:** the best pure team wiki in this list for a 30-person group, cheap and self-hostable, with an agent-ready MCP. It fails N1 and "the repo is complete": the DB is the source of truth, git becomes at best a nightly OKF dump.

### 3.6 Wiki.js 3 (self-hostable, git-backed)

The strongest candidate for "product on top of our repo". Details from the source (`scarlett` branch).

- **Status:** AGPL-3.0, 29k★. After five years of alpha/beta, **3.0.1 was released as first stable on 2026-11-01**; 3.1.0 followed on 2026-11-05 with four security fixes. Very fresh; expect churn.
- **Git storage target:** "committed per change and synchronized with a remote". Modes: `sync` (pull then push), `push` only (force-pushes, the wiki wins), **`pull` only** (remote is the authority). Sync runs on a schedule (default every 5 min in 2.x docs).
- **Commit authorship:** each commit's author is the wiki user who made the change (`commitAuthor`), unless `alwaysUseDefaultAuthor` is set. The edit's required **reason** becomes the commit message. This matches R18.
- **Conflicts:** a conflicted rebase is redone with **the remote winning every conflicting hunk**; the replaced wiki version stays in the wiki's page history but not in git. Automatic and deterministic, but it can silently drop a web edit from the git history.
- **Front matter (key finding):** on write, Wiki.js serialises a fixed set: `title, description, published, date, tags, editor, dateCreated` (`pageMeta()` in `storageFiles.ts`). On import, `adoptStoredPage` keeps only `title, description, editor, tags, isPublished` (plus a few Wiki.js keys). **OKF `type`, `status`, `aliases` and any other key are dropped**, and the next web edit writes the file back without them. `date` changes on every save (diff noise). Two-way sync therefore breaks R1/P1 unless Wiki.js is patched or the agent restores fields after each sync.
- **Links:** Wiki.js page paths have no `.md` extension and may carry a locale prefix. Whether our root-absolute links `[x](/wiki/project/foo.md)` resolve in Wiki.js is **[unverified]**; likely they need a rewrite or a redirect rule.
- **MCP server (`/_mcp`, built in 3.0):** read tools (`discover`, `pages`, `history` incl. `diff_versions`, `glossary`); write tools `create_page`, `update_page`, `suggest_edit`, `post_comment`. Design points that match our needs:
  - `update_page` requires the `baseVersionId` the agent read and refuses stale ones (optimistic concurrency, as B report recommends).
  - Edits are `str_replace`-style, each matching exactly once.
  - `create_page` on an existing path is refused *with the existing page*, steering against duplicates (our #1 concurrency failure, B report).
  - A **reason is required** on every write; versions are marked `via: mcp` and shown with an **AI badge**.
  - Authentication via personal access token or OAuth 2.1; the agent acts **as the person** (R10 "agent commits name the human" fits).
  - `update_page` refuses while a human has the page open in the editor.
- **Permissions:** multiple sites per instance with shared users/groups; groups get permissions per site; page rules and approval rules (edits from one group reviewed by another). Three tiers = three sites, each backed by its own tier repo. Fixed in 3.0.1: "some page level permissions incorrectly handled as global permissions", "users shouldn't be able to tell if a path exists if they don't have access" — the permission code is young.
- **Search:** built-in full-text; no semantic search (explicit non-goal).
- **Fit:** in **pull-only** mode Wiki.js becomes a rebuildable web reader of our repo with SSO, per-tier sites, full-text search and history, and it never writes our files. In two-way mode it fails our front matter rules today.

### 3.7 Docmost (self-hostable)

- AGPL-3.0 core with enterprise directories under a separate license; 22k★, active.
- Pricing (official): Community free ("real-time collaboration, spaces, full-text search"); **Business $6/seat/month** (10-seat minimum) adds AI, **MCP**, page-level permissions, SSO, version history; Enterprise adds audit logs and SCIM.
- Official MCP (Business+): search, read, create, update pages, manage spaces; OAuth or API key; examples for Claude Code.
- Content in Postgres. Markdown export per page and space; no git sync found.
- **Fit:** a Confluence-like self-hosted alternative. Same structural problem as Outline, with fewer features in the free tier.

### 3.8 BookStack

- MIT, 19k★, active, mature. Books/chapters/pages, fine-grained role permissions, revisions, REST API. No built-in AI and no official MCP; several community MCP servers wrap the API.
- MySQL is the source of truth; Markdown export per page/book.
- **Fit:** solid classic wiki, nothing AI-specific, fails "the repo is complete".

### 3.9 Git-native wikis: Otter Wiki, Gollum

- **Otter Wiki** (MIT, 1.6k★, active): Flask app whose content *is* a git repo of Markdown; full page history; experimental git HTTP server for clone/push. Permissions are coarse (anonymous/registered/approved, read/write/admin), so one instance per tier repo. Small project, one main maintainer. Unclear how it treats YAML front matter and root-absolute `.md` links **[unverified]**.
- **Gollum** (MIT, 14k★): the classic git-backed wiki (GitHub wikis used it). Last release v6.1.0 on 2024-12-23, last push 2025-11. No auth of its own. Stagnating.
- **Fit:** philosophically closest to us (git is the store), but both add little over GitHub's own UI, and their permission models are weaker.

### 3.10 SilverBullet, Logseq, Obsidian Sync/Publish, Quartz

- **SilverBullet** (MIT, 6.5k★): self-hosted, browser-based Markdown editor over a folder of files, programmable in Lua. It calls itself a *personal* knowledge database; no multi-user permission model. Could serve as a web editor for the Markdown folder of one tier, but git commits, attribution and tiers would be ours to add.
- **Logseq** (AGPL, 45k★): outliner; its syntax (block bullets, properties) does not match our page format. Team sync is not mature. Not a fit.
- **Obsidian Sync shared vaults:** ~$4–5 per user per month, **every collaborator pays**, **max 20 collaborators per shared vault**, and all collaborators get the owner's permissions (official help, via search). EU region (Frankfurt) available. It would also run a second sync system alongside git. Obsidian stays what R17 says: an optional local viewer over a git clone. **Obsidian Publish** is a hosted public/password site; not suitable for confidential tiers.
- **Quartz** (MIT, 13.5k★): static site generator for Markdown folders (backlinks, graph, search). It reads the repo and writes nothing, so it fully satisfies "derive, don't store". One static site per tier behind university SSO would be a minimal web viewer. No editing, no server-side permissions beyond the web server's.

---

## 4. When would a product actually be the better choice?

Honestly: if the group's real need were **a shared, human-edited team wiki with AI search**, then **self-hosted Outline** (or Confluence, if LMU already pays for it) would beat our plan on day one: web editing for 30 people, permissions, comments, history, an MCP server for agents, OKF export, for €0–120/month. Our design costs more engineering.

Our plan wins because of what the brain is for:

- **The writer is mainly the agent, not humans** (R10). An agent works best on files in a git worktree (grep, qmd, diff, branch, revert, CI lint). Through an MCP server it works page by page over HTTP, with no cheap bulk read, no branch, no CI gate, and rate limits.
- **Git is our provenance and log** (R6, R18, P1). Products keep their own history in a DB, often time-limited (Notion 90 days on Business).
- **Deterministic lint in CI** (P8, R9) needs the corpus as files.
- **qmd over wiki *and* `raw/`** (N2). Products hold only the wiki, not the immutable raw sources.
- **Tool independence and "the repo is complete".** Every DB-backed product fails the delete-and-rebuild test.

The main argument *for* a product, multi-user web editing with permissions, is a v2 need: the MVP is Claude Code + Obsidian over one `group` repo.

## 5. Recommendation

**Option (2): keep the git repo as the source of truth; use a product only as an optional, rebuildable viewer on top. Do not adopt one for v1.**

1. **v1 (MVP):** no product. Viewers are GitHub's web UI (renders Markdown, per-repo permissions = tiers, history, blame, revert, code search; already implied by N3) and Obsidian over a clone. Cost €0, nothing new to operate.
2. **When the group needs a web reader with SSO and search** (likely with the bot milestone or when non-technical members join): **Wiki.js 3, git storage in `pull` only mode, one site per tier repo**, self-hosted on the group server. It satisfies the delete-and-rebuild test, maps the three tiers to sites with groups, and keeps all writes in git. Do a spike first and check:
   - root-absolute `.md` links resolve (or need a redirect rule) **[unverified]**;
   - unknown front matter is ignored harmlessly in pull mode;
   - SSO against LMU's identity provider;
   - stability of 3.x (stable only since 2026-11-01).
   Lighter alternative: **Quartz**, one static build per tier behind the web server's auth. No server app, no database, but no search ranking beyond client-side and no editing.
3. **Two-way web editing** (humans editing in a browser, the result committed to git): defer. Wiki.js 3 is the only candidate with per-user commit authorship and an agent-aware design, but today it drops OKF front matter and resolves conflicts with "remote wins per hunk". Revisit if a spike or upstream change fixes front-matter preservation. Its MCP design (required reason, `baseVersionId`, str_replace edits, duplicate refusal, AI badge) is worth **borrowing as conventions** for our own skill now, whatever we host.
4. **Ignore** Notion, Glean, Slite, Guru (answer layers over a vendor DB, US hosting below Enterprise), GitBook (public-docs product, own syntax), Logseq, Obsidian Sync as team store (20-user cap, flat permissions).
5. **Fallback for option (1):** if the owner ever drops git-as-provenance for the sake of web collaboration, choose **self-hosted Outline** (Business tier for AI, or Community + our own agent via its MCP/API), with a scheduled OKF export into git as the backup. Do not choose a hosted US product.

Items for the owner (not decided here): whether a web viewer is a v2 requirement at all (add to R17?), and whether to spike Wiki.js 3 pull-only on the group server.

## 6. Gaps and unverified items

- Nothing was installed or run; Wiki.js findings come from reading source and design docs on 2026-11-05, days after its first stable release.
- Outline: MCP availability on self-hosted Community; OKF export's link format and attachments; agent edit attribution.
- Confluence per-user prices, Rovo credit cost per MCP call, Data Center retirement dates, LMU's existing Atlassian licences.
- Notion Custom Agents pricing and credits; current Markdown exporter quality.
- GitBook hosting region and education pricing; Slite "Super"; Glean and Guru pricing (third-party only).
- Otter Wiki front matter and link handling.
- No product was found that implements the Karpathy compile loop natively.

## 7. Sources

Official pages and changelogs:
- Notion pricing: https://www.notion.com/pricing ; data residency: https://www.notion.com/help/data-residency ; MCP: https://github.com/makenotion/notion-mcp-server
- Atlassian Rovo licensing: https://www.atlassian.com/licensing/rovo ; Rovo MCP: https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/ ; https://github.com/atlassian/atlassian-mcp-server ; GA announcement: https://community.atlassian.com/forums/Atlassian-Remote-MCP-Server/Announcing-GA-of-the-Atlassian-Rovo-MCP-server/ba-p/3186690
- GitBook pricing: https://gitbook.com/pricing ; Git Sync: https://gitbook.com/docs/getting-started/git-sync ; content configuration: https://gitbook.com/docs/getting-started/git-sync/content-configuration
- Outline pricing: https://www.getoutline.com/pricing ; MCP changelog: https://www.getoutline.com/changelog/mcp ; OKF export changelog: https://www.getoutline.com/changelog/okf-export ; license: https://github.com/outline/outline/blob/main/LICENSE
- Wiki.js 3 release: https://github.com/requarks/wiki/releases/tag/3.0.1 , https://github.com/requarks/wiki/releases/tag/3.1.0 , https://js.wiki/blog/2026-wiki-js-3-release/ ; source (branch `scarlett`): `backend/modules/storage/git/{definition.yml,storage.ts}`, `backend/helpers/storageFiles.ts`, `backend/models/pages.ts`, `dev/specs/mcp.md`, `.claude/rules/mcp.md`, `.claude/rules/storage.md` ; 2.x git docs: https://github.com/requarks/wiki-docs/blob/master/storage/git.md
- Docmost pricing: https://docmost.com/pricing ; MCP: https://docmost.com/docs/user-guide/mcp ; import/export: https://docmost.com/docs/user-guide/import-export ; pages/history: https://docmost.com/docs/user-guide/pages
- Obsidian shared vaults: https://obsidian.md/help/sync/collaborate
- GitHub repos (metadata via `gh api`, 2026-11-05): outline/outline, requarks/wiki, BookStackApp/BookStack, docmost/docmost, silverbulletmd/silverbullet, logseq/logseq, jackyzha0/quartz, gollum/gollum, redimp/otterwiki

Third-party (pricing estimates, lower confidence):
- Glean: https://www.getmacha.com/blog/glean-ai-pricing-explained , https://www.gosearch.ai/blog/glean-pricing-explained
- Slite / Guru: https://costbench.com/compare/guru-vs-slite/ , https://www.costbench.com/changelog/guru-price-increase-2026-02/ , https://www.featurebase.app/blog/slite-pricing
- Confluence pricing: https://www.usecarly.com/blog/confluence-pricing/ , https://redresscompliance.com/confluence-cloud-pricing-tiers-enterprise-cost.html
- Notion Agents/credits: https://www.activepieces.com/blog/notion-agents-vs-workflows-what-each-costs-in-2026.md
- Wiki.js / BookStack / Docmost comparison (German): https://wz-it.com/blog/bookstack-wikijs-xwiki-docmost-vergleich/
