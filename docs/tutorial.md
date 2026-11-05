# wintermute-brain — tutorial

wintermute-brain is software for a **team brain**: a knowledge base that
LLM agents write and maintain for a team, lab or organisation. Commands
and settings are in the READMEs; the full design is in `specs/`.

## 1. What a brain is

A brain is a wiki of plain Markdown pages about a team's projects,
people, decisions and results. Agents (Claude) file, summarise and
cross-link; people choose the input, ask, correct and steer.

It answers questions about the team's work, such as the state of a
project, what was decided and why, what the sources say on a topic, or
how things are done, each answer with citations.

The approach follows Karpathy's "LLM wiki": sources are compiled once
into maintained pages, and questions are answered from those pages
rather than from the raw documents. wintermute-brain adds concurrent
writers, automatic capture of knowledge from work sessions, a review
gate on every change, and a citation behind every claim.

## 2. Core ideas

**Two layers.** `raw/` holds the sources exactly as they arrived (a web
page, a paper, a session digest) and is never edited. `wiki/` holds the
pages written from them; every non-trivial claim links to the summary
page of its source.

**Schema.** `CLAUDE.md`, a few page templates and `scope.md` (what
belongs in this brain) define how agents work. The brain's owner writes
them; agents may only propose changes.

**Git as the record.** The content repo's history is the log of who
changed what, when, why and from which source. Search indexes and caches
are derived and can be rebuilt from the repo.

**Few page types.** Only types whose membership is indisputable:
`person`, `meeting`, `paper`, `grant`, and `source` (the summary of one
raw item). Everything else is an untyped `page` with free tags such as
`project`, `idea` or `decision`.

**Grounding.** Numbers, dates and quotes are copied verbatim from the
source and checked by a script. Anything an assistant computed or
suggested on its own is marked as such. Genuine disagreement between
sources is kept in a `Status: Disputed` block; a fact that changed is
updated in place, with the old version in git.

**People decide.** Agents may change a line a person wrote only on the
basis of a newer source, and may not touch a page marked `locked: true`.

## 3. Architecture

### Code and content

| Repo | Contents | Changed by |
|---|---|---|
| **Code** (`wintermute-brain`) | tools, Claude Code plugin, server worker, reusable checks, specs, tests | developers |
| **Content** (one per brain, e.g. per team or confidentiality level) | sources, pages, schema, scope, settings | agents and members |

One code base serves any number of brains. For now every brain's checks,
server worker and members run the code's latest version; pinning a brain
to a release is planned. Development work on the code is never captured
as brain content.

### Components

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

- **Members' machines** run their commands and capture their work
  sessions.
- **The server** compiles new sources into pages (a single writer) and
  hosts search.
- **GitHub** gates and records every change.

### Write path

1. The agent works in a fresh worktree of the content repo.
2. It writes pages, runs the evidence check, and commits through
   `commit-op`. The commit records the agent, the person who asked, the
   source, the planned pages and a reason for each changed page.
3. `commit-op` opens a pull request with auto-merge.
4. The required check validates formats and links, the immutability of
   sources, the absence of secrets, locks and protected lines, and that
   no one else changed the same pages in the meantime.
5. A passing PR merges and the indexes are regenerated. A failing one is
   discarded and the operation starts again; agents never resolve
   conflicts.

Concurrent writers therefore cannot overwrite each other silently.

### Input

**Ingest (on request).** Given a URL, DOI, arXiv id or file, the agent
fetches the source, removes secrets, checks it against `scope.md`, stores
it in `raw/`, classifies it (new, update, disputed, no new material),
writes its summary page and updates the affected pages in one PR.

**Session capture (automatic).** In projects where the plugin is
enabled, hooks digest the conversation in the background every ~20
messages. A small model keeps decisions, findings, failed approaches,
how-tos and open questions, and by default nothing. Each digest is added
to `raw/` by PR; the compile worker turns digests into pages one at a
time, oldest first.

### Queries and checks

- **Ask** reads the indexes, searches, reads the most relevant pages and
  answers with citations, stating which parts come from pages and which
  from raw sources, and what the brain does not cover. It writes nothing.
- **Lint** runs mechanical checks on every change and, on request, a
  judgment pass by an agent (claims against sources, duplicates, stale
  statements). It also lists open disputes and sources flagged as out of
  scope. Unattended runs report to a single GitHub issue, "Brain health".

## 4. Installing

Reading a brain needs nothing but access to its content repo (section
5). Asking, adding and editing need the setup:

