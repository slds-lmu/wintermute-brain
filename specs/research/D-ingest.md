# Prior art D: Ingest (sources -> clean, citable Markdown in `raw/`)

Research date: 2026-10-29. Repo stats come from `gh api` the same day (stars, last push, latest release, SPDX license). Benchmark numbers come from the sources cited. Most are published by a vendor, and the report says so where that applies. Claims I could not check against a primary source are marked **[unverified]**. I did not execute any downloaded code.

## 0. TL;DR

| Source | MVP pick | Fallback / later | Ready-made Claude Code skill? |
|---|---|---|---|
| Web pages | **defuddle CLI** (`defuddle parse <url> --md`, with frontmatter metadata) | trafilatura when defuddle fails or for batch crawls. Obsidian Web Clipper for humans clipping in the browser | **Yes:** `kepano/obsidian-skills` -> `defuddle` skill (50k stars, MIT) |
| arXiv papers | **LaTeX source** (`arxiv.org/e-print/<id>`), kept verbatim, plus **arXiv HTML** (`arxiv.org/html/<id>`) converted to Markdown as the readable layer | ar5iv for older papers. PDF pipeline if both fail | Our own `slds-paper-litdownload` already does e-print download plus S2/OpenAlex/Crossref/DBLP resolution |
| Non-arXiv PDFs | **MinerU 4.x** (math quality; CPU-capable default install) or **Marker 2 balanced** (GPU) | Claude native PDF reading for spot-checks or short papers. Docling (with `--enrich-formula`) for Office docs | **Yes:** MinerU ships an official `mineru` agent skill. Docling has an official MCP server |
| Metadata | Semantic Scholar -> OpenAlex -> Crossref (-> DBLP) | — | Already in `slds-paper-litdownload` |
| Mattermost | Small in-house script on the REST API (or the existing Mattermost MCP), one thread -> one `.md` with permalinks | — | Nothing mature exists. Build it |
| Claude Code sessions | `claude-code-log --format md` for the deterministic transcript -> MD step, then an agent distills it | claude-obsidian-vault-skill as a design reference only | Several small skills exist; none is mature enough to adopt as is |
| Mail / GDocs / meetings | Drive API `text/markdown` export. faster-whisper / whisperX for audio. Mail: `.eml` -> MD via markitdown or a small script | — | — |
| Secret / PII filtering | **gitleaks `stdin`** as a pre-write gate, plus a gitleaks pre-commit hook on `raw/` | Presidio (selective) for PII in chat, mail and transcripts. trufflehog for periodic verified scans | — |

Cross-cutting point: **nougat, the current fallback in `slds-paper-litdownload`, is effectively unmaintained** (last push 2025-02). Replace it with MinerU or Marker.

---

## 1. Web pages (MVP)

| Tool | Stars / last push / latest release | License | Form | Notes |
|---|---|---|---|---|
| **defuddle** (kepano) | 9.8k / 2026-10-25 / 0.19.6 (2026-10-24) | MIT | npm lib + CLI (`npx defuddle parse <url\|file> --markdown [--json] [--frontmatter] [-p title]`) | The extraction engine behind Obsidian Web Clipper. Normalizes MathJax/KaTeX to MathML, and the Node/full bundle converts MathML to LaTeX. Keeps code-block language and standardizes footnotes. Rich metadata (title, author, published, site, schema.org, word count). Still 0.x and calls itself work in progress. |
| **Obsidian Web Clipper** | 5.4k / 2026-09 / 1.7.1 (2026-07) | MIT | Browser extension | Uses defuddle plus templates (frontmatter, highlights). Built for humans, so an agent cannot drive it. Good for "a human clips into `inbox/`". Renders JS-heavy pages in the real browser, which also covers pages behind logins. |
| **trafilatura** | 7.0k / 2026-10-29 / v2.3.1 (2026-10) | Apache-2.0 | Python lib + CLI (`trafilatura -u URL --output-format markdown --with-metadata`) | Academic-grade boilerplate removal with strong precision in published evaluations. Does not run JS. Weaker handling of math, footnotes and code. One single-author test: 1 of 17 boilerplate units leaked vs 5 for Readability **[single source]**. |
| **Mozilla Readability** | 11.5k / 2026-08 | Apache-2.0 | JS lib (no official CLI; outputs HTML) | Baseline. Needs `markdownify`/turndown afterwards. Superseded by defuddle for our use. |
| **Jina Reader** (`r.jina.ai/<url>`) | 12.2k / 2026-05 | Apache-2.0 (server code) | Hosted API (MCP exists) | Easiest option, with JS rendering. But every URL and its content goes to a third party, and retention terms are not documented **[unverified]**. Rate limits roughly 20 RPM without a key and 200 RPM with one; sources conflict. Not suitable for internal or authenticated pages. |
| **python-markdownify** | 2.3k / 2026-06 | MIT | Python lib | HTML -> MD converter only, with no content extraction. Useful as a building block (e.g. for arXiv HTML). |
| **markitdown** (Microsoft) | 193k / 2026-10 / v0.1.9 | MIT | Python CLI + MCP | Multi-format converter (HTML, DOCX, PPTX, XLSX, PDF via pdfminer, Outlook msg, …). Shallow per-format quality; no main-content extraction for web. Useful for the "later" Office formats. |

