# Knowledge base — verified facts for the DOE GEMS Prize (2026-09-30)

Every statement is tagged **OBSERVED** (read from the linked source), **COMPUTED** (calculated from files in this repo) or **INFERENCE** (reasoning). Unknowns are listed in Section 6. The full claim-by-claim audit table is on the [Audit page](audit.html). Reuse this page as the starting point for other fault-detection projects.

## 1. The task in one page

* **OBSERVED.** Predict faults in the GeoDAWN region (Nevada/California) as a probability raster; public known faults are incomplete; scoring uses new faults labelled by NLR/USGS experts. [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
* **OBSERVED.** Grid: EPSG:32611, 100 m, 3,292 × 3,730 pixels, origin (243350, 4508550); footprint = {{footprint_px}} pixels. Outside the footprint the file must be null/NaN.
* **OBSERVED.** Metric: `DTI = TP_w / (TP_w + α·FP_w + β·FN_w + ε)`, α = 0.2, β = 0.8, triangular kernel, R = 300 m (3 px).
* **OBSERVED.** Known-fault pixels are masked pixel-exactly and only new faults are scored ([staff ruling](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4)).
* **OBSERVED.** Deadline **Dec 3, 2026 23:59 UTC**; up to three uploads per rolling week; one final submission per entity; Phase 1 $50,000, Phase 2 $250,000 ([home](https://www.drivendata.org/competitions/306/competition-doe-gems/), [rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).

### What drives the score (COMPUTED from the published formula)
Because `FN_w = G − TP_w` (G = number of scored ground-truth pixels) and α + β = 1:

`DTI = TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·G)`

1. While false-positive mass is small next to G, DTI ≈ `TP_w / (0.8·G)`: **the score is recall-dominated.**
2. Adding a pixel raises DTI only if its expected TP gain per unit of FP mass exceeds `τ = α·DTI / (1 − α·DTI)`: τ = {{tau_156}} at DTI 0.1563 and τ = {{tau_317}} at 0.3168. **INFERENCE:** this is consistent with thick, low-precision blobs failing (GEMSDOE4's thick union blobs scored 0.0343) and with modest pixel budgets working better, but the score history alone does not prove it.
3. **Exact lower bound.** Even with zero false-positive mass, reaching a score *s* needs kernel-weighted recall `TP_w / G ≥ 0.8·s / (1 − 0.2·s)`: at least **{{tmin_156}} %** of G for 0.1563 and **{{tmin_317}} %** of G for the leader's 0.3168. False positives raise both requirements. Illustration, not a measurement: recall 0.35·G with FP mass 1.17·G gives 0.3168.

## 2. Data we hold, and where each piece comes from

| File | What it is | Provenance status |
|---|---|---|
| `training_features.tif` (19 bands, float32, 418,912,844 B) | GeoDAWN + INGENIOUS layers at 100 m | Bridged from the team's public GitHub (SHA-256 pinned); DrivenData's own copy is login-gated, so **not independently compared** |
| `labels.tif` | rasterised known faults (int8; 1 fault, 0 none, −1 outside) | **Independently verified:** {{labels_exact_pct}} % of pixels reproduced from the official GDR INGENIOUS fault shapefiles (Audit flag F04) |
| `sample_submission.tif` | grid template; finite footprint {{footprint_px}} px | Footprint verified (= labels footprint; area within 0.4 % of the USGS GeoDAWN area). **Values are not all zero** (flag F02) |
| external stacks (lidar scarp, radiometric K/Th/U/TC, extensions, 13 DEM10 channels) | derived by earlier group repos from USGS 3DEP and GeoDAWN | hash-pinned bridge copies; upstream products are public domain (3DEP) / CC0 (GeoDAWN) |

### The 19 feature layers (COMPUTED from the file's own tags and footprint statistics)
{{layers_table}}

**Flag F01:** band 6 `tc` is labelled "tilt angle" in the file but behaves as radiometric **total count** (r = {{tc_corr_ext}} with the USGS GeoDAWN TC channel; r = {{tc_corr_tilt}} with a computed magnetic tilt). **Flag F05:** every band has {{invalid_min}}–{{invalid_max}} invalid pixels *inside* the footprint.

## 3. Geology that matters for fault discovery (OBSERVED unless marked)

* Most Great Basin hydrothermal systems are fault-controlled; faults can also be barriers ([Hermant et al. 2025](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf), the paper the DrivenData About page cites).
* Structural settings of 426 known systems (≥ 37 °C): step-overs/relay ramps ~32 %, normal-fault terminations ~25 %; ~39 % are blind; estimates suggest up to ~75 % of resources are blind ([Faulds & Hinz 2015](https://www.osti.gov/servlets/purl/1724082)). Step-overs, terminations, intersections and accommodation zones are long-term critically stressed areas where fluid pathways stay open ([OSTI dataset 1148722](https://www.osti.gov/dataexplorer/biblio/dataset/1148722)).
* Fault intersections and terminations identify upflow locations along faults ([Siler et al. 2019](https://pubs.usgs.gov/publication/70202167)).
* Most northern-Nevada hot springs lie on basin flanks along Basin and Range faults, some in inner basins ([Hose & Taylor 1974](https://www.usgs.gov/publications/geothermal-systems-northern-nevada)).
* A ~15 km left-step between range-front fault systems contains numerous ENE-striking intra-basin faults ([USGS, Argenta Rise](https://www.usgs.gov/publications/geophysical-modeling-a-possible-blind-geothermal-system-near-battle-mountain-nv)).
* USGS Quaternary faults can sit up to ~400 m from lidar-based labels; database density varies with the source map (Hermant et al. 2025).
* **COMPUTED.** Of {{n_springs}} GDR spring features in the footprint, {{springs_near_pct}} % lie within 1 km of a catalogued fault (random footprint pixels: {{random_near_pct}} %) and {{springs_far_pct}} % lie beyond 3 km.
* **GeoDAWN acquisition (OBSERVED).** Area 2 (most of the extent) used 400 m east–west flight lines and 4,000 m north–south tie lines at 150–200 m terrain clearance ([USGS](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)). **INFERENCE:** cross-line resolution is coarse, so east–west lineaments in magnetic derivatives may be acquisition artefacts.

## 4. Methods & Statistical Learning Knowledge (`20GEMSDOE`)

* **OBSERVED.** The organizers' reference solution is a U-Net with Tversky loss (α 0.2, β 0.8) on 128-pixel patches with Monte-Carlo splits; it zero-fills NaN features ([repo](https://github.com/drivendataorg/gems-prize-reference-solution)).
* **OBSERVED.** The group's earlier baseline live score (`0.1563`) was a binary, thinned mask from an 11-model CNN ensemble (U-Net++, DeepLabV3+, U-Net, ResNet-34), followed by `16GEMSDOE` (`0.1855`, account `extradr19`) and `19GEMSDOE-H19-4` (`0.1894`, account `smrtdoog5`).
* **COMPUTED.** **Positive-Unlabeled (PU) Reframing (`20GEMSDOE`):** In `existing_faults.tif` (`labels.tif`), `s = 1` (`60,988` pixels, $\pi_P = 0.011803$) is positive, while `s = 0` (`5,106,385` pixels) is **unlabeled**, containing `~126,599` unmapped fault pixels ($\pi_{\text{hidden}} = 0.024500$) under power-law length-frequency scaling ($N(\ge L) = C L^{-1.762}, R^2 = 0.9936$ above $L_{\min} = 1,650\text{ m}$), giving total true fault class prior $\pi = 0.036303$ and overall labeling frequency $c = \pi_P / \pi = 0.3251$ ($c(L < 1,650\text{ m}) = 0.0678$).
* **COMPUTED.** **Kiryo et al. (NeurIPS 2017) Non-Negative PU (`SAR-nnPU`) Risk Estimator:** Training with non-negative PU risk $\tilde{R}_{\text{nnPU}}(g) = \pi \hat{R}_P^+(g) + \max(0, \hat{R}_U^-(g) - \pi \hat{R}_P^-(g))$ and length-dependent SAR propensity weights raises out-of-fold AUC across all 5 physical expert arms (e.g. Topographic Openness + LRM OOF AUC rises from `0.8763` under naive PN to `0.8806` under SAR-nnPU) and lifts 4-quadrant holdout DTI to **0.21442 Dense / 0.08696 Sparse** (`H20-1`) and **0.21314 Dense / 0.08792 Sparse** (`H20-5`) vs `H16-1` ({{h16_dense}} Dense).
* **COMPUTED.** **Murphy (1973) Brier-Score Decomposition & Out-of-Fold Calibration:** On $N = 466,731$ held-out candidate ridge pixels, Out-of-Fold PU-Isotonic calibration reduces Murphy Reliability error $\text{REL}$ by **99.3%** (`0.019674` $\to$ `0.000143`) and ECE by **96.9%** (`0.132771` $\to$ `0.004050`). In the `[0.65, 0.75)` stated-0.70 probability bin ($N = 16,455$), mean predicted probability is `0.6896` vs true empirical hit rate `0.6714` (`bias = -0.0183`).
* **COMPUTED.** On the four-quadrant holdout: geophysics-only arms reach dense ≈ 0.16, while arms that add 1 m lidar / 10 m DEM scarp features reach ≈ 0.20; blending them with SAR-nnPU and Novel Physical Hypotheses (`H20-1`..`H20-5`) clears both Holm-Bonferroni multiple-testing correction on 16 Dev sub-blocks ($p_{\text{Holm}} = 0.00311$ Dense, $0.00257$ Sparse) and the single-shot 20% Vault Holdout (`+0.00059` Dense, `+0.00086` Sparse).

## 5. Compliance checklist (OBSERVED)

* DrivenData Terms of Use forbid robots/spiders and say accounts are personal ([ToU](https://www.drivendata.org/termsofuse/)) — therefore **no automated leaderboard/forum scraping** here.
* Rules require disclosure of generative-AI use and one final submission per entity ([rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
* External data must be licensed for use and sharing with the sponsor ([page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#external-datasets)).

## 6. Unknowns (do not treat as facts)

* What data and fault types the new test faults come from (the organizers decline to say).
* How the public/private split is drawn (page 967 says the region is "chunked"; the rules say labels are divided). 
* The exact server-side file checker behind "Predicted values must be in range [0, 1]" (not public).
* Whether the bridged `sample_submission.tif` equals the data-tab file (login-gated).
* Whether geologic-map, thermal-conduit or step-overs faults are present in the test labels.
