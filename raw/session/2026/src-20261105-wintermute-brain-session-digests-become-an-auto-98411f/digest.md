# Session digests become an automatic MVP channel; PR-per-op gate; no answer filing

**Session digests (decided by the owner, 2026-11-05):**
- Session digests are automatic. Once a project repo is configured, the agent decides what to keep, and no human reads or confirms the logs. The owner said the system must "just work" without intervention.
- The default is to keep nothing. The digest agent keeps only decisions with rationale, findings, failed approaches with the reason they failed, how-tos, and open questions. It never keeps code details, chatter, personal remarks, or secrets.
- Digests are produced in pieces during a session, not only at session end, because sessions are often left open or crash. A hook checks after each reply. The checkpoint is derived from the brain repo, since each digest's `source.yaml` records the session and message range it covers.
- Thresholds: 20 turns or 30 minutes (I2). The digest model is a small, cheap, Haiku-class model (I3).
- Sessions are in the MVP, not a later milestone (I1). The owner's reasoning is that sessions are the main knowledge source.
- The brain repo itself also opts in, so knowledge from query conversations is captured too.
- Accepted gap: a repo that is not opened again after a crash leaves its last session tail undigested until someone next starts a session there.

**Answers reach the wiki only through raw (O2):**
- There is no "file an answer" operation. A query writes nothing to `raw/` or `wiki/`. A worthwhile conversation becomes a session digest in `raw/`, and the server worker then compiles it into `wiki/`.
- Reason: every wiki change should have a raw source behind it, and one operation fewer is simpler.
- The digest agent must never write restated wiki content back into `raw/`, or the wiki would copy itself.

**Write targets must be explicit (owner's instruction):**
- Every operation in `specs/03-agent-ops.md` §0 must state whether it writes to `raw/`, `wiki/`, or neither. The owner noted that the raw/wiki question had been confused.

**Server-side gate (O1, decided by the owner):**
- Each agent change is a pull request with auto-merge, and GitHub merges it only after the checks pass. The owner chose this over checking after the push, so nothing bad lands on `main`.
- Indexes are no longer part of the PRs. A GitHub Action regenerates them on `main` after each merge, which avoids conflicts between parallel PRs.

**Personal data (owner's correction):**
- The assistant had proposed a hard gate before any Mattermost, mail, or meeting ingest. The owner rejected that. There is no policy for now: the first phase is a test run, and humans decide what gets ingested.
- The personal-data policy is parked as a priority item (K27) in `specs/parked.md`.

**Recorded meetings (owner's priority):**
- Recorded oral meetings are a very high priority source (K28, parked). The owner ranked them above the other channels, and the worry is the same personal-data question as K27.

**Proposals batch:**
- Tier items T1–T3 are deferred to v2/v3 (2026-11-05).
