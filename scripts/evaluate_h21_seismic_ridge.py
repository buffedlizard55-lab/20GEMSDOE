#!/usr/bin/env python3
"""Single preregistered H21 test: multi-scale line ridges in earthquake intensity.

This is a spatial-transfer proxy against the supplied known-fault catalogue, not
an evaluation against hidden competition labels. It never writes a submission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems.footprint import load_footprint  # noqa: E402
from gems.holdout import Holdout, gate  # noqa: E402
from gems.paths import DATA_DIR, EVIDENCE_DIR, LABELS_PATH  # noqa: E402

PREREG_PATH = ROOT / "docs/research/preregistration_h21.md"
RESULT_PATH = EVIDENCE_DIR / "h21_seismic_ridge_holdout.json"
SIGMAS = (2.0, 4.0, 8.0)
BETA = 0.5
EDGE_GUARD_PX = 32
BUDGET = 0.025


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_layers() -> tuple[np.ndarray, np.ndarray, np.ndarray, str, int]:
    with rasterio.open(DATA_DIR / "sample_submission.tif") as ds:
        template = ds.read(1)
        footprint_from_template = np.isfinite(template)
        template_hash = sha256(DATA_DIR / "sample_submission.tif")
    footprint = load_footprint()
    if not np.array_equal(footprint, footprint_from_template):
        raise RuntimeError("docs/data/footprint.bin does not exactly match sample_submission.tif")

    with rasterio.open(DATA_DIR / "training_features.tif") as ds:
        if ds.count < 16:
            raise RuntimeError(f"training_features.tif has {ds.count} bands; H21 requires band 16")
        description = ds.descriptions[15] or ""
        tags = ds.tags(16)
        band_name = tags.get("band_name", "")
        if band_name != "ieq_n100a15" or "Earthquake intensity" not in description:
            raise RuntimeError(
                f"Band 16 metadata mismatch: band_name={band_name!r}, description={description!r}"
            )
        ieq = ds.read(16).astype(np.float32, copy=False)

    with rasterio.open(LABELS_PATH) as ds:
        labels = (ds.read(1) > 0) & footprint

    invalid = (~np.isfinite(ieq)) | (ieq < -1e20)
    invalid_inside_count = int(np.sum(footprint & invalid))
    finite_nonnegative = np.where(invalid, 0.0, np.maximum(ieq, 0.0))
    signal = np.log1p(finite_nonnegative).astype(np.float32, copy=False)

    # Replace invalid and out-of-footprint cells with the nearest valid footprint
    # value before filtering; the 32-cell guard then prevents footprint-edge
    # derivatives from entering the ranked region.
    valid_source = footprint & ~invalid
    if not valid_source.any():
        raise RuntimeError("H21 input contains no valid footprint values")
    _, nearest = distance_transform_edt(~valid_source, return_indices=True)
    signal = signal[tuple(nearest)].astype(np.float32, copy=False)
    interior = distance_transform_edt(footprint) > EDGE_GUARD_PX
    if int(interior.sum()) < int(0.5 * footprint.sum()):
        raise RuntimeError("H21 edge guard leaves less than half the footprint")
    return footprint, labels, signal, description, invalid_inside_count


def hessian_ridge_score(signal: np.ndarray, interior: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    # Centering is mathematically derivative-invariant and removes the small
    # nonzero discrete-kernel sum of a truncated Gaussian second derivative.
    signal = (signal - np.float32(np.median(signal[interior]))).astype(np.float32, copy=False)
    score = np.zeros(signal.shape, dtype=np.float32)
    scale_meta: dict[str, float] = {}
    eps = np.finfo(np.float32).eps
    for sigma in SIGMAS:
        # Scale-normalized Gaussian Hessian, with fixed 4-sigma truncation.
        hxx = gaussian_filter(signal, sigma=sigma, order=(0, 2), mode="nearest", truncate=4.0) * sigma**2
        hxy = gaussian_filter(signal, sigma=sigma, order=(1, 1), mode="nearest", truncate=4.0) * sigma**2
        hyy = gaussian_filter(signal, sigma=sigma, order=(2, 0), mode="nearest", truncate=4.0) * sigma**2
        trace = hxx + hyy
        disc = np.sqrt(np.maximum((hxx - hyy) ** 2 + 4.0 * hxy**2, 0.0))
        eig_a = 0.5 * (trace + disc)
        eig_b = 0.5 * (trace - disc)
        abs_a, abs_b = np.abs(eig_a), np.abs(eig_b)
        small = np.where(abs_a <= abs_b, eig_a, eig_b)
        large = np.where(abs_a <= abs_b, eig_b, eig_a)
        strength = np.sqrt(small**2 + large**2)
        c = float(np.quantile(strength[interior], 0.90))
        if not np.isfinite(c) or c <= eps:
            response = np.zeros(signal.shape, dtype=np.float32)
        else:
            ratio = np.abs(small) / (np.abs(large) + eps)
            blobness = np.exp(-(ratio**2) / (2.0 * BETA**2))
            strengthness = 1.0 - np.exp(-(strength**2) / (2.0 * c**2))
            response = np.where(large < 0.0, blobness * strengthness, 0.0).astype(np.float32)
            response[~interior] = 0.0
        np.maximum(score, response, out=score)
        scale_meta[str(sigma)] = c
        del hxx, hxy, hyy, trace, disc, eig_a, eig_b, abs_a, abs_b, small, large, strength
    return score, scale_meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    ledger = EVIDENCE_DIR / "runs/h21_seismic_ridge_holdout_historical_consumed.json"
    if RESULT_PATH.exists() or ledger.exists():
        parser.error("historical one-shot test consumed; no rerun, force, or retuning allowed")
    for path in (feature_path, label_path, template_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    footprint, labels, signal, band_description, invalid_inside_count = load_layers()
    score_2d, c_by_scale = hessian_ridge_score(signal, distance_transform_edt(footprint) > EDGE_GUARD_PX)
    fp_idx = np.flatnonzero(footprint.ravel())
    p_h21 = score_2d.ravel()[fp_idx].astype(np.float32, copy=False)
    p_raw = signal.ravel()[fp_idx].astype(np.float32, copy=False)
    evaluator = Holdout(footprint, labels, budget=BUDGET, sparse_seed_offset=0)
    h21 = evaluator.evaluate(p_h21, ridge=True)
    raw = evaluator.evaluate(p_raw, ridge=True)

    stored_path = EVIDENCE_DIR / "spatial_holdout_results.json"
    stored = json.loads(stored_path.read_text()) if stored_path.exists() else {}
    summary = stored.get("summary", {})
    h20_1 = summary.get("H20_1_SAR_nnPU_MultiLine_Corroborated")
    h20_5 = summary.get("H20_5_Calibrated_Continuous_SoftTail_nnpu")
    h16_legacy = summary.get("H16_1_SeamFree_MultiScale_Synthesis")
    h16_path = EVIDENCE_DIR / "spatial_holdout_h16_results.json"
    h16_doc = json.loads(h16_path.read_text()) if h16_path.exists() else {}
    h16_current = h16_doc.get("summary", {}).get("H16_1_SeamFree_MultiScale_Synthesis")

    comparison = {
        "stored_h20_reference_present": bool(h20_1 and h20_5),
        "reproduced_h16_reference_present": bool(h16_current),
    }
    if h20_1 and h20_5:
        # Conservative track-wise comparator: use the higher stored H20 Dense
        # and Sparse references even though they came from different artifacts.
        mixed_baseline = {
            "mean_dense_dti": h20_1["mean_dense_dti"],
            "mean_sparse_dti": h20_5["mean_sparse_dti"],
            "fold_dense": h20_1["fold_dense"],
            "fold_sparse": h20_5["fold_sparse"],
        }
        comparison["gate_vs_stored_h20_best"] = gate(h21, mixed_baseline)
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
        comparison["gate_vs_reproduced_h16_1"] = gate(h21, h16_current)
        comparison["reproduced_h16_1_reference"] = {
            "source": "evidence/spatial_holdout_h16_results.json",
            "mean_dense_dti": h16_current["mean_dense_dti"],
            "mean_sparse_dti": h16_current["mean_sparse_dti"],
            "fold_dense": h16_current["fold_dense"],
            "fold_sparse": h16_current["fold_sparse"],
        }
    elif h16_legacy:
        comparison["gate_vs_legacy_stored_h16_1"] = gate(h21, h16_legacy)
        comparison["legacy_h16_1_reference_reproduced"] = False

    h20_pass = comparison.get("gate_vs_stored_h20_best", {}).get("passed", False)
    h16_pass = comparison.get("gate_vs_reproduced_h16_1", {}).get("passed", False)
    comparison["conservative_screen_passed"] = bool(h20_pass and h16_pass)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_id": "H21-1-multiscale-seismic-density-ridge",
        "status": "EXPLORATORY_KNOWN_CATALOGUE_SPATIAL_TRANSFER_PROXY",
        "slot_recommendation": False,
        "slot_reason": (
            "The evaluator uses known-catalogue fault labels and a synthetic sparse-component proxy, not hidden competition ground truth. "
            "A proxy-screen pass would be necessary but not sufficient for a submission recommendation. "
            "Both the historical H20 threshold screen and the current reproduced H16-1 comparator must pass."
        ),
        "preregistration": {
            "path": "docs/research/preregistration_h21.md",
            "sha256": prereg_hash,
            "transform_constants": {
                "band": 16,
                "band_name": "ieq_n100a15",
                "sigmas_px": list(SIGMAS),
                "beta": BETA,
                "c_quantile": 0.90,
                "edge_guard_px": EDGE_GUARD_PX,
                "budget_per_quadrant": BUDGET,
                "ridge_nms": True,
                "threshold_search": False,
            },
        },
        "input_sha256": {
            "training_features.tif": sha256(feature_path),
            "labels.tif": sha256(label_path),
            "sample_submission.tif": sha256(template_path),
        },
        "input_metadata": {
            "band_16_description": band_description,
            "footprint_pixels": int(footprint.sum()),
            "known_fault_pixels_in_footprint": int(labels.sum()),
            "invalid_or_sentinel_band16_cells_in_footprint": invalid_inside_count,
            "interior_pixels_after_edge_guard": int((distance_transform_edt(footprint) > EDGE_GUARD_PX).sum()),
            "hessian_c_q90_by_sigma": c_by_scale,
        },
        "evaluation": {
            "protocol": "4 contiguous geographic quadrants; fixed 2.5% per-quadrant emission; deterministic 20%-of-connected-components sparse proxy; exact repository DTI implementation",
            "target_scope": "held-out portions of the supplied known-fault catalogue, not newly discovered/hidden fault labels",
            "h21_multiscale_ridge": h21,
            "raw_seismic_ieq_control": raw,
            "comparison_to_stored_references": comparison,
            "primary_gate_passed_against_stored_h20_values": h20_pass,
            "gate_passed_against_current_reproduced_h16_1": h16_pass,
            "conservative_screen_passed_both_comparators": comparison["conservative_screen_passed"],
        },
        "multiple_comparison_note": (
            "Only one preregistered candidate was evaluated; raw seismic intensity is a descriptive control. "
            "No post-hoc parameter sweep or significance claim was made."
        ),
        "submission_artifact_created": False,
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "candidate": report["candidate_id"],
        "dense": h21["mean_dense_dti"],
        "sparse": h21["mean_sparse_dti"],
        "raw_dense": raw["mean_dense_dti"],
        "raw_sparse": raw["mean_sparse_dti"],
        "gate": comparison.get("gate_vs_stored_h20_best"),
        "slot_recommendation": False,
        "report": str(RESULT_PATH.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