1. **Prerequisites:** git, the GitHub CLI `gh`, Claude Code and
   Python 3.11 or newer; gitleaks is optional.
2. **Run `setup-brain` once.** It asks how to log in to GitHub (your
   normal `gh` login, or a dedicated token for the brain) and who you
   are, clones the brain without large files, makes git use the same
   login, writes your settings to `~/.config/brain/config.toml`,
   installs the `brain` command, and checks that everything works.
3. **Start work with `brain`** instead of `claude`. It updates the code,
   loads the brain plugin and your settings for this session.

Sessions are captured only in folders listed under `capture` in your
settings; by default that is the brain's own folder. The content repo's
README has the exact commands.

## 5. Reading

A brain is plain Markdown in git, so any viewer works: GitHub in the
browser, Obsidian (link settings ship with the repo), or an editor.

**Obsidian.** Obsidian is optional, but works well as a reader:

- Open your clone of the content repo as a vault ("Open folder as
  vault"). The repo ships the two link settings it needs (Markdown links
  instead of wikilinks, absolute paths), so nothing has to be configured.
- **Backlinks** show where a page is cited; on a source's summary page
  they list every page that relies on that source.
- **Graph view** shows how pages connect and makes isolated pages
  visible.
- **Search** and the file explorer (one folder per page type) work as
  usual.
- Keep the vault current with `git pull`; the brain changes several
  times a day.
- If you edit in Obsidian, your changes reach the brain like any human
  edit: commit them and open a PR. Write plain Markdown: no wikilinks,
  embeds or callouts, which other tools cannot read.

**Where to start.** `index.md` at the root links one catalog per page
type (`wiki/person/index.md`, `wiki/page/index.md`, …), one line per
page with its description.

**What a page contains.**

- A header (frontmatter) with `type`, `title`, a one-line `description`,
  `tags`, and optionally `status: deprecated` or `locked: true`.
- Sections from the type's template; untyped pages are free-form.
- Citations: each claim ends with a link to the summary page of its
  source.
- Possibly a `Status: Disputed` block, where sources disagree, or a
  `Scope check:` line, where a source may not belong in the brain.

**Following a claim to its source.** Click the citation to reach the
source's summary page; that page names the raw item in `raw/`, which
holds the original text.

**Seeing why a page says what it says.** A page's history on GitHub
("History", or "Blame" line by line) shows every change with its author
(an agent or a person), the person who triggered it, the source, and the
reason given for the change.

## 6. Using a brain

**Asking.** In any Claude Code session with the plugin, e.g. "What did
we decide about the evaluation protocol of project X?"

**Adding sources.** `ingest <url | DOI | arXiv id | file>`, one source
per request.

**Session capture.** Work with the plugin loaded and decisions and
findings are captured automatically, including the names of the people
involved; code, chatter, personal remarks and secrets are not. Stating
the reason for a decision makes the digest useful. Each captured session
starts with a one-line notice; capture can be switched off per session
or per repo, and anyone can ask the owner to remove content about them,
including from the history.

**Scope.** Sources outside a brain's `scope.md` are ingested but flagged
until someone deletes them or clears the flag.

**Corrections.**

- Edit a page directly (editor, Obsidian, GitHub) and open a PR; your
  lines are then protected from agents.
- Ask an agent for larger changes ("merge these two pages", "mark this
  page as deprecated").
- Set `locked: true` on pages agents must not change; they will only
  report suggested changes.
- Resolve a `Status: Disputed` block by editing the page, or by asking
  an agent and giving the reason. Agents resolve disputes on their own
  only when a newer source explicitly corrects the old one.

## 7. Operating a brain

- **Owner:** decides the schema (page types, templates, agent rules)
  and the scope, and approves code upgrades for the content repo.
- **Developers:** change the code repo through tested PRs, tag a
  release, and upgrade content repos with a one-line PR.
- **Server operator:** runs the compile worker and search. The worker
  polls the content repo, checks out the pinned code release and
  compiles new raw items. One compile worker per brain.
- **GitHub setup** per content repo: the required check, a ruleset
  protecting the main branch, and a GitHub App, the only actor allowed
  to push regenerated indexes directly.
- **Admins:** perform rare history-rewriting operations, such as
  erasing personal data on request (`admin/`).

## 8. Further reading

- Content repo README: member setup and commands.
- This repo's README: layout, tools, releases.
- `specs/00`–`06`: requirements, data model, ingest, agent operations,
  retrieval, interfaces, operations.
- `specs/implementation-status.md`: what is built, tested and open.
- `specs/parked.md`: deferred ideas, priority items first.
