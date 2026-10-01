# 20GEMSDOE — DOE GEMS fault-mapping research

[![DrivenData DOE GEMS #306](https://img.shields.io/badge/DrivenData-DOE_GEMS_%23306-0f766e)](https://www.drivendata.org/competitions/306/competition-doe-gems/)
[![Current public leader](https://img.shields.io/badge/Public_leader-DARD_0.3168-1d4ed8)](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

**Project status as of 2026-10-01:** research artifacts and the submission-page packaging flow are present. No 20GEMSDOE candidate is recommended for a weekly submission. Two preregistered single-shot tests are now complete and both are rejected as submission candidates: H21-1 (multi-scale seismic ridges; Dense `0.06207` / Sparse `0.02511`) and H21-2 (multi-geothermometer coherence; Dense `0.03244` / Sparse `0.01388`), each far below the reproduced H16-1 comparator (Dense `0.21269` / Sparse `0.08554`). H20 holdout values remain unreproduced historical reports, and the former “hidden-fault calibration” used a synthetic target, not hidden-fault evidence. The full competition raster stack was re-verified this session from the hash-pinned GitHub bridge (all SHA-256 matches) and H21-2 was executed end-to-end on it; the USGS-derived external DEM stack needed by the legacy H16/H20 feature pipeline is not restorable in this sandbox (flag F38).

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

- The repository's working inputs live in ignored local `data/` (a symlink to `.cache/gems_data` here). All 13 10 m DEM channels were verified and `prepare_data.py` completed **in an earlier session on an unrestricted machine**. On 2026-10-01 the three core competition rasters were restored in this sandbox from the hash-pinned GitHub bridge; every part and the reassembled feature stack matched the manifest SHA-256 pins exactly (`4371c82e…3123bc5` features, `7ba308cc…9e4093` labels, `2176d08e…4d35cbc` template). The USGS-derived external DEM stack (needed by `scripts/prepare_data.py` and the H16/H20 feature pipeline) cannot be fetched from this sandbox (flag F38); `prepare_data.py` therefore cannot complete here, but the metric/holdout/submission code and the H21-2 evaluation run fully against the restored core rasters.
- The reported 19-band feature stack (`3292×3730`, EPSG:32611, 100 m cells, geotransform identical to the template) was re-read and band-name-verified against its own metadata this session.
- The current core competition rasters were recovered from hash-pinned team GitHub bridge copies. Their local SHA-256 values are recorded and checked, and the labels raster was compared with the public GDR fault vectors. **The files were not independently downloaded from or byte-compared with DrivenData's login-gated competition archive in this session.** Hash integrity is not the same as official-host provenance.
- Band 6's `tc` tag is inconsistent with its behaviour: its correlation with the external GeoDAWN `TC` channel is 0.9971, versus 0.0128 with computed magnetic tilt. Do not describe this layer as a validated tilt feature without resolving the discrepancy; see [F01](docs/audit.html#F01) and [`evidence/feature_profile.json`](evidence/feature_profile.json).
- The OOF files needed by the former H20 workflow are absent. `evaluate_h19_and_build_submissions.py` and its H20 wrappers are now retired compatibility notices that perform no training, evaluation, packaging, or file writes. No H20 reproduction is claimed.
- The automated leaderboard/forum feed requested in the project brief is intentionally not implemented: DrivenData's Terms of Use prohibit robots/spiders or other automatic website access. Use the dated manual snapshot above; do not poll or scrape the site.

### H20 results and calibration: required corrections

`evidence/spatial_holdout_results.json` records H20-1 mean Dense/Sparse DTI `0.21442 / 0.08696` and H20-5 `0.21314 / 0.08792`. Treat these only as **reported historical results**: they use spatially held-out portions of the known-fault catalogue, with a synthetic 20%-component sparse proxy—not independent hidden-fault labels—and they have not been reproduced. The shared spatial slice was evaluated for at least two H20 candidates, so it is not an untouched single-shot gate. The 20GEMSDOE calibration report constructed its outcome as `s_hit | Bernoulli(p_hidden_u)` from catalogue/SGMC proximity and a chosen prior; its bin rates and Brier/REL/ECE therefore describe a **synthetic target**, not observed hidden ground truth.

A fresh H16-1 known-catalogue baseline was reproduced on 2026-10-01 at Dense/Sparse `0.21269 / 0.08554`; see [`evidence/spatial_holdout_h16_results.json`](evidence/spatial_holdout_h16_results.json). The frozen H21-1 transform scored `0.06207 / 0.02511` (raw scalar control `0.07977 / 0.02849`) and failed both required comparator gates. The frozen H21-2 multi-geothermometer-coherence transform scored `0.03244 / 0.01388` and likewise failed both gates; its coherence-selected field even lost to the unselected thermal-point control (`0.03857`), and all descriptive point-anomaly controls remained below the pure catalogue-proximity transfer ceiling (`0.04190`). These are negative spatial-transfer proxy results, not proof about hidden-fault performance; they rule out weekly submission recommendations for H21-1 and H21-2 under the preregistered criteria.

A separate exploratory rank-correlation scan across 19 archived scored rasters found Spearman ρ `-0.05` for the known-catalogue Dense proxy (p=`0.8473`) and `+0.44` for the SGMC-gap proxy (p=`0.0615`). These uncorrected associations are hypothesis-generating only; the reported feature scan has nothing significant after Bonferroni correction (smallest listed p=`0.0059`, threshold=`0.00098`). See [`evidence/proxy_calibration_vs_lb.json`](evidence/proxy_calibration_vs_lb.json) and [`evidence/lb_signal_attribution.json`](evidence/lb_signal_attribution.json).

Consequently, no stored H20 metric, Holm p-value, Vault result, proxy comparison, or calibration number is represented here as independent confirmation of leaderboard performance. See flags F17 and F25–F29 in [`registry/irregularities.json`](registry/irregularities.json).

## Candidate research — H22 register

Four untested, materially different ideas plus two completed preregistered single-shot tests are in [`docs/research/hypothesis_register.md`](docs/research/hypothesis_register.md). The ranges for **untested** hypotheses below are subjective planning priors, not measured effects. Completed tests are reported separately and are not presented as expected-gain estimates.

| Rank | Hypothesis | Named layers and physical transform | Catalogue-gap rationale | Difference from existing work | Planning expectation / cost / status |
|---|---|---|---|---|---|
| 1 | **H22-2: magnetic hydrothermal-destruction low lineaments** (proposed; next preregistration candidate) | Band 2 `rtp` (cross-check band 1 `mag_anom`, band 14 `tmi`); H21-1's frozen Hessian machinery applied to the *negative* field — linear magnetic **lows** | Sustained upflow can destroy magnetite along faults, producing linear lows that need not coincide with mapped traces, including blind/covered settings | Prior work uses magnetic *edges/gradients* as positive ridge evidence; a trough lineament transform is the opposite polarity and a different physical process. Low cost: inputs local, protocol pattern exists. Caution: family-adjacent 15GEMSDOE `conj_alteration_mag` scored `0.0782`. | **Subjective prior:** `+0.000–0.003`; low cost. No new data needed. |
| 2 | **H21-3: persistent Landsat alteration lineaments** (proposed) | Landsat Collection 2 Level-2 SR_B2–SR_B7, QA_PIXEL, vegetation mask; multi-date iron/clay ratios with terrain controls | Hydrothermal alteration may mark fault-hosted fluid pathways; albedo, shadows, transported minerals and illumination are confounders | Adds visible/NIR/SWIR spectral evidence distinct from existing GeoDAWN radiometric and DEM channels | **Subjective prior:** `+0.000–0.004`; high cost. USGS product is no-cost; scene coverage/quality not checked. |
| 3 | **H21-4: structurally perturbed drainage** (proposed) | USGS 3DHP flowlines/catchments, conditioned 3DEP DEM, independent scarp/relief channels; aligned offsets/deflections/knickpoints | Fault movement may deflect channels where the trace is subtle; lithology, roads, drainage capture and DEM artifacts can mimic it | H17-2 parked a drainage idea; this is a specific hydrology-conditioned operator, not another generic DEM blend | **Subjective prior:** `+0.000–0.003`; high cost. USGS 3DHP is public, but local regional product completeness must be checked before reliance. |
| 4 | **H22-1: Quaternary vent-alignment structural control** (proposed) | Committed `evidence/ci/gdr_volcanic_vents_in_footprint.csv` (21 vents) vs `gdr_qfaults_traces.csv`; ≥3-vent collinear alignments, proximity field | Aligned vents may trace feeder fractures tapping deep permeability, unmapped at catalogue scale; tiny sample limits power | No prior artifact used vent geometry as lineament evidence | **Subjective prior:** `+0.000–0.002`; low cost. Data already CI-fetched and hash-pinned. |
| — | **H21-2: multi-geothermometer coherence** (**tested once; rejected by both proxy gates**) | GDR 1391 spring/well chemistry; ≥2 concordant quartz/chalcedony/cation estimators ≥ 120 °C, agreement-weighted 500 m kernels (67 eligible cells) | Concordant reservoir geothermometers may mark fault-controlled upflow conduits absent from the catalogue | First test of cross-indicator agreement; H20-4 used unselected thresholded thermal points | **Computed proxy result:** Dense/Sparse `0.03244 / 0.01388` vs reproduced H16-1 `0.21269 / 0.08554`; unselected thermal-point control `0.03857`, seeded random control `0.02901`, catalogue-proximity ceiling `0.04190`. Both gates failed; no retuning. See [`evidence/h21_2_geotherm_coherence_holdout.json`](evidence/h21_2_geotherm_coherence_holdout.json) and [`docs/research/preregistration_h21_2.md`](docs/research/preregistration_h21_2.md). |
| — | **H21-1: multi-scale earthquake-intensity lineations** (tested once; rejected by both proxy gates) | Band 16 `ieq_n100a15`; fixed Hessian ridge transform at 200/400/800 m, ridge-NMS, 2.5% budget | Seismicity clusters could reflect active/re-activated structures, but broad/induced clusters confound the relationship | H16-5 uses scalar seismic intensity; this test isolated multi-scale line geometry | **Computed proxy result:** Dense/Sparse `0.06207 / 0.02511`; raw scalar control `0.07977 / 0.02849`. Both gates failed. No tuning or slot recommendation. |

**Submission decision:** no candidate is recommended. Any next candidate needs a frozen protocol, exact input provenance, a spatially blocked comparison against the reproducible current best, and a passing preregistered gate. Even a proxy pass is not hidden-fault validation. The H21-1 report records the transform/input hashes and both failed comparisons at [`evidence/h21_seismic_ridge_holdout.json`](evidence/h21_seismic_ridge_holdout.json). **Cross-test observation (inference, not proof):** both preregistered single-mechanism tests lost to the H16-1 multi-feature ridge synthesis by wide margins, and pure catalogue proximity yields only ~`0.042` mean Dense on this protocol — weakening the family of sparse point/line co-occurrence hypotheses and favouring multi-feature composed surfaces.

### Official external data availability checked before proposals

- [USGS ANSS/ComCat documentation](https://earthquake.usgs.gov/data/comcat/index.php): documents catalogue/API access; no new catalog download was used for H21-1 because the official competition raster already contains an earthquake-intensity layer.
- [USGS Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-collection-2): USGS states surface-reflectance products are available at no cost. Scene-level availability/quality for a chosen footprint/date is still to be checked before H21-3 is executed.
- [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program) and [data.gov downloadable collection](https://catalog.data.gov/dataset/usgs-3d-hydrography-program-3dhp-downloadable-data-collection): public/non-proprietary; confirm regional product completeness before H21-4 is relied upon. USGS notes the National Hydrography Dataset was retired in 2023 and is no longer maintained.
- [OpenEI GDR 1391](https://gdr.openei.org/submissions/1391), [DOI 10.15121/1881483](https://doi.org/10.15121/1881483): the recorded CI run fetched the official `wellspringdata.gdb.zip` (20,810,222 bytes; SHA-256 in [`evidence/ci/external_verification.json`](evidence/ci/external_verification.json)) and extracted named chemistry/temperature fields to the committed `evidence/ci/gdr_wellspring_in_footprint.csv`. The schema/units/missingness/bias audit demanded before feature construction is now complete ([`evidence/h21_2_wellspring_audit.json`](evidence/h21_2_wellspring_audit.json)), and H21-2 was evaluated once under its preregistration and rejected (S60). Recheck the direct download if a future idea needs the raw GDB; the GDR landing page had returned HTTP 502 during the earlier audit window.
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

## Next steps and current limitations

**Next session's queue (in order):**

1. **Preregister and run H22-2** (magnetic hydrothermal-destruction low lineaments on band 2 `rtp`). Data is local; the H21 evaluator pattern exists; this is the cheapest remaining mechanism-distinct test. Commit the preregistration first, push, run once, report regardless of outcome, reject without retuning on failure.
2. **Re-run the full H16/H20 feature pipeline on an unrestricted machine** to clear flag F38: fetch the USGS 3DEP stack with `scripts/fetch_dem10.py`, then `scripts/prepare_data.py` and `scripts/run_spatial_holdout_and_build.py`, and byte-compare the three core rasters against a logged-in DrivenData download to upgrade bridge provenance to official-host provenance.
3. **If any candidate ever passes both proxy gates**: separately reviewed packaging with `gems.forensics.gate_candidate` uniqueness proof, `gems.submission.check_variants`, unique filename + note, and an owner decision on slot spend (3 per rolling 7 days). Never two duplicate-effective files.
4. **H22-1 vent alignment / H21-3 Landsat / H21-4 3DHP** remain proposed, in register order after H22-2; each requires its own preregistration and (for Landsat/3DHP) a footprint coverage/quality check via the CI workflow first.
5. **Manually refresh the leaderboard snapshot** (no automation — DrivenData ToU) and record any new group scores with `scripts/record_score.py`.

**Standing limitations (workarounds noted):**

- **No DrivenData login in the agent environment; no official-archive byte comparison yet** (hash-pinned GitHub bridge is the current provenance chain).
- **No USGS/GDR egress from the dev sandbox** — external data enters through the GitHub Actions CI workflow (`scripts/ci_external_verify.py`) with recorded SHA-256s; the dev sandbox reaches GitHub only.
- **No GPU in this sandbox** — heavy model training cannot run here; transform-based proxy tests (H21/H22 style) are fully runnable on CPU.
- **Known-catalogue proxies only** — no measurement can predict hidden-fault leaderboard scores; two preregistered hypotheses already failed even the proxy. Leaderboard reality checks remain the owner's manual submissions.
- **The `[0, 1]` server-rejection root cause is unproven** (F31): the historical rejected file is unavailable; current downloads pass every local check including the repo's `check_variants` gate.

## Reproduction and review commands

```bash
# Use the repository virtual environment; large inputs remain outside Git.
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/profile_features.py
.venv/bin/python scripts/forensic_audit.py

# H21-1 has already run once and failed both proxy gates; the evaluator refuses an accidental rerun.
.venv/bin/python scripts/evaluate_h21_seismic_ridge.py --help

# H21-2 schema audit is rerunnable (no outcome data); the evaluator has run once, failed both gates, and refuses an accidental rerun.
.venv/bin/python scripts/audit_h21_2_wellspring_data.py
.venv/bin/python scripts/evaluate_h21_2_geotherm_coherence.py --help

# H16 historical baseline training/OOF run is CPU-intensive; it is not hidden-fault validation.
.venv/bin/python scripts/run_spatial_holdout_and_build.py

# Retired H20 entry points are compatibility notices; they do not train, evaluate, or write artifacts.
.venv/bin/python scripts/evaluate_h19_and_build_submissions.py --status

.venv/bin/python scripts/build_site.py
.venv/bin/python scripts/check_site.py
.venv/bin/python -m pytest -q
```

## Trusted source and audit registry

The machine-readable audit currently contains **60 sourced claims, 38 flags** (including resolved and mitigated items); counts are enforced against both registries in tests. `docs/audit.html` distinguishes source/computation status and highlights open issues.

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
6. Work only on the session branch assigned by the platform (this session: `arena/01a0f564-20gemsdoe`; earlier text mistakenly named the previous session's branch — see flag F36); create a PR from that branch and never claim that a merge occurred unless GitHub confirms it.

## Original request (verbatim) — re-read at the start of every session

The text below is the project brief exactly as received (2026-10-01 session). It is stored verbatim per the brief's own instruction ("Put this prompt into the repo readme and read it everytime we work on the project"). Dated facts inside it (scores, leaderboard values, file states) reflect the moment it was written; the *Status* section at the top of this README supersedes stale values.

~~~~text
Review the repo.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Reframe the entire prediction task at the level of its statistical structure, not just its features: because the competition's own confirmed rules state that "new fault" includes any structurally real fault pixel absent from the training catalogue — extensions, splays, and corrections included — every pixel labeled "no fault" in the training raster is not a verified negative, it is an unlabeled pixel that may secretly be a positive the catalogue simply hasn't found yet; formally, this is not an ordinary binary classification problem but a Positive-Unlabeled (PU) learning problem, and training a standard cross-entropy or focal-loss classifier on it silently assumes the unlabeled set is clean, which is provably false by the competition's own premise and is a plausible, testable explanation for why independent attempts across different teams cluster in the same narrow low-score band — a shared statistical blind spot, not a shared skill ceiling. The corrective machinery already exists in the literature: replace the naive risk with an unbiased or non-negative PU risk estimator such as Kiryo, Niu, du Plessis, and Sugiyama's nnPU (NeurIPS 2017), which explicitly reweights the loss for the unknown fraction of hidden positives sitting inside the unlabeled class, rather than punishing the model every time it correctly flags an unmapped fault as faulted; this requires estimating that hidden-positive fraction (the class prior, π), which is where a power-law fault length-frequency extrapolation becomes load-bearing rather than decorative — use the extrapolated undercount of short faults, fit against the known INGENIOUS/USGS trace-length distribution, as a literature-grounded prior on π instead of guessing it or tuning it directly against the leaderboard. Because the metric consumes continuous probabilities rather than a threshold, pair this with a genuine calibration study — a reliability diagram and Brier-score decomposition computed specifically on recovered hidden-fault pixels in the holdout, never on the training distribution — to check whether a stated 0.7 actually behaves like a 70% hit rate on truly novel structure, since PU-contaminated training is expected to bias a naive model toward systematic underconfidence on exactly the pixels this competition pays for. Finally, hold yourself to the standard a dissertation committee would: once multiple sophisticated interventions are being tested against the same holdout — new mechanistic features, the length-frequency prior, the loss function itself — repeated testing inflates the false-discovery rate exactly as uncorrected multiple comparisons would in any other empirical study, so pre-register each hypothesis and its predicted effect before looking, apply an explicit correction rather than quietly keeping the best of many runs, and reserve one final, untouched slice of held-out data that a candidate change must clear exactly once before it is trusted near a submission slot.

Here are the results from our groups submissions, separated by ....:
GEMSDOE1 https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html GEMSDOE SCORE: 0.1563
....
https://buffedlizard55-lab.github.io/6GEMSDOE/ 6GEMSDOE SCORE: 0.0286
....
GEMSDOE3 https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html GEMSDOE3 SCORE: 0.1193 1 · SUBMIT FIRST f347b70daa Pindrop nodes
....
GEMSDOE2 https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html GEMSDOE2 SCORE: 0.1560
....
GEMSDOE3 https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html GEMSDOE3 SCORE: 0.0830 2 · SUBMIT SECOND 37f9d5b855 Pindrop catalogue-gap target SECOND SYSTEM
....
https://buffedlizard55-lab.github.io/GEMSDOE4/ GEMSDOE 4 SCORE: 0.0343
....
GEMSDOE3 https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html GEMSDOE3 SCORE: 0.1152 3 · CONTROL · UPLOAD LAST 4e03fc9705 Pindrop dense ridge control
....
https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html 5GEMSDOE SCORE: 0.1563
....
https://buffedlizard55-lab.github.io/7GEMSDOE/ 7GEMSDOE SCORE: 0.1461
....
https://buffedlizard55-lab.github.io/8GEMSDOE/ 8GEMSDOESCORE: 0.1563
....
https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html 9GEMSDOE SCORE: 0.0107
....
https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html 11GEMSDOE SCORE: 0.0202
....
https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html 12GEMSDOE SCORE: 0.1294 r7-nms3-dem10-scarp_0c9199f14e62
https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html 12GEMSDOE SCORE: 0.1294 r7-nms3-dem10-scarp_0c9199f14e62_allfinite SDCF9
....
https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html 15GEMSDOE SCORE: 0.0782 gems-tso1-20260929T005627Z-conj_alteration_mag smashi34
....
https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html 14GEMSDOE SCORE: 0.0020 smrtdoog5
....
https://buffedlizard55-lab.github.io/GEMSDOE10/ 10GEMSDOE SCORE: h16-continuation: 0.0461; h20-dem10-scarp-thin: 0.0921; H25-ctx-ridge: 0.1280; h28-dotted-ridge: (unscored) wbg1
....
https://buffedlizard55-lab.github.io/13GEMSDOE/ 13GEMSDOE SCORE: (none)
....
https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html 16GEMSDOE SCORE: h16-1-topo-geophys-baseline-ridges: 0.1855; h18-3a, h18-4: (unscored) extradr19
....
https://buffedlizard55-lab.github.io/17GEMSDOE/ 17GEMSDOE SCORE: 0.0187 17GEMSDOE_F-ensemble-2pct_20260930T050626Z
....
https://buffedlizard55-lab.github.io/18GEMSDOE/ 18GEMSDOE SCORE: 0.0297
....
19GEMSDOE SCORE: (none yet) | 20GEMSDOE SCORE: (none yet)
HIGHEST SCORE SO FAR: https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html 16GEMSDOE h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan: 0.1855. The following is the leaderboard for the competition: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ — 0.3049 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website. It should be unique, take unique approaches to generating a submission that can score higher than .3049.

We need to figure out why we keep scoring 0.1563, are we copying the same work over and over again? We need to come up with different ideas, and not just the same idea tried a different way. Need to figure out why 5GEMSDOE and GEMSDOE1 have the same score. We should not be generating the same score submissions, they should all be unique.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above. We need to come up with distinct and unique strategies to score higher in this competition leaderboard. We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents. We should store all of our information and knowledge that we can gather from official verified sources. We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize. So it's important to be contrarian but be smart about it. We need to find sources of data that others are overlooking or areas of the project when it comes to geothermal vents. We need to do deep research and critical thinking and come up with new hypothesis to test.

Core Values (from the Arena AI team): Maximize P(Win) — in every decision, weigh tradeoffs, assess risk, and choose the path that maximizes the probability of winning; set aside emotions and make tough decisions. Own the Outcome — own results end to end, act without waiting for permission, treat failure and success as signals, stay accountable to the final outcome.

The goal: place top of the leaderboard (https://www.drivendata.org/competitions/306/competition-doe-gems/). Understand the problem; collect and organize data into a clean, easily auditable table with official verified links. Guidelines: overview & problem description https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/, resources https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/, data https://www.drivendata.org/competitions/306/competition-doe-gems/data/ (requires login), reference solution https://github.com/drivendataorg/gems-prize-reference-solution, submission rules PDF https://docs.nlr.gov/docs/fy26osti/96647.pdf. Data mirror links (GDR submission https://gdr.openei.org/submissions/1391; Dropbox mirrors for GEMS_96647.pdf, example_submission.tif, existing_faults.tif, gems-geodawn-numerical-features.tif, Digital-elevation-model-links-JSON.pdf) were supplied with the brief; no DrivenData auth is available to the agent.

The site must be able to generate a TIF file as easy as download-to-click for submission into the competition; it must be in the executive summary or the very beginning of the site and obvious on visit. A downloaded file returned the submission-form error "Predicted values must be in range [0, 1]"; the submission page has a File-to-submit control and a Note field ("A short comment to help you or your team tell submissions apart later e.g. clustering with k=25"). Give each submission a unique name and short note. Create an executive summary subpage explaining exactly how to make a submission. Create a GitHub Pages site with clean UI that is organized, clean, user friendly, simple, and includes all relevant information in an easy-to-read format with official verified links.

Work on the next steps from the previous sessions first. Provide suggestions and improvements and implement them. Do your own research, deep research, scientific literature research; organize knowledge; critically think; generate solutions through scientific and free publicly available information; do this autonomously; constantly review and improve. Tell me your limitations and what you need access to. Use free, publicly available, official, verified sources for third-party/external data.

Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input; work on your own to complete tasks. Flag any irregularities for review. No hallucinations. Verify no hallucinations. The goal of this project is to get a full list that follows our requirements. Verify line by line. Run tasks through multiple passes: Pass 1 implement completely and verify; Pass 2 review for bugs, missing requirements, incorrect assumptions, edge cases and fix everything; Pass 3 re-check the entire implementation against the original request, improve accuracy/reliability/completeness/code quality, fix remaining issues. Do not stop after the first pass; each pass builds on the previous; verify the final result fully satisfies the original request.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations in the way of a successful project; it should be worked on in the next session.
~~~~

**Latest consolidation (2026-10-01):** every actionable criterion above is mapped to a repository artifact in the *Start here* and *Candidate research* sections at the top of this README; when the brief and older site copy disagree, the top-of-file *Status* section and `registry/` are authoritative.
