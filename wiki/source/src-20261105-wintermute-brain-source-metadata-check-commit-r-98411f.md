---
type: source
title: "Source-metadata check, commit reasons and plans, Obsidian settings, GitHub limits"
description: "Session digest: source.yaml metadata check, plans and reasons in commits, Obsidian settings, GitHub plan limits and Actions risk."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

The owner chose to check source metadata mechanically, made a plan and a reason per page mandatory in every commit, shipped shared Obsidian link settings, and the GitHub org limits were read from the billing API.

## Key points

- `tools/check_evidence` flags any `title` or author in `source.yaml` that does not appear in the fetched source; DOI/arXiv-sourced metadata and session digests are exempt. The first ingest (karpathy-2026-llm-wiki) is flagged, a known case.
- Every ingest, compile and edit commit carries `Planned:` and `Reasons:`; `tools/commit-op` refuses a commit if a changed page lacks a reason.
- The repo ships `.obsidian/app.json` with `useMarkdownLinks: true` and `newLinkFormat: absolute`; the rest of `.obsidian/` is gitignored. Test: links resolve and backlinks show.
- `${VAR:-default}` expansion works in plugin `.mcp.json`; an empty `BRAIN_QMD_URL` stays empty.
- GitHub: `slds-lmu` is on the Team plan with 307 seats, 182 in use. Actions use was 600–1,000 minutes a month, peak 3,217 in May, net cost $0 except $4.26 in July. LFS storage is about 5 GB, net cost $0.
- Risk (the assistant's estimate, not measured): automatic session digests could add roughly 1,000–2,000 Actions minutes a month. Mitigations: skip the index run for raw-only PRs, or run workflows on the group server.
- The owner added org-level "Administration: Read-only" to the `slds-write` token to read billing, against the assistant's advice that it exposes all org settings.
- Open for Marc: qmd installation and testing at scale, and the PDF converter benchmark (MinerU vs. Marker).

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): metadata check, commit plans and reasons, Obsidian check, GitHub limits.
