# wintermute-brain — tutorial

wintermute-brain is software for a **team brain**: a shared, LLM-maintained
knowledge base for a team, lab or organisation. This tutorial explains it
top down: what it is, the ideas behind it, how it is built, how to use it,
and how to run it. Exact commands and settings live in the READMEs and in
`specs/`; this text explains the concepts.

## 1. What it is

A brain is a team's **long-term memory**: a wiki of plain Markdown pages
about the team's work (projects, people, decisions, results, how things
are done). What makes it different is who writes it. **Agents** (Claude)
do the filing, summarising and cross-linking; **humans** choose what goes
in, ask questions, correct and steer.

Typical questions a brain should answer:

- *Status:* "Where do we stand with project X? Who works on it?"
- *Synthesis:* "What do our sources say about topic Y? With citations."
- *Decisions:* "What did we decide about Z, and why?"
- *Onboarding:* "How do things work here, and whom do I ask?"

The pattern goes back to Karpathy's "LLM wiki": instead of searching raw
documents for every question, an agent **compiles** them once into
maintained pages, and later questions are answered from those pages.
wintermute-brain adds what a team needs on top: many writers at once,
automatic capture of knowledge from everyday work, review gates, and
traceability for every sentence.

## 2. Core ideas

**Two layers of content.**

- `raw/`: the sources, exactly as they came in (a web page, a paper, a
  digest of a work session). Written once, never changed.
- `wiki/`: the pages the agents write from them. Every non-trivial claim
  links to the summary page of its source, so every sentence can be
  traced back.

**Rules for agents.** A schema file (`CLAUDE.md`), a few page templates
and a scope file (`scope.md`: what belongs into this brain) tell the
agents how to work. The brain's owner writes these files; agents only
propose changes.

**Git is everything else.** The history of the content repo *is* the
log: who changed what, when, why, and from which source. Search indexes
and caches are derived and can always be rebuilt from the repo. Nothing
lives only inside a tool.

**Few page types.** A type exists only where membership can never be
disputed: `person`, `meeting`, `paper`, `grant`, and `source` (the
summary of one raw item). Everything else is an untyped `page` with free
tags (`project`, `idea`, `decision`, …). There is no ontology to argue
about.

**Nothing unsourced.** Numbers, dates and quotes are copied verbatim
from the source and checked by a script. What an assistant computed or
suggested on its own is marked as such and never becomes a "result".
Real disagreements between sources stay visible in a `Status: Disputed`
block; facts that simply changed are updated in place, and git keeps the
old version.

**Humans have the last word.** A human-written line is protected from
agents unless a newer source justifies the change, and a page marked
`locked: true` is off-limits to agents altogether.

## 3. Architecture

### Code and content are separate

| Repo | Contains | Changed by |
|---|---|---|
| **Code** (`wintermute-brain`, this repo) | tools, Claude Code plugin, server worker, reusable checks, design specs, tests | developers |
| **Content** (one per brain, e.g. per team or per confidentiality level) | sources, pages, schema, scope, settings | agents and members |

One code base can serve several brains. Each content repo **pins a
release** of the code (`.brain-version`); its checks, its server worker
and its members' plugin all use that release. Upgrading a brain is a
small, reviewable change in its content repo. Work on the code itself
never becomes brain content.

### Three places

```
 member's machine                 GitHub                        server
 ────────────────                 ──────                        ──────
 Claude Code + brain plugin  ──▶  content repo  ◀──────────────  compile worker
  · commands (ingest, ask,        · every change is a PR          · turns new raw items
    edit, lint)                   · required check gates it         into pages
  · session hooks + digest        · index regenerated after       search (qmd)
    agent                           each merge                    · answers members'
                                  · "Brain health" issue            searches
```

- **Members' machines** do what needs the person: their commands and
  their work sessions.
- **The server** does the heavy and the single-writer work: compiling
  new sources into pages, and search.
- **GitHub** is the gate and the record: nothing reaches the main branch
  without passing the check.

### How a change flows

Every write follows the same path:

1. The agent works in a **fresh private copy** of the content repo.
2. It writes its pages, checks the evidence, and commits through one
   tool (`commit-op`). The commit names the agent, the person who asked,
   the source, a **plan** (which pages it meant to touch) and a
   **reason** for each changed page.