No rigorous three-way benchmark of defuddle, trafilatura and Readability turned up.

**Recommendation (MVP):** `defuddle parse <url> --md` via `npx` or a project-local `node_modules`, so no global install is needed. Write the result to `raw/web/<date>-<slug>.md` with frontmatter (`source_url`, `retrieved_at`, `title`, `author`, `published`, `extractor: defuddle@0.19.6`). Also store the fetched HTML next to it (`.html`, via LFS if large) so the extraction can be redone later. That makes `raw/` immutable even if the extractor changes. Fall back to trafilatura when defuddle returns nearly empty output. Adopt or vendor kepano's `defuddle` SKILL.md, which is about 40 lines and MIT.

---

## 2. Papers (MVP)

### 2a. arXiv: avoid PDF where possible

- **LaTeX source:** `https://arxiv.org/e-print/<id>` (tar.gz or a single gz file). This gives the highest math fidelity: equations are the author's own LaTeX, with nothing to OCR. Use `export.arxiv.org` for programmatic access, at about 4 req/s in bursts with 1 s sleeps. Downstream, keep the source, and for readability flatten it (`latexpand`) or convert it with pandoc (`pandoc -f latex -t markdown`). Pandoc handles custom macros poorly; LaTeXML handles them better.
- **arXiv native HTML:** `https://arxiv.org/html/<id>[vN]`, produced by LaTeXML. Live for new submissions since late 2023. Older papers are only on **ar5iv** (`ar5iv.labs.arxiv.org`, covers sources up to 2026-07). Conversion success is roughly 75% error-free and about 97% at least partially readable, per a 2026 LaTeXML/arXiv paper **[snippet only, metric mapping unverified]**. Math comes as MathML with LaTeX `alttext`, so an HTML -> MD step can emit `$...$` from the alttext.
- **Tooling:** `ar2md` (PyPI; arXiv HTML -> pandoc MD with ar5iv fallback). Tiny project **[unverified quality]**. Several 0-star Claude skills named "arxiv-to-markdown" exist; they are not worth adopting, but they show that the approach works. Writing our own 50-line converter (alttext -> `$..$`, then markdownify) is reasonable.
- **Existing in-house prior art:** `slds-paper-litdownload` (wintermute repo) already resolves IDs via Semantic Scholar / OpenAlex / Crossref / DBLP, downloads PDF plus e-print source into `literature/{citekey}/`, and falls back to **nougat** for non-arXiv PDFs. Reuse its metadata and download logic for `raw/papers/` rather than rebuilding them.

### 2b. PDF -> Markdown converters

