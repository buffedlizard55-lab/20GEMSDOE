#!/usr/bin/env python3
"""One frozen H22-2 magnetic-trough spatial-transfer screen. Never packages an upload.

Consumes a versioned run ledger before outcome access. No force/rerun flag.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems.footprint import load_footprint  # noqa: E402
from gems.holdout import Holdout, gate  # noqa: E402
from gems.lineaments import fill_and_guard, hessian_line_response, scalar_low_control  # noqa: E402
from gems.multiple_testing import exact_paired_signflip_test, holm_bonferroni_and_bh_correction  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR  # noqa: E402
from gems.research_gate import SingleUseRun, committed_protocol, utc_now  # noqa: E402
from gems.validator import sha256_file  # noqa: E402

ID = "H22-2"
RESULT = EVIDENCE_DIR / "h22_2_magnetic_low_holdout.json"
LOCK = EVIDENCE_DIR / "runs/h22_2_once.json"
PREREG = ROOT / "docs/research/preregistration_h22_2.md"
PINS = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}
REFERENCES = {
    "spatial_holdout_h16_results.json": "c681ef8d3eca77cc1579c7f74ea608ed8a046f665a2965ba51d856831ee67897",
    "spatial_holdout_results.json": "45913754a58b9eb772dbba62005699c8cff8252599f6e3030cb38a72efae4a99",
}
FAMILY = ("H22-2", "H22-1", "H22-3", "H21-3", "H21-4")


def continuous_scores(evaluator: Holdout, score: np.ndarray) -> dict:
    # score_mask handles real-valued p in [0,1]; no emission/threshold operation.
    return evaluator.score_mask(score)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if RESULT.exists() or LOCK.exists():
        parser.error("H22-2 already consumed; refusing a second outcome test")
    protocol = committed_protocol(ROOT, [
        PREREG, Path(__file__), ROOT / "src/gems/lineaments.py", ROOT / "src/gems/holdout.py",
        ROOT / "src/gems/metric.py", ROOT / "src/gems/multiple_testing.py", ROOT / "src/gems/research_gate.py",
    ])
    hashes = {}
    for name, expected in PINS.items():
        actual = sha256_file(DATA_DIR / name)
        if actual != expected:
            raise RuntimeError(f"input SHA-256 mismatch: {name}")
        hashes[name] = actual
    for name, expected in REFERENCES.items():
        if sha256_file(EVIDENCE_DIR / name) != expected:
            raise RuntimeError(f"Comparator changed after preregistration: {name}")
    bindings = {"protocol": protocol, "inputs": hashes, "comparator_hashes": REFERENCES}
    with SingleUseRun(LOCK, ID, bindings):
        with rasterio.open(DATA_DIR / "sample_submission.tif") as template:
            fp = np.isfinite(template.read(1))
            grid = (template.shape, template.crs, template.transform)
        if not np.array_equal(fp, load_footprint()):
            raise RuntimeError("template / published footprint mismatch")
        with rasterio.open(DATA_DIR / "training_features.tif") as ds:
            if (ds.shape, ds.crs, ds.transform) != grid or ds.tags(2).get("band_name") != "rtp":
                raise RuntimeError("RTP band/grid metadata mismatch")
            rtp = ds.read(2)
            description = ds.descriptions[1]
        filled, interior, metadata = fill_and_guard(rtp, fp)
        del rtp
        trough, scales = hessian_line_response(filled, interior, polarity="trough")
        ridge, _ = hessian_line_response(filled, interior, polarity="ridge")
        scalar = scalar_low_control(filled, interior)
        del filled
        with rasterio.open(DATA_DIR / "labels.tif") as ds:
            if (ds.shape, ds.crs, ds.transform) != grid:
                raise RuntimeError("labels grid mismatch")
            labels = (ds.read(1) > 0) & fp
        evaluator = Holdout(fp, labels, budget=0.025, sparse_seed_offset=0)
        idx = evaluator.fp_idx
        candidate = evaluator.evaluate(trough.ravel()[idx], ridge=True)
        control_low = evaluator.evaluate(scalar.ravel()[idx], ridge=True)
        control_bright = evaluator.evaluate(ridge.ravel()[idx], ridge=True)
        confidence = continuous_scores(evaluator, trough)
        h16_doc = json.loads((EVIDENCE_DIR / "spatial_holdout_h16_results.json").read_text())
        h16 = h16_doc["summary"]["H16_1_SeamFree_MultiScale_Synthesis"]
        old = json.loads((EVIDENCE_DIR / "spatial_holdout_results.json").read_text())["summary"]
        dense = old["H20_1_SAR_nnPU_MultiLine_Corroborated"]
        sparse = old["H20_5_Calibrated_Continuous_SoftTail_nnpu"]
        historical = {"mean_dense_dti": dense["mean_dense_dti"], "fold_dense": dense["fold_dense"],
                      "mean_sparse_dti": sparse["mean_sparse_dti"], "fold_sparse": sparse["fold_sparse"]}
        vs_h16, vs_h20 = gate(candidate, h16), gate(candidate, historical)
        test = exact_paired_signflip_test(candidate["fold_sparse"], h16["fold_sparse"])
        rows = [{"id": x, "p_value_raw": test["p_value_raw"] if x == ID else 1.0,
                 "status": "evaluated" if x == ID else "pending; conservatively p=1"} for x in FAMILY]
        adjusted = holm_bonferroni_and_bh_correction(rows)
        significant = next(x for x in adjusted if x["id"] == ID)["pass_holm_fwer"]
        control_pass = candidate["mean_sparse_dti"] > control_low["mean_sparse_dti"]
        screen_pass = vs_h16["passed"] and vs_h20["passed"] and control_pass
        report = {
            "schema_version": 1, "generated_utc": utc_now(), "candidate_id": ID,
            "status": "EXPLORATORY_REUSED_KNOWN_CATALOGUE_SPATIAL_TRANSFER_PROXY",
            "preregistration": protocol, "input_sha256": hashes,
            "software_versions": {k: importlib.metadata.version(k) for k in ("numpy", "scipy", "rasterio")},
            "layer": {"band": 2, "name": "rtp", "description": description},
            "transform_metadata": {**metadata, "scales": scales, "polarity": "trough", "edge_guard_px": 32},
            "evaluation": {"candidate": candidate, "scalar_low_control": control_low,
                           "opposite_polarity_control": control_bright,
                           "continuous_confidence_dti_descriptive_only": confidence},
            "comparisons": {"vs_h16": vs_h16, "vs_historical_h20_thresholds": vs_h20,
                            "sparse_beats_scalar_low_control": control_pass, "practical_screen_passed": screen_pass},
            "multiplicity": {"family_ids_frozen_before_test": list(FAMILY), "primary_endpoint": "Sparse proxy DTI vs H16-1",
                             "raw_exact_signflip_test": test, "holm_and_bh": adjusted,
                             "passes_holm_fwer": significant, "future_missing_tests_not_dropped": True},
            "final_confirmation": {"status": "BLOCKED_NO_NEW_INDEPENDENT_LABELS", "touched": False,
                                   "old_catalogue_and_H20_vault_not_untouched": True},
            "slot_recommendation": False, "submission_artifact_created": False, "submission_slot_spent": False,
            "decision": "REJECT_NO_RETUNING" if not screen_pass else "PROXY_SCREEN_ONLY_BLOCKED_INDEPENDENT_CONFIRMATION",
            "limitations": [
                "Known-catalogue labels and synthetic sparse components, not hidden competition ground truth.",
                "Adjacent spatial quadrants reused across experiments; exact sign-flip assumptions are unverified.",
                "Holm controls the declared family under valid p-values; it cannot fix adaptive reuse or label bias.",
                "H16 comparator is the hash-pinned prior reproduction; H20 is historical, unreproduced, mixed-track thresholds.",
                "Continuous transform scores are confidence values, not calibrated probabilities.",
                "Demagnetization mechanism already existed in H16-4 and family-adjacent 15GEMSDOE.",
            ],
        }
        with RESULT.open("x") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
    print(json.dumps({"candidate": ID, "dense": candidate["mean_dense_dti"], "sparse": candidate["mean_sparse_dti"],
                      "screen_passed": screen_pass, "holm_passed": significant, "decision": report["decision"],
                      "slot_spent": False, "report": str(RESULT.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
