---
type: paper
title: "mlr3mbo: Bayesian Optimization in R"
description: "Introduces mlr3mbo, a modular R toolbox for Bayesian optimization, with tuned defaults that match HEBO, SMAC3, Ax and Optuna."
authors: [Marc Becker, Lennart Schneider, Martin Binder, Lars Kotthoff, Bernd Bischl]
year: 2026
venue: "arXiv preprint"
doi: ""
arxiv: "2603.29730"
tags: [bayesian-optimization, hpo, automl, r, software, mlr3]
---

## Problem & Context

Black-box optimization needs sample-efficient methods for expensive,
possibly noisy objectives over search spaces with integer, categorical and
hierarchical parameters. Bayesian optimization (BO) is the standard approach
and a core part of HPO and AutoML. In R the main toolkits were `DiceOptim`
and `mlrMBO`, the predecessor of `mlr3mbo`
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Key idea

`mlr3mbo` is a modular, object-oriented BO toolbox in the `mlr3` ecosystem.
It has three user groups: researchers composing custom BO variants from
building blocks, practitioners running a configurable standard BO, and HPO
users who get it as a tuner in `mlr3tuning`. Any regression model can serve
as the surrogate [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Method

The building blocks are the initial design, surrogate model, acquisition
function, acquisition function optimizer, termination, predefined loop
functions and final-point selection. On top of these come output and input
transformations, random interleaving, warmstarting, error handling, mixed and
hierarchical spaces, multi-objective optimization, multi-point batch
proposals and asynchronous parallel BO. The package builds on `bbotk` and
`paradox` [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

Defaults were found by greedy coordinate descent (CD) over a discretized
`mlr3mbo` configuration space, separately for numeric and mixed-hierarchical
problems. Each configuration ran on the YAHPO-SO v1 suite of YAHPO Gym, with
30 seeds per instance. Performance is the "random search normalized score"
(RSNS): 0 is random search with the BO budget, 1 is random search with one
million evaluations. The CD took approximately 7.7 CPU-years on NCAR's
Derecho cluster [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Results

- **Numeric defaults:** GP with Matérn 3/2 kernel and a small nugget, log
  output transformation, LCB with λ = 3, CMA-ES as acquisition optimizer, and
  a small random initial design. Mean RSNS rose from 0.76 for the
  start configuration to 1.19, with a standard deviation of 0.01. Replacing
  CMA-ES with RS or L-BFGS-B costs at least 0.2 RSNS
  [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).
- **Mixed-hierarchical defaults:** random forest with 500 trees and the
  LTV variance estimator, log output transformation, LCB with λ = 1, and
  local search (LS) as acquisition optimizer. Mean RSNS rose from 0.34 to
  0.82, with a standard deviation of 0.02. RS instead of LS costs 0.20; no
  output transformation costs 0.22; 10 trees instead of 500 costs 0.15
  [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).
- **Against other tools:** compared with Ax (v1.1.2), HEBO (v0.3.6), SMAC3
  (v2.3.1) and Optuna (v4.5.0). On numeric instances `mlr3mbo` has the
  highest mean RSNS from the start. Its final rank does not differ
  significantly from Ax, HEBO and SMAC4BB, and SMAC4HPO and Optuna rank
  significantly worse. On mixed-hierarchical instances no two frameworks
  differ significantly [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).
- **Runtime overhead:** lower than the competitors on numeric instances. On
  38-dimensional mixed instances it is about double, because of the larger
  acquisition optimization budget, which did not pay off in performance
  [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Limitations

The authors name these limitations
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md):

- CD ignores parameter interactions, and its result depends on the start
  configuration.
- RSNS is noisy, and the stopping point was chosen by "eyeballing".
- Defaults were tuned and compared on the same YAHPO instances, so they may
  overfit.
- Surrogate benchmarks are deterministic, unlike real HPO problems.
- Only sequential BO was benchmarked.

## Open questions

- How much acquisition optimization effort is actually needed. The
  authors' benchmarks favour strong optimizers with enough budget, but the
  wider evidence is mixed [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).
- How well the defaults hold on a held-out benchmark family and on real,
  noisy HPO problems [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).
- Multi-fidelity and multi-information-source BO, which is "high on our
  development roadmap" [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Relevance to us

The paper documents the group's own BO package and the empirical basis for
its defaults; four of the five authors are at LMU Munich. Code and results
for the experiments are in https://github.com/mlr-org/mbo_config, archived on
Zenodo [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Related

- [mlr3mbo](/wiki/page/mlr3mbo.md)
