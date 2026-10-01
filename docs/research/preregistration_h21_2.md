# H21-2 multi-geothermometer coherence — preregistration

**Registered:** 2026-10-01, before the H21-2 transform is evaluated.
**Status:** preregistered; exploratory test on a spatial-transfer proxy only. This protocol does **not** create hidden-fault ground truth and cannot by itself qualify a submission.

## Hypothesis

**H21-2 — Multi-geothermometer coherence.** Where two or more independent chemical geothermometers (quartz, chalcedony, Na–K–Ca cation) at the same spring or well agree that the reservoir is hot, the site is more likely to tap a fault-controlled upflow conduit than a site with a single or mutually inconsistent estimate. Concordant-upflow sites may sit on structures absent from the USGS/INGENIOUS fault catalogue. This is an INFERENCE about geothermal fluid pathways, not an established relation for this competition's hidden labels.

**Novelty check:** H20-4 used thresholded thermal/geochemical point anomalies as anchors; H15 used an alteration–magnetics conjunction. Neither tested *cross-indicator agreement among the three solute geothermometers* as the scored quantity. The H21-2-specific elements are (a) requiring ≥ 2 estimators, (b) scoring their mutual agreement, and (c) freezing out all other layers. A complete code audit of every historical repository is not available, so novelty beyond this checkout is **not verified**.

**Data-audit boundary (what was examined before freezing):** only schema-level facts from `evidence/h21_2_wellspring_audit.json` (row counts, layer membership, unit plausibility, missingness, per-cell duplicate sampling, thermalclass spelling variants, coordinate-vs-geotransform consistency, and the previously published overall distance-to-catalogue distribution). **No fold assignment, no label overlap, no candidate field, and no DTI of any kind was computed before this document was committed.**

## Frozen data and transform

- Input: `evidence/ci/gdr_wellspring_in_footprint.csv` (27,092 rows), extracted from the official GDR 1391 `wellspringdata.gdb.zip` by the committed CI workflow; the source zip's SHA-256 is `72221784…f356590f` in `evidence/ci/external_verification.json`. [GDR 1391](https://gdr.openei.org/submissions/1391), [DOI 10.15121/1881483](https://doi.org/10.15121/1881483).
- **Layers:** only records whose layer name contains `chemistry` (`spring_chemistry_20220808`, `well_chemistry_20220808`). Temperature-only and feature-catalogue records are excluded from the candidate (they form control C1 instead).
- **Positions:** cell coordinates are re-derived from `utm_x/utm_y` through the `sample_submission.tif` geotransform (EPSG:32611, 100 m cells); the CSV's provided row/col is used only as a QA cross-check (tolerance 1 px). The audit found 2 of 27,092 rows outside a half-cell offset; deriving positions from UTMs makes the geotransform the single source of truth.
- **Sanitization:** geothermometer estimates outside `[0, 350] °C` or non-finite are invalid (the audit found 29 negative estimates — physically implausible). Bounds are inclusive.
- **Per cell:** for each estimator take the median of its valid values across the cell's records; `n_est` = number of estimators with a valid median; `t_med` = median of the 2–3 estimator medians; `spread_rel = (max − min) / t_med`.
- **Eligibility (all required):** `n_est ≥ 2`, `t_med ≥ 120 °C`, `agreement = clip(1 − spread_rel / 0.25, 0, 1) > 0`.
- **Weight:** `w = (t_med / 120) * agreement` for eligible cells, else 0.
- **Field:** impulse amplitudes `w` at eligible cells, convolved with a Gaussian `σ = 5` cells (500 m), truncated at 3σ, zero outside the footprint, max-normalized to `[0, 1]` inside the footprint.
- **Judgment constants and their basis:** `120 °C` — moderate-temperature hydrothermal reservoir relevance cutoff (judgment, not derived from any leaderboard or holdout information); `0.25` — maximum tolerated relative estimator disagreement (judgment); `σ = 500 m` — near the 300 m metric-kernel scale, small enough to keep point locality (judgment). None was tuned against any outcome.

Constants `GEOTHERM_COLUMNS`, `VALID_RANGE_C`, `MIN_ESTIMATORS`, `T_HOT_MIN_C`, `REL_SPREAD_MAX`, `SIGMA_PX`, `KERNEL_TRUNCATE`, `CONTROL_TEMP_MIN_C`, `CONTROL_RANDOM_SEED` are implemented in `src/gems/geotherm.py` and pinned by its unit tests.

## Spatial evaluation and decision rule

Use `gems.holdout.Holdout` exactly as for H21-1: four contiguous NW / NE / SW / SE quadrants, supplied `labels.tif`, fixed 20%-of-connected-components sparse proxy (seed 4242, offset 0), 2.5% per-quadrant emission budget, no threshold search. Because the candidate is an isotropic point-anomaly field and not a lineament surface, emission uses `ridge=False` (the 1-pixel ridge NMS is a morphology designed for ridge surfaces; applying it to Gaussian blobs would be an arbitrary deformation). The comparator numbers below were produced under their own preregistered emissions; the comparison shares folds, labels, budget and DTI implementation.

Promotion gate (unchanged from H21-1), applied against **both** comparators:

