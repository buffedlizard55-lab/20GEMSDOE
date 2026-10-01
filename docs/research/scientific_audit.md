# Scientific audit — 2026-10-01

## What changed, and what did not

Historical H16/H20 outcome reports and submission TIFFs are preserved. The fresh, fixed-parameter H16 reproduction (`evidence/spatial_holdout_h16_reproduction.json`) exactly matches all seven historical arm means, including H16-1 **Dense 0.21269 / Sparse 0.08554**. Core, lidar, radiometric, extension and 13 DEM channels were restored and hash-verified. The earlier missing-data blocker is resolved; direct official-host connectivity is a separate issue. No retuning or new submission followed the reproduction.

H16 remains a **PN training heuristic on unlabeled samples**, not a verified-negative or exact nnPU estimator. H20's pseudo-label/tree blend is not Kiryo's risk optimizer. Those obsolete `fit_nnpu_boosted_expert`/stack entry points now fail explicitly rather than silently repeating the false attribution. The corrected CPU `KiryoNNPULinearHead` implements the actual objective and reverse-gradient update; numerical unit tests cover the derivatives and small batches. **It has not yet been trained/validated as a competition candidate using an identified geological class prior.** Unit tests are not competition evidence.

## Correct PU sampling mathematics

Let Y denote real fault presence, S catalogue inclusion, π=P(Y=1), μ=P(S=1). Positive inaccuracies are excluded by the working assumption S=1 ⇒ Y=1; the official task warns that assumption may fail. If labeled positives are representative (SCAR, or separately validated propensity correction):

- Marginal U sampled from the whole X population: `R_neg = E_U loss(-g) − π E_P loss(-g)`.
- Catalogue-complement U sampled only from S=0: `R_neg = (1−μ) E_U loss(-g) − (π−μ) E_P loss(-g)`.
- Unbiased total risk = `π E_P loss(g) + R_neg`.
- Nonnegative risk = `π E_P loss(g) + max(0, R_neg)`.
- Kiryo Algorithm-1 reverse update descends on `−γ R_neg` when `R_neg < −β`; it is **not** the derivative of the displayed clamped objective. Default β=0, γ=1. Optional logistic loss is implemented and tested; bounded sigmoid scores are classification confidence, not posterior calibration evidence.

The corrected code requires explicit distribution semantics and μ for S=0 samples. Excluding a catalogue collar from U changes the population again and cannot be called unbiased under this formula without a sampling correction. No heuristic scarp-based propensity is substituted for measured selection probability.

