# 06 — Operations

Status: **draft**
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
| **GitHub** (`slds-lmu`) | brain repo, required check on PRs, index Action, "Brain health" issue (03 § 2.1, § 5.3) |

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
  plugin. Anyone opening the repo in Claude Code gets it. The brain
  repo itself does the same (03 § 4).
- **CLI tools, installed once per member** (setup guide or script):

  | Tool | Needed for | Who |
  |---|---|---|
  | git, `gh` | PRs | everyone |
  | gitleaks | secret scan before a digest leaves the machine | everyone |
  | defuddle, `slds-paper-litdownload` | manual web / paper ingest | only people who ingest by hand |

- Later, if installs are a hurdle: move fetching to the server.

## 3. Search (Q2, Q9)

- **One central qmd on the server**, re-indexed after every pull
  (§ 4). Members' agents query it over MCP. Hybrid mode uses the GPU.
- **Fallback:** if the server is unreachable, the agent uses the
  generated indexes plus grep on the local clone. Nothing depends on
  qmd (CLAUDE.md, tool independence).
- **Access (Q9): per-person login.** Only people with read access to
  the brain repo may query. Sketch: an auth proxy in front of qmd's
  MCP endpoint checks the caller's GitHub token against the repo's
  permissions. With one repo per tier later, the same check gives
  per-tier access.
- qmd's index lives outside git and is rebuildable from the repo.

## 4. The server worker (Q4, Q5)

- **Polling every 5 minutes:** pull `main`; compile raw items without a
  summary page, one at a time (03 § 3); re-index qmd. No webhook, so
  the server needs no inbound access from the internet.
- **GitHub access: a GitHub App** installed on the brain repo only,
  with the rights to open PRs and comment on the "Brain health" issue.
  No seat, short-lived tokens. Its commits carry the git author
  `brain-agent-compile` (03 § 6.1).
- **State:** a clone of the repo and qmd's index, both rebuildable from
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

- **GitHub only for now, plus branch protection on `main`:** no
  force-push, no deletion.
- **Priority for later** (`parked.md` K30): a full mirror (incl. LFS)
  outside GitHub, e.g. on the server, whose disk is covered by the
  university backup.

## 8. Still open

- LFS limits and cost of the `slds-lmu` plan (§ 6).
- GitHub Actions minutes for a private repo: the required check and
  the index Action run on every PR and merge. Check the plan's quota.
- Who administers the server worker and the API key.
