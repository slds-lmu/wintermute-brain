# Session 2026-11-05: build vs. reuse, and what's left

Working doc for this session. Owner answers go under **Owner:** lines.

## a) Build or use existing software?

### What the plan already reuses

We're not really writing it from scratch:

- Agent loop: Claude Code.
- Skill: fork of Astro-Han (mostly prompts plus one Python checker).
- Search: qmd. Web capture: defuddle. Papers: litdownload.
- Secret filter: gitleaks. Field names: OKF.

Our own code would be small: `tools/commit-op`, the index generator,
the deterministic lint, the ingest adapters, and later a bot. That's a
few hundred lines of scripts, not an application.

### Why a ready-made product doesn't fit

| Class | Examples | Fails on |
|---|---|---|
| LLM-wiki apps | nashsu/llm_wiki, gbrain | single user; gbrain keeps state in Postgres |
| "AI second brain" / RAG servers | Khoj, AnythingLLM | data lives in their database, not git ("repo is complete"); they retrieve rather than compile a maintained wiki; AGPL (Khoj) |
| Team wikis with AI | Notion AI, Confluence, Outline | multi-user access and permissions are solved, but humans write the pages and the AI only answers; content isn't plain Markdown in git |
| Memory frameworks | Mem0, Zep, Basic Memory | chat memory, not citable pages (Basic Memory is also AGPL and writes into every file) |

### Where we take on real risk

Our custom parts are exactly the hard parts, and nobody has proven
them: concurrent autonomous writers, duplicate pages, human
corrections getting overwritten, and tiers.

So the real question isn't "build or buy". It's whether a **compiled
wiki beats plain retrieval** over the raw sources. qmd or AnythingLLM
pointed at papers and Mattermost needs none of the concurrency
machinery.

### Recommendation

~~Spike v0 plus a retrieval-only baseline before forking.~~
**Owner (2026-11-05): no spike.** A 15-source test can't show whether
the wiki helps; only real use by the group over time can. Build the
fork directly. The MVP done-criterion (00 § 7) is the first check.
Removed from `v0-foundation.md`.

### Gaps closed (research done 2026-11-05)

Full reports: `specs/research/F-anythingllm-arkon.md`,
`G-nashsu-llm-wiki.md` and `H-team-wikis.md`. Repos were cloned and
read; nothing was installed or run.

**Result: none of them should be our base, so the plan stands.** All
fail the same hard rule: state lives in a database or app folder, so
it can't be rebuilt from git. None runs multi-writer agents
server-side.

