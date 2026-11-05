---
type: page
title: "mlr3mbo"
description: "The group's R package for Bayesian optimization in the mlr3 ecosystem; successor of mlrMBO."
aliases: [mlrMBO successor]
tags: [project, software, bayesian-optimization, hpo, r, mlr3]
---

## What it is

`mlr3mbo` is an R toolbox for Bayesian optimization (BO), part of the
`mlr3` ecosystem and built on `bbotk` and `paradox`. It supports single- and
multi-objective optimization, multi-point proposals, batch and asynchronous
parallelization, and robust error handling. It is the HPO backend
`tnr("mbo")` in `mlr3tuning`
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

It replaces `mlrMBO` and was redesigned to be more modular, more
object-oriented and integrated with `mlr3`
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Defaults

The defaults come from a coordinate descent search on YAHPO Gym
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md):

- **Numeric spaces:** GP surrogate, CMA-ES acquisition optimizer, LCB, log
  output transformation.
- **Mixed-hierarchical spaces:** random forest with LTV variance, local
  search, LCB, log output transformation.

With these defaults the package performs on par with HEBO, SMAC3, Ax and
Optuna [mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Roadmap

Native multi-fidelity and multi-information-source BO is planned
[mlr3mbo paper](/wiki/paper/becker-2026-mlr3mbo.md).

## Links

- Code: https://github.com/mlr-org/mlr3mbo/ (also on CRAN)
- Paper: [mlr3mbo: Bayesian Optimization in R](/wiki/paper/becker-2026-mlr3mbo.md)
- People: Marc Becker, Lennart Schneider, Martin Binder, Lars Kotthoff,
  Bernd Bischl (authors of the paper)
