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
- The H20 evaluator's “hidden-fault” calibration label is synthetic: it combines catalogue/SGMC proximity with random Bernoulli outcomes derived from the model/prior. The resulting Brier REL/ECE statistics do not measure independent hidden-fault reliability (F25). The Brier decomposition implementation can be mathematically correct while its proxy outcome is not ground truth.

## 4. Spatial validation scope

The repository's four-quadrant holdout withholds components of the supplied known-fault raster; its sparse track keeps a deterministic random 20% of connected components. This measures **spatial transfer to known catalogue geometry** and a synthetic sparsity scenario. It does not test the unreleased hidden new-fault labels; official scoring masks the known-fault pixels. The stored H20 results have not been reproduced, and the reported Vault was used for H20-1 and H20-5 (F17, F27, F28).

Use `evidence/h21_seismic_ridge_holdout.json` for the preregistered H21-1 proxy test once available. A proxy pass is not a predicted private score or automatic submission clearance. No hidden-test reliability diagram or true hidden-fault Brier score is possible without observed hidden-fault outcomes.

## 5. Geological hypotheses and external source access

- **OBSERVED:** Faulds & Hinz summarize step-overs, relay ramps, terminations and intersections among structural settings of known Great Basin geothermal systems ([OSTI report](https://www.osti.gov/servlets/purl/1724082)). This is geological context, not evidence that any proposed feature improves this contest metric.
- **OBSERVED:** USGS reports on Great Basin seismicity discuss spatially variable small-earthquake activity and possible clusters beyond mapped major faults ([Gomberg 1991](https://www.usgs.gov/publications/seismicity-and-shear-strain-southern-great-basin-nevada-and-california)); a USGS fault/lineament compilation also documents induced-seismicity caveats ([OFR 96-262](https://pubs.usgs.gov/of/1996/0262/report.pdf)).
- **OBSERVED:** GDR 1391 is publicly accessible and lists geological, geothermal, temperature and chemistry data ([GDR page](https://gdr.openei.org/submissions/1391), [DOI](https://doi.org/10.15121/1881483)). Exact chemistry fields/quality still require review before H21-2.
- **OBSERVED:** USGS states Landsat Collection 2 Level-2 surface-reflectance data are no-cost ([USGS Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-collection-2)); footprint/date-specific scene quality has not been screened.
- **OBSERVED:** USGS 3DHP data is public/non-proprietary; NHD was retired in 2023 and is no longer maintained ([3DHP collection](https://catalog.data.gov/dataset/usgs-3d-hydrography-program-3dhp-downloadable-data-collection), [NHD status](https://www.usgs.gov/national-hydrography/national-hydrography-dataset)). Product completeness for the competition footprint has not been checked.

Ranked hypotheses, subjective planning ranges and costs are in [`docs/research/hypothesis_register.md`](../research/hypothesis_register.md). H21-1's frozen protocol is [`docs/research/preregistration_h21.md`](../research/preregistration_h21.md). Availability on an official landing page does not equal validated footprint coverage or proven DTI gain.

## 6. Current leaderboard and duplicate-effective files

Manual official leaderboard snapshot dated 2026-10-01: DARD 0.3168 (#1), `smrtdoog5` 0.1894 (#23), `extradr19` 0.1855 (#25); account-to-repository associations are owner-reported. See [`docs/data/leaderboard.json`](../data/leaderboard.json) and the [official live page](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

**COMPUTED:** On the official scored-pixel mask, `GEMSDOE1` and `5GEMSDOE` are byte-identical; `8GEMSDOE` and archived `17GEMSDOE` match those predictions on scored pixels despite different file hashes. This is the artifact-level explanation for the repeated historical `0.1563` entries. `17GEMSDOE-F` is a different raster (reported 0.0187); `GEMSDOE2` is a near-duplicate, not an exact duplicate. See [`evidence/submission_similarity.json`](../../evidence/submission_similarity.json).

## 7. Still unknown

- Which data sources, fault types, orientations or areas underlie the unreleased test labels.
- Whether the bridge rasters exactly match the official login-gated archive.
- The cause of the earlier server-side `[0, 1]` error; the original rejected TIF and server checker are unavailable (F31).
- Whether any H21 hypothesis improves the hidden-fault DTI; pre-submission holdouts use known-fault proxies.
