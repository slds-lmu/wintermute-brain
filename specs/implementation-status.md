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
- **Not yet tested live:** the session hooks firing on their own (the
  digest step was run by hand), the server worker on the server. Paper
  ingest was done by Marc (PR #15).
- Who administers the server worker and the API key (06 § 8).

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
