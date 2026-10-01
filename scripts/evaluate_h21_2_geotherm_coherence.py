#!/usr/bin/env python3
"""Single preregistered H21-2 test: multi-geothermometer coherence field.

This is a spatial-transfer proxy against the supplied known-fault catalogue, not
an evaluation against hidden competition labels. It never writes a submission.
Frozen constants live in ``src/gems/geotherm.py`` and
``docs/research/preregistration_h21_2.md`` (committed before this run).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems.footprint import load_footprint  # noqa: E402
from gems.geotherm import (  # noqa: E402
    CHEMISTRY_LAYER_TOKEN,
    catalogue_transfer_field,
    coherence_field,
    positions_from_utm,
    random_pseudo_sites,
    sanitize_geothermometers,
    site_estimates,
    thermal_control_cells,
    unit_field,
)
from gems.holdout import Holdout, gate  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH, TEMPLATE_PATH  # noqa: E402

PREREG_PATH = ROOT / "docs/research/preregistration_h21_2.md"
RESULT_PATH = EVIDENCE_DIR / "h21_2_geotherm_coherence_holdout.json"
AUDIT_PATH = EVIDENCE_DIR / "h21_2_wellspring_audit.json"
CSV_PATH = ROOT / "evidence" / "ci" / "gdr_wellspring_in_footprint.csv"
BUDGET = 0.025


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_inputs() -> tuple[np.ndarray, np.ndarray, int, object]:
    with rasterio.open(TEMPLATE_PATH) as ds:
        template = ds.read(1)
        transform = ds.transform
        footprint_from_template = np.isfinite(template)
    footprint = load_footprint()
    if not np.array_equal(footprint, footprint_from_template):
        raise RuntimeError("docs/data/footprint.bin does not exactly match sample_submission.tif")
    with rasterio.open(LABELS_PATH) as ds:
        labels = (ds.read(1) > 0) & footprint
    return footprint, labels, int(footprint.sum()), transform


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="rerun for audit/debug; existing result is preserved in a timestamped backup",
    )
    args = parser.parse_args()
    if RESULT_PATH.exists() and not args.force:
        parser.error(f"{RESULT_PATH} already exists; refusing a second test without --force")
    for path in (PREREG_PATH, AUDIT_PATH, CSV_PATH, TEMPLATE_PATH, LABELS_PATH):
        if not path.is_file():
            raise FileNotFoundError(path)

    prereg_hash = sha256(PREREG_PATH)
    footprint, labels, n_footprint, transform = load_inputs()
    shape = footprint.shape

    df_raw = pd.read_csv(CSV_PATH)
    df = positions_from_utm(df_raw, transform)
    df = sanitize_geothermometers(df)
    coord_qa_mismatches = int(df["coord_qa_mismatch"].sum())

    chem = df[df["layer"].str.contains(CHEMISTRY_LAYER_TOKEN, na=False)].copy()
    sites = site_estimates(chem)
    n_eligible = int(sites.eligible.sum())
    candidate = coherence_field(sites, shape, footprint)

    fp_idx = np.flatnonzero(footprint.ravel())
    evaluator = Holdout(footprint, labels, budget=BUDGET, sparse_seed_offset=0)

    def evaluate_global(field: np.ndarray) -> dict:
        return evaluator.evaluate(field.ravel()[fp_idx].astype(np.float32, copy=False), ridge=False)

    cand_res = evaluate_global(candidate)

    # C1: thermal-point anchors without coherence selection (descriptive).
    c1_rows, c1_cols = thermal_control_cells(df)
    c1_res = evaluate_global(unit_field(c1_rows, c1_cols, shape, footprint))

    # C2: seeded random pseudo-sites, same count as eligible cells (descriptive).
    c2_rows, c2_cols = random_pseudo_sites(n_eligible, footprint)
    c2_res = evaluate_global(unit_field(c2_rows, c2_cols, shape, footprint))

    # C3: per-fold known-catalogue proximity transfer ceiling (descriptive).
    c3_dense, c3_sparse = [], []
    for f_id, _name, _m, _sl, _td, _ts, _kc, _fm in evaluator.quads:
        known_train = labels & ~(evaluator.fold_2d == f_id)
        surf = catalogue_transfer_field(known_train, footprint)
        pred = evaluator.emit_quadrant(surf.ravel()[fp_idx].astype(np.float32, copy=False), f_id, ridge=False)
        c3_dense.append(evaluator.score_quadrant(pred, f_id, "dense"))
        c3_sparse.append(evaluator.score_quadrant(pred, f_id, "sparse"))
    c3_res = {
        "mean_dense_dti": round(float(np.mean(c3_dense)), 5),
        "mean_sparse_dti": round(float(np.mean(c3_sparse)), 5),
        "fold_dense": [round(x, 5) for x in c3_dense],
        "fold_sparse": [round(x, 5) for x in c3_sparse],
    }

    stored_path = EVIDENCE_DIR / "spatial_holdout_results.json"
    stored = json.loads(stored_path.read_text()) if stored_path.exists() else {}
    summary = stored.get("summary", {})
    h20_1 = summary.get("H20_1_SAR_nnPU_MultiLine_Corroborated")
    h20_5 = summary.get("H20_5_Calibrated_Continuous_SoftTail_nnpu")
    h16_path = EVIDENCE_DIR / "spatial_holdout_h16_results.json"
    h16_doc = json.loads(h16_path.read_text()) if h16_path.exists() else {}
    h16_current = h16_doc.get("summary", {}).get("H16_1_SeamFree_MultiScale_Synthesis")

    comparison = {"stored_h20_reference_present": bool(h20_1 and h20_5),
                  "reproduced_h16_reference_present": bool(h16_current)}
    if h20_1 and h20_5:
        mixed_baseline = {
            "mean_dense_dti": h20_1["mean_dense_dti"],
            "mean_sparse_dti": h20_5["mean_sparse_dti"],
            "fold_dense": h20_1["fold_dense"],
            "fold_sparse": h20_5["fold_sparse"],
        }
        comparison["gate_vs_stored_h20_best"] = gate(cand_res, mixed_baseline)
        comparison["stored_h20_reference"] = {
            "dense_candidate": "H20-1",
            "dense_mean": h20_1["mean_dense_dti"],
            "dense_folds": h20_1["fold_dense"],
            "sparse_candidate": "H20-5",
            "sparse_mean": h20_5["mean_sparse_dti"],
            "sparse_folds": h20_5["fold_sparse"],
            "reproduced_in_this_run": False,
            "comparator_note": "historical, unreproduced; dense and sparse tracks are drawn from separate candidates",
        }
    if h16_current:
        comparison["gate_vs_reproduced_h16_1"] = gate(cand_res, h16_current)
        comparison["reproduced_h16_1_reference"] = {
            "source": "evidence/spatial_holdout_h16_results.json",
            "mean_dense_dti": h16_current["mean_dense_dti"],
            "mean_sparse_dti": h16_current["mean_sparse_dti"],
            "fold_dense": h16_current["fold_dense"],
            "fold_sparse": h16_current["fold_sparse"],
        }
    h20_pass = comparison.get("gate_vs_stored_h20_best", {}).get("passed", False)
    h16_pass = comparison.get("gate_vs_reproduced_h16_1", {}).get("passed", False)
    comparison["conservative_screen_passed"] = bool(h20_pass and h16_pass)

    eligible_t = sites.t_med[sites.eligible]
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_id": "H21-2-multigeothermometer-coherence",
        "status": "EXPLORATORY_KNOWN_CATALOGUE_SPATIAL_TRANSFER_PROXY",
        "slot_recommendation": False,
        "slot_reason": (
            "The evaluator uses known-catalogue fault labels and a synthetic sparse-component proxy, not hidden competition ground truth. "
            "A proxy-screen pass would be necessary but not sufficient for a submission recommendation; sampling bias toward mapped faults "
            "(C3) further limits interpretation. The evaluator never writes a submission artifact."
        ),
        "preregistration": {
            "path": "docs/research/preregistration_h21_2.md",
            "sha256": prereg_hash,
            "frozen_constants_module": "src/gems/geotherm.py",
            "data_audit_path": "evidence/h21_2_wellspring_audit.json",
            "data_audit_sha256": sha256(AUDIT_PATH),
            "threshold_search": False,
        },
        "input_sha256": {
            "gdr_wellspring_in_footprint.csv": sha256(CSV_PATH),
            "labels.tif": sha256(LABELS_PATH),
            "sample_submission.tif": sha256(TEMPLATE_PATH),
        },
        "input_metadata": {
            "footprint_pixels": n_footprint,
            "known_fault_pixels_in_footprint": int(labels.sum()),
            "csv_rows": int(len(df_raw)),
            "chemistry_records": int(len(chem)),
            "chemistry_cells": int(len(sites.row)),
            "coord_qa_mismatch_rows": coord_qa_mismatches,
            "eligible_coherent_hot_cells": n_eligible,
            "eligible_t_med_degC": {
                "min": round(float(eligible_t.min()), 2) if eligible_t.size else None,
                "median": round(float(np.median(eligible_t)), 2) if eligible_t.size else None,
                "max": round(float(eligible_t.max()), 2) if eligible_t.size else None,
            },
            "records_with_geothermometers_invalidated_by_bounds": int(
                df_raw[["geothermquartz_c", "geothermchalc_c", "geothermcat_c"]].notna().sum().sum()
                - df[["geothermquartz_c", "geothermchalc_c", "geothermcat_c"]].notna().sum().sum()
            ),
        },
        "evaluation": {
            "protocol": (
                "4 contiguous geographic quadrants; fixed 2.5% per-quadrant emission; deterministic 20%-of-connected-components "
                "sparse proxy; exact repository DTI implementation; ridge-NMS disabled (isotropic point-anomaly field, preregistered)"
            ),
            "target_scope": "held-out portions of the supplied known-fault catalogue, not newly discovered/hidden fault labels",
            "h21_2_coherence_candidate": cand_res,
            "controls_descriptive_only": {
                "c1_thermal_points_no_coherence": {"n_cells": int(len(c1_rows)), **c1_res},
                "c2_random_pseudo_sites_seed4243": {"n_cells": int(len(c2_rows)), **c2_res},
                "c3_catalogue_proximity_transfer_ceiling": c3_res,
            },
            "comparison_to_stored_references": comparison,
            "primary_gate_passed_against_stored_h20_values": h20_pass,
            "gate_passed_against_current_reproduced_h16_1": h16_pass,
            "conservative_screen_passed_both_comparators": comparison["conservative_screen_passed"],
            "candidate_vs_c3_ceiling_mean_dense_delta": round(cand_res["mean_dense_dti"] - c3_res["mean_dense_dti"], 5),
            "candidate_vs_c3_ceiling_mean_sparse_delta": round(cand_res["mean_sparse_dti"] - c3_res["mean_sparse_dti"], 5),
        },
        "multiple_comparison_note": (
            "Exactly one preregistered candidate was evaluated under one frozen protocol; controls are descriptive and incur no "
            "promotion multiplicity. No post-hoc parameter sweep or significance claim was made."
        ),
        "submission_artifact_created": False,
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if RESULT_PATH.exists():
        backup = RESULT_PATH.with_name(f"{RESULT_PATH.stem}.rerun-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{RESULT_PATH.suffix}")
        RESULT_PATH.replace(backup)
        report["rerun_backup"] = str(backup.relative_to(ROOT))
        report["rerun_note"] = "Rerun requested with --force; this is not a second confirmatory test."
    RESULT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "candidate": report["candidate_id"],
        "dense": cand_res["mean_dense_dti"],
        "sparse": cand_res["mean_sparse_dti"],
        "c1_dense": c1_res["mean_dense_dti"],
        "c2_dense": c2_res["mean_dense_dti"],
        "c3_dense": c3_res["mean_dense_dti"],
        "gate_vs_h20": comparison.get("gate_vs_stored_h20_best", {}).get("passed"),
        "gate_vs_h16": comparison.get("gate_vs_reproduced_h16_1", {}).get("passed"),
        "slot_recommendation": False,
        "report": str(RESULT_PATH.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