3. `commit-op` opens a **pull request** with auto-merge.
4. GitHub runs the **check**: formats and links are valid, sources
   unchanged, no secrets, locked pages and human lines respected, and
   nobody else changed the same pages in the meantime.
5. If it passes, the PR merges by itself, and the indexes are
   regenerated. If it fails, the agent throws its copy away and starts
   over. It never resolves conflicts itself.

So many people and agents can write at the same time: conflicts are
rejected, not silently overwritten.

### Two kinds of input

**On request (ingest).** Someone says "ingest this URL / paper / file".
The agent fetches it, scans it for secrets, checks it against the
brain's scope, stores it in `raw/`, decides what it adds (new, update,
disputed, nothing), writes a summary page and updates the affected
pages, all in one PR.

**Automatically (session capture).** While someone works with Claude
Code in a project, the plugin's hooks digest the conversation every ~20
messages in the background. A small model keeps only decisions,
findings, failed approaches, how-tos and open questions; the default is
to keep nothing. The digest goes into `raw/` as a PR. The server's
**compile worker** later turns digests into pages, one at a time and
oldest first, so later decisions update earlier ones.

### Questions and health

- **Asking** reads the indexes, searches, reads the best pages and
  answers with citations. It says which parts come from pages and which
  from raw sources, and what the brain does not know. Asking writes
  nothing.
- **Lint** checks the brain: mechanical checks on every change, and a
  judgment check by an agent (claims vs. sources, duplicates, stale
  statements) on request. It also lists open disputes and sources
  flagged as outside the scope. Problems from unattended runs go to one
  GitHub issue, "Brain health".

## 4. Using a brain

### Getting started

Setup takes a few minutes: clone the brain's content repo, load the
plugin into Claude Code, set your name. Each content repo's README has
the exact steps.

### Reading

Browse the content repo on GitHub, or open it in Obsidian (the link
settings come with the repo). Start at `index.md`: one catalog per page
type.

### Asking

Ask in any Claude Code session with the plugin, e.g. "What did we decide
about the evaluation protocol of project X?" Expect citations, and
expect the answer to say what is missing or how old the newest source
is.

### Adding knowledge

- **Sources:** "ingest <url / DOI / arXiv id / file>". One source per
  request: documents, papers, meeting notes, web pages about the team's
  work.
- **Your work sessions:** work with Claude Code in your project with the
  plugin loaded; decisions and findings flow in by themselves. Say *why*
  when you decide something; the reason is what makes a digest useful
  later.
- **What session capture keeps, and how to say no:** decisions,
  findings, failed approaches and open questions, *with names*; never
  code, chatter, personal remarks or secrets. Every captured session
  starts with a one-line notice. Switch it off for a session, or don't
  enable the plugin in a repo. You can ask the brain's owner to remove
  content about you, including from the history.
- **Scope:** each brain's `scope.md` says what belongs in it. Sources
  outside it are still taken in but flagged, until a human decides.

### Correcting

- **Small fixes:** edit the page yourself (editor, Obsidian, GitHub) and
  open a PR. Your lines are then protected from agents.
- **Larger changes:** ask an agent ("edit: merge these two pages",
  "mark this as deprecated").
- **Important pages:** set `locked: true`; agents will only report what
  they think should change.
- **Disagreements:** if sources really disagree, the page shows both in
  a `Status: Disputed` block. Resolve it by editing the page, or ask an
  agent with your reason. Agents resolve a dispute on their own only
  when a newer source explicitly corrects the old one.

## 5. Running a brain

**The brain's owner** decides its schema (page types, templates, agent
rules) and scope, and approves new code releases for its content repo.

**Developers** change the code repo through PRs with tests, publish a
release tag, and move content repos to it with a small PR.

**The server operator** runs the compile worker and search. The worker
pulls the content repo regularly, switches its code copy to the pinned
release, and compiles new raw items. Only one compile worker may run per
brain.

**GitHub setup** per content repo: the required check, a ruleset that
protects the main branch, and a GitHub App that is the only thing
allowed to push regenerated indexes directly.

**Admins** handle the rare disruptive operations, such as erasing
personal data from the history on request (`admin/`).

## 6. Where to read on

- A content repo's README: setup and commands for its members.
- This repo's README: layout, tools, releases.
- `specs/00`–`06`: requirements, data model, ingest, agent operations,
  retrieval, interfaces, operations.
- `specs/implementation-status.md`: what is built, tested and open.
- `specs/parked.md`: ideas for later, with the priority items on top.
