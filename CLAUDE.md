# CLAUDE.md — wintermute-brain (code and design)

This repo is the **code and design** of the SLDS brain, an LLM-maintained
group wiki. The **content** lives in separate repos
(`slds-lmu/wintermute-brain-content-slds`, later one per tier); agents
working *on the wiki* follow that repo's `CLAUDE.md` and the `brain` skill
(`plugin/skills/brain/SKILL.md`). See `README.md` for the layout.

## Working mode: specs first

- Design lives in `specs/` (00–06 accepted 2026-11-05; status in each
  header). Change a spec before changing behaviour; if implementation
  shows a spec is wrong, fix the spec, then the code.
- `specs/implementation-status.md`: what is built, tested and open.
  `specs/parked.md`: ideas for after v1/v2 (priority items on top).
- Discussion goes into docs (`specs/…`), not the console; keep console
  replies short. Temporary session notes are allowed but must be folded
  into proper files and deleted.
- Do not resolve open questions yourself: list options with a
  recommendation and leave the decision to the owner.

## Rules for this repo

- **No brain content here** (01 § 1): no `raw/`, `wiki/` or indexes.
  Test fixtures live in `tests/fixtures/`.
- **This repo never opts in to session digests**: no `.claude/settings.json`
  enabling the brain plugin. Development sessions must not become
  knowledge.
- For now everyone (members, the content repos' checks, the server
  worker) runs this repo's latest `main` (06 § 2.1): every push here
  affects the brains immediately. Pinning to releases comes later (K40).
- Run `python3 -m unittest discover -s tests` before committing.
- No commits or pushes unless the user asks.

## Design principles (owner, 2026-10-29)

KISS; tool independence (plain Markdown + YAML in git; Obsidian and qmd
optional, no tool-specific syntax); derive, don't store; the repo is
complete (everything outside git is rebuildable from it); standards over
inventions (OKF field names). The owner's laptop rules (manifests,
yolobox) are not design constraints for the brain.
