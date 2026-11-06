# Implementation status

Status: **living document**
Last updated: 2026-11-05

What is built, what was decided while building it, what the live tests
showed, and what is still open. Design decisions live in the specs
(00–06); parked ideas in `parked.md`.

## 1. Built (MVP, 2026-11-05, PR #1 by Marc Becker)

Specs 00–06 accepted; this repo *is* the brain repo (later
`slds-lmu/wintermute-brain-content-slds`).

| Part | Where | Spec |
|---|---|---|
| Repo skeleton: `raw/`, `wiki/<type>/`, `templates/`, `agents.txt`, LFS attributes, generated indexes | repo root | 01 |
| `tools/index` (per-folder indexes, `page/` split by first letter) | `tools/` | 01 § 7, 04 R3 |
| `tools/lint` (all rules of 03 § 5.1; safe fixes with `--fix`; lock + human-line rules with `--agent`) | `tools/` | 03 § 5.1, 01 § 5.3 |
| `tools/check_evidence` (fork of v0's checker; per-paragraph citations → raw folders; `--queue` = compile backlog) | `tools/` | 03 § 3 |
| `tools/start-op`, `tools/commit-op` (worktree; indexes; lint; preconditions; agent author; PR with auto-merge; `--check` for CI) | `tools/` | 03 § 2, § 6 |
| `tools/log`, `tools/report-health` ("Brain health" issue comments) | `tools/` | 01 § 8, 03 § 5.3 |
| Tests: good fixture wiki, one broken copy per rule, git flow, merge wait (43 tests) | `tools/tests/` | L6 |
| Required check (`check.yml`) and index Action (`index.yml`, pushes as the GitHub App) | `.github/workflows/` | 03 § 2.1 |
| Plugin: `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint`, `brain` skill, qmd MCP config | `plugin/` | 05, 03 |
| Session digests: Stop/SessionStart/SessionEnd hooks, background digest agent (Haiku), gitleaks, raw-only PR via the GitHub API | `plugin/scripts/` | 02 § 2 |
| Server: compile worker (poll, derived queue, 3 tries + backoff, qmd re-index), GitHub App token, qmd auth proxy, systemd units | `server/` | 06, 02 § 2.4 |
| Search gateway: GitHub token checks that survive GitHub outages and limit unauthenticated use, one GPU qmd next to OCR and transcription, limited parallel searches, errors instead of false empty results when GPU memory runs out | `server/brain_server/` | 06 § 3, § 9 |

## 2. Decisions taken while implementing (made by Marc's agent in PR #1; all reviewed by the owner 2026-11-05)

- **SUPERSEDED (owner, 2026-11-05) by the code/content split (01 § 1, K32).** **One repo.** Brain content, `tools/`, `plugin/` and `server/` live in
  this repo; the wintermute marketplace points at `plugin/`.
- **CONFIRMED (owner, 2026-11-05).** **Session digest ids:** `src-YYYYMMDD-<repo>-<title>-<sid6>` (first 6
  chars of the session id), so parallel digests never collide.
  Checkpoints are derived from `source.yaml` (`session`, `messages`); a
  local cache speeds it up.
- **CONFIRMED (owner, 2026-11-05).** **Digest trigger:** 20 new human turns, or 30 minutes since the last
  digest with at least 3 new turns; session start/end flush needs 3.
- **CONFIRMED (owner, 2026-11-05).** **Index Action also applies the safe link fix** on `main` (Obsidian's
  slash-less links).
- **CONFIRMED (owner, 2026-11-05; review cost after the first weeks).** **Compile worker model:** `sonnet` by default (`BRAIN_MODEL`).
- **CONFIRMED (owner, 2026-11-05).** **Lint levels:** slash-less links are a warning (auto-fixed on main);
  relative and broken links are errors; open Disputed blocks are `info`.
- **CONFIRMED (owner, 2026-11-05).** `lint --check-index` runs only on pushes to `main` (PRs never
  carry index files).

## 3. GitHub setup (done 2026-11-05)

- Ruleset "main: required check" on `main`: required check `check`, no
  deletion, no force-push. Bypass: the GitHub App and, during the test
  phase, repository admins (`parked.md` K31). Not visible via the
  classic branch-protection API.
- GitHub App `wintermute-brain` (ID 5628051), owned by `slds-lmu`,
  installed on this repo only. Repo secrets `BRAIN_APP_ID`,
  `BRAIN_APP_PRIVATE_KEY`; the index Action mints a token per run.
- Auto-merge and rebase-merge enabled.
- Bernd's yolobox: fine-grained token `slds-write` (owner `slds-lmu`,
  this repo only), used via `ghr`/`gitr`. Fine-grained tokens cannot
  read check runs or commit statuses; `commit-op` reads the check result
  from the Actions run instead (03 § 2 step 5).

