# Implementation status

Status: **living document**
Last updated: 2026-11-05

What is built, what was decided while building it, what the live tests
showed, and what is still open. Design decisions live in the specs
(00–06); parked ideas in `parked.md`.

## 1. Built (MVP, 2026-11-05, PR #1 by Marc Becker)

Specs 00–06 accepted; this repo *is* the brain repo (later
`slds-lmu/brain-group`).

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

## 2. Decisions taken while implementing (owner to confirm)

- **One repo.** Brain content, `tools/`, `plugin/` and `server/` live in
  this repo; the wintermute marketplace points at `plugin/`.
- **Session digest ids:** `src-YYYYMMDD-<repo>-<title>-<sid6>` (first 6
  chars of the session id), so parallel digests never collide.
  Checkpoints are derived from `source.yaml` (`session`, `messages`); a
  local cache speeds it up.
- **Digest trigger:** 20 new human turns, or 30 minutes since the last
  digest with at least 3 new turns; session start/end flush needs 3.
- **Index Action also applies the safe link fix** on `main` (Obsidian's
  slash-less links).
- **Compile worker model:** `sonnet` by default (`BRAIN_MODEL`).
- **Lint levels:** slash-less links are a warning (auto-fixed on main);
  relative and broken links are errors; open Disputed blocks are `info`.
- `tools/lint --check-index` runs only on pushes to `main` (PRs never
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
  - Obsidian: do root-absolute `/wiki/...` links resolve?
  - LFS limits and cost of the `slds-lmu` plan; GitHub Actions minutes
    (06 § 8).
  - `.mcp.json` uses `${VAR:-default}` expansion; verify Claude Code
    expands it, else set `BRAIN_QMD_URL` explicitly.
- **Not yet tested live:** paper ingest, session digests end to end, the
  server worker, `/brain-lint`, `/brain-edit`.
- Who administers the server worker and the API key (06 § 8).

## 6. Changes after the live tests (2026-11-05)

- **Reasons and plan in every commit** (owner): `commit-op --plan` and
  `--reason`; a change without a reason per changed wiki page is refused
  (ingest, compile, edit). 03 § 3, § 6; skill; compile prompt; tests.
