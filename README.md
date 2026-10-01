# 20GEMSDOE — DOE GEMS fault-mapping research

[![DrivenData DOE GEMS #306](https://img.shields.io/badge/DrivenData-DOE_GEMS_%23306-0f766e)](https://www.drivendata.org/competitions/306/competition-doe-gems/)
[![Current public leader](https://img.shields.io/badge/Public_leader-DARD_0.3168-1d4ed8)](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

**Project status as of 2026-10-01:** research artifacts and the submission-page packaging flow are present. No 20GEMSDOE candidate is recommended for a weekly submission. H21-1's preregistered known-catalogue spatial-transfer test is complete and failed both the historical H20 screen and the newly reproduced H16-1 comparator by a wide margin; it is rejected as a submission candidate. H20 holdout values remain unreproduced historical reports, and the former “hidden-fault calibration” used a synthetic target, not hidden-fault evidence.

## Start here — evidence, status, and safe use

### Competition objective and official scoring clarification

The DOE GEMS challenge asks for fault-probability GeoTIFFs for the Nevada/California GeoDAWN footprint. The public catalogue is incomplete, and the evaluation concerns new fault pixels. The distance-weighted Tversky index uses `alpha=0.2`, `beta=0.8`, and a 300 m triangular distance kernel. **Official staff clarified** that “new fault” means a fault pixel not already captured by USGS/INGENIOUS, including newly mapped geometry of an existing system; the known-fault exclusion is pixel-exact; a prediction near a known trace is not exempt from false-positive penalty; and a new-fault pixel may lie within 300 m of a known trace. The 300 m metric kernel is not a blanket buffer around known faults. The three-submissions allowance is a rolling window.

Manual review links: [competition page](https://www.drivendata.org/competitions/306/competition-doe-gems/), [problem statement and metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/), [staff clarification: what counts as a new fault](https://community.drivendata.org/t/where-do-you-draw-the-line/11536/2), [pixel-exact mask and 300 m rule](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4), and [rolling submission window](https://community.drivendata.org/t/weekly-submissions/11524/2).

### Current public leaderboard snapshot (manual check, 2026-10-01)

- Public leader: **DARD, 0.3168**.
- Best group-associated score: **0.1894** (account `smrtdoog5`, rank 23 on the captured page; association with 19GEMSDOE H19-4 is owner-reported).
- Next group-associated score: **0.1855** (account `extradr19`, rank 25; association with 16GEMSDOE H16-1 is owner-reported).
- The requested starting value DARD `0.3049` is stale. Ranks can move; scores and ranks are a dated snapshot, not a live feed. See [`docs/data/leaderboard.json`](docs/data/leaderboard.json) and the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

### Why `0.1563` repeated — artifact evidence, not a claim about model code

The forensics compare the 27 archived GeoTIFF entries on the **officially relevant pixel set** (template footprint minus the pixel-exact supplied known-fault mask). `GEMSDOE1` and `5GEMSDOE` are byte-identical (`7f00890a…` SHA-256; Git blob `812e61b740…`). `8GEMSDOE` has a different file hash but matches their prediction at every scored pixel; its differences are confined to masked known-fault pixels. The archived `17GEMSDOE` raster also matches on scored pixels, but it is **not** the separately named `17GEMSDOE-F` artifact, which scored `0.0187`. `GEMSDOE2` is a near-duplicate (positive-mask Jaccard 0.9464), not an identical scored surface; its reported score is `0.1560`.

**Best-supported explanation:** the three archived candidates associated with `0.1563` had the same effective predictions after the official mask, so changing the repository/model label did not change the evaluated surface. This explains repeated output, but does not prove how the files were produced or independently authenticate each historic account-to-file mapping. See [`evidence/submission_similarity.json`](evidence/submission_similarity.json), [`docs/data/forensics.json`](docs/data/forensics.json), and the [forensic results page](docs/results.html).

### Data provenance and reproducibility limits

- The repository's working inputs live in ignored local `data/` (a symlink to `.cache/gems_data` here). All 13 10 m DEM channels were verified and `prepare_data.py` completed.
- The current core competition rasters were recovered from hash-pinned team GitHub bridge copies. Their local SHA-256 values are recorded and checked, and the labels raster was compared with the public GDR fault vectors. **The files were not independently downloaded from or byte-compared with DrivenData's login-gated competition archive in this session.** Hash integrity is not the same as official-host provenance.
- Band 6's `tc` tag is inconsistent with its behaviour: its correlation with the external GeoDAWN `TC` channel is 0.9971, versus 0.0128 with computed magnetic tilt. Do not describe this layer as a validated tilt feature without resolving the discrepancy; see [F01](docs/audit.html#F01) and [`evidence/feature_profile.json`](evidence/feature_profile.json).
- The OOF files needed by the former H20 workflow are absent. `evaluate_h19_and_build_submissions.py` and its H20 wrappers are now retired compatibility notices that perform no training, evaluation, packaging, or file writes. No H20 reproduction is claimed.
- The automated leaderboard/forum feed requested in the project brief is intentionally not implemented: DrivenData's Terms of Use prohibit robots/spiders or other automatic website access. Use the dated manual snapshot above; do not poll or scrape the site.

### H20 results and calibration: required corrections

`evidence/spatial_holdout_results.json` records H20-1 mean Dense/Sparse DTI `0.21442 / 0.08696` and H20-5 `0.21314 / 0.08792`. Treat these only as **reported historical results**: they use spatially held-out portions of the known-fault catalogue, with a synthetic 20%-component sparse proxy—not independent hidden-fault labels—and they have not been reproduced. The shared spatial slice was evaluated for at least two H20 candidates, so it is not an untouched single-shot gate. The 20GEMSDOE calibration report constructed its outcome as `s_hit | Bernoulli(p_hidden_u)` from catalogue/SGMC proximity and a chosen prior; its bin rates and Brier/REL/ECE therefore describe a **synthetic target**, not observed hidden ground truth.

A fresh H16-1 known-catalogue baseline was reproduced on 2026-10-01 at Dense/Sparse `0.21269 / 0.08554`; see [`evidence/spatial_holdout_h16_results.json`](evidence/spatial_holdout_h16_results.json). The frozen H21-1 transform scored `0.06207 / 0.02511` (raw scalar control `0.07977 / 0.02849`) and failed both required comparator gates. This is a negative spatial-transfer proxy result, not proof about hidden-fault performance; it does rule out a weekly submission recommendation for H21-1 under the preregistered criterion.

A separate exploratory rank-correlation scan across 19 archived scored rasters found Spearman ρ `-0.05` for the known-catalogue Dense proxy (p=`0.8473`) and `+0.44` for the SGMC-gap proxy (p=`0.0615`). These uncorrected associations are hypothesis-generating only; the reported feature scan has nothing significant after Bonferroni correction (smallest listed p=`0.0059`, threshold=`0.00098`). See [`evidence/proxy_calibration_vs_lb.json`](evidence/proxy_calibration_vs_lb.json) and [`evidence/lb_signal_attribution.json`](evidence/lb_signal_attribution.json).

Consequently, no stored H20 metric, Holm p-value, Vault result, proxy comparison, or calibration number is represented here as independent confirmation of leaderboard performance. See flags F17 and F25–F29 in [`registry/irregularities.json`](registry/irregularities.json).

## Candidate research — H21 register

Four materially different ideas and their evidence status are in [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md). H21-1 has completed its one preregistered known-catalogue transfer test and failed; H21-2 is now the next proposed experiment, not a recommendation or submission candidate. The ranges for **untested** hypotheses below are subjective planning priors, not measured effects. The completed H21-1 result is reported separately and is not presented as an expected-gain estimate.

| Rank | Hypothesis | Named layers and physical transform | Catalogue-gap rationale | Difference from existing work | Planning expectation / cost / status |
|---|---|---|---|---|---|
| 1 | **H21-2: multigeothermometer coherence** (proposed; next preregistration candidate) | GDR 1391 `spring_chemistry_20220808` / `well_chemistry_20220808` (`temp_c`, `geothermquartz_c`, `geothermchalc_c`, `geothermcat_c`) plus spring/well temperature tables; concordance with location uncertainty | Concordant reservoir geothermometers may separate deep-fluid conduit systems from ordinary springs and locate structures absent from fault vectors | H20-4 used thresholded thermal/geochemical points; H21-2 would test cross-indicator agreement and uncertainty-aware filtering. Exact units/fields need audit. | **Subjective prior:** `+0.000–0.003`; medium cost. Official GDR page and CI download evidence exist; local chemistry schemas still need review. |
| 2 | **H21-3: persistent Landsat alteration lineaments** (proposed) | Landsat Collection 2 Level-2 SR_B2–SR_B7, QA_PIXEL, vegetation mask; multi-date iron/clay ratios with terrain controls | Hydrothermal alteration may mark fault-hosted fluid pathways; albedo, shadows, transported minerals and illumination are confounders | Adds visible/NIR/SWIR spectral evidence distinct from existing GeoDAWN radiometric and DEM channels | **Subjective prior:** `+0.000–0.004`; high cost. USGS product is no-cost; scene coverage/quality not checked. |
| 3 | **H21-4: structurally perturbed drainage** (proposed) | USGS 3DHP flowlines/catchments, conditioned 3DEP DEM, independent scarp/relief channels; aligned offsets/deflections/knickpoints | Fault movement may deflect channels where the trace is subtle; lithology, roads, drainage capture and DEM artifacts can mimic it | H17-2 parked a drainage idea; this is a specific hydrology-conditioned operator, not another generic DEM blend | **Subjective prior:** `+0.000–0.003`; high cost. USGS 3DHP is public, but local regional product completeness must be checked before reliance. |
| 4 | **H21-1: multi-scale earthquake-intensity lineations** (tested once; rejected by both proxy gates) | Band 16 `ieq_n100a15`; fixed Hessian ridge transform at 200/400/800 m, ridge-NMS, 2.5% budget | Seismicity clusters could reflect active/re-activated structures, but broad/induced clusters confound the relationship | H16-5 uses scalar seismic intensity; this test isolated multi-scale line geometry. A related H17-3 idea was already parked, so novelty is implementation here, not first proposal | **Computed proxy result:** Dense/Sparse `0.06207 / 0.02511` vs reproduced H16-1 `0.21269 / 0.08554`; raw scalar control `0.07977 / 0.02849`. Both gates failed. No tuning or slot recommendation. |

**Submission decision:** no candidate is recommended. Any next candidate needs a frozen protocol, exact input provenance, a spatially blocked comparison against the reproducible current best, and a passing preregistered gate. Even a proxy pass is not hidden-fault validation. The H21-1 report records the transform/input hashes and both failed comparisons at [`evidence/h21_seismic_ridge_holdout.json`](evidence/h21_seismic_ridge_holdout.json).

### Official external data availability checked before proposals

- [USGS ANSS/ComCat documentation](https://earthquake.usgs.gov/data/comcat/index.php): documents catalogue/API access; no new catalog download was used for H21-1 because the official competition raster already contains an earthquake-intensity layer.
- [USGS Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-collection-2): USGS states surface-reflectance products are available at no cost. Scene-level availability/quality for a chosen footprint/date is still to be checked before H21-3 is executed.
- [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program) and [data.gov downloadable collection](https://catalog.data.gov/dataset/usgs-3d-hydrography-program-3dhp-downloadable-data-collection): public/non-proprietary; confirm regional product completeness before H21-4 is relied upon. USGS notes the National Hydrography Dataset was retired in 2023 and is no longer maintained.
- [OpenEI GDR 1391](https://gdr.openei.org/submissions/1391), [DOI 10.15121/1881483](https://doi.org/10.15121/1881483): the recorded CI run fetched the official `wellspringdata.gdb.zip` (20,810,222 bytes; SHA-256 in [`evidence/ci/external_verification.json`](evidence/ci/external_verification.json)) and extracted named chemistry/temperature fields. The GDR landing page returned HTTP 502 during this audit, and raw GDB is not in this checkout; recheck the direct download, units, missingness and sampling/location biases before implementing H21-2.
- Geological rationale is not proof of score lift. See [Faulds & Hinz, OSTI](https://www.osti.gov/servlets/purl/1724082) for geothermal structural settings; [Gomberg (1991), USGS](https://www.usgs.gov/publications/seismicity-and-shear-strain-southern-great-basin-nevada-and-california) for Southern Great Basin seismicity; and the [USGS Pahute Mesa lineament/earthquake compilation](https://pubs.usgs.gov/of/1996/0262/report.pdf), which includes induced-seismicity caveats.

## Submission downloads and upload guide

The static-site builder at [`docs/index.html`](docs/index.html) and [`docs/executive_summary.html`](docs/executive_summary.html) makes the existing H20 raster files easy to download, copies their unique filename and pasteable note, and runs client-side GeoTIFF pre-flight checks. It is a **packager/browser checker**, not a model trainer or a candidate recommender. Existing files pass the recorded format checks: one float32 band, EPSG:32611, 3292×3730 grid, template geotransform, finite values in `[0,1]` over the 5,167,373-cell footprint; the official outside-footprint convention is NaN/null. This does not prove a hidden-fault score or reproduce the server's historical range error.

- Use the Executive Summary page for the step-by-step DrivenData upload flow.
- The generated `-nan.tif` is the format-compliant artifact. The optional all-finite twin uses zeros outside the footprint and is **not** the official outside-footprint convention; do not prefer it unless a validator explicitly requires it.
- The builder provides file names, notes and SHA-256 values. They are formatting metadata, not an endorsement to upload.
- Current official rules allow up to three submissions per rolling 7-day window; never spend a slot on an unvalidated or duplicate-effective file.

## Persistent project charter — re-read every turn

### Arena AI Core Values

1. **Maximize P(Win):** prioritize work that can improve the competition metric and do not optimize a convenient proxy as if it were the target. Protect submission slots; require evidence before promotion.
2. **Own the Outcome:** verify inputs, code, claims and deliverables; report uncertainties and failures; do not disguise a failed or irreproducible result as success.

### Durable task requirements

- Preserve the original standard: “Work line by line verifying from official verified trusted sources.” Verify claims against official/trusted sources and computed artifacts; link sources for manual review and flag irregularities. Do not invent facts.
- The methodological literature reference includes Kiryo, Niu, du Plessis, & Sugiyama's (NeurIPS 2017) non-negative PU risk estimator; cite it for the estimator only, not as validation of the prior or competition performance.
- Work autonomously; do not require manual input.
- Maintain 3–5 distinct, non-cosmetic geological hypotheses with named layers, physical transform/signature, catalogue-gap rationale, novelty relative to actually tested repo work, expected-gain estimate labeled as estimate, and implementation cost.
- Before testing a leading hypothesis, preregister it; then run a spatially blocked evaluation. Do not recommend a slot unless it beats the reproducible current holdout best. A proxy-gate pass must not be represented as hidden-fault validation.
- Verify official free external data availability before relying on it; record whether availability is only documented or the actual files/coverage were downloaded and checked.
- Keep an easy download path for a single-band GeoTIFF with footprint values in `[0,1]`, unique filename, pasteable note, and Executive Summary upload guide. Do not label a file “recommended” without a valid score comparison.
- Use separate implementation, review/fix, and final-audit passes. Preserve the charter in this README. Create a PR from the session branch; merge only when checks and repository permissions allow.

This charter summarizes the user's original project request and the corrections discovered during review; the current actionable acceptance criteria are recorded here so stale starting values are not repeated.

## Reproduction and review commands

```bash
# Use the repository virtual environment; large inputs remain outside Git.
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/profile_features.py
.venv/bin/python scripts/forensic_audit.py

# H21-1 has already run once and failed both proxy gates; the evaluator refuses an accidental rerun.
.venv/bin/python scripts/evaluate_h21_seismic_ridge.py --help

# H16 historical baseline training/OOF run is CPU-intensive; it is not hidden-fault validation.
.venv/bin/python scripts/run_spatial_holdout_and_build.py

# Retired H20 entry points are compatibility notices; they do not train, evaluate, or write artifacts.
.venv/bin/python scripts/evaluate_h19_and_build_submissions.py --status

.venv/bin/python scripts/build_site.py
.venv/bin/python scripts/check_site.py
.venv/bin/python -m pytest -q
```

## Trusted source and audit registry

The machine-readable audit currently contains **58 sourced claims, 34 flags** (including resolved and mitigated items); counts are enforced against both registries in tests. `docs/audit.html` distinguishes source/computation status and highlights open issues.

- [Source verification and irregularity ledger](docs/audit.html)
- [`registry/sources.json`](registry/sources.json) — source, claim, method of verification and status
- [`registry/irregularities.json`](registry/irregularities.json) — open, resolved and mitigated flags
- [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md) — ranked candidate hypotheses and evidence status
- [`docs/research/preregistration_h21.md`](docs/research/preregistration_h21.md) — frozen H21-1 test protocol
- [Competition rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) — automatic site access is prohibited

## Review protocol for future changes

1. Read this README, `AGENTS.md`, open irregularities, and the active preregistration before changing model/site claims.
2. Inspect `git status` and `git diff`; do not assume prior builds were clean.
3. Reproduce the relevant test/metric from a clean output path and keep proxy truth separated from independent ground truth.
4. Update code, evidence, source registry and site copy together; rebuild pages only after correcting the generator.
5. Run tests, `git diff --check`, a rendered-site audit, and a final claim-by-claim source review. Do not overwrite historical evidence without keeping an auditable copy.
6. Work only on `arena/01a0f501-20gemsdoe`; create a PR from that branch and never claim that a merge occurred unless GitHub confirms it.