| Tool | Stars / push / release | License | Hardware | Math | Agent integration | Verdict |
|---|---|---|---|---|---|---|
| **MinerU** (OpenDataLab) | 82.7k / 2026-10-29 / 4.0.12 (2026-10-11) | **Apache-2.0 + extra terms** (commercial licence needed only above 100M MAU or $20M monthly revenue; attribution required if offered as an online service). Earlier versions were AGPL. | Default install: ONNX CPU + llama.cpp/Vulkan VLM (8 GB RAM, CPU works). `[full]`: NVIDIA ≥8 GB VRAM, vLLM/lmdeploy | Often recommended as strongest OSS for dense math. The VLM backend scores above its pipeline backend. ">90% BLEU on displayed equations" **[unverified vendor/tutorial claim]** | **Official `mineru` agent skill** (`npx skills add opendatalab/MinerU --skill mineru`), CLI `mineru` with tiered quality (`basic/standard/advanced`) | **Top pick for non-arXiv math-heavy PDFs.** Note that the skill's install instructions ask the agent to write global skill and memory entries; vet that before use. |
| **Marker 2** (Datalab) | 40.7k / 2026-10-22 / v2.0.0 (2026-07-20) | Code Apache-2.0 (was GPL in v1); **weights: modified OpenRAIL-M** (free for research, personal use and orgs under $5M, so fine for a university) | balanced/fast need a GPU (surya VLM served locally); `fast --disable_ocr` is CPU-only | olmOCR-bench "arXiv math": **balanced 83.9**, fast 23.4, no-OCR 0.0 (vendor numbers) | CLI `marker_single`; optional `--use_llm` (Gemini default, Claude supported) | Strong and fast with a GPU. **Must use balanced mode for math.** |
| **Docling** (IBM / LF AI) | 69.8k / 2026-10-29 / v2.144.0 | MIT | CPU OK, GPU faster | **Display equations are dropped by default** (placeholder comments, confirmed in a CUHK test). Fix with `--enrich-formula` (CodeFormula model -> LaTeX), which is off by default | CLI `docling`, **official `docling-mcp`** (779 stars, MIT, v3.4.0) | Best for DOCX/PPTX/XLSX/HTML and tables. Weaker on math (olmOCR-bench overall 50.3 in Datalab's harness, which is vendor-run against a competitor). |
| **GROBID** | 5.2k / 2026-10-27 / 0.9.1 (2026-08) | Apache-2.0 | Java/Docker service, CPU | Poor (not its job) | REST service | **Use for metadata and bibliography extraction** (TEI header, references with DOIs), not for body Markdown. Optional. |
| **pymupdf4llm** | 2.3k / 2026-10 / v0.3.4 | **AGPL-3.0** | CPU, very fast | None (text layer only). User report: layout mode silently drops formula blocks **[unconfirmed]** | Python | Fast text-only preview. AGPL is fine for internal use but no math. Not recommended as primary. |
| **nougat** (Meta) | 10.1k / last push **2025-02** | MIT (code), CC-BY-NC weights **[from memory, unverified]** | GPU strongly preferred | Good LaTeX on arXiv-like pages but hallucinates and loops on others | CLI | **Effectively abandoned.** Replace in litdownload. |
| **Claude native PDF** (Read tool / API) | — | — | none locally | No published math-accuracy benchmark. Vision + text-layer. Limits ~32 MB / 100 pages per request (official docs; some 2026 sources claim more for 1M-context models **[unverified]**). Claude Code has reported "PDF too large" and spurious "password-protected" failures | Built in | Very good for **spot-checking and per-claim verification** against the page image, and for short papers. Non-deterministic and token-costly as a bulk converter; output is not reproducible, which conflicts with immutable `raw/`. |

Benchmark context (olmOCR-bench, 1,403 PDFs, **numbers published by Datalab, Marker's vendor**): Chandra 2 (hosted) 85.8; Gemini Flash 3.5 76.4; Marker balanced 76.0 (2.9 pg/s on a B200); MinerU pipeline 72.7 (0.54 pg/s); Marker fast 66.6; Docling 50.3; liteparse 22.4. MinerU's VLM backend was **not** in that table, and Datalab acknowledges that it scores higher. One independent test (CUHK econ blog, 2026-07, a single 52-page paper): Docling dropped all display equations; Marker handled inline math but struggled with complex display math; a vision-LLM path was the only one to recover display equations.

**Recommendation (MVP), in order:**
1. arXiv ID known -> store the e-print source and the arXiv/ar5iv HTML; generate `paper.md` from the HTML (alttext math) or from LaTeX via pandoc. No GPU needed.
2. Otherwise, PDF -> **MinerU** (CPU default tier for a laptop; GPU tier on a group server) **or Marker balanced** on a group GPU box. Pick one after a 10-paper bake-off on our own math-heavy ML papers. Running olmOCR-bench's arXiv-math split ourselves is cheap.
3. Always store the original PDF in `raw/` (LFS). The Markdown is a derived, regenerable artifact; record `converter@version` in frontmatter.
4. Use Claude's native PDF reading at **wiki-writing time** to verify cited equations against the page, not as the converter.
5. Metadata: DOI/arXiv -> Semantic Scholar Graph API (`/paper/arXiv:<id>`, `/paper/DOI:<doi>`) -> OpenAlex (`/works/doi:<doi>`, add `mailto` for the polite pool) -> Crossref (`/works/<doi>`). This logic already exists in `slds-paper-litdownload/references/apis.md`.

Install footprint caution: MinerU and Marker both pull in torch and model weights (several GB). Per the global CLAUDE.md they should go in a **project-local venv** (`uv` in the wiki repo) or on a dedicated group conversion box, not into the user toolchain.

---

## 3. Mattermost (later)

- **No mature thread -> Markdown tool exists.** GitHub search returns only 0–9-star exporters (e.g. `alallier/Mattermost-Export`, last push 2024). `mattermost-python-extractor` (GLiCID forgejo) exports channels to JSONL/CSV/MD, with no thread awareness. The official Channel Export plugin outputs CSV and needs admin install. `mmctl` (export/bulk) is now an archived standalone repo and lives in the server repo; it is admin-only and too coarse.
- **Best path:** a small script, or agent use of the **Mattermost MCP already configured in this environment** (`mattermost-me` read-only: `read_thread`, `search_posts`, `get_post`), or the REST API v4 (`GET /api/v4/posts/{post_id}/thread`, `GET /api/v4/channels/{id}/posts?since=`). Write one file per thread: `raw/chat/<channel>/<root-post-id>.md`, with frontmatter (channel, participants, root timestamp, permalink) and one `### <author> · <ISO time> · [link](…/pl/<post_id>)` block per post so each message can be cited.
- **Permalink format:** `https://<server>/<team>/pl/<post_id>` (`/pl/` = permalink; works for replies too and opens the thread). The official doc shows only the `mattermost://` deep-link form; the https form comes from autolink configs and forum posts. Verify on our server version.
- **"Chat -> knowledge base" distillers:** no Mattermost-specific mature tool found. The Slack ecosystem (slackdump etc.) has exporters, but distillation is generic LLM summarization, which our agent does anyway. Consent and filtering matter more here: decide channel opt-in and run PII/secret filtering (section 6).

---

## 4. Claude Code / claude.ai session digests (later)

**Where transcripts live:** `~/.claude/projects/<cwd-with-slashes-as-dashes>/<session-uuid>.jsonl`, one JSON event per line (user/assistant messages, tool_use/tool_result, summaries; sub-agent transcripts in a sibling `<uuid>/` dir). Verified on this machine. Claude Code deletes old transcripts after `cleanupPeriodDays`, **default 30 days [from memory, verify in settings docs]**, so set it higher or ingest promptly. claude.ai web chats have no local files; they are only available via the account data export (ZIP of JSON) or by copy/paste.

| Tool | Stars / push | License | What it does | Fit |
|---|---|---|---|---|
| **claude-code-log** (daaain) | 1.25k / 2026-10 / 1.7.0 | MIT | `uvx claude-code-log` -> HTML/**Markdown**/JSON from JSONL; `--depth`, `--compact`, `watch` mode, date filters, also Codex/agy | **Best deterministic transcript -> MD step.** Run with `uvx` (ephemeral) or in the project venv. Feed the output to the distilling agent. |
| **claude-mem** (thedotmack) | 104k / 2026-10-29 / v15.5.0 | Apache-2.0 | Hooks capture tool observations; an LLM summarizes into SQLite + Chroma; local Bun worker service with web viewer; optional **cloud sync to cmem.ai**; associated crypto token | Personal memory product, not a group wiki ingester. Heavy (daemon, vector DB) and opinionated. Some integrations default to the hosted backend. **Not recommended**; at most borrow ideas (`<private>` tag exclusion, observation types). |
| **claude-obsidian-vault-skill** (mehmetcakoglu) | **1 star**, 35 commits, no releases / 2026-06 | MIT per README (GitHub shows NOASSERTION) | `SessionStart` hook queues new JSONL sessions; user-triggered `/vault:ingest` distills them into session/decision/entity/concept/bug pages; secret filtering on ingest; `ingested.txt` dedupe; global vs per-project vault | **Closest design match to our pattern** (Karpathy-style, queue + explicit ingest + secret filter + dedupe). Too immature to depend on; **use as a design reference**. Its queue previews store prompt snippets unfiltered, which we should avoid. |
| Others (small) | — | various | `cc2md`, `alkham` (CLI to Obsidian notes; verbatim capture), Simon Willison's `claude-code-transcripts` (HTML), Obsidian plugins "Claude Code Sync" / "Claude Sessions", skills "claude-session-manager", "export-session-as-markdown" | Confirm the pattern is common; nothing beats claude-code-log. |

**Recommendation (later):** a two-stage pipeline. (1) `claude-code-log --format md --depth assistant` (no tool noise) -> `raw/sessions/<user>/<date>-<uuid>.md` **after** a secret/PII gate. (2) The wiki agent distills that into decisions and findings with citations to `raw/sessions/...#<anchor>`. Make it opt-in per user and per session. Transcripts contain pasted tokens, env dumps and private paths far more often than papers do.

---

## 5. Mail, Google Docs/Drive, meeting transcripts (later, brief)

- **Google Docs:** Drive API `files.export(fileId, mimeType="text/markdown")` is natively supported (Docs gained Markdown export in 2024; 10 MB export cap). Also available interactively via File > Download > Markdown. This environment already has the claude.ai Google Drive/Docs connectors (`read_file_content`, `download_file_content`), which an agent can use directly. Store `raw/gdocs/<fileId>@<revisionId>.md` plus the URL, since Docs are mutable and the revision ID is what makes a citation stable.
- **Mail:** no dominant tool. Options are `.eml` -> MD with **markitdown** (MIT, handles Outlook `.msg`) or a ~50-line Python `email` + markdownify script; `message_md` (IMAP fetch, unverified); Dead Letter (PolyForm **Noncommercial**, avoid); Obsidian IMAP importer (GUI). Recommended: explicit forwarding to a wiki mailbox, or a human dropping `.eml` into `inbox/`, then a script. Cite by `Message-ID`. Never bulk-ingest mailboxes (PII, GDPR).
- **Meetings / audio:** **faster-whisper** (26k, MIT, CTranslate2, ~4x faster than openai/whisper) or **whisperX** (24.9k, BSD-2, v3.8.6; word timestamps + pyannote **diarization**, which needs an HF token and accepting pyannote's terms) or **whisper.cpp** (54.8k, MIT, CPU-friendly). For German/English group meetings: whisperX large-v3 on a group GPU, output as Markdown with `[hh:mm:ss] Speaker:` lines so citations can point at timestamps. If Zoom/Teams transcripts (VTT) already exist, convert those instead; it is trivial. Consent is a must.

---

## 6. Secret / PII filtering at ingest

| Tool | Stars / push / release | License | Pre-write suitability |
|---|---|---|---|
| **gitleaks** | 30.5k / 2026-10-28 / v8.30.1 (2026-03) | MIT | **Best fit as a pre-write gate.** Single static Go binary; `cat file \| gitleaks stdin --redact -v` with a non-zero exit on findings; `dir` mode for `raw/`; also a pre-commit hook; TOML-configurable rules and allowlists. Regex + entropy, no network. |
| **trufflehog** | 28.8k / 2026-10-28 / v3.99.7 | **AGPL-3.0** | Has `stdin` and `filesystem` modes. Its strength is **verifying** secrets live against provider APIs, which sends candidate secrets out over the network; use `--no-verification` offline. Heavier. Good as a periodic/CI scan of the whole repo history. |
| **detect-secrets** (Yelp) | 4.7k / last release **v1.5.0, 2024-05** | Apache-2.0 | Baseline-file workflow for legacy repos. Slowing maintenance. Python. Not preferred. |
| **Presidio** (now `data-privacy-stack/presidio`, moved from Microsoft) | 11.6k / 2026-10-29 / 2.2.366 | MIT | **PII**, not secrets: NER (spaCy/transformers) + regex for names, emails, phone numbers, IBAN, etc.; anonymizer can redact or replace. Python library/Docker service, no simple CLI. Higher false-positive rate on research text (author names in papers are PII by its definition). Use **selectively** on chat, mail and transcripts, with a German model (spaCy `de_core_news_*`) configured. |

**Recommendation:** in the ingest script, run `gitleaks stdin` on every converted Markdown file before writing to `raw/`; on a finding, block the write and ask the human, or write with `--redact` and keep a log. Add a gitleaks pre-commit hook to the wiki repo as a second line of defence. Git history is forever, and LFS objects are also hard to purge. Later, add Presidio only to the chat/mail/session/meeting ingesters, configured for emails, phone numbers and IBANs and *not* person names (names are the point of a group wiki), with human review on hits. A periodic `trufflehog git file://. --no-verification` sweep is optional.

---

## 7. Ready-made Claude Code skills / MCPs worth knowing

- `kepano/obsidian-skills` -> **defuddle** skill (MIT, 50k stars): adopt as is or vendor it.
- **MinerU official `mineru` skill** (in the MinerU repo, `skills/mineru/SKILL.md`): good, but its install prompt writes global skills and memory, so vendor it into the project instead.
- **docling-mcp** (official, MIT): an MCP server for document conversion.
- markitdown has an MCP server (`markitdown-mcp`).
- Mattermost MCP (`mattermost-me`, read-only) and Google Drive/Docs connectors are **already available in this environment**.
- In-house: `slds-paper-litdownload` (metadata + arXiv source + PDF; swap nougat out) and `slds-setup-memory` (already has an `ingest` operation writing `memory/sources/<slug>.md`, so check for overlap and conventions before designing a new `raw/` layout).
- Session digests: claude-obsidian-vault-skill (design reference only), claude-code-log (CLI, not a skill).

## 8. Open questions / to verify before committing

1. PDF bake-off: MinerU (VLM tier) vs Marker balanced vs Claude-native on ~10 of our own math-heavy papers, scored on equation fidelity, tables and reading order. No independent math-specific head-to-head exists.
2. Does arXiv HTML alttext -> `$…$` preserve custom macros well enough, or should we always keep the LaTeX as primary?
3. Claude Code `cleanupPeriodDays` default and the claude.ai export format: check current docs.
4. Mattermost `/pl/` permalink behaviour on our server version.
5. Is a group GPU box available (it decides between MinerU CPU-tier and Marker/MinerU GPU)?

## Sources

- defuddle README: https://github.com/kepano/defuddle ; skill: https://github.com/kepano/obsidian-skills
- Marker README & benchmark table: https://github.com/datalab-to/marker
- MinerU README / LICENSE.md: https://github.com/opendatalab/MinerU
- Docling enrichments: https://docling-project.github.io/docling/usage/enrichments/
- CUHK PDF comparison: https://scrp.econ.cuhk.edu.hk/blog/analysis/2026/07/31/pdf-processing.html
- MarkTechPost Marker v2 benchmark write-up (403 when fetched): https://www.marktechpost.com/2026/07/24/datalab-marker-v2-vs-mineru-docling-and-liteparse-benchmark-breakdown/
- Spheron self-hosting guide (MinerU math claim, unverified): https://www.spheron.network/blog/self-host-document-intelligence-docling-marker-mineru-rag-guide/
- pymupdf4llm formula-drop report: https://forum.mupdf.com/t/layout-mode-silently-drops-the-text-of-blocks-classified-as-formula-to-markdown-to-text/361
- arXiv bulk data / API etiquette: https://info.arxiv.org/help/bulk_data.html ; ar5iv: https://ar5iv.labs.arxiv.org/ ; ar2md: https://pypi.org/project/ar2md/ ; arXiv HTML blog: https://blog.arxiv.org/2022/02/21/arxiv-articles-as-responsive-web-pages
- Anthropic PDF support: https://docs.anthropic.com/en/docs/build-with-claude/pdf-support
- Trafilatura vs Readability test: https://thunderbit.com/de/blog/trafilatura
- Jina Reader limits: https://jina.ai/contact-sales , https://jina.ai/news/jina-reader-for-search-grounding-to-improve-factuality-of-llms
- Mattermost share links: https://docs.mattermost.com/end-user-guide/collaborate/share-links ; channel export: https://docs.mattermost.com/administration-guide/comply/export-mattermost-channel-data ; autolink: https://github.com/mattermost-community/mattermost-plugin-autolink
- claude-code-log: https://github.com/daaain/claude-code-log ; claude-mem: https://github.com/thedotmack/claude-mem ; claude-obsidian-vault-skill: https://github.com/mehmetcakoglu/claude-obsidian-vault-skill ; cc2md: https://pypi.org/project/cc2md/ ; Simon Willison transcripts: https://simonwillison.net/e/9106
- Drive export formats: https://developers.google.com/drive/api/v3/ref-export-formats ; Docs Markdown export: https://workspaceupdates.googleblog.com/2024/07/import-and-export-markdown-in-google-docs.html
- Mail: https://pypi.org/project/eml2md/ , https://github.com/thephm/message_md , https://socket.dev/pypi/package/dead-letter
- gitleaks: https://github.com/gitleaks/gitleaks ; trufflehog: https://github.com/trufflesecurity/trufflehog ; detect-secrets: https://github.com/Yelp/detect-secrets ; Presidio: https://github.com/data-privacy-stack/presidio ; comparison: https://appsecsanta.com/gitleaks-vs-trufflehog
- Whisper family: https://github.com/SYSTRAN/faster-whisper , https://github.com/m-bain/whisperX , https://github.com/ggml-org/whisper.cpp
