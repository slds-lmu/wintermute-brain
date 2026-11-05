---
type: source
title: "Wiki spec decisions: minimal page types, lock and commit checks, two-layer lint"
description: "Session digest: page types, locked pages and the pre-merge check, two-layer lint, qmd with grep fallback, accepted spec batches."
resource: "git@github.com:slds-lmu/wintermute-brain.git"
tags: [session, brain, decision]
---

Session digest from the wintermute-brain repo (commit ee2c599, person bernd-bischl).

## Summary

The owner fixed the minimal set of page types, the human-correction mechanism (`locked: true`, `Overrides-human:`, a pre-merge check), a two-layer lint, and qmd with a grep fallback. Spec batches 1–4 were accepted; batch 5 is still pending.

## Key points

- Types exist only where membership can't be disputed: `person`, `meeting`, `paper`, `grant`, `source`; everything else is an untyped `page`, with projects and courses as tags. A `synthesis` type was rejected.
- `locked: true` is the emergency brake. `tools/commit-op` rejects commits that touch locked pages or overwrite lines last written by a human, unless the commit message names a newer source (`Overrides-human:`). The same checks run as a required GitHub check before merge, because local hooks can be skipped. The `audit/` inbox is parked as K18.
- Lint has two layers: mechanical checks on every push; AI judgment checks (stale claims, duplicates, uncited claims, sentence-to-source mismatch) run by hand in the MVP and only report. Own validator instead of IWE; revisit IWE if the script starts duplicating it (K19).
- Search: qmd from the MVP on, grep kept as fallback.
- Batch 1 (concurrency) and batch 2 (ingest) accepted; batches 3–4 (lint and query) accepted, with a false-alarm goal of about 15%. Parked: K20–K26.
- Open, priority (K17): workflow for resolving visible disputes (who is notified, how a human resolves, whether an agent may propose, how it is recorded, a lint report for old disputes).
- Pending: batch 5 (F1–F5, M1, M10, M11, M16, M18, slug patterns) is not yet approved; the owner must talk to the `slds-setup-memory` authors (F4).

## Pages updated

- [Wintermute brain](/wiki/page/wintermute-brain.md): page types, locking, lint layers, spec batch status and open dispute workflow.
