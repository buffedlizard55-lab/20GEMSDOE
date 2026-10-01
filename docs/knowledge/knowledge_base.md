# Evidence and limitations knowledge base — 2026-10-01

**Labels:** **OBSERVED** = stated in the linked source; **COMPUTED** = calculated from a named repository file; **INFERENCE** = a hypothesis, not an established contest finding. The complete source and issue ledgers are [`registry/sources.json`](../../registry/sources.json) and [`registry/irregularities.json`](../../registry/irregularities.json).

## 1. Competition rules that materially affect the model

- **OBSERVED:** The supplied catalogue is incomplete. The challenge evaluates new faults; staff defines a new fault as a pixel not already in the USGS/INGENIOUS catalogue, including newly mapped geometry of an existing system. [Problem statement](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [staff definition](https://community.drivendata.org/t/where-do-you-draw-the-line/11536/2).
- **OBSERVED:** Known-fault exclusion is pixel-exact and identical to the provided training fault labels. Predictions near known faults are not exempt from false-positive penalties; new-fault pixels may nevertheless lie within 300 m of known traces. [Staff clarification](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4).
- **OBSERVED:** DTI uses `alpha=0.2`, `beta=0.8` and a triangular 300 m kernel. The 300 m kernel is not a blanket forgiveness zone around known traces. [Metric specification](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
- **OBSERVED:** At most three submissions are allowed in a **rolling** seven-day window; DrivenData Terms of Use prohibit automatic site access. [Staff on rolling window](https://community.drivendata.org/t/weekly-submissions/11524/2) · [Terms of Use](https://www.drivendata.org/termsofuse/).

## 2. Inputs and provenance

| Input | What is known | Limitation |
|---|---|---|
| `training_features.tif` | **COMPUTED:** 19-band float32 raster, 3292×3730, on the competition grid; band descriptions and hashes are recorded in `evidence/data_verification.json`. | Recovered from a team-maintained GitHub bridge and locally hash-checked; not independently compared with the login-gated official archive. |
| `labels.tif` | **COMPUTED:** supplied catalogue-positive raster; overlap/provenance was compared with GDR 1391 fault vectors. | It is a catalogue of known faults, not ground truth for hidden new faults. |
| `sample_submission.tif` | **COMPUTED:** finite footprint defines the template grid; candidate artefacts are checked against it. | Local template is also bridge-provided, not independently fetched from the official data tab. |
| DEM10 channels | **COMPUTED:** all 13 channels verified by `scripts/fetch_dem10.py`; details in `evidence/dem10_fetch_verification.json`. | This verifies the local files and recorded source hashes, not competition-label performance. |
| GDR geothermal layers | GDR 1391 is a public Great Basin compilation. CI evidence lists wells/springs, temperature/chemistry, probes, deposits and volcanic features. | Some source files exist only in CI evidence or external download records, not in current local `data/`; audit exact schemas/units before using a layer. |

**Flag F01:** Band 6 `tc` metadata says “tilt angle or total curvature”; its measured correlation with external GeoDAWN `TC` is 0.9971, but only 0.0128 with computed magnetic tilt. Treat the tag/interpretation as unresolved. **Flag F05:** the raw stack contains invalid/sentinel values inside the footprint; sanitize explicitly before numerical transforms.

## 3. Positive-unlabeled framing — useful, but conditional

**INFERENCE:** Because the catalogue is incomplete, a zero outside a known-fault line may mean “not mapped” rather than verified fault-free background. This motivates a PU formulation, but does not establish the label-generation mechanism or a true hidden-fault prevalence.

- Kiryo et al. (2017) derive a non-negative PU risk estimator under mixture assumptions and a specified/estimated class prior. See [the paper](https://proceedings.neurips.cc/paper/2017/file/7cce53cf90577442771720a370c3c723-Paper.pdf) and local implementation [`src/gems/pu_learning.py`](../../src/gems/pu_learning.py).
- The often-repeated `pi=0.0363` is a power-law extrapolation from known trace geometry below a selected completeness cutoff. It is a **model-based prior scenario**, not a measured fraction of hidden pixels. Its result depends on the assumed power law, completeness cutoff, vectorization and rasterization.
- Do not claim all earlier repositories used naive PN loss without inspecting each training pipeline; the historical code audit is incomplete (F24).
- The H20 evaluator's “hidden-fault” calibration label is synthetic: it combines catalogue/SGMC proximity with random Bernoulli outcomes derived from the model/prior. The resulting Brier REL/ECE statistics do not measure independent hidden-fault reliability (F25). The corrected raw Brier equals REL−RES+UNC plus within-bin forecast variance minus twice within-bin forecast/outcome covariance; the simple partition alone is exact for bin-mean forecasts, not arbitrary soft scores. Numerical correctness does not make synthetic outcomes ground truth.

## 4. Spatial validation scope

The repository's four-quadrant holdout withholds components of the supplied known-fault raster; its sparse track keeps a deterministic random 20% of connected components. This measures **spatial transfer to known catalogue geometry** and a synthetic sparsity scenario. It does not test the unreleased hidden new-fault labels; official scoring masks the known-fault pixels. The stored H20 results have not been reproduced, and the reported Vault was used for H20-1 and H20-5 (F17, F27, F28).

**COMPUTED (2026-10-01):** two preregistered single-shot proxy tests are complete — H21-1 (multi-scale seismic ridges; Dense `0.06207` / Sparse `0.02511`) in `evidence/h21_seismic_ridge_holdout.json` and H21-2 (multi-geothermometer coherence; Dense `0.03244` / Sparse `0.01388`) in `evidence/h21_2_geotherm_coherence_holdout.json`. Both failed the historical-H20 and reproduced-H16-1 (Dense `0.21269` / Sparse `0.08554`) gates and are rejected as submission candidates. H21-2's descriptive controls add transferable context: the unselected thermal-point control scored *higher* than the coherence-selected candidate (`0.03857` vs `0.03244` Dense), seeded random cells scored `0.02901`, and the pure catalogue-proximity transfer ceiling is only `0.04190` Dense on this protocol — so sparse point-anomaly fields, selected or not, sit far below the multi-feature ridge-synthesis baseline, and catalogue-proximity leakage alone cannot explain a pass. These are known-catalogue proxy facts, not hidden-fault evidence. A proxy pass is not a predicted private score or automatic submission clearance. No hidden-test reliability diagram or true hidden-fault Brier score is possible without observed hidden-fault outcomes.

## 5. Geological hypotheses and external source access

- **OBSERVED:** Faulds & Hinz summarize step-overs, relay ramps, terminations and intersections among structural settings of known Great Basin geothermal systems ([OSTI report](https://www.osti.gov/servlets/purl/1724082)). This is geological context, not evidence that any proposed feature improves this contest metric.
- **OBSERVED:** USGS reports on Great Basin seismicity discuss spatially variable small-earthquake activity and possible clusters beyond mapped major faults ([Gomberg 1991](https://www.usgs.gov/publications/seismicity-and-shear-strain-southern-great-basin-nevada-and-california)); a USGS fault/lineament compilation also documents induced-seismicity caveats ([OFR 96-262](https://pubs.usgs.gov/of/1996/0262/report.pdf)).
- **OBSERVED:** GDR 1391 is publicly accessible and lists geological, geothermal, temperature and chemistry data ([GDR page](https://gdr.openei.org/submissions/1391), [DOI](https://doi.org/10.15121/1881483)). **COMPUTED (audit done 2026-10-01):** the committed footprint chemistry extract was schema/unit-audited (`evidence/h21_2_wellspring_audit.json`): `*_c` fields behave as °C; 29 negative (physically implausible) geothermometer estimates must be invalidated; `thermalclass` has spelling variants (`'Hot '` vs `'Hot'`); 572 cells carry ≥ 2 of the 3 solute geothermometers; UTM-derived positions agree with extract row/col within 1 px. Also computed: springs are ~1.8× enriched within 1 km of catalogued faults (sampling bias; S30) — a standing confound for any chemistry-proximity hypothesis.
- **OBSERVED:** USGS states Landsat Collection 2 Level-2 surface-reflectance data are no-cost ([USGS Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-collection-2)); footprint/date-specific scene quality has not been screened.
- **OBSERVED:** USGS 3DHP data is public/non-proprietary; NHD was retired in 2023 and is no longer maintained ([3DHP collection](https://catalog.data.gov/dataset/usgs-3d-hydrography-program-3dhp-downloadable-data-collection), [NHD status](https://www.usgs.gov/national-hydrography/national-hydrography-dataset)). Product completeness for the competition footprint has not been checked.

Ranked hypotheses, subjective planning ranges and costs are in [`docs/research/hypothesis_register.md`](../research/hypothesis_register.md). Frozen protocols: H21-1 [`preregistration_h21.md`](../research/preregistration_h21.md), H21-2 [`preregistration_h21_2.md`](../research/preregistration_h21_2.md). Availability on an official landing page does not equal validated footprint coverage or proven DTI gain.

**COMPUTED (data access, 2026-10-01):** core rasters, three external rasters plus metadata and 13 DEM10 vectors restored/verified through immutable GitHub commits (see [`registry/data_inputs.json`](../../registry/data_inputs.json)). H16's seven means reproduced; F38 resolved. Transport hashes are not an independent official archive or fresh USGS tile comparison. Direct official ZIP/browser-binary downloads failed in the sandbox; official text pages were read using the manual page tool. No DrivenData login, upload or automated polling occurred.

## 6. Current leaderboard and duplicate-effective files

Manual official leaderboard snapshot dated 2026-10-01: DARD 0.3168 (#1), `smrtdoog5` 0.1894 (#24), `extradr19` 0.1855 (#27); account-to-repository associations are owner-reported. See [`docs/data/leaderboard.json`](../data/leaderboard.json) and the [official live page](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

**COMPUTED:** On the official scored-pixel mask, `GEMSDOE1` and `5GEMSDOE` are byte-identical; `8GEMSDOE` and archived `17GEMSDOE` match those predictions on scored pixels despite different file hashes. This is the artifact-level explanation for the repeated historical `0.1563` entries. `17GEMSDOE-F` is a different raster (reported 0.0187); `GEMSDOE2` is a near-duplicate, not an exact duplicate. See [`evidence/submission_similarity.json`](../../evidence/submission_similarity.json).

## 7. Still unknown

- Which data sources, fault types, orientations or areas underlie the unreleased test labels.
- Whether the bridge rasters exactly match the official login-gated archive.
- The cause of the earlier server-side `[0, 1]` error; the original rejected TIF and server checker are unavailable (F31).
- Whether any H21/H22 hypothesis improves the hidden-fault DTI; pre-submission holdouts use known-fault proxies, and both preregistered H21 tests failed even those.

## 8. Current scientific corrections and negative evidence

- **COMPUTED:** H22-2 binary `0.06131/0.02222`, H22-3 binary `0.06215/0.02433`, both permanently rejected after one execution. H22-3 loses zero-lag `0.06958/0.03186`. No rerun, retuning, artifact or slot. See the [scientific audit](../research/scientific_audit.md) and immutable consumed ledgers.
- **CORRECTION:** archived H22 soft-confidence diagnostic DTI values were >0.5 binary scores, not unthresholded DTI. Primary binary decisions unchanged; no replacement holdout access. [Hash-bound annotation](../../evidence/h22_metric_schema_annotations.json). New soft scoring dispatches to exact probability-mass/kernel-credit DTI; the binary API rejects soft input. Official wrappers exclude known pixels from both predictions and truth; old proxy comparisons explicitly preserve FP-only catalogue neutrality, not a claim of identical official masking.
- **COMPUTED:** genuine nnPU numerical head implements the negative-risk reversed-gradient branch. For complement U with labelled mass mu, R_minus=(1−mu)E_U l(−g)−(pi−mu)E_P l(−g). SCAR, correct positives and pi remain assumptions; legacy H20/H16 loss labels do not establish Kiryo training.
- **COMPUTED:** vector length-tail primary scenario pi=0.0124163671, cutoff sensitivity ~[0.01234,0.01348], 399-refit KS p=0.0025. Fit rejected; sensitivity is not a CI or measured prevalence. Bbox extract is not exact-footprint clipped; selection/width/overlap uncertainty prevents identification. [Prior study](../../evidence/pu_vector_prior_study.json).
- **BLOCKED:** no independent hidden-positive/representative negative evidence, genuine reliability/Brier, identified class prior or untouched final confirmation. Four reused blocks have minimum exact p=.0625, incompatible with Holm FWER .05. No calibrated candidate was trained with an identified prior.
- **INFERENCE:** continuous DTI rewards fault coverage and weighted mass; it is not a proper probability-calibration scoring rule. Optimizing DTI does not by itself prove that a value of .7 is a 70% hidden-fault frequency.
- **OBSERVED/SCOPED:** [literature notes](../research/literature_notes.md) distinguish structural permeability/upflow from the fault-detection target; thermal anomalies/vent alignments are not fault ground truth. Landsat/3DHP coverage is unacquired; full chapter/paper reading is not implied by abstract access.
- **FORMAT ONLY:** browser export preserves all in-footprint predictions, writes NaN outside, and returns a fresh filename/SHA/note. This is an effective duplicate, not novelty or slot authorization. Node/Python roundtrips and actual Chromium desktop/mobile pre-flight/export/file-picker smoke tests pass in [GitHub CI](https://github.com/buffedlizard55-lab/20GEMSDOE/actions/runs/36874200770). The sandbox still lacks browser binaries; automated checks are not manual visual or geological validation.