Sources: [NeurIPS abstract, Kiryo et al. 2017](https://proceedings.neurips.cc/paper/2017/hash/7cce53cf90577442771720a370c3c723-Abstract.html), [author implementation](https://github.com/kiryor/nnPUlearning/blob/master/pu_loss.py). Abstract and author code read; full paper PDF could not be fetched. Neither source establishes SCAR, a true GEMS class prior or calibration of these data.

## Official-vector prior study: a scenario, not recovered truth

`evidence/pu_vector_prior_study.json` uses the SHA-256-pinned GDR/INGENIOUS vector-length extraction (official ZIP identity retained in the report). The extract contains **1,126 vector segments intersecting the template rectangle**, not exact-footprint-clipped or independent geological faults. Raster connected components are a different segmentation and cannot be equated to vector traces.

Fixed primary completeness cutoff 1,650 m; lower extrapolation limit 300 m. Tail exponent is now fitted by Pareto MLE, not only log-log OLS. A 399-replicate parametric KS reference refits the exponent in each simulation. Fixed sensitivity cutoffs 1,500/1,650/2,000/2,500/3,000 m are reported without selecting a holdout winner. The exact α=1 truncated-Pareto mean was also corrected and checked against numerical integration.

- Observed catalogue pixel fraction: **0.0118025155**.
- Primary official-vector scenario total fraction: **0.0124163671**.
- Fixed-cutoff vector scenario range: **0.0123399259–0.0134815118**.
- Primary tail-model reference diagnostic: **p=0.0025** (lowest possible with 399 replicates).
- **Hidden-fault prevalence is not identified.** Tail completeness, lower cutoff, spatial independence, clipping, transfer of length to raster pixels and selection representativeness remain unverified. Even a good Pareto fit would not prove completeness. The DTI 300 m support does not establish a minimum fault length.

The historical raster-derived total prior **0.0376564649** belongs to the old estimator/report; it is not a measured prevalence, and the new vector scenario does not retroactively validate or change H20. No prior is chosen using the leaderboard.

## Brier/reliability repair and genuine-label blocker

`brier_decomposition_murphy1973` now rejects malformed probabilities and nonbinary/soft targets. It does not silently clip forecasts or threshold invented targets. Weighted estimates support a *documented* inclusion design, but the function cannot verify that design.

`REL − RES + UNC` is exact for **bin-mean/coarsened forecasts**. For arbitrary continuous scores, raw Brier equals that partition plus `within-bin forecast variance − 2×within-bin forecast/outcome covariance`. Both scores, the correction and numerical closure are reported separately. Empty-bin rates are null, not fictional zero observations. The 0.70 audit retains exactly [0.65,0.75); it does not secretly widen the sample window. No IID pixel confidence interval is invented for clustered geology.

Out-of-fold isotonic mapping has no guessed default labeling frequency. If c is explicitly supplied, the SCAR identity is `P(Y=1|X)=P(S=1|X)/c`, not the former odds adjustment. Only the evaluation mask is mapped; underlying model/target independence remains an external requirement.

**No independently recovered hidden-fault positives plus representative verified negatives are available.** Catalogue thinning, existing catalogue positives, model-generated labels and the reused H20 Vault cannot supply unconditional empirical reliability. Accordingly **no real hidden-fault reliability diagram or Brier result is claimed or fabricated**. This remains a scientific/data blocker, not a solved software task.

## Final confirmation and multiplicity

The old Vault was inspected for multiple H20 arms. It is not untouched and cannot be relabeled. New research uses pushed preregistrations and persistent single-use ledgers. The final gate is globally single-use across candidates and requires new independently adjudicated positive/background evidence and recorded hashes. Manifest assertions are necessary software checks, **not scientific verification of provenance**.

H22 uses a fixed five-idea family; pending tests remain p=1. Holm FWER 0.05 is the promotion requirement; BH is descriptive. Four-block exact sign-flip p-values have minimum 0.0625. Reused adjacent quadrants also do not establish independent/exchangeable blocks. No statistical confirmation or submission slot can be authorized from these screens.

## Cache and report integrity

Local H16 feature/context/OOF caches now bind exact input and source SHA-256, parameters, software versions, output array shapes/dtypes and array-file SHA-256. Missing/stale/tampered metadata is a cache miss; rebuilding is required. Writes are atomic with metadata installed last. These caches are ignored and may disappear after a workspace snapshot. Historical reports cannot be overwritten by the H16 runner; choose a fresh `--output` path.

The old continuous H22-2 `emitted_px` field was truncated prediction **mass**, not a pixel count. Its result is preserved; interpret it as a legacy schema issue. Current holdout reports distinguish prediction mass, nonzero pixels and binary emitted counts; primary binary gates are unchanged and neither H22 test is rerun. **Additional correction:** H22-2 and H22-3 soft-confidence DTI diagnostics were actually scored after >0.5 thresholding. They are not true continuous DTI and must not be cited as such. [Hash-bound additive correction](../../evidence/h22_metric_schema_annotations.json) preserves original reports. New code dispatches continuous forecasts to the exact probability-mass scorer and makes the binary API reject soft input. Official wrappers mask both predictions and truth on known pixels; historical proxy comparisons explicitly retain their FP-only catalogue-neutral convention for comparability.

**No scientifically confirmed winning candidate; no slot recommended.** Improving code correctness and reproducibility is not an achieved hidden-test gain.

The stylized one-to-one marginal utility calculation now accounts for FN reduction: with alpha+beta=1, q must exceed alpha×current DTI. Spatial kernel overlap/multi-truth credit violates this simplification; it is not a calibrated hidden-pixel threshold or slot policy.
