# 04 — Retrieval

Status: **accepted** (owner, 2026-11-05; implemented, see `implementation-status.md`)
Owner: Bernd Bischl
Last updated: 2026-11-05
Depends on: `01-data-model.md` § 7, `03-agent-ops.md` § 4, `06-ops.md` § 3

How agents find things in the brain. Most of this is already decided
elsewhere and collected here. Open questions are marked **[R#]**.
Research: `research/C-retrieval.md`.

## 1. Building blocks

| Block | What | Decided |
|---|---|---|
| Generated indexes | root `index.md` + one per type folder, one line per page from `description` | 01 § 7 (P3) |
| qmd | search over wiki pages and `raw/` text; one central instance on the GPU server, reached via MCP | 01 § 7 (Q2), 06 § 3 |
| Fallback | indexes + grep on a local clone, when qmd is unreachable | 06 § 3 |
| Access | per-person login: only people with read access to the content repo | 06 § 3 (Q9) |
| Models | local only, no external embedding API | Q5 |

qmd's index lives outside git and is rebuilt from the repo; the server
re-indexes after every pull (06 § 4). Pin the qmd version.

## 2. Query procedure

From 03 § 4 (Q3):

1. Read the root `index.md`, then the relevant folder index.
2. Search with qmd.
3. Read the top 3–5 pages and follow their links.
4. "Nothing found" only if the index *and* the search both come up
   empty.

The query writes nothing (03 § 0).

## 3. What is searched

- `wiki/`: all pages.
- `raw/`: the text of every raw item (Markdown; for PDFs the converted
  text, not the binary).
- Not searched: index files (redundant), `CLAUDE.md` and specs.

## 4. Decisions

| # | Question | Decision |
|---|---|---|
| R1 | ~~BM25 first or hybrid from the start?~~ | **decided 2026-11-05: hybrid (embeddings + rerank) from the MVP** on the GPU server; BM25 stays as the cheap mode |
| R2 | ~~Wiki or raw first?~~ | **decided 2026-11-05: the agent uses both, and tells the user which parts of the answer come from wiki pages and which from raw sources** |
| R3 | ~~How is the `wiki/page/` index split?~~ | **decided 2026-11-05: by first letter** (`index-a-f.md`, …), generated; the root index links the parts |
