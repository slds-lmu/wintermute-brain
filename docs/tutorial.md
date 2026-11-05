# The SLDS brain — tutorial

A top-down introduction: what the brain is, how it is built, how to use
it, and how it is run. Exact commands and settings live in the READMEs
and in `specs/`; this text explains the ideas and flows behind them.

## 1. What it is

The brain is the group's **long-term memory**: a wiki of plain Markdown
pages about our research, projects, people, decisions and teaching. Its
special feature is who writes it. **Agents** (Claude) do the filing,
summarising and cross-linking; **humans** choose what goes in, ask
questions, correct and steer.

Typical questions it should answer:

- *Status:* "Where do we stand with project X? Who works on it?"
- *Research:* "What do our sources say about method Y? With citations."
- *Decisions:* "What did we decide about Z, and why?"
- *Onboarding:* "How do things work here, and whom do I ask?"

The pattern goes back to Karpathy's "LLM wiki": instead of searching raw
documents for every question, an agent **compiles** them once into
maintained pages, and later questions are answered from those pages.

## 2. Core ideas

**Two layers of content.**

- `raw/`: the sources, exactly as they came in (a web page, a paper, a
  session digest). Written once, never changed.
- `wiki/`: the pages the agents write from them. Every non-trivial claim
  links to the summary page of its source, so every sentence can be
  traced back.

**Rules for agents.** A schema file (`CLAUDE.md`) plus a few page
templates tell the agents how to work. Humans own these files; agents
only propose changes.

**Git is everything else.** The history of the content repo *is* the log
(who changed what, when, why, from which source). Search indexes and
caches are derived and can always be rebuilt from the repo.

**Few page types.** A type exists only where it can never be disputed:
`person`, `meeting`, `paper`, `grant`, `source` (summary of one raw
item). Everything else is an untyped `page` with free tags (`project`,
`idea`, `decision`, …). No ontology to argue about.

**Nothing unsourced.** Numbers, dates and quotes are copied verbatim
from the source and checked by a script. What an assistant computed or
suggested on its own is marked as such and never becomes a "result".
Real disagreements between sources stay visible in a
`Status: Disputed` block; facts that simply changed are updated in place
(git keeps the old version).

**Humans have the last word.** A human-written line is protected from
agents unless a newer source justifies the change, and a page marked
`locked: true` is off-limits to agents altogether.

## 3. Architecture

### Two repos

| Repo | Contains | Changed by |
|---|---|---|
| **Code** (`wintermute-brain`) | tools, Claude Code plugin, server worker, checks, design specs, tests | developers |
| **Content** (`wintermute-brain-content-slds`, later one per confidentiality tier) | sources, pages, schema, settings | agents and members |

The content repo **pins a release** of the code (`.brain-version`). Its
checks, the server and the members' plugin all use that release.
Upgrading is a small, reviewable change in the content repo. Work on the
code never becomes brain content.

### Three places

```
 member's machine                 GitHub                        group server
 ────────────────                 ──────                        ────────────
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

1. The agent works in a **fresh private copy** of the repo.
2. It writes its pages, checks the evidence, and commits through one
   tool (`commit-op`). The commit names the agent, the person who asked,
   the source, a **plan** (which pages it meant to touch) and a
   **reason** for each changed page.
3. `commit-op` opens a **pull request** with auto-merge.
4. GitHub runs the **check**: formats and links are valid, sources
   unchanged, no secrets, locked pages and human lines respected, and
   nobody else changed the same pages in the meantime.
5. If it passes, the PR merges by itself; afterwards the indexes are
   regenerated. If it fails, the agent throws its copy away and starts
   over. It never resolves conflicts itself.

Because of this, many people and agents can write at the same time:
conflicts are rejected, not silently overwritten.

### The two kinds of input

**On request (ingest).** A person says "ingest this URL / paper". The
agent fetches it, scans it for secrets, stores it in `raw/`, decides
what it adds (new, update, disputed, nothing), writes a summary page
and updates the affected pages, all in one PR.

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
  from raw sources, and what the wiki does not know. Asking writes
  nothing.
- **Lint** checks the wiki: mechanical checks on every change, and a
  judgment check by an agent (claims vs. sources, duplicates, stale
  statements) on request. Problems from unattended runs go to one
  GitHub issue, "Brain health".

## 4. Using it

### Getting started

Setup takes a few minutes: clone the content repo, load the brain plugin
into Claude Code, set your name. The steps are in the content repo's
README.

### Reading

Browse the content repo on GitHub, or open it in Obsidian (the right
link settings come with the repo). Start at `index.md`: one catalog per
page type.

### Asking

Ask in any Claude Code session with the plugin, e.g. "What did we decide
about the evaluation protocol of project X?" Expect citations, and
expect the answer to say what is missing or how old the newest source
is.

### Adding knowledge

- **Sources:** "ingest <url / DOI / arXiv id / file>". One source per
  request. Good candidates: papers, project documents, meeting notes,
  web pages about the group's work.
- **Your work sessions:** simply work with Claude Code in your project
  with the plugin loaded. Decisions and findings flow in by themselves.
  Say *why* when you decide something; the reason is what makes a
  digest useful later.
- **What session capture keeps, and how to say no:** decisions,
  findings, failed approaches and open questions, *with names*; never
  code, chatter, personal remarks or secrets. Every captured session
  starts with a one-line notice. Switch it off for a session, or don't
  enable the plugin in a repo. You can ask the owner to remove content
  about you, including from the history.
- **Scope:** research, leadership and organisation, teaching. Not
  private life.

### Correcting

- **Small fixes:** edit the page yourself (editor, Obsidian, GitHub) and
  open a PR. Your lines are then protected from agents.
- **Larger changes:** ask an agent ("edit: merge these two pages",
  "mark this as deprecated").
- **Important pages:** set `locked: true`; agents will only report
  what they think should change.
- **Disagreements:** if two sources really disagree, the page shows both
  in a `Status: Disputed` block. Resolve it by editing the page once it
  is settled.

## 5. Running it

**The owner** decides the schema (page types, templates, agent rules)
and the design (`specs/`), and approves new code releases for the
content repo.

**Developers** change the code repo through PRs with tests, publish a
release tag, and move the content repo to it with a small PR.

**The server operator** runs the compile worker and search on the group
server. The worker pulls the content repo regularly, switches its code
copy to the pinned release, and compiles new raw items. Only one compile
worker may run at a time.

**GitHub setup** per content repo: the required check, the gate on the
main branch, and the brain's GitHub App, which is the only thing allowed
to push regenerated indexes directly.

## 6. Where to read on

- Content repo README: setup and commands for members.
- Code repo README: layout, tools, releases.
- `specs/00`–`06`: requirements, data model, ingest, agent operations,
  retrieval, interfaces, operations.
- `specs/implementation-status.md`: what is built, tested and open.
- `specs/parked.md`: ideas for later, with the priority items on top.
