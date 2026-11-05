# 06 — Operations

Status: **accepted** (owner, 2026-11-05; implemented, see `implementation-status.md`)
Owner: Bernd Bischl
Last updated: 2026-11-05
Depends on: `00-requirements.md`, `02-ingest.md`, `03-agent-ops.md`

Where the brain runs, how it gets onto machines, access, cost, storage
and backup. All points below were decided by the owner on 2026-11-05
(06-Q1 to Q9), unless marked otherwise.

## 1. What runs where (Q1)

| Where | What |
|---|---|
| **Member's machine** | Claude Code with the brain plugin: ingest / query / lint commands, session hooks, digest agent (02 § 2) |
| **Group GPU server** | compile worker (02 § 2.4), central qmd (§ 3), PDF conversion; later the Mattermost bot |
| **GitHub** (`slds-lmu`) | code repo (releases, reusable workflows) and content repo (required check on PRs, index Action, "Brain health" issue; 03 § 2.1, § 5.3) |

Members' machines do only what needs their local context (their
sessions) or their command. Heavy work (GPU, models, PDF conversion)
and single-writer work (compile) run on the server. GitHub is the gate
and the record.

## 2. Distribution to members (Q3)

- The brain is a **Claude Code plugin in the wintermute marketplace**
  (F3). It bundles the commands, the session hooks, the digest agent
  and the MCP connection to the server's qmd.
- **Set up once per project repo:** the project repo's committed
  `.claude/settings.json` declares the marketplace and enables the
  plugin. Anyone opening the repo in Claude Code gets it. The content
  repo (`wintermute-brain-content-slds`) does the same (03 § 4); the code repo
  (`wintermute-brain`) never does (01 § 1).
- **Code and content are separate repos** (01 § 1, 2026-11-05). The
  plugin and the tools come from the code repo (latest `main`, § 2.1);
  installing the plugin never downloads brain content.
- **CLI tools, installed once per member** (setup guide or script):

  | Tool | Needed for | Who |
  |---|---|---|
  | git, `gh` | PRs | everyone |
  | gitleaks | secret scan before a digest leaves the machine | everyone |
  | defuddle, `slds-paper-litdownload` | manual web / paper ingest | only people who ingest by hand |

- Later, if installs are a hurdle: move fetching to the server.

### 2.1 Member setup (decided 2026-11-05)

Designed after the first user test (`implementation-status.md` § 7):
one command sets everything up and checks it; one command starts work.

- **Everything runs the latest code** (owner): members, the content
  repo's checks and the server worker all use the code repo's `main`.
  No `.brain-version`, no release tags for now; pinning returns later
  (`parked.md` K40), the marketplace install too (K41).
- **`setup-brain`** (in the code repo, run once):
  1. checks the prerequisites (git, gh, Claude Code, Python ≥ 3.11;
     gitleaks optional);
  2. asks for the login (S1): **(a)** the member's normal `gh` login, or
     **(b)** a dedicated token for the brain (a fine-grained token
     limited to the content repo; contents, pull requests, issues: read
     and write; actions: read), stored in a file only the member can
     read. "Brain login" via the GitHub App later (K39);
  3. clones the code repo and the content repo over HTTPS, without PDFs
     (LFS downloads skipped);
  4. configures the content clone so that git uses the same credentials
     as `gh` (a repo-local credential helper); nothing global changes;
  5. writes the config (S2) `~/.config/brain/config.toml`: content repo,
     its folder, code folder, person slug, login mode and token file,
     search address, and the folders whose sessions are captured;
  6. installs the command **`brain`** (`~/.local/bin/brain`);
  7. checks the result: repo visible and writable, git fetch works,
     Claude Code found; reports clearly what is wrong.
- **`brain`** (start work): updates the code copy to the latest `main`,
  sets the brain settings (and, in token mode, the token) for this
  session only, and starts Claude Code with the brain plugin. Arguments
  are passed to Claude Code.
- **Captured sessions** (N6): a session is captured only if it runs in a
  folder listed under `capture` in the config, or below it. The content
  repo is listed by default; others are added by the member. Elsewhere
  `brain` works, but nothing is captured and no notice is shown.

## 3. Search (Q2, Q9)

- **One central qmd on the server**, re-indexed after every pull
  (§ 4). Members' agents query it over MCP. Hybrid mode uses the GPU.
- **Fallback:** if the server is unreachable, the agent uses the
  generated indexes plus grep on the local clone. Nothing depends on
  qmd (CLAUDE.md, tool independence).
- **Access (Q9): per-person login.** Only people with read access to
  the content repo may query. Sketch: an auth proxy in front of qmd's
  MCP endpoint checks the caller's GitHub token against the repo's
  permissions. With one repo per tier later, the same check gives
  per-tier access.
- qmd's index lives outside git and is rebuildable from the repo.

## 4. The server worker (Q4, Q5)

- **Polling every 5 minutes:** pull the content repo's `main`; update
  the code repo to the latest `main`; compile
  raw items without a summary page, one at a time and oldest first
  (03 § 3); re-index qmd. No webhook, so
  the server needs no inbound access from the internet.
- **GitHub access: a GitHub App** (`wintermute-brain`) installed on
  the code repo and the content repo only, with the rights to open PRs
  and comment on the "Brain health" issue; it is also the ruleset's
  bypass actor for the index Action.
  No seat, short-lived tokens. Its commits carry the git author
  `brain-agent-compile` (03 § 6.1).