## 4. Live tests (2026-11-05)

Run from Bernd's yolobox; gitleaks 8.30.1 and defuddle via npx in a
scratch folder (Marc adds them to the slds docker image).

| Test | Result |
|---|---|
| Unit tests, lint on the repo | pass, clean (47 tests after the fixes below) |
| Ingest 1 (web, new): Karpathy's LLM-wiki gist | PR #2, check passed, auto-merged in ~2 min; author `brain-agent-interactive` |
| Ingest 2 (web, update): rohitg00's LLM Wiki v2 gist | PR #4; existing page updated, no duplicate; `commit-op` reported "merged" correctly |
| Index Action via the App | pushed `index: regenerate` after PRs #3 and #4 |
| Query (by hand, grep fallback) | answer from wiki pages with citations and limits |
| `/brain-edit`: clean up the project page (personal token section, superseded status lines, wrong attribution) | PR #23 merged, with plan and reason |
| `/brain-lint` over 18 pages (mechanical, evidence, judgment sample) | 1 orphan; 2 false evidence suspects (ORCID read as dates); 1 overstated claim; missing person pages; no duplicates, no open disputes |
| Session channel end to end: 7 digests of this design session (02 § 2), then one compile-worker pass run by hand (`server/worker.py --once`, Sonnet, no qmd) | 7 digest PRs (#5–#11) and 7 compile PRs (#12–#21), all merged, no failures; one project page `wintermute-brain` built up by update, never duplicated; others ingested in parallel (#15, #16, #19) without conflicts |

Problems found and how they were handled:

1. `commit-op` reported a merged PR as failed and advised a redo
   (token could not read check results). **Fixed:** exit 4 "outcome
   unknown", never redo; check read from the Actions run (PR #3).
2. The index Action could not push to `main` (ruleset). **Fixed:**
   GitHub App as bypass actor (PR #3).
3. Admin bypass vs. "nobody pushes directly to `main`". **Parked**
   (K31), lenient during the test phase.
4. SSH remote without SSH agent in the box. **Done:** docs say "clone
   over HTTPS" for members and the server. Bernd's clone stays on SSH
   (it is the host's folder mounted into yolobox); in the box, push with
   a per-command HTTPS override and `slds-write`.
5. Ingest 2: the agent filled `authors` in `source.yaml` from its own
   knowledge (a full name the source does not contain); caught by hand.
   **Fixed (owner chose rule + check):** 01 § 4 rule "metadata only from
   the source", skill rule, and `tools/check_evidence` now reports
   `title`/`authors` not found in the raw files (registry metadata and
   session digests excepted; 3 new tests, 46 pass). The check flags
   ingest 1 too: "Andrej Karpathy" isn't in the fetched gist either.
   That raw item is immutable, so the suspect stays as a known case.

## 5. Open

- **Empirical checks:**
  - 10-paper PDF converter benchmark (MinerU vs. Marker; I12). Paper
    ingest relies on litdownload (arXiv TeX/HTML) until then.
  - qmd: pick and pin a version (its MCP HTTP flags depend on it); test
    at several thousand files; set up on the server.
- **Not yet tested live:** the server worker on the actual server. Paper
  ingest was done by Marc (PR #15).
- Who administers the server worker and the API key (06 § 8).
- **One GPU qmd (06 § 9, PR #35)** replaced the accepted handoff to OCR, on
  measurements. The owner's agreement is pending.
- **Search login scope.** In `gh` login mode `brain` sends the member's `gh`
  token, usually with broad scopes, to the search server on every request. The
  gateway forwards it only to GitHub and keeps no plaintext copy. Options: (a)
  leave it; (b) have `setup-brain` ask for a separate read-only token for search.
  Recommendation: (b), at the cost of one setup step. Owner to decide.

## 6. Changes after the live tests (2026-11-05)

- **Reasons and plan in every commit** (owner): `commit-op --plan` and
  `--reason`; a change without a reason per changed wiki page is refused
  (ingest, compile, edit). 03 § 3, § 6; skill; compile prompt; tests.
- **Obsidian works with our links** (Bernd, 2026-11-05): root-absolute
  `/wiki/...` links resolve and backlinks show. The repo now ships
  `.obsidian/app.json` with the two link settings (01 § 6); the rest of
  `.obsidian/` is git-ignored.
- **Plugin search config is valid:** Claude Code expands `${VAR}` and
  `${VAR:-default}` in `.mcp.json` `url` and `headers`, also for plugin
  servers (code.claude.com/docs/en/mcp, checked 2026-11-05). Gotcha: a
  variable set to the empty string expands to empty, not to the default.
- **GitHub usage checked** (2026-11-05, 06 § 8.1): Team plan; org-wide
  Actions and LFS use are inside the included amounts. Watch Actions
  minutes once session digests run.
- **Session-channel test findings** (2026-11-05, all open):
  1. **FIXED (2026-11-05):** a backlog is digested in pieces of ~20 human
     turns (`pieces()` in `brain_session.py`; test); the run-is-pending
     flag is cleared only after the last piece. Was: **Long backlogs lose their middle.** A first digest of an
     undigested long session sends at most 60,000 + 60,000 characters
     (head and tail); the middle is cut. Fix: digest a backlog in pieces
     of ~20 turns, as the live hook does.
  2. **FIXED (2026-11-05):** queue is oldest first (author time of the
     adding commit, then session and message range; 02 § 2.4; test).
     Was: **Compile order is alphabetical, not chronological.** The worker's
     queue sorts raw items by folder name (= title), so later digests can
     be compiled before earlier ones and older states survive (e.g. "not
     done: ruleset, GitHub App" on the project page, though both exist).
     Fix: sort by `retrieved` date, then session and message range.
  3. **Digests are snapshots.** Each piece sees only its own ~20 turns,
     so it records "still open" items that were settled minutes later.
     Compile must let newer digests overwrite (works when order is
     right, see 2).
  4. **Assistant errors are copied.** A digest attributed the server
     setup to "Marc" because the assistant said so; Martin sets it up.
  5. **FIXED (2026-11-05):** digest rule "never keep personal machine
     or tool setup" (02 § 2.3, digest prompt). Was: **Personal tool setup leaks in.** Bernd's token setup (yolobox,
     `ghr`, `~/.gh-tokens`) became a section of the project page. Digest
     rule to add: skip personal machine and tool setup.
  6. **Everything lands on one page.** With no project-specific
     structure, all decisions went onto `wiki/page/wintermute-brain.md`
     (very long). Acceptable for now; watch page length.
  7. **PARTLY FIXED (2026-11-05):** `commit-op` waits 20 minutes by
     default (03 § 2 step 5). Throughput of the single-writer worker is
     still bounded by merge latency. Was: **Auto-merge latency varies** from ~2 to ~9 minutes (PR #18). The
     10-minute wait in `commit-op` is tight, and the single-writer
     worker's throughput is bounded by it.
  8. **Scope is not checked.** An out-of-scope test source (PR #22,
     polar-bear tracks at a zoo) can be ingested; neither triage nor
     lint enforces 00 § 3.
- **Lint findings** (2026-11-05):
  - **FIXED (2026-11-05):** URLs are skipped (test). Was: `check_evidence` reads parts of ORCID ids in URLs as dates
    (`0000-00`, `8115-04` on `person/marc-becker`). Fix: skip literals
    inside URLs.
  - `page/mlr3mbo` says multi-fidelity BO "is planned"; the paper only
    calls it "a natural direction for future work". Judgment fix by
    `/brain-edit` or by hand.
  - Orphan: `source/src-20261105-zoo-rostock-polar-bear-tracks` (a
    tracking-dataset figure) is linked from no page. Its `resource` is a
    filename (`r11.png`), not a URL.
  - Missing person pages for the other mlr3mbo authors (named, not
    linked).
- **Code/content split** (K32, 01 § 1; 2026-11-05): code repo
  `wintermute-brain` keeps tools (now `plugin/tools/`, shipped with the
  plugin), plugin, server, specs, tests and reusable workflows
  (`brain-check.yml`, `brain-index.yml`); content moves to the new repo
  `wintermute-brain-content-slds` (fresh start), pinned to code tag
  `v0.1.0` via `.brain-version`. The test content of today stays only in
  this repo's history.
  **Done 2026-11-05:** PR #32 merged; tags `v0.1.0`, `v0.1.1` (fix:
  brain-check on a repo's first commit). Content repo set up (schema,
  thin workflows at v0.1.1, ruleset "main: required check" with required
  check `check / check`, bypass App + admins, auto-merge on). First
  ingest into it (SLDS homepage, content PR #1) passed end to end with
  the tools from `plugin/tools/`; index Action pushed via the App.
  **Still to do:** the wintermute marketplace entry must point at
  `slds-lmu/wintermute-brain`, path `plugin` (not important now, owner
  2026-11-05); open code PRs (closed as outdated; authors may redo them) from before
  the split (#29 containers, #31 check/digest fixes) need a rebase onto
  the new layout; members re-point clones and `BRAIN_REPO`.
- **Live hook test on the split layout** (2026-11-05): a scratch project
  with the plugin loaded via `--plugin-dir`, a short real `claude -p`
  conversation (threshold lowered with `BRAIN_DIGEST_TURNS=2`), content
  repo `wintermute-brain-content-slds` as target.
  - **Bug, fixed:** `brain-session.sh` redirected its log into
    `~/.cache/brain/` without creating it, so on a fresh machine the
    hook silently never ran. Now `mkdir -p` first (needs a release).
  - **Passed:** Stop hook triggers after 2 messages and digests in the
    background (content PR #2); a second hook call during the run
    spawns nothing (pending flag); the SessionEnd flush digests a tail
    of 3 messages (PR #3); checkpoint advances (1–4, 5–13); the compile
    queue comes out oldest first on real data.
  - **Catch-up at SessionStart passed** (2026-11-05): a 3-message
    session with capture off, backdated 20 minutes; a new session in
    the same project digested its messages 1–7 at start (content PR
    #10). The new session's single message was not digested (end flush
    needs 3). The digest marked both assistant suggestions as such.
  - **FIXED (2026-11-05, rule "mark it"):** digest prompt, 02 § 2.3,
    compile prompt and skill keep assistant contributions marked, never
    in titles, Decisions or Results. Was: **Finding:** digests record the assistant's own contributions
    as group results. PR #3 states "the 8-of-11 win count is not
    significant: a two-sided sign test gives p ≈ 0.11", a calculation
    Claude made, and puts "gap not significant" in the title. Rule to
    add to the digest prompt: mark everything the assistant contributed
    (calculations, advice, judgments) as such, or leave it out (00 § 8,
    guesses hardening into facts).
  - Minor: without a git remote, `repo:` in `source.yaml` is a local
    path.
  - **Compile worker on the split layout passed:** a fresh content clone
    plus a separate code clone; the worker checked out `v0.1.1` from
    `.brain-version` by itself and compiled both digests oldest first
    into `wiki/page/demo-project.md` (Decisions, Status, Results, Failed
    approaches, Open questions), ~2 min each; index Action via the App.
    The finding above propagated: the assistant's sign test (p ≈ 0.11)
    now stands under "Results" as a project result.
- **Erasure tool** (06 § 7a, PD2; 2026-11-05): `admin/erase` + runbook
  `admin/README.md`. Tested: refuses non-admins, refuses the code repo,
  dry run reports and changes nothing, not shipped with the plugin.
  **Not tested:** the actual rewrite and force-push (needs
  git-filter-repo, not installed in the test environment).
- **v0.1.4** (2026-11-05): session-start capture notice (PD3), dispute
  age in lint and "resolve only clear cases" in skill and compile
  prompt (K17), scope check (v0.1.3). Content repo moved to it.

## 7. User test as a new member (2026-11-05, Bernd, laptop)

Following the content repo's README step by step: install, read,
ingest. Findings (open unless marked):

- **N1** Prerequisites are one sentence of prose: no check commands, no
  install hints.
- **N2** `gitleaks` is not installed by default, and the README neither
  says how to install it nor that it is optional (the tools fall back to
  built-in secret patterns without it).
- **N3** `gh` may be logged in with a fine-grained token whose owner is
  the user, not the org, so it cannot see the content repo; the README
  says "write access" but not how to check it.
- **N4 (stopper)** With the default `gh` login (a fine-grained token owned
  by the user) the content repo is invisible (`404 Not Found`). A new
  member cannot continue, and the README says nothing about which token
  is needed (owner `slds-lmu`, access to the content repo, permissions:
  contents, pull requests, issues read/write, actions read) or how to
  use it only for the brain.
- **N5** A member needs two clones (content and code) and must check out
  the code at the pinned tag by hand; git greets them with the
  "detached HEAD" warning. When `.brain-version` changes, nothing tells
  them to check out the new tag, so their plugin can silently lag
  behind the brain's pinned release.
- **N6 (important)** Which sessions are captured is unclear in the
  tutorial ("projects where the plugin is enabled") and, with the
  README's `claude-brain` alias (`--plugin-dir`), wrong in practice: the
  hooks then run in **every** session started with the alias, in any
  folder, including the code repo and private projects. The per-repo
  opt-in (02 § 2.1) only works with the marketplace install. Fix
  options: the hook itself checks that the repo opted in (e.g. a marker
  in the repo, or a list in the user's config) and stays silent
  otherwise; and the docs state exactly which sessions are captured.
- **N7** Nothing in the content repo explains its structure to a human
  reader: what `raw/` and its channel folders hold, what each `wiki/`
  folder and page type is for, and what goes where. The full
  description is in the code repo (01 § 2, § 4, § 5.2); the content
  repo's `CLAUDE.md` addresses agents and its README covers setup only.
  Fix idea: a short "How this brain is organised" page in the content
  repo (or the README's first section), linked from `index.md`, and
  one line per folder in the generated catalogs.
- **N8** Clone size for Obsidian readers. Measured: a paper ~190 KB of
  text (+ PDF in LFS), a web page 10–50 KB, a digest ~2 KB, a wiki page
  3–10 KB. Estimate for year one (~300 papers, ~300 web/README sources,
  ~1500 digests, ~2000 pages): a clone without PDFs **~50–150 MB**
  (fine); with PDFs by mistake **+1–1.5 GB**; only `wiki/` at the latest
  version **~10–20 MB**. Risks: forgetting to skip LFS, growth over
  years (meetings, chat), and readers downloading `raw/` and history
  they do not need. Fix idea: a reader setup that clones only `wiki/`
  without history (sparse, shallow), and LFS skipping set by default.
- **N9** Page types and folders are not configurable per brain: the six
  types are hardcoded (`plugin/tools/brainlib.py` `TYPES`), and catalogs,
  lint and agent rules depend on them. Per brain today: templates,
  `scope.md`, the agents' `CLAUDE.md`. Idea (derive, don't store): a
  brain's types are its `templates/*.md` plus the built-in `page` and
  `source`; adding `templates/project.md` adds the type and its folder.
- **N10** No `projects` folder, although projects are the most important
  pages (status questions). Cause: the minimal-type decision (P5,
  2026-11-05): `project` is a tag on untyped pages, so projects sit in
  the large `wiki/page/` folder and are found only via the tag. Options:
  (a) a generated "Projects" catalog from the tag; (b) `project` as a
  real type; (c) each brain decides via its templates (needs N9).
  Assistant's view: (c), plus (a) in any case. Owner to decide.
- **N11** `claude-brain` looks like a tool but is only a shell alias
  (`claude --plugin-dir ~/wintermute-brain/plugin`) defined in the
  content README's setup. Not mentioned in the tutorial or the plugin
  README; not explained as a stopgap until the marketplace install; only
  exists in shells where it was defined. Related to N6 (with the alias,
  every session is captured).
- **Worked:** the capture notice at session start; `/brain-ask` ("who is
  Marc Becker, is he nice?") answered with citations, separated wiki
  pages from the raw source, stated its limits and the newest source's
  date, declined the personal judgment by design, and reported the
  search fallback.
- **N12 (fixed 2026-11-06)** The search server was not configured for
  members: the plugin tried `localhost` and got "connection refused"
  (fallback to index + grep works and is reported). Also, `.mcp.json` reads
  `BRAIN_GITHUB_TOKEN`, which `brain` did not set in either login mode, so
  every member would have got a 401. `brain` now sets the address and the
  token, and `brain --check` tests them.
- **N13** Review `slds-paper-litdownload` and the connected SLDS skills
  (litsearch, litbrowse, …) that paper ingest relies on: what they
  fetch, where they write, their dependencies, and whether they fit the
  brain's ingest (staging folder, metadata from registries, LaTeX vs.
  PDF).
- **N14** Why scan published papers (and public web pages) for secrets?
  R15 applies the gitleaks / regex scan to every source, but a published
  paper is very unlikely to contain credentials, while the scan costs a
  tool install (gitleaks) and can raise false positives on LaTeX or code
  listings. Option: scan only channels that can carry secrets (sessions,
  documents, mail, chat, meetings) and skip registry-backed papers and
  public pages. Owner to decide.
- **N15 (stopper)** `gh` used the brain token from `GH_TOKEN`, but `git`
  itself used other stored credentials, so `start-op`'s `git fetch` got
  "403 write access not granted". The README covers `gh` login only; it
  must make git use the same credentials (e.g. `gh auth setup-git`, or a
  repo-local credential helper `!gh auth git-credential`).
- **N16** The commands are namespaced by the plugin: `/brain:brain-ingest`
  etc., while all docs say `/brain-ingest`.
- **Worked (ingest, up to the failure):** the agent explained each step,
  used litdownload, fell back to the built-in secret scan without
  gitleaks, stopped before writing anything, diagnosed the 403 exactly,
  kept the staged paper, showed its plan (paper page, new `mlr3mbo`
  page, link from the person page), and left the DOI empty instead of
  taking it from another source.

### User test 2, with `setup-brain` (2026-11-05)

- **N17** The README asks for a brain token with write access to the
  content repo but read-only access to the code repo. Fine-grained
  tokens cannot do that: permissions apply to all selected repos.
  Options: (a) one token for both repos with the same permissions (it
  can then also write to the code repo); (b) make the code repo public
  (no token access needed for it; its history still holds the pre-split
  test content); (c) two tokens. **Decided (owner): (b), the code repo
  becomes public.** A gitleaks scan of its full history (all branches)
  found no secrets. The brain token then needs only the content repo.
- **N18, fixed:** the self-check reported the optional gitleaks as
  FAIL, so setup ended with "setup has problems" and no "Done" line.
  Optional items now show as "note".
- **Worked:** plain clone of the public code repo; token prompt
  (pasted, stored in `~/.config/brain/token`); person slug suggested
  from the git name; write access confirmed; clones without PDFs; config
  and `brain` installed; git reached the content repo with the same login
  (the 403 of test 1 is gone).
- **Worked:** `brain` in a new terminal started Claude Code; in the code
  repo (not listed under `capture`) no capture notice was shown, as
  intended (N6 fixed in practice).
- **N19, fixed in the tutorial:** the capture list was only mentioned in
  one sentence; § 3 and § 6 still described the old behaviour ("where
  the plugin is enabled"), and nothing said how to add a project or how
  to tell whether a session is captured.
- **N20, fixed:** the ask agent did not find the clone: `env` was denied
  by the user's permissions and the skill's default folder
  (`~/wintermute-brain-content-slds`) did not match `setup-brain`'s
  (`~/brain/…`). The skill now uses the same default and reads single
  settings with `echo`, never the whole environment (it holds the token).
- **N21, fixed:** `brain` updated the code but not the content clone, so
  answers could be stale; it now updates both at startup.
- **Worked:** `/brain:brain-ask` on the demo project: cited, open points
  listed, assistant contributions marked, and the difference between the
  raw digest and the corrected wiki page explained. N12 (no search
  address) still open.
- **N22, fixed:** in the brain session `BRAIN_DIR` had the old value:
  `~/.zshenv` still exported the test-1 settings, and Claude Code's
  shells read it after `brain` had set the environment. The settings
  file is now authoritative: the session hooks read it directly, and the
  skill gets its settings from `brain --settings`; environment variables
  are only a fallback. (The member removes the old lines from
  `~/.zshenv`.)
