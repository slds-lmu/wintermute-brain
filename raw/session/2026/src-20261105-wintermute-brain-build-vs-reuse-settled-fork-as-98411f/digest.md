# Build vs. reuse settled: fork Astro-Han, drop the spike, keep Disputed

Decisions from the 2026-11-05 session on the wintermute-brain specs:

- **Build vs. reuse (accepted by the owner):** keep the plan to fork `Astro-Han/karpathy-llm-wiki`, with qmd and plain git/Markdown. No existing product qualifies as the base (research reports F–H):
  - AnythingLLM keeps its data in SQLite/LanceDB, not in git, and its per-workspace permissions don't protect the tiers. At most, it could be an optional chat front end later.
  - arkon keeps pages only in Postgres, with no git export. Its PolyForm Internal Use licence rules out a fork in `slds-lmu`. It is effectively one author's project, with no push since 2026-06-03. Borrow ideas only.
  - nashsu/llm_wiki is GPL-3.0 and about 92k lines. Its apps auto-ingest on every machine that pulls a shared repo, so it breaks there, and its state lives outside the repo. Borrow ideas only.
  - Team-wiki products (Notion, Confluence, Outline, Wiki.js 3 and others): none has AI that maintains the wiki the way our loop does. Only git-backed ones pass "the repo is complete". Wiki.js 3 drops OKF fields such as `type`, `status` and `aliases` on web edits. A pull-only viewer could come later, but not in v1.
- **No v0 spike and no retrieval-only baseline (owner decision, 2026-11-05).** A 15-source test can't show whether the wiki helps the group. Page quality will show up in the first days of the MVP build. The MVP done-criterion in `00-requirements.md` §7 (about 20 sources, UC1–UC4 answered with citations) is the first real check. The spike section in `v0-foundation.md` was replaced with this decision.
- **Contradictions (owner decision):**
  - Changed facts are overwritten in place, and git keeps the old version. This is R5.
  - Real disagreements get the Astro-Han `Status: Disputed` blockquote, with both sources cited. Lint lists these; it doesn't hunt for contradictions.
  - Owner: "keep it and use it, we will fine-tune later."
  - `Status: Outdated` is dropped, because it conflicts with edit-in-place (R5). R5, R9, `01-data-model.md` §6, `v0-foundation.md` and M13 were updated to match.
- **Parking lot:** research ideas not needed for v1 go into `specs/parked.md` (K1–K16). Review them after v1 or v2. New parked ideas go there too.
- **Working mode:** discussion and results go into the docs (`today.md`, specs), not the console. This is recorded in `CLAUDE.md`.

Still open at the end of the session: 2b (qmd keyword search from the start, with grep as fallback, versus N2's grep-only wording) and 2c (cleanup of stale text). The owner had not answered either.
