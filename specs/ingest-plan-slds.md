# Ingest plan: existing SLDS material

Status: **draft (plan only, nothing ingested)**
Owner: Bernd Bischl
Last updated: 2026-11-05

Which material we already have, in which order it goes into the content
repo `wintermute-brain-content-slds`, and how we check that it pays off.
Open questions are marked **[P#]**.

## 1. Goal

Reach the MVP done-criterion (00 § 7) with real material: enough sources
that the four use cases can be answered with correct citations:

| Use case | Needs pages on |
|---|---|
| UC1 status ("where is project X, who works on it?") | projects, people |
| UC2 research synthesis ("what do our papers say about Y?") | papers, methods |
| UC3 decisions and meetings | decisions, meetings (mostly from session digests later) |
| UC4 onboarding ("how do things work here?") | groups, courses, infrastructure how-tos |

## 2. Principles

- **Group tier only.** Nothing for leadership or owner tiers yet: no
  grants with budgets, no personnel matters, no reviews.
- **Public and stable first.** Website, public repos and published
  papers before internal documents.
- **One source per operation** (03 § 1), each its own PR. A wave is a
  list of sources that one person or agent works through in order.
- **Anchors before details.** Group and people pages first, so later
  sources update existing pages instead of creating near-duplicates.
- **Test phase:** content may be wiped; the plan is also a load test.

## 3. Waves

| Wave | What | Sources (what we have) | Becomes | Size |
|---|---|---|---|---|
| 0 | **Anchors** | SLDS website: homepage (done), the nine research-group pages, people overview and profiles | `page` per research group; `person` pages (role, projects, expertise only) | ~10 + people |
| 1 | **Research** | **all** group papers (owner, P2), arXiv first (LaTeX via litdownload); many have a `paper_*` code repo in `slds-lmu` | `paper` pages; project pages (`page`, tag `project`) | all (likely 100+) |
| 2 | **Code** | **all** code repos of `slds-lmu` (owner, P3): packages, benchmarks, `paper_*` code, tools (READMEs and docs, as `web` sources with the GitHub URL) | project pages (tag `software`), linked to their papers | all (~117 public) |
| 3 | **Teaching** | lecture sites and repos: i2ml, i2dl, sl, iml, dl4nlp, appml, advml; `lecture_service`, `latex-math` | course pages (tag `teaching`), how-tos for the lecture infrastructure | ~10 |
| 4 | **How we work** | `ai-scaffolding`, `slds-tools`, `lrz_configs`, wintermute skills, the brain's own tutorial | how-to and convention pages (tag `howto`) | ~5–10 |
| 5 | **Later, needs decisions** | theses (`msc_*`), meeting notes, Mattermost, mail, internal documents | depends on K27 (personal data), K28 (meetings) and the tiers | — |

Session digests run alongside from the start: everyone who tests works
with the plugin loaded in their own project repos.

## 4. How

**Automatic** (owner, P4): waves are not worked through by hand. One
runner takes a wave's source list and ingests one source after the other
with the normal ingest rules (one source per operation, one PR each,
check, auto-merge), so the waves need no volunteers and cause no
duplicates.

1. **Source lists per wave**, one line per source (URL, DOI or arXiv
   id), generated where possible: wave 1 from the group's publication
   list, wave 2 from the `slds-lmu` repo list.
2. **One runner at a time**, like the compile worker (single writer):
   on the group server, or by one person by hand until the server runs.
   How it is built is a follow-up for `03-agent-ops.md` (extend the
   compile worker with a source list, or a separate batch runner).
3. **Order inside a wave:** anchors and broad sources first, details
   later.
4. **After each wave:** `/brain-lint` (duplicates, orphans, unsupported
   claims) and a short look at the new pages.
5. **Cost and time:** roughly 2–5 minutes and one model run per source;
   at 200+ sources that is a day or more of unattended runs. Watch the
   API spending limit (06 § 5) and GitHub Actions minutes (06 § 8.1).

## 5. Check after waves 0–1

Before going further, ask a fixed set of questions and judge the
answers (correct, cited, says what it doesn't know):

- UC1: "Who works on interpretable ML, and on which projects?"
- UC2: "What have we found about hyperparameter optimization
  overtuning?" / "Compare our uncertainty-quantification papers."
- UC3: "What did we decide about the evaluation protocol in project X?"
  (needs session digests)
- UC4: "I'm new: which research groups exist and whom do I ask about
  Bayesian optimization?"

If the answers are weak, fix the rules (skill, templates) before adding
more material.

## 6. Questions

| # | Question | Decision / recommendation |
|---|---|---|
| P1 | Person pages from public profiles: ask each person first? | **not needed now** (owner, 2026-11-05) |
| P2 | Wave 1: all papers or a curated set? | **all papers** (owner) |
| P3 | Code repos as sources? | **all code repos**, as `web` sources with the GitHub URL (owner) |
| P4 | Who runs the waves? | **automatically**: one runner, one source per operation (owner); design follows in 03 |
| P5 | Internal, non-public documents: when? | **open** (owner: don't know yet) |