1. higher mean Dense and mean Sparse DTI,
2. Sparse DTI wins in at least 3 of 4 folds,
3. no fold loses more than 0.01 DTI (dense or sparse),

versus (a) the conservative stored H20 track-wise reference (H20-1 Dense `0.21442`, folds `[0.20851, 0.24333, 0.15610, 0.24973]`; H20-5 Sparse `0.08792`, folds `[0.08959, 0.08486, 0.06774, 0.10951]` — historical, **unreproduced**) and (b) the reproduced H16-1 baseline (Dense `0.21269`, folds `[0.20774, 0.23898, 0.15453, 0.24951]`; Sparse `0.08554`, folds `[0.08900, 0.07794, 0.06675, 0.10847]`; `evidence/spatial_holdout_h16_results.json`, 2026-10-01).

**Controls (descriptive only, never promotion candidates):**

- **C1 thermal points:** every unique cell with a measured temperature ≥ 25 °C or normalized thermalclass Hot/Warm — a stand-in for H20-4-style thresholded thermal anchors without coherence selection (unit weights, same σ). Thermalclass is normalized for case/whitespace; the audit found a `'Hot '` spelling variant (flagged F35).
- **C2 random pseudo-sites:** as many unique footprint cells as eligible coherence cells, uniform without replacement, seed 4243 — the chance level for the fixed point-count × σ × budget geometry.
- **C3 known-catalogue proximity transfer:** per held fold, the Gaussian-decay (same σ) of distance to catalogue fault pixels *outside* that fold — a sampling-bias ceiling. Springs are ~1.8× enriched within 1 km of catalogued faults (S30), so any proximity-driven field gets partial transfer credit; if H21-2 does not beat C3, a pass is attributable to sampling geometry rather than chemistry.

**One candidate, no sweeps.** If the gates fail, H21-2 is rejected and the constants are not retuned on this register entry (a materially altered version would require a new hypothesis ID and its own preregistration). Descriptive control outcomes are reported as observed numbers without significance claims; this single-candidate design incurs no multiplicity correction.

## Limitations and submission eligibility

- The evaluation truth is the supplied known-fault catalogue; its quadrants are transfer proxies, not hidden competition labels (staff: known-fault pixels are excluded from scoring pixel-exactly; new faults may be extensions/splays).
- **Sampling-bias confound:** springs/wells are preferentially sited and sampled near mapped faults (S30); a proxy pass cannot separate "chemistry finds faults" from "chemistry was measured near mapped faults". C3 quantifies but does not remove this confound.
- Measured temperatures (especially well bottom-hole values) are depth-dependent and are deliberately **not** part of the candidate score; sample-date/analytical-batch comparability across the GDR compilation was not resolvable in this sandbox (audit note).
- The CSV is a CI extraction of the official GDB; the sandbox cannot reach gdr.openei.org directly, so bytes are authenticated by the committed CI SHA-256 chain, not re-downloaded here.
- **The evaluator never writes a submission artifact.** A double-gate pass authorizes nothing by itself. On a pass, a *separate*, separately reviewed packaging step may add a downloadable GeoTIFF clearly labelled "holdout-proxy pass only; hidden-fault evidence absent", subject to the uniqueness gate and the 3-per-rolling-7-days limit; the slot decision remains with the project owner. On any failure, nothing is packaged and no slot is spent.

## Physical rationale and sources

- Reservoir-temperature estimation from multiple solute geothermometers (quartz: Fournier 1973, DOI [10.2118/4062-PA](https://doi.org/10.2118/4062-PA); chalcedony constraint: Fournier 1977, USGS, cited via DOI [10.3133/ofr78680](https://doi.org/10.3133/ofr78680); Na–K–Ca: Fournier & Truesdell 1973, DOI [10.1016/0016-7037(73)90080-4](https://doi.org/10.1016/0016-7037(73)90080-4); Na/K/Mg equilibrium interpretation: Giggenbach 1988, DOI [10.1016/0016-7037(88)90143-3](https://doi.org/10.1016/0016-7037(88)90143-3)) is standard geothermal practice; estimator concordance is interpreted as reservoir equilibration. **Bibliographic references; not re-fetched in this sandbox** — used for method identity only, not performance claims.
- Upflow zones localize at fault intersections/terminations and step-overs in Great Basin systems ([Faulds & Hinz, OSTI](https://www.osti.gov/servlets/purl/1724082)); springs cluster on basin flanks along Basin and Range faults (S27); GeoDAWN-footprint springs are ~1.8× enriched within 1 km of catalogued faults (S30). These motivate the test and document the sampling-bias confound; they are not evidence of DTI improvement.
- Data: [GDR 1391](https://gdr.openei.org/submissions/1391) (verified public, S28/S51); unit meanings inferred from GDR field names (`*_c` = °C) — flagged as an inference from names, not a re-read data dictionary.

## Reproduction

```bash
.venv/bin/python scripts/audit_h21_2_wellspring_data.py      # QA audit (schema only)
.venv/bin/python scripts/evaluate_h21_2_geotherm_coherence.py
```

The evaluator writes `evidence/h21_2_geotherm_coherence_holdout.json`, embedding the SHA-256 of this preregistration and of every input. It refuses to overwrite an existing result unless `--force` is passed; forced reruns are audit-only and labelled as such.
