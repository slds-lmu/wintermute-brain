# 06 - Operations

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
  plugin. Anyone opening the repo in Claude Code gets it. The content
  repo (`wintermute-brain-content-slds`) does the same (03 § 4); the code repo
  (`wintermute-brain`) never does (01 § 1).
- **Code and content are separate repos** (01 § 1, 2026-11-05). The
  plugin and the tools come from the code repo at the version pinned in
  the content repo's `.brain-version`; installing the plugin never
  downloads brain content.
- **CLI tools, installed once per member** (setup guide or script):

  | Tool | Needed for | Who |
  |---|---|---|
  | git, `gh` | PRs | everyone |
  | gitleaks | secret scan before a digest leaves the machine | everyone |
  | defuddle, `slds-paper-litdownload` | manual web / paper ingest | only people who ingest by hand |

- Later, if installs are a hurdle: move fetching to the server.

## 3. Search (Q2, Q9)

- **One central qmd on the server**, re-indexed after every pull
  (§ 4). Members' agents query it over MCP. Hybrid mode uses the GPU;
  a CPU instance of the same qmd answers while the GPU is taken (§ 9).
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

- Who administers the server worker and the API key.

### 8.1 GitHub usage (checked 2026-11-05 via the billing API)

`slds-lmu` is on the **Team** plan (307 seats, 182 used). Usage across
the whole org, Jan-Nov 2026:

| | Typical month | Peak | Billed |
|---|---|---|---|
| Actions (all runners) | ~600-1,000 min | 3,217 min (May) | $0 except $4.26 (July) |
| Git LFS storage | ~5 GB (approximately 3,800 GB-hours) | - | $0 |
| Git LFS bandwidth | ~0.1 GB | - | $0 |

So today's use is inside the included amounts. The exact included
quotas are not in the API; check the billing page before scaling up.

**Expected brain load:** each agent operation costs about two short
Actions runs (the PR check, then the index Action after merge). With
automatic session digests plus their compile PRs, that could be about
1,000-2,000 extra minutes a month at group scale [estimate], which
could push the org past its included minutes. PDFs add a few GB of LFS
per thousand papers. **Watch the Actions minutes once session digests
run;** options then are a cheaper check (skip the index Action for
raw-only PRs) or a self-hosted runner on the group server.

## 9. Container deployment

The GPU deployment uses a shared application image for the compile worker
and authenticated search gateway. The code repository owns the Dockerfile
and server-image workflow. The VM operations repository owns Compose,
Ansible, Caddy, secrets, host paths, and the immutable image pin. Review
branches may publish a pinned image without merging their PR.

The content clone is wintermute-brain-content-slds. The worker checks out
the code tag named by its .brain-version before invoking plugin/tools and
the compile plugin. Service infrastructure runs from the pinned container
image. Updating the service image does not change the content's tool pin.

The GPU qmd holds the shared lock until another GPU caller requests it.
Search drains active requests for a bounded time, stops qmd, waits for
process exit, and yields the GPU. Queue and running-job checks keep it
unloaded across a MinerU batch; it reloads after a short idle interval.
Whisper HTTP stays resident. The index and models are local persistent
mounts outside images.

A second qmd process runs CPU-only on the same index, at low scheduling
priority, and never touches the GPU or its lock. It answers every call that
needs no model. Searches go to the GPU qmd whenever it is available. While
it is not, a search also starts on the CPU qmd, one search at a time, and
the first complete answer wins. Both use the same models and settings, so
a CPU answer has full quality and only takes longer. qmd cannot cancel a
running search, so abandoning a CPU search kills that process, which
restarts within a second. An index update waits for the GPU qmd.

Members use personal GitHub tokens with read access to the content repo.
The compile worker uses a separate internal service credential for MCP.
Only the public MCP and health routes are exposed by Caddy. The GitHub
App is installed on the code and content repos; git and gh renew their
installation tokens without periodic worker restarts.

Operational details and validation commands are in server/README.md.

qmd's HTTP server buffers every response until it is complete, so it can
deliver no notification on an open stream. The gateway therefore asks qmd
for an empty subscription, which qmd acknowledges and closes immediately.
Clients learn at connection time that no change notifications will come.
Search calls hold their GPU admission until completion or disconnect.
