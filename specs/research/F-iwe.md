# Prior art F: IWE as validator and formatter

Status: **auxiliary research; nothing here is decided.** Feeds the open
items P8 (`prior-art.md`) and L5 (`proposals.md`).
Research date: 2026-11-05. Version read: IWE v0.30.0 (commit `6f8907b`).

Method: I read IWE's docs, source and tests and queried the GitHub API.
**I did not run IWE**, because `CLAUDE.md` rules out installing brain
tooling on this machine. *(source)* marks my own reading of the code,
where no doc or test states the behaviour.

## 1. Summary

IWE is a Markdown knowledge-graph tool: CLI, editor language server
(LSP), MCP server and Mac app, with no LLM inside. Only part of it
matters to us:

- **Validator (`iwe schema validate`): good fit.** It enforces the
  frontmatter and section rules of 01 § 5, is read-only and suits CI.
- **Formatter (`iwe normalize`): not yet.** It changes the headings of
  all our pages, deletes HTML blocks, and by default also rewrites
  `raw/`.
- **The rest: mostly skip.** Its search and agent write tools overlap
  with qmd and `tools/commit-op`.

**Recommendation:** use IWE read-only as the deterministic lint layer
(option A, § 5), after a short spike (§ 6).

## 2. What it offers

| Part | What it does | For us |
|---|---|---|
| `iwe schema validate` | Checks pages against YAML schemas bound by path glob. Frontmatter: JSON Schema 2020-12. Body: required sections, order, token budgets, block types. Exit 0 clean, 1 violations, 2 bad schema | **yes** |
| `iwe stats` | Broken links, orphans, page metrics; `stats similarity` lists near-duplicate pages | **yes** |
| `iwe normalize` | Rewrites Markdown in place: headings, lists, whitespace, link paths. No check mode | **not yet** (§ 4) |
| LSP (`iwes`), `iwe rename` | Link completion, backlinks, rename across pages | optional for humans; format-on-save has the § 4 problems |
| MCP (`iwec`), `find`, `create`, `update` | Agent read/write and BM25 search | **no**: overlaps qmd and A2 |

**`schematter`** is the same schema language as a standalone CLI, with
no IWE dependency and no write commands. IWE builds on its validator
crate (0.2.0), so our schema files would not be locked to IWE's CLI.

**Maturity.** Apache-2.0, 1.8k stars, pre-1.0 and moving fast: five
releases between 2026-10-20 and 2026-11-03. One developer dominates (314
commits; the next human has 2), and `schematter` comes from the same
org. Releases include static Linux binaries with SHA-256 files. The
project's own benchmark loads 20,000 synthetic documents in under 1 s.

## 3. How it would help

| Need | Spec | IWE coverage |
|---|---|---|
| Required fields, `description` ≤ 140 chars, `status` enum | 01 § 5.1 | frontmatter JSON Schema |
| `type` matches its folder | 01 § 2 | `type: { const: paper }` bound to `wiki/paper/**` |
| Per-type fields (`year`, `date`, `resource`) | 01 § 5.2 | JSON Schema, including `format: date` |
| Each type's sections, in order | 01 § 5.2 | `sections` + `additionalSections: false`; empty sections pass |
| Broken links | R9 | `iwe stats`; catches slash-less Obsidian links too *(source)* |
| Near-duplicate pages | L1, G1 | `iwe stats similarity` |

It is compatible with what we have decided:

- **Links.** `refs_path = "absolute"` plus `refs_extension = ".md"`
  produces exactly `/wiki/paper/x.md`. The workspace must be the repo
  root; `workspace.path = "wiki"` would break these links.
- **OKF.** IWE's `okf.yaml` allows extra fields such as `aliases`. Bind
  schemas to `wiki/**` only, because `raw/` and `CLAUDE.md` have no
  `type`.
- **Page shape.** Docs define depth structurally, so a body with only
  `##` headings should bind as top-level sections.
- **Wikilinks** (open in `prior-art.md` § 6). IWE accepts `[[…]]` as
  links, so it won't enforce our ban; a lint script must.

**Not covered; these stay in `tools/`:** generated indexes, the
slash-less link fix, `raw/` immutability, uncited claims, repo-unique
slugs, git-age staleness, `source.yaml`, and broken links to PDFs
*(source)*.

## 4. Why not the formatter yet

