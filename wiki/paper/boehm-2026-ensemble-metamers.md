---
type: paper
title: "Understanding cross-model perceptual invariances through ensemble metamers"
description: "Generates model metamers with ensembles of CNNs/ViTs; CNN ensembles give recognizable late-layer metamers, transformers do not."
authors: [Lukas Boehm, Jonas Leo Mueller, Christoffer Loeffler, Leo Schwinn, Bjoern Eskofier, Dario Zanca]
year: 2026
venue: "Neural Computing and Applications"
doi: "10.1007/s00521-026-12145-5"
arxiv: "2504.01739"
tags: [metamers, perceptual-invariances, explainability, adversarial-examples, vision-transformers, cnn]
---

The text on this page comes from the open arXiv preprint (version 2, see the arxiv field);
the journal version in Neural Computing and Applications (volume 38,
article 430) is paywalled and was not compared [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Problem & Context

Model metamers are stimuli that are physically distinct from a reference
image but produce the same activation at a chosen layer of a neural
network. Prior work (Feather et al.) found that metamers from late layers
of single models are often unrecognizable to humans and to other models,
which points to model-specific ("idiosyncratic") invariances [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Key idea

Optimize each metamer across an ensemble of models instead of one. The
authors' claim: "Optimizing metamers across multiple models enhances
recognizability by prioritizing task-specific invariances while
disregarding model-specific idiosyncrasies." [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md)

## Method

- Metamers are generated with projected gradient descent (PGD), switching
  the active model round-robin during optimization; SGD with an
  exponential learning-rate schedule from 1.0 to 0.005, a large projection
  value ($\epsilon = 10000$) and 40000 total steps [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- Model sets: single CNN (VGG19), single transformer (ViT-B), and
  ensembles of CNNs, robust CNNs, transformers (Deit-S, ViT-B, Swin-B,
  XCiT-S) and robust transformers, all pre-trained on ImageNet [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- Data: a simplified dataset with 16 classes mapped to 231 of the 1000
  ImageNet synsets; metamers are inverted from three intermediate layers per
  model, spread over its depth ("early", "middle", "late") [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- Evaluation: recognizability (accuracy of the other zoo models on the
  metamers), image-quality metrics (including FID, LPIPS, CLIP-IQA), and
  representational similarity compared with the Jensen-Shannon divergence [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Results

- CNN ensembles and robust CNN ensembles keep high recognizability for
  late-stage metamers. Averaged over the classification models,
  recognizability is 0.477 for early, 0.547 for middle and 0.419 for late
  stages, whereas late-stage recognizability in most previous experiments was
  usually below 0.2 [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- Robust transformer ensembles produce natural-looking metamers with low
  recognizability; plain transformer ensembles produce neither natural nor
  recognizable metamers. The authors attribute this to architectural
  biases [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- Restricting the perturbation to adversarial-style budgets
  ($\varepsilon$ of 8/255 and 0.3) severely limits the metamers, which then
  behave like adversarial examples [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Limitations

- Claims about human-like or recognizable metamers rest on model-based
  recognizability and image metrics. The paper describes no new human
  experiment; human recognizability is carried over from prior work [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- High late-stage recognizability "comes at the cost of rather low
  accuracy in the early stage", and the authors write: "The primary
  challenge remains the mitigation of idiosyncratic model invariances" [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).
- The model sets were limited by the robust networks available in a public
  repository (RobustBench) [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Open questions

Whether training on diverse noise types could align invariances across
models, which the authors suggest as a direction [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Relevance to us

No direct link to an SLDS project yet. Recorded as a co-authored paper of
[Jonas Müller](/wiki/person/jonas-muller.md); per the contribution
statement, he co-conceived the study and designed the experiments with
D.Z. and L.B. and provided supervision [Ensemble metamers paper](/wiki/paper/boehm-2026-ensemble-metamers.md).

## Related

- [Jonas Müller](/wiki/person/jonas-muller.md)
