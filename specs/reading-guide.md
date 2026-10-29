# Reading guide: prior art

Suggested order for the owner. Every source has a matching section in
our reports (`specs/research/`), so you can read our digest first and
the original second, or the other way round. Times are rough.

## Day 1: the pattern and its limits (≈ 1 h)

1. **Karpathy, LLM Wiki** (the origin, short):
   https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
2. **rohitg00, LLM Wiki v2: lessons at scale**, including the comments:
   https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
   → our digest: `B-team-and-scale.md` § 1.1 and § 2 (failure modes)
3. **Our synthesis**: `specs/prior-art.md` (5 min), then
   `specs/proposals.md` (what Claude would adopt)

## Day 2: the skill we'd fork (≈ 1 h)

4. **Astro-Han/karpathy-llm-wiki**: read `SKILL.md` and
   `scripts/check_evidence.py`:
   https://github.com/Astro-Han/karpathy-llm-wiki
   → `A-claude-code-wiki-skills.md` § 2
5. **kepano/obsidian-skills** (read; decided 2026-10-29: not a dependency, only `defuddle` as a tool):
   https://github.com/kepano/obsidian-skills
   → A § 5

## Day 3: schemas and formats (≈ 1–1.5 h)

6. **Open Knowledge Format v0.2**: `SPEC.md` §§ 4–9 (frontmatter,
   provenance, trust, index):
   https://github.com/GoogleCloudPlatform/open-knowledge-format
   → B § 1.10
7. **AutoSci**, the ML-research ontology (entities, edges, writer
   rules):
   https://github.com/PKU-DAIR/AutoSci
   → B § 1.2, A § 9
8. **gbrain**: the current-state + timeline page shape and the trust
   labels:
   https://github.com/garrytan/gbrain
   → B § 1.7

## Day 4: bigger skill suites (skim, ≈ 1 h)

9. **claude-obsidian**: claim states, worker/committer split,
   compilation-value gate:
   https://github.com/AgriciDaniel/claude-obsidian → A § 1
10. **Ar9av/obsidian-wiki**: epistemic suffixes, page lifecycle,
    paper deep-dive template:
    https://github.com/Ar9av/obsidian-wiki → A § 6
11. **nvk/llm-wiki**: generated indexes, raw revisions, thesis mode:
    https://github.com/nvk/llm-wiki → A § 8
12. **lewislulu/llm-wiki-skill**: the `audit/` correction inbox:
    https://github.com/lewislulu/llm-wiki-skill → A § 7

## Day 5: multi-writer, search, ingest, in-house (≈ 1 h)

13. **np6126/mcp-llm-wiki** (tiny, but the only one designed around
    git with several writers):
    https://github.com/np6126/mcp-llm-wiki
    and **praneybehl/llm-wiki-plugin** (index split thresholds, retry
    rule): https://github.com/praneybehl/llm-wiki-plugin → A § 9
14. **qmd** (search): https://github.com/tobi/qmd → `C-retrieval.md`
15. **Ingest tools**: just read our digest, `D-ingest.md`
16. **In-house overlap**: `E-inhouse-wintermute.md` (and
    `~/cos/wintermute/skills/setup/slds-setup-memory/`)

## Optional

- IWE (schema validator): https://github.com/iwe-org/iwe
- Basic Memory (why not): https://github.com/basicmachines-co/basic-memory
- Letta MemFS (git-backed agent memory): https://docs.letta.com/concepts/memfs
- nanoclaw's group-chat wiki skill (Mattermost-bot reference):
  https://github.com/nanocoai/nanoclaw (`.claude/skills/add-karpathy-llm-wiki`)
- denser.ai survey of implementations:
  https://denser.ai/blog/llm-wiki-karpathy-knowledge-base/

As you read, mark items in `specs/proposals.md` as
`accept` / `reject` / `discuss`, or note questions, and we'll go
through them together.