| Candidate | What it is | Why not as the base | Verdict |
|---|---|---|---|
| AnythingLLM (MIT, very active) | chat with your documents (RAG), no wiki | state in SQLite/LanceDB; chunk citations only; roles too coarse for tiers (every manager sees all workspaces); duplicates qmd | ignore; at most an optional web chat later |
| arkon | very close to our design: compiled pages, revisions, roles, MCP | Postgres only, no git, no Markdown export; PolyForm Internal Use license (not open source, can't be forked); one author, inactive since June; per-claim citations promised in the docs but not in the code | borrow ideas |
| nashsu/llm_wiki (GPL-3.0, plain) | desktop app for one user | every member's app would re-ingest each source pulled via git; no headless mode; rewrites `log.md`/`index.md`; state in `.llm-wiki/`; graph only understands wikilinks; ~92k lines, so a fork = a rewrite | borrow ideas (rewritten in our own words, not copied, because of GPL) |
| Team wikis (Notion, Confluence/Rovo, Glean, Outline, GitBook, Wiki.js, BookStack, Docmost) | humans write, AI answers or drafts | no AI maintains a wiki; only git-backed ones pass "repo is complete", and even Wiki.js 3 drops our OKF fields on web edits; Notion stores data in the US unless on Enterprise | keep git as the source of truth; possibly an optional viewer later |

**One honest caveat (H report):** if we ever stop treating git as the
record, self-hosted **Outline** would beat our plan for a
human-edited team wiki. Our plan wins because the main writer is the
agent, git is the provenance, lint runs on files, and qmd searches
`raw/` as well.

**New ideas from this research** (16 items, including the web
viewer) are parked in `specs/parked.md` (K1–K16) for review after v1
or v2.

**Decisions for you:**

- [x] Accept the conclusion: no product as the base; the fork plan
  stands. **Owner: accepted (2026-11-05).**
- [ ] Should any parked item go into v1 after all? Candidates: K1
  (reason per edit) and K3 (plan before writing) are cheap prompt
  rules that fit `03-agent-ops.md`. Recommendation: decide while
  writing 03.

**Owner:**

## b) What still needs investigating and deciding

### 1. Contradictions inside the specs (fix first, small)

- [x] **Disputed handling.** **Owner (2026-11-05): keep v0's
  `Status: Disputed` blockquote (plain Markdown, not a callout) for
  real disagreements; fine-tune later.** Changed facts are edited in
  place; `Status: Outdated` is not used. Updated in 00 R5/R9, 01 § 6,
  v0-foundation, proposals M13.
- [x] **Search at MVP.** **Owner (2026-11-05): qmd directly from the
  MVP on.** N2 updated; the grep fallback stays (tool independence).
- [x] **Stale text** cleaned up (2026-11-05): 01 § 10, `CLAUDE.md`
  status, P4/P6 marked in `prior-art.md`, kepano note in `LINKS.md`.
  Rejected syntax in P2/M2 stays as history behind its REJECTED tag.

**Owner:**

### 2. Open decisions

Before the MVP:

- [x] **P5 → minimal type system** (owner, 2026-11-05). No ontology:
  types only where membership is indisputable: `person`, `meeting`,
  `paper`, `grant`, `source`. Everything else is the untyped `page`,
  with free tags (`project`, `idea`, `decision`, …). No `synthesis`
  type. Updated 01 § 5.2 (+ layout, slugs, examples, D6), 00 § 9,
  proposals M8/M9, prior-art P5, CLAUDE.md.
- [x] **P7 → lock + protected human lines** (owner, 2026-11-05).
  `locked: true` stops agents; agents may override a human-written
  line only with a newer source (`Overrides-human:` trailer). Both
  enforced in `tools/commit-op` and as a required GitHub check.
  `audit/` inbox parked (K18). Updated 01 § 5.3, v0-foundation
  G6/A2, proposals C9/C10, prior-art P7, CLAUDE.md.
  *Open for 03/06:* a required GitHub check on `main` and agents'
  fast-forward pushes need to fit together (PRs vs. direct push).
- [x] **P8 → two-layer lint** (owner, 2026-11-05): mechanical
  scripts on every push + CI; LLM lint by hand in the MVP, scheduled
  later, reports only. No IWE: own validator script (owner
  confirmed); revisit IWE if we start duplicating it (parked K19). Updated 00 R9, proposals L1/L5, prior-art P8,
  CLAUDE.md.

About 50 unmarked items in `proposals.md`:

- [x] **Batch 1, concurrency** (owner, 2026-11-05): accept C1, C3,
  C4 (search before create), C6, C12; park slug reservation, C5, C8
  (K20–K22); reject C7, C11. Marked in `proposals.md`.
- [x] **Batch 2, ingest** (owner, 2026-11-05): accept I1–I5, I8
  (new raw revision), I9, I10, I11, R3, R5; I12 = MVP task (10-paper
  converter benchmark); park I7, retract op (K23, K24); defer I13–I16
  to their milestones. Marked in `proposals.md`.
- [x] **Batch 3, lint** (owner, 2026-11-05): accept L2, L4 (goal),
  L6; park L3, L7 (K25). Marked in `proposals.md`.
- [x] **Batch 4, query** (owner, 2026-11-05): accept Q3, Q6, Q7;
  park Q4 (K26). Marked in `proposals.md`.

- [x] **Batch 5, leftovers** (owner, 2026-11-05): accept F1–F3;
  F4 skipped; defer F5
  with tiers; M1 marked decided; reject M10, M11, M16; M18 = `First
  Last`; slug patterns confirmed. `proposals.md` is now fully
  decided.

**Owner:**

### 3. Specs not written yet

- [ ] `03-agent-ops.md`: **drafted 2026-11-05.** Owner to review;
  open questions O1–O4 in its § 9: **all decided** (2026-11-05).
- [ ] `02-ingest.md`: **drafted 2026-11-05** with the automatic
  `session` channel (Claude Code hooks, digest agent, server-side
  compile). I1–I3 decided: sessions are in the MVP.
- [ ] `04-retrieval.md`, `05-interfaces.md`: **drafted 2026-11-05.**
  R1–R3 and U1–U2 decided.
- [ ] `06-ops.md`: **drafted 2026-11-05** from Q1–Q9 below; three
  small items still open in its § 8.

**Owner:**

### 4. Things to test (empirical)

- [x] ~~The v0 spike plus the retrieval baseline~~ (dropped 2026-11-05, see a).
- [ ] 10-paper PDF converter benchmark (MinerU vs. Marker).
- [ ] qmd at several thousand files.
- [x] ~~IWE as the validator~~ (not adopted; parked K19).
- [ ] Obsidian with root-absolute links: does `/wiki/...` resolve?
  Not tested.
- [ ] Git LFS quotas and cost in `slds-lmu`, and how GitHub handles
  several agent identities.

**Owner:**

### 5. Coordination and policy

- [x] **F4** (talk to `slds-setup-memory` authors): **skipped** (owner,
  2026-11-05).
- [x] **Personal data:** no policy and no gate for now (owner,
  2026-11-05). The first phase is a test run; humans decide what gets
  ingested. Parked as **priority K27**. Updated 00 § 7 and § 8.

## Suggested order

1. ~~Fix the spec contradictions (b1).~~ Done.
2. ~~Run the spike~~ (dropped).
3. ~~Decide P5 / P7 / P8 (b2).~~ Done, plus all of `proposals.md`.
4. Write `03-agent-ops.md`.

**Owner:**

## 06-ops decisions (written into `specs/06-ops.md`, 2026-11-05)

- **Q1 What runs where** (owner, 2026-11-05): member's machine =
  Claude Code + brain plugin (commands, session hooks, digest agent);
  group GPU server = compile worker, qmd, PDF conversion, later the
  bot; GitHub = repo, required check, index Action, "Brain health"
  issue.
- **Q2 Search** (owner, 2026-11-05): one central qmd on the server,
  re-indexed after every merge, reached by members' agents via MCP.
  Fallback: index + grep on the local clone.
- **Q3 Distribution** (owner, 2026-11-05): the brain is a Claude Code
  plugin in the wintermute marketplace, declared once in each project
  repo's committed `.claude/settings.json`. Members install the few
  CLI tools once (git, gh, gitleaks; defuddle and litdownload only for
  manual web/paper ingest), with a short setup guide or script. Moving
  fetching to the server: later, if installs are a hurdle.
- **Q4 Worker trigger** (owner, 2026-11-05): polling every 5 minutes
  (pull, compile raw items without a summary page, re-index qmd). No
  webhook, so no inbound access to the server is needed.
- **Q5 Server's GitHub access** (owner, 2026-11-05): a GitHub App
  installed on the brain repo only (open PRs, comment on the "Brain
  health" issue). No seat, short-lived tokens. Separate from the git
  author `brain-agent-compile` (03 § 6.1).
- **Q6 Model access and cost** (owner, 2026-11-05): members' machines
  use the member's own Claude account (interactive agent and digest
  agent). The server uses a group Anthropic API key with a monthly
  spending limit; set the limit after measuring the first weeks.
- **Q7 Large files** (owner, 2026-11-05): keep D2, PDFs in git LFS on
  GitHub. Member clones skip LFS downloads by default; only the server
  fetches PDFs. Check the LFS limits of the `slds-lmu` plan first (§ 4).
- **Q8 Backups** (owner, 2026-11-05): GitHub only, plus branch
  protection on `main` (no force-push, no deletion). Backup outside
  GitHub parked as **priority K30**.
- **Q9 Search access** (owner, 2026-11-05): per-person login. Only
  people with read access to the brain repo may query the server's
  qmd. Sketch: an auth proxy in front of qmd's MCP endpoint checks the
  caller's GitHub token against the repo's permissions. Fits the tiers
  later (one repo per tier).

## Implementation (2026-11-05)

Owner declared the spec stage finished; specs 00–06 are marked
**accepted** and the MVP (00 § 7) is implemented in this repo, which now
*is* the brain repo (to become `slds-lmu/brain-group`). Nothing has run
against GitHub or the server yet.

### Built

| Part | Where | Spec |
|---|---|---|
| Repo skeleton: `raw/`, `wiki/<type>/`, `templates/`, `agents.txt`, LFS attributes, generated indexes | repo root | 01 |
| `tools/index` (per-folder indexes, `page/` split by first letter) | `tools/` | 01 § 7, 04 R3 |
| `tools/lint` (all rules of 03 § 5.1; safe fixes with `--fix`; lock + human-line rules with `--agent`) | `tools/` | 03 § 5.1, 01 § 5.3 |
| `tools/check_evidence` (fork of v0's checker; per-paragraph citations → raw folders; `--queue` = compile backlog) | `tools/` | 03 § 3, G2 |
| `tools/start-op`, `tools/commit-op` (worktree; indexes; lint; preconditions; agent author; PR with auto-merge; `--check` for CI) | `tools/` | 03 § 2, § 6, A2 |
| `tools/log`, `tools/report-health` ("Brain health" issue comments) | `tools/` | 01 § 8, 03 § 5.3 |
| Tests: good fixture wiki + one broken copy per rule + git flow (38 tests, all pass) | `tools/tests/` | L6 |
| Required check (`check.yml`) and index Action (`index.yml`) | `.github/workflows/` | 03 § 2.1 |
| Plugin: `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint`, `brain` skill (forked SKILL.md with our rules), qmd MCP config | `plugin/` | 05, 03 |
| Session digests: Stop/SessionStart/SessionEnd hooks, background digest agent (Haiku), gitleaks, raw-only PR via the GitHub API | `plugin/scripts/` | 02 § 2 |
| Server: compile worker (poll, derived queue, 3 tries + backoff, qmd re-index), GitHub App token, qmd auth proxy, systemd units | `server/` | 06, 02 § 2.4 |
| Schema `CLAUDE.md`, `README.md`, `plugin/README.md`, `server/README.md` | repo | 01 § 2 |

### Decisions taken while implementing (owner to confirm)

- **One repo.** Brain content, `tools/`, the plugin (`plugin/`) and the
  server code live in this repo; the wintermute marketplace points at
  `plugin/` (snippet in `plugin/README.md`). Simplest thing that keeps
  CI, tools and the skill in one place.
- **Session digest ids** carry the repo name, the title and the first 6
  chars of the session id (`src-YYYYMMDD-<repo>-<title>-<sid6>`), so
  parallel digests of different sessions never collide. Checkpoints are
  derived from `source.yaml` (`session`, `messages`); a local cache
  speeds it up.
- **Digest trigger:** 20 new human turns, or 30 minutes since the last
  digest with at least 3 new turns; session end/start flush needs 3.
- **Index Action also applies the safe link fix** on `main` (Obsidian's
  slash-less links), so a human push never fails the check for that.
- **Compile worker model:** `sonnet` by default (`BRAIN_MODEL`).
- **Lint levels:** slash-less links are a warning (auto-fixed on main),
  relative and broken links are errors; open Disputed blocks are `info`.
- `tools/lint --check-index` is only run on pushes to `main` (PRs never
  carry index files).

### Not done / needs a real environment

- Nothing was run against GitHub: branch protection, the required check,
  auto-merge, the GitHub App, LFS quotas (06 § 8) are set up by hand.
- `.mcp.json` uses `${VAR:-default}` expansion; verify Claude Code
  expands it, else set `BRAIN_QMD_URL` explicitly.
- The qmd MCP HTTP flags depend on the pinned qmd version (not chosen).
- 10-paper PDF converter benchmark (I12) still to run; paper ingest
  currently relies on litdownload (arXiv TeX/HTML) only.
- The LLM lint (03 § 5.2) is a prompt in the skill, by hand only (as specified).
- Obsidian: whether `/wiki/...` links resolve is still untested.
- The session hook was smoke-tested with a fake transcript (spawns a
  digest, no crash); an end-to-end digest needs `gh` access to the real repo.

## First live test (2026-11-05, afternoon)

Run from Bernd's yolobox with the `slds-write` token (`ghr`), gitleaks
8.30.1 and defuddle via npx in a scratch folder (not installed; Marc
adds them to the slds docker image).

- **Unit tests:** 38/38 pass. `tools/lint` on the repo: clean.
- **First ingest worked end to end:** Karpathy's LLM-wiki gist →
  `raw/web/2026/src-20261105-karpathy-llm-wiki/` + `wiki/source/…` +
  `wiki/page/llm-wiki.md`; check_evidence and lint clean; PR #2 opened
  by `commit-op`, required check passed, auto-merged (rebase) about two
  minutes later. Commit on `main` has author `brain-agent-interactive`.
- **A ruleset on `main` already exists** ("main: required check":
  required check `check`, no deletion, no force-push; bypass: repository
  admins). Not visible via the classic branch-protection API.

### Problems found

1. **FIXED (2026-11-05)** — new exit 4 "outcome unknown" (PR stays
   open, never redo), 10-minute wait, check result read from the Actions
   run; 03 § 2 step 5, skill, compile prompt, 5 new tests (43 pass),
   verified live against PR #2. Was: **`commit-op` misreports a merged PR as failed.** `wait_for_merge`
   asks `gh pr view` for `statusCheckRollup`, which the fine-grained
   token may not read ("Resource not accessible by personal access
   token"). The call fails every time, so after `--wait` seconds it
   reports "not merged … Redo the operation" although PR #2 had merged.
   An agent following the skill would then redo the ingest and create a
   duplicate. **Fix:** query `state,mergedAt` separately and only read
   check results when permitted; never advise a redo when the state is
   unknown.
2. **The index Action cannot push to `main`:** the ruleset's required
   check blocks it ("Required status check "check" is expected"). So
   `index.md` / `wiki/*/index.md` on `main` don't list the new pages yet.
   **Fix:** the brain GitHub App (06 § 4) as the ruleset's bypass actor,
   with its token as `BRAIN_APP_TOKEN`.
3. **Admin bypass vs. "nobody pushes directly to `main`"** (03 § 2.1,
   decided today): the ruleset lets repository admins bypass. Remove the
   admin bypass once the App exists.
4. **SSH remote in the box:** the clone's remote is `git@github.com:…`
   and the box has no SSH agent; the test used a per-command
   `url.https://github.com/.insteadOf` override. For members' setups,
   clone over HTTPS (or document the override).
