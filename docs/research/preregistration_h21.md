# H21 seismic-density lineation — preregistration

**Registered:** 2026-10-01, before the H21 transform is evaluated.  
**Status:** preregistered; exploratory test on a spatial-transfer proxy only. This protocol does **not** create hidden-fault ground truth and cannot by itself qualify a submission.

## Hypothesis

**H21-1 — Multi-scale earthquake-intensity ridges.** Linear bands of elevated earthquake intensity may reveal active or reactivated structures that are not represented by the supplied USGS/INGENIOUS fault raster. A local line-shaped response could be more specific than the existing scalar earthquake-intensity feature. This is an inference, not an established relation in this competition.

The concept was previously listed as an unrun idea in the older H17-3 register. H21 is therefore a first implementation/test of that parked idea, not a claim that no one had ever proposed it. The existing H16-5 feature set uses scalar `seismic_ieq_log`, and the H20-3 description uses seismic intensity as a gate; neither is a multi-scale Hessian line-ridge transform. A complete code audit of every historical repository is not available, so novelty beyond this checkout is **not verified**.

## Frozen data and transform

- Input: band 16, `ieq_n100a15`, tagged in `training_features.tif` as “Earthquake intensity or density (n=100km radius, a=15° parameters)”. The parameter name's exact construction is not independently documented here; no further interpretation is assumed.
- Sanitize non-finite and float32 sentinel values to zero; use `log1p(max(ieq, 0))`.
- Compute scale-normalized 2-D Hessians at exactly `sigma = 2, 4, 8` raster cells (200, 400, 800 m at 100 m/cell): multiply second derivatives by `sigma**2`, order eigenvalues by absolute magnitude, and retain only bright-ridge responses (dominant eigenvalue < 0).
- Per scale, use fixed Frangi-style constants `beta = 0.5` and `C = q90(sqrt(lambda1**2 + lambda2**2))` over valid interior cells; take the pixelwise maximum of the three responses. Do not tune the scales, percentile, threshold, or fusion weights after seeing results.
- Exclude the outer 32-cell footprint ring from response ranking to cover the four-sigma support of the largest (8-cell) Gaussian derivative and avoid derivatives of the footprint edge. Keep the evaluation budget at 2.5% of each quadrant and the repository's fixed 1-pixel ridge-NMS evaluation setting.
- Primary control: the raw `seismic_ieq_log` feature evaluated with the same budget and ridge-NMS rule. This is descriptive; it is not a second promotion candidate.

## Spatial evaluation and decision rule

Use `gems.holdout.Holdout` with the repository's four contiguous NW / NE / SW / SE quadrants, `labels.tif`, fixed 20%-of-connected-components sparse proxy, seed 4242, 2.5% per-quadrant emission budget, and no threshold search. Record fold-level Dense and Sparse DTI and compare with the stored H20 reference fold vectors:

- Dense comparator: H20-1 `[0.20851, 0.24333, 0.15610, 0.24973]`, mean `0.21442`.
- Sparse comparator: H20-5 `[0.08959, 0.08486, 0.06774, 0.10951]`, mean `0.08792`.

These are historical values from `evidence/spatial_holdout_results.json`, **not reproduced in this session**. The preregistered numerical gate is strictly higher mean Dense and Sparse DTI than those respective comparators, Sparse wins in at least 3/4 folds, and no fold loses more than 0.01 in either track. Also report the same metrics against the H16-1 comparator if its OOF predictions are reproduced. A pass against stored values is only a screening result: it does not establish a valid comparison or unseen-fault transfer.

### Pre-execution amendment — current reproducible comparator (2026-10-01)

Before the H21 run, the repository's H16-1 reference was recomputed with the current spatial holdout runner and saved separately at `evidence/spatial_holdout_h16_results.json`: Dense mean `0.21269`, folds `[0.20774, 0.23898, 0.15453, 0.24951]`; Sparse mean `0.08554`, folds `[0.08900, 0.07794, 0.06675, 0.10847]`. This reproduces a known-catalogue transfer proxy, not hidden-fault performance.

The original conservative track-wise H20 screen remains unchanged. H21 must also pass the same fixed gate against this newly reproduced H16-1 result. Both gates are required for a proxy-screen pass: each requires higher Dense and Sparse means, at least 3/4 Sparse-fold wins, and no fold loss exceeding 0.01 in either track. Because the historical H20 Dense and Sparse thresholds come from different candidates and remain unreproduced, passing both gates is still only necessary—not sufficient—for recommending a submission. H21 cannot automatically create or authorize an artifact.

## Limitations and submission eligibility

The available truth is the supplied known-fault catalogue. Official staff clarified that those pixels are excluded from contest scoring exactly; their spatial holdout is a transfer proxy, not hidden-fault truth. The sparse proxy is synthetically thinned known components, not an independent geological inventory. No true hidden-fault reliability or Brier calibration can be measured from these labels. No untouched vault remains independently demonstrated: stored records show that the same “vault” was evaluated for at least two H20 candidates.

**No H21 submission slot is authorized by this preregistration or by a proxy-gate pass.** A recommendation would require a reproducible comparison against a valid baseline, no data/label leakage, format validation, and evidence that the candidate clears the user's holdout criterion. Hidden test truth is unavailable before submission, so that final generalization limit must be stated explicitly.

## Physical rationale and sources

- USGS describes Great Basin seismicity as spatially variable and discusses earthquake clusters whose extent may exceed mapped major faults; that supports testing, not a guarantee of predictive value: [Gomberg (1991), USGS Publications Warehouse](https://www.usgs.gov/publications/seismicity-and-shear-strain-southern-great-basin-nevada-and-california).
- A USGS compilation documents both lineated earthquake clusters and caveats including induced seismicity in the Pahute Mesa area: [USGS Open-File Report 96-262](https://pubs.usgs.gov/of/1996/0262/report.pdf).
- The supplied `ieq_n100a15` layer is documented in the raster's own band description and `evidence/data_verification.json`; its provenance is part of the competition feature stack, not a newly acquired external source.

## Reproduction

```bash
.venv/bin/python scripts/evaluate_h21_seismic_ridge.py
```

The script writes `evidence/h21_seismic_ridge_holdout.json`, including the SHA-256 of this preregistration and the actual input rasters. It must refuse to overwrite an existing result unless `--force` is explicitly provided; reruns are audit-only and must be labelled as such.
