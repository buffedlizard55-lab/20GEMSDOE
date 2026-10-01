#!/usr/bin/env python3
"""Fit official-vector length-frequency PRIOR SCENARIOS without leaderboard tuning.

Goodness-of-fit and bootstrap diagnostics concern the assumed length model only;
they do not reveal hidden-fault prevalence or validate catalogue completeness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.paths import DATA_DIR, EVIDENCE_DIR  # noqa: E402
from gems.pu_learning import estimate_power_law_class_prior, extract_skeleton_trace_lengths_m  # noqa: E402
from gems.research_gate import utc_now  # noqa: E402
from gems.validator import sha256_file  # noqa: E402

TRACE_PATH = EVIDENCE_DIR / "ci/gdr_qfaults_traces.csv"
TRACE_SHA = "9702f2e5c382a4f472ae834d22b94990983b059677a37adfafd51c50f75e643c"
CUTOFFS = (1500.0, 1650.0, 2000.0, 2500.0, 3000.0)
PRIMARY = 1650.0


def pareto_tail_fit(lengths, cutoff):
    t = np.sort(np.asarray(lengths, float)[np.asarray(lengths) >= cutoff])
    if len(t) < 8 or np.log(t/cutoff).sum() <= 0:
        raise ValueError("insufficient tail")
    a = len(t) / np.log(t/cutoff).sum()
    fitted = 1-(t/cutoff)**(-a)
    ks = max(np.abs(fitted-np.arange(len(t))/len(t)).max(),
             np.abs(fitted-np.arange(1,len(t)+1)/len(t)).max())
    return float(a), float(ks), len(t)


def tail_bootstrap(lengths, cutoff, *, n=399, seed=20261001):
    """Parametric KS reference refits alpha in every replicate (fixed cutoff).

    Valid p-values require independent Pareto samples; geological segments are
    correlated/clipped, so this is a model-mismatch diagnostic, not a proof.
    """
    alpha, ks, count = pareto_tail_fit(lengths, cutoff)
    rng = np.random.default_rng(seed)
    simulated_ks, alpha_boot = [], []
    for _ in range(n):
        sample = cutoff * (1+rng.pareto(alpha, count))
        a, d, _ = pareto_tail_fit(sample, cutoff)
        alpha_boot.append(a)
        simulated_ks.append(d)
    return {"alpha_mle": alpha, "ks_distance": ks, "tail_count": count, "replicates": n,
            "fixed_cutoff_parametric_ks_p": float((1+np.sum(np.asarray(simulated_ks)>=ks))/(n+1)),
            "simulated_refitted_alpha_95pct": np.quantile(alpha_boot, [0.025, 0.975]).tolist(),
            "seed": seed,
            "scope": "Conditional i.i.d. Pareto reference diagnostic, not a completeness test or hidden-prevalence interval."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE_DIR / "pu_vector_prior_study.json")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("prior study exists; preserve it and choose a new audit output path")
    if sha256_file(TRACE_PATH) != TRACE_SHA:
        raise RuntimeError("GDR-extracted trace table SHA-256 changed")
    traces = pd.read_csv(TRACE_PATH)
    with rasterio.open(DATA_DIR / "sample_submission.tif") as d:
        fp = np.isfinite(d.read(1))
    with rasterio.open(DATA_DIR / "labels.tif") as d:
        labels = (d.read(1)>0) & fp
    lengths = traces.clipped_length_m.to_numpy(float)
    scenarios = []
    for cutoff in CUTOFFS:
        est = estimate_power_law_class_prior(labels, fp, l_min=cutoff, l0=300,
                                             lengths_override_m=lengths)
        scenarios.append({**est.to_dict(), "tail_fit_diagnostic": tail_bootstrap(lengths, cutoff)})
    skeleton = extract_skeleton_trace_lengths_m(labels)
    legacy_comparison = estimate_power_law_class_prior(labels, fp).to_dict()
    primary = next(x for x in scenarios if x["l_min_m"]==PRIMARY)
    report = {
        "schema_version": 1, "generated_utc": utc_now(),
        "status": "DESCRIPTIVE_PRIOR_SCENARIOS_NOT_IDENTIFIED_HIDDEN_PREVALENCE",
        "source": {"official_url": "https://gdr.openei.org/submissions/1391", "doi": "10.15121/1881483",
                   "official_zip_url": "https://gdr.openei.org/files/1391/qfaults_ingenious_nad83conus117_2023-06-27.zip",
                   "official_zip_sha256": "c7b091c9ac8bca140ad89ee6bb2bd63dd3ac12e3013acbfd8373d11c9faee59d",
                   "extract": str(TRACE_PATH.relative_to(ROOT)), "extract_sha256": TRACE_SHA,
                   "extraction_scope": "Vector traces intersecting template bounding rectangle, not exact footprint clipping.",
                   "direct_official_zip_refetch_this_session": False},
        "input_hashes": {p:sha256_file(DATA_DIR/p) for p in ("labels.tif", "sample_submission.tif")},
        "fixed_choices_not_leaderboard_tuned": {"primary_cutoff_m": PRIMARY, "lower_cutoff_m": 300,
             "sensitivity_cutoffs_m": list(CUTOFFS), "estimator": "tail MLE (OLS diagnostic only)"},
        "counts": {"vector_rows": len(traces), "vector_centroids_inside_footprint": int((traces.centroid_in_footprint==1).sum()),
                   "raster_components": len(skeleton), "catalogue_pixels": int(labels.sum()), "footprint_pixels": int(fp.sum()),
                   "bbox_clipped_vectors": int((traces.clipped_length_m < traces.full_length_m-0.1).sum())},
        "vector_scenarios": scenarios,
        "primary_scenario": primary,
        "raster_component_scenario_not_geological_trace_truth": legacy_comparison,
        "pi_sensitivity_range": [min(s["pi_total"] for s in scenarios), max(s["pi_total"] for s in scenarios)],
        "raw_ccdf": {"vector_clipped_lengths_m": sorted(lengths.tolist()), "raster_component_lengths_m": skeleton.tolist()},
        "identification": {"hidden_positive_fraction_identified": False, "verified_complete_tail": False,
                           "SCAR_positive_representativeness_verified": False, "eligible_for_probability_calibration": False},
        "limitations": [
            "The lower cutoff 300 m is a scenario; the DTI kernel does not imply a minimum fault length.",
            "Source features are cartographic segments; merged raster components and vector segments are different populations.",
            "Rectangle/footprint clipping and map scale affect length-frequency observations.",
            "A good power-law fit would not establish catalogue completeness or a correct hidden-positive prior.",
            "The approximate pixel conversion assumes unseen faults rasterize like known traces; overlaps are ignored.",
            "These global scenarios are descriptive; fold training must estimate its own prior using training data only.",
            "No leaderboard values enter the study; no scenario is selected by a holdout score.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"primary_pi": primary["pi_total"], "pi_range": report["pi_sensitivity_range"],
                      "ks_p_primary":primary["tail_fit_diagnostic"]["fixed_cutoff_parametric_ks_p"],
                      "hidden_prevalence_identified":False}, indent=2))


if __name__ == "__main__":
    main()
