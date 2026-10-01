# H22-2 — magnetic-low lineaments: frozen protocol

Registered 2026-10-01 on the Arena session branch **before computing this candidate's outcome**. This file, the evaluator and `gems.lineaments` must be committed and pushed before the first run. The result records their commit and SHA-256 values. Historical H21/H20 outcomes are already known; this is a prospective, **exploratory** spatial-transfer screen, not a fresh confirmatory holdout.

## Hypothesis and novelty audit

Fault-hosted hydrothermal alteration can reduce magnetization. A line-shaped **magnetic trough** could therefore identify fluid pathways, including unmapped extensions or covered structures. This is a proposed mechanism, not a guarantee that the Great Basin faults or competition labels have this signature.

- OBSERVED: [Fox (1978), DOE OSTI, Coso](https://www.osti.gov/biblio/5598190) attributes a magnetic low **in part** to magnetite destruction. [Finn & Morgan (2002), USGS](https://www.usgs.gov/publications/high-resolution-aeromagnetic-mapping-volcanic-terrain-yellowstone-national-park) describes magnetic lows, hydrothermal alteration and bounding gradients in Yellowstone. These settings are not this competition's test area.
- CORRECTION to the previous register: the physical *demagnetization idea is not new*. `run_spatial_holdout_and_build.py` already computes `hydro_demag_conduit = max(-rtp_local15,0) * log1p(tmi_hg) * non_playa` for H16-4; 15GEMSDOE also tried alteration/magnetics. Novelty is limited to the **isolated multi-scale trough geometry and its polarity ablation**, not discovery of a new mechanism. We test this queued, unrun operator once, then do not retune it.
- Lithology, remanent magnetization, shallow Curie depth, survey leveling, and broad nonmagnetic basin fill can also cause lows. The [official GeoDAWN release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) documents 400 m east–west flight lines for most of the survey; 100 m raster cells do not imply 100 m independent magnetic resolution.

## Frozen inputs

| Input | SHA-256 |
|---|---|
| `training_features.tif` | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` |
| `labels.tif` | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` |
| `sample_submission.tif` | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` |
| Recorded H16-1 comparator (`evidence/spatial_holdout_h16_results.json`) | `c681ef8d3eca77cc1579c7f74ea608ed8a046f665a2965ba51d856831ee67897` |
| Historical H20 thresholds (`evidence/spatial_holdout_results.json`) | `45913754a58b9eb772dbba62005699c8cff8252599f6e3030cb38a72efae4a99` |

Use only band 2 (`rtp`), verify band-name metadata, CRS, dimensions and transform against the template. Bands 1/14 are **not** alternative candidates or a selection rule. Data are hash-verified team bridge copies, not independently compared with the login-gated DrivenData originals (F30). No new external data is needed.

## Frozen transform and emission

1. Fill nonfinite/sentinel (`< -1e20`) and out-of-footprint cells from their nearest valid footprint value. Center at the interior median; reverse the sign for trough detection. Record counts of filled cells. Do not mask known faults when constructing features.
2. Scale-normalized Gaussian Hessian at `sigma=(2,4,8)` cells, `truncate=4`, `mode=nearest`. Order eigenvalues by absolute magnitude. Retain bright-ridge responses in the **negative RTP** field (dominant eigenvalue < 0). Use `beta=0.5`, `C=q90(Hessian strength)` over the interior per scale. Response = `exp(-ratio²/(2 beta²)) * (1-exp(-strength²/(2 C²)))`, max over scales.
3. Set response to zero within 32 cells of the footprint boundary (largest four-sigma support). No tuning of scales, normalization, budgets or sign after results.
4. Primary evaluation: legacy `Holdout` quadrant folds; deterministic 20%-component sparse proxy, seed 4242; per-quadrant 2.5% emission, sigma=1 ridge NMS. This preserves historical comparison conditions, including the legacy sparse prediction-neutralization convention.
5. Descriptive controls, **not selectable candidates**: (a) scalar negative RTP (shifted/scaled to [0,1] by interior min/max), same budget/NMS; (b) opposite-polarity bright RTP ridges, same transform/budget. Also record direct **continuous-confidence** DTI for the trough response without binarizing; its amplitudes are not calibrated probabilities and are not comparable to the binary H16 threshold gate.

## Predicted effect and practical gates

Subjective planning upside: +0.000–0.003 DTI, not a forecast or confidence interval. Directional hypothesis: mean Sparse DTI exceeds H16-1 and trough geometry exceeds the scalar-low control. We do not predict an absolute hidden-test score.

H16-1 recorded baseline: Dense/Sparse `0.21269/0.08554`; folds Dense `[0.20774,0.23898,0.15453,0.24951]`, Sparse `[0.08900,0.07794,0.06675,0.10847]`. It was reproduced in the previous session; fresh baseline reproduction may be recorded separately, never substituted after seeing H22 outcomes.

Require the existing gate **against both** this H16 reference and historical track-wise H20 threshold screen: greater Dense and Sparse means, ≥3/4 Sparse wins, no fold loss >0.01 on either track. The H20 track-wise comparator is Dense H20-1 / Sparse H20-5; it is unreproduced and not a single model. Require Sparse improvement vs scalar-low control as well. Failure of any rule rejects this candidate without retuning.

## Explicit multiplicity and independence limits

Freeze a five-idea family before this run: **H22-2** (trough operator), **H22-1** (vent alignment), **H22-3** (displaced lithologic markers), **H21-3** (persistent spectral alteration), **H21-4** (drainage offsets). Pending/unavailable tests carry p=1, so family size cannot shrink when results disappoint. For this run compute the exact one-sided paired sign-flip p-value of four Sparse-fold differences vs H16-1 (all 16 sign patterns, including ties; exchangeability/independence is an assumption, not proven). Apply Holm FWER 0.05 and report BH FDR 0.05 descriptively to **all five** family entries. Require Holm rejection for any statistical promotion. Four folds have minimum possible p=1/16=0.0625; this deliberately prevents a spurious significant claim. No pixel-level pseudoreplication or uncentered-bootstrap tail is used as a significance test.

The current folds have already informed many experiments. Corrections do not undo adaptive reuse or turn a selected proxy into hidden truth. No final untouched slice can honestly be carved out of labels that have already been scored in their entirety. The future one-shot gate must use **new, independently adjudicated labels** never used for training, prior estimation, calibration, ranking or descriptive tests. Its persistent lock is globally single-use, consumed *before* evaluation, and bound to label/split/candidate/protocol hashes. It remains blocked until such data exists; the old H20 Vault cannot be reused.

## Output / slot decision

One immutable result: `evidence/h22_2_magnetic_low_holdout.json`. The evaluator refuses any existing result or consumed run lock; there is no `--force` promotion path. A crashed run remains consumed and must be disclosed, not silently reset. It writes no submission and spends no slot. **A proxy pass is necessary but insufficient**; lack of independent hidden-fault labels/calibration and a genuine untouched final gate blocks a recommendation. Results and failed controls are published regardless of outcome.

Reproduce the frozen computation only for audit under a new explicitly non-confirmatory run ID; never call that a second independent test.