- **State:** clones of the content and code repos and qmd's index, all rebuildable from
  GitHub. The worker keeps no state of its own (02 § 2.4).

## 5. Model access and cost (Q6)

- **Members' machines:** the member's own Claude account, for both the
  interactive agent and the background digest agent (small model, 02
  I3).
- **Server:** a **group Anthropic API key** with a monthly spending
  limit in the Anthropic console. Set the limit after measuring the
  first weeks of real use.

## 6. Storage (Q7)

- **PDFs and other binaries in `raw/` go into git LFS on GitHub** (D2
  kept). The originals stay, so text can be re-converted later with a
  better tool.
- **Member clones skip LFS downloads by default** (`lfs.fetchexclude`
  or equivalent); they only need the Markdown. The server fetches
  everything.
- **To check first:** the LFS storage and bandwidth limits of the
  `slds-lmu` plan, and the cost of data packs.

## 7. Backup (Q8)

- **GitHub only for now, plus the ruleset on `main`:** no force-push,
  no deletion.
- **Priority for later** (`parked.md` K30): a full mirror (incl. LFS)
  outside GitHub, e.g. on the server, whose disk is covered by the
  university backup.

## 7a. Personal data (K27, decided 2026-11-05)

Not a legal opinion. The brain processes personal data: person pages,
names in digests and pages, later meeting transcripts, chat and mail.
Git makes this harder than in a normal wiki: everything stays in the
history, in LFS, in backups and in every member's clone.

**What already limits it** (decided earlier):

- `person` pages hold only role, projects and expertise (01 § 5.2);
  evaluations and personnel matters belong to the owner tier.
- Session digests never keep personal remarks or personal machine setup
  (02 § 2.3); transcripts themselves are never stored, only digests.
- `scope.md` lists private life as out of scope; such sources are
  flagged (01 § 2.1).
- Secrets are stripped before anything is written (R15).

**Proposal:**

1. **Minimise at the door** (PD4): no fixed list of refused content;
   what belongs into a brain is defined by its `scope.md`, and anything
   outside is flagged and linted (01 § 2.1). Prefer digests over full
   transcripts for any new channel (meetings, chat, mail).
2. **Inform and opt out** (PD3): members are told what the brain
   captures (tutorial, content README): which repos opt in, that
   digests keep decisions and findings with names, and how to switch
   capture off. **Every captured session starts with a one-line notice**
   ("Brain: this session is captured into … Off for one session:
   BRAIN_SESSION_DIGEST=off"). Anyone can ask to be removed.
3. **Removal on request**, in two steps: first remove the content from
   the current pages (an `edit`, immediately); then, if the person asks
   for erasure, remove it from the history too (rewrite the content
   repo's history, purge LFS objects, ask everyone to re-clone, re-clone
   on the server). The second step is disruptive and **admin-only**
   (PD2): the tool `admin/erase` in the code repo (not shipped with the
   plugin) checks admin rights, defaults to a dry run, needs the repo
   name typed to execute, writes a backup bundle first, and its
   force-push only passes the ruleset for admins. Runbook:
   `admin/README.md` (including GitHub Support for PR refs and LFS).
4. **Data protection officer:** the owner has already consulted the
   LMU data protection officer (2026-11-05); no further step planned.

| # | Question | Recommendation |
|---|---|---|
| PD1 | Involve the LMU data protection officer, and when? | **decided (owner, 2026-11-05): no further step; the owner has already talked to him** |
| PD2 | Erasure requests: rewrite git history, or only remove from current pages? | **decided (owner, 2026-11-05): rewrite history, admin-only** via `admin/erase` and its runbook; members and agents cannot do it |
| PD3 | How are members informed and how do they opt out? | **decided (owner, 2026-11-05): notice in tutorial and README, plus a one-line notice at every captured session start**; capture off per session; removal on request |
| PD4 | What is never ingested? | **decided (owner, 2026-11-05): no fixed list**; each brain's `scope.md` decides, with flagging and lint (01 § 2.1) |

## 8. Still open

- Who administers the server worker and the API key.

### 8.1 GitHub usage (checked 2026-11-05 via the billing API)

`slds-lmu` is on the **Team** plan (307 seats, 182 used). Usage across
the whole org, Jan–Nov 2026:

| | Typical month | Peak | Billed |
|---|---|---|---|
| Actions (all runners) | ~600–1,000 min | 3,217 min (May) | $0 except $4.26 (July) |
| Git LFS storage | ~5 GB (≈ 3,800 GB-hours) | — | $0 |
| Git LFS bandwidth | ~0.1 GB | — | $0 |

So today's use is inside the included amounts. The exact included
quotas are not in the API; check the billing page before scaling up.

**Expected brain load:** each agent operation costs about two short
Actions runs (the PR check, then the index Action after merge). With
automatic session digests plus their compile PRs, that could be about
1,000–2,000 extra minutes a month at group scale [estimate], which
could push the org past its included minutes. PDFs add a few GB of LFS
per thousand papers. **Watch the Actions minutes once session digests
run;** options then are a cheaper check (skip the index Action for
raw-only PRs) or a self-hosted runner on the group server.
