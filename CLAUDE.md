1. de# CLAUDE.md — wintermute-brain

## What this is

An **LLM-maintained wiki / second brain**: a personal knowledge base of
plain-text notes that an LLM agent helps capture, organise, link, and
query. Humans read and steer; the agent does most of the filing,
cross-linking, and summarising.

Nothing is built yet. The repo is at the **spec stage**.

## IMPORTANT: this repo designs the brain; it does not run it here

- **This repo is the design and spec of the brain.** It will become a
  GitHub repo in `slds-lmu`. It is **not** installed or run on the
  machine where the specs are being written (Bernd's personal laptop
  or the yolobox sandbox on it).
- **The laptop's admin rules have nothing to do with the brain.**
  Bernd's global CLAUDE.md install rules (manifests, the
  system-package-manager skill, yolobox) govern *this laptop*. They
  are **not** design constraints for the brain, and they must not
  shape its specs.
- **Tools the brain uses** (qmd, defuddle, MinerU, gitleaks, …) are
  installed on the brain's own deployment targets: the group GPU
  server and group members' machines. How that happens is a design
  question for the brain's specs (`06-ops.md`), decided on its own
  merits.
- **Don't mix the two.** Don't propose installing brain tooling on
  this laptop, and don't argue from the laptop's install policy when
  designing the brain. Installs here happen only if the owner
  explicitly asks, e.g. for a spike, and then follow the laptop's
  rules.

## Working mode: specs first

No implementation code until the relevant spec exists and has been
agreed. Order of work:

1. **Spec** — write or update a document under `specs/`.
2. **Review** — the user reads it and resolves the open questions.
   Do not resolve open questions yourself; list options with a
   recommendation and leave the decision to the user.
3. **Implement** — only what an accepted spec describes. If
   implementation shows the spec is wrong, update the spec first, then
   the code.

Spec status lives in each file's header: `draft` → `accepted` →
`superseded`. Only `accepted` specs may be implemented.

### Spec layout

```
specs/
  00-requirements.md  # users, scope, use cases, R-/N-requirements, MVP
  01-data-model.md    # note format, frontmatter, IDs, links, folders
  02-ingest.md        # how material gets in (paste, URL, PDF, chat, mail…)
  03-agent-ops.md     # what the LLM does: file, link, summarise, lint, answer
  04-retrieval.md     # search / query / Q&A over the wiki
  05-interfaces.md    # CLI, editor, web view, chat
  06-ops.md           # storage, sync, backup, privacy, versioning
  v0-foundation.md    # v0 = fork of Astro-Han/karpathy-llm-wiki; gaps + fixes
  prior-art.md        # what we reuse / fork / borrow, and why
  proposals.md        # itemised ideas from prior art, awaiting decisions
  reading-guide.md    # ordered reading list for the prior art
  research/           # full prior-art reports backing prior-art.md
  decisions/          # short ADRs: NNNN-title.md, one decision each
```

Create files as they become relevant; this list is a starting point,
not a contract. Keep specs short and concrete — examples beat prose.

## Prior art

Reading list: `LINKS.md`. Baseline we start from (to be confirmed in
`00-requirements.md`) is **Karpathy's LLM Wiki pattern**:

- **Three layers:** `raw/` (immutable sources, never edited by the
  agent) → `wiki/` (agent-owned Markdown pages: summaries, entities,
  concepts, comparisons, syntheses) → **schema** (this file, co-evolved).
- **Three operations:** *ingest* (read source, summarise, update the
  10–15 affected pages, update index, log), *query* (answer from the
  wiki with citations; file good answers back as pages), *lint*
  (contradictions, stale claims, orphans, missing links/pages, gaps).
- **Bookkeeping:** `index.md` (catalog, one line per page, read first
  on every query) and `log.md` (append-only, `## [YYYY-MM-DD] op | title`).
- **Tooling:** Obsidian as viewer, Web Clipper for capture, git for
  history; local hybrid search (e.g. qmd) only once `index.md` stops
  scaling (~100+ sources / few hundred pages).

Lessons from scaled-up variants (rohitg00 v2, denser.ai survey) to
weigh in the specs:

- Provenance per claim; cite sources rather than numeric confidence.
- Epistemic status (fact / inference / hypothesis) so guesses don't
  harden into facts.
- Contradictions → explicit "disagreements" sections or research
  tasks, not silent overwrites. Supersede explicitly; git is the audit
  trail, no time-based decay.
- Filter at ingest (quality, secrets, PII); keep a human write gate
  until the manual loop is stable; automate (hooks, scheduled lint) last.
- Add structure (typed graph, hybrid retrieval) only when flat pages
  demonstrably fail.
- The wiki is plain Markdown with root-absolute links that Obsidian
  displays well; we do not use Obsidian-specific syntax or
  `kepano/obsidian-skills` (decided 2026-10-29). Existing suites (claude-obsidian, llm-wiki-agent,
  karpathy-llm-wiki skill) are references to borrow from, not deps.

## Status

- Requirements: `specs/00-requirements.md` (draft).
- Data model: `specs/01-data-model.md` (draft). Uses OKF v0.2 field
  names, root-absolute Markdown links, and git as provenance.
- v0 foundation: `specs/v0-foundation.md`, a fork of
  Astro-Han/karpathy-llm-wiki (accepted).
- Prior art: `specs/prior-art.md`. P1 (OKF), P2 (citations) and P3
  (generated per-folder index) are decided. **P4–P8 are open and
  important: revisit ASAP.**
- Next: `03-agent-ops.md`.

## Design principles (owner, 2026-10-29)

These apply to every spec and implementation decision.

- **KISS.** Keep it simple. Avoid over-engineering, especially in v1:
  defer anything that isn't needed to run the basic loop
  (ingest / query / lint). When in doubt, leave it out and note it as
  deferred.
- **Tool independence.** The wiki is plain Markdown + YAML in git,
  readable by any tool: GitHub, an editor, an agent. Tools such as
  Obsidian, qmd or OKF validators *can* be used on top, but nothing
  *depends* on them. No tool-specific syntax: no wikilinks, embeds or
  callouts. Example: Obsidian is an optional viewer, not a dependency.
- **Derive, don't store.** If something can be computed from the repo
  (git history, links, citations), don't keep a second copy that can
  drift. Examples: git is the provenance; source lists are derived
  from citations.
- **The repo is complete.** Everything outside git (qmd's index,
  caches, a future bot's state) must be rebuildable from the repo
  alone. No tool may hold state that exists only in that tool. Test
  for any tool proposal: "if we delete its data, can we rebuild it
  from git?" (Lesson from gbrain, whose README warns that "Markdown
  export is not a full backup".)
- **Standards over inventions.** Use an existing convention where one
  fits (e.g. OKF field names) instead of designing our own.

## Conventions (provisional, until specs say otherwise)

- Everything is plain text in git; the repo is the source of truth.
- Prefer boring, inspectable formats over databases and custom tooling.
- No commits or pushes unless the user asks (see global CLAUDE.md).