| Behaviour of `iwe normalize` | Effect on us | Way out |
|---|---|---|
| Without `-k`, rewrites every `.md` in the workspace and re-serialises frontmatter | Breaks R2 (`raw/`) and the human-only rule for `CLAUDE.md` and `templates/` | Only ever use `-k <key>`, which keeps frontmatter as written |
| A body with only `##` headings becomes `#` (tested) | Changes every page template (01 § 5.2, § 9) | Change templates to `#`, or add an H1 that repeats `title` |
| **Deletes HTML blocks** (tested) | Silent content loss, probably including `<!-- comments -->` | Ban HTML in `wiki/` by lint |
| Joins soft-wrapped lines by default | Noisy diffs on wrapped pages | `preserve_newlines = true` |
| `wiki/paper/x.md` inside `wiki/concept/y.md` resolves relative, then is written as `/wiki/concept/wiki/paper/x.md` *(source)* | Corrupts links with the Obsidian quirk (01 § 6) | Run our link fix first |
| Math parsing is off *(source)* | `$x_i$` is treated as ordinary Markdown and may change | Test on math-heavy pages |

The LSP's format-on-save normalizes too. No requirement in
`00-requirements.md` asks for a formatter, so under KISS this can wait.

## 5. Integration and options

**Repo.** Commit `.iwe/config.toml` and `.iwe/schemas/*.yaml`: a common
schema for shared fields plus one per page type. They would be
human-only, like `templates/`. Pages stay plain Markdown.

```toml
# .iwe/config.toml (a page gets every schema that matches it)
version = 4
[markdown]
refs_path = "absolute"
refs_extension = ".md"
[schemas.common]
match = ["wiki/**", "!wiki/*/index"]
[schemas.concept]
match = ["wiki/concept/**", "!wiki/concept/index"]
```

```yaml
# .iwe/schemas/concept.yaml
frontmatter:
  properties:
    type: { const: concept }
sections:
  - header: { const: Definition }
  - header: { const: Explanation }
  - header: { const: Related }
additionalSections: false
```

**CI (the hard gate).** Run a pinned, checksum-verified static binary
from the repo root. Installation details belong in `06-ops.md`.

```bash
iwe schema validate
iwe stats -f json | jq -e '.brokenLinkCount == 0'   # stats doesn't fail on broken links (source)
iwe stats similarity                                # advisory
```

**Agent loop.** `tools/commit-op` runs `iwe schema validate -k <page>` on
changed pages if `iwe` is present and gives the agent the violations,
which can carry hints from the schema. If `iwe` is absent, it skips and
CI catches the problem, the same pattern as "use qmd if available".

**Orphan trap.** Generated indexes link every page, so `iwe stats` won't
report wiki pages as orphans, while unlinked `raw/*.md` files will show
up *(source)*. Run a second `iwe stats` with a CI-only `.ignore` file
listing `raw/` and `index.md`. Don't commit that file: ripgrep reads it
too and would stop searching `raw/`.

**Design principles.** "The repo is complete" holds: the CLI rebuilds its
graph on each run, and config and schemas live in git. Deleting `.iwe/`
loses only lint rules. One caveat on "standards over inventions": the
body schema dialect (`draft/2026-06`) is young and comes from IWE's own
authors; only the frontmatter half is plain JSON Schema.

| Option | Gives | Costs |
|---|---|---|
| **A. `iwe` read-only (recommended)** | Schema checks, broken links and duplicates from one binary | Pre-1.0 binary to pin; it also has write commands, so `normalize` stays forbidden |
| B. `schematter` only | Schema checks, with no way to touch files | Schema binding, links and duplicates become our scripts |
| C. Own script (`jsonschema` + heading check) | No external binary | Reinvents existing tooling (N4); no token budgets or hints |
| D. A + `iwe normalize -k` | Uniform formatting | Needs § 4 settled first, including a template change |

A is cheap to reverse: moving to B keeps the schemas and replaces only
the runner. Using IWE as the agents' write and search layer is not a
serious option, because it duplicates qmd and A2.

**Decision for the owner:** which option (P8, L5).

## 6. Spike and open points

A half-day spike in a scratch repo, on a deployment target (or here only
if the owner asks):

1. Validate all 13 page types; break each rule once and check exit codes.
2. Confirm `##`-only pages bind as top-level sections, with `iwe` and
   `schematter` agreeing.
3. Confirm `.ignore` hides `raw/` and `index.md` from `iwe stats`.
4. If D is of interest, run `iwe normalize -k` on pages with math, tables,
   HTML comments and action items, and read the diffs.
5. Time `iwe schema validate` at 5,000 pages plus `raw/`.

Not examined in depth: MCP and LSP behaviour, the Mac app, and the
`iwe-org/skills` plugin. Report B § 1.9 names `## Sources` and
`## Contradictions` sections that the data model has since dropped.

## Sources

- https://github.com/iwe-org/iwe: `docs/` (`document-schema`, `cli-schema`,
  `cli-normalize`, `cli-stats`, `configuration`, `keys`, `okf`, `benchmark`);
  `crates/liwe/src/{fs,model}.rs`, `crates/liwe/src/markdown/reader.rs`,
  `crates/diwe/src/stats.rs`; `crates/liwe/tests/normalization_*.rs`,
  `crates/iwe/tests/normalize_test.rs`
- https://github.com/iwe-org/schematter and https://document-schema.org/
