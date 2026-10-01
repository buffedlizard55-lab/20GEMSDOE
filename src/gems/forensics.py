"""Forensics for prediction rasters: byte identity, effective (scored-pixel) similarity, uniqueness gate."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

NEAR_PX = 3.0      # 300 m kernel support at 100 m pixels
MID_PX = 15.0      # 1.5 km
NEAR_DUP_JACCARD = 0.80


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gh_fetch_raw(owner: str, repo: str, path: str, dest: Path, ref: str = "main") -> bytes:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gh",
        "api",
        f"repos/{owner}/{repo}/contents/{path}?ref={ref}",
        "-H",
        "Accept: application/vnd.github.raw",
    ]
    data = subprocess.run(cmd, check=True, capture_output=True).stdout
    dest.write_bytes(data)
    return data


@dataclass
class Grid:
    footprint: np.ndarray
    catalogue: np.ndarray
    scored: np.ndarray
    dist_to_cat: np.ndarray

    @classmethod
    def from_footprint(cls, footprint: np.ndarray, labels: np.ndarray) -> "Grid":
        footprint, labels = np.asarray(footprint), np.asarray(labels)
        if footprint.ndim != 2 or labels.shape != footprint.shape or not np.isin(footprint,[0,1]).all() or not np.isfinite(labels[footprint.astype(bool)]).all():
            raise ValueError("matching binary footprint and finite in-footprint catalogue required")
        footprint = footprint.astype(bool)
        catalogue = (labels > 0) & footprint
        dist = distance_transform_edt(~catalogue).astype(np.float32)
        return cls(footprint, catalogue, footprint & ~catalogue, dist)

    @classmethod
    def load(cls, template_path: Path, labels_path: Path) -> "Grid":
        with rasterio.open(template_path) as src:
            footprint = np.isfinite(src.read(1))
            grid = (src.shape,src.crs,src.transform)
        with rasterio.open(labels_path) as src:
            if src.count != 1 or (src.shape,src.crs,src.transform) != grid:
                raise ValueError("catalogue grid differs from template")
            catalogue = (src.read(1) > 0) & footprint
        dist = distance_transform_edt(~catalogue).astype(np.float32)
        return cls(footprint, catalogue, footprint & ~catalogue, dist)


def read_prediction(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1)


def describe(arr: np.ndarray, grid: Grid) -> dict[str, Any]:
    inside = arr[grid.footprint]
    outside = arr[~grid.footprint]
    fin = np.isfinite(inside)
    pos_all = (np.nan_to_num(arr, nan=0.0) > 0.5) & grid.footprint
    pos = pos_all & grid.scored
    n_pos = int(pos.sum())
    d = grid.dist_to_cat[pos]
    uniq = np.unique(inside[fin])
    return {
        "in_footprint_nan": int((~fin).sum()),
        "in_footprint_min": float(inside[fin].min()) if fin.any() else None,
        "in_footprint_max": float(inside[fin].max()) if fin.any() else None,
        "outside_mode": "nan"
        if np.isnan(outside).all()
        else ("zero" if np.all(np.nan_to_num(outside, nan=1.0) == 0) else "other"),
        "is_binary_0_1": bool(len(uniq) <= 2 and set(np.round(uniq, 6).tolist()) <= {0.0, 1.0}),
        "n_unique_values": int(len(uniq)),
        "positive_pixels_all": int(pos_all.sum()),
        "positive_on_known_faults": int((pos_all & grid.catalogue).sum()),
        "positive_scored_pixels": n_pos,
        "scored_fraction_of_footprint": round(n_pos / float(grid.footprint.sum()), 5),
        "dist_le_300m": int((d <= NEAR_PX).sum()),
        "dist_300m_to_1500m": int(((d > NEAR_PX) & (d <= MID_PX)).sum()),
        "dist_gt_1500m": int((d > MID_PX).sum()),
        "frac_near_le_300m": round(float((d <= NEAR_PX).mean()), 4) if n_pos else None,
        "frac_far_gt_1500m": round(float((d > MID_PX).mean()), 4) if n_pos else None,
    }


def scored_positive(arr: np.ndarray, grid: Grid) -> np.ndarray:
    return (np.nan_to_num(arr, nan=0.0) > 0.5) & grid.scored


def pair_metrics(
    a: np.ndarray,
    b: np.ndarray,
    grid: Grid,
    pa: np.ndarray | None = None,
    pb: np.ndarray | None = None,
    dist_b: np.ndarray | None = None,
) -> dict[str, Any]:
    pa = scored_positive(a, grid) if pa is None else pa
    pb = scored_positive(b, grid) if pb is None else pb
    if np.asarray(a).shape != grid.footprint.shape or np.asarray(b).shape != grid.footprint.shape:
        raise ValueError("prediction/grid shape mismatch")
    sa, sb = np.asarray(a)[grid.scored], np.asarray(b)[grid.scored]
    finite = bool(np.isfinite(sa).all() and np.isfinite(sb).all())
    delta = np.abs(sa.astype(np.float64)-sb.astype(np.float64)) if finite else None
    inter = int((pa & pb).sum())
    union = int((pa | pb).sum())
    out = {
        "identical_on_scored_pixels": bool(finite and np.array_equal(sa, sb)),
        "scored_values_finite": finite,
        "mean_absolute_scored_difference": float(delta.mean()) if finite and delta.size else None,
        "max_absolute_scored_difference": float(delta.max()) if finite and delta.size else None,
        "fraction_scored_values_changed_exactly": float(np.mean(sa != sb)) if finite and sa.size else None,
        "positive_support_union_nonempty": union > 0,
        "jaccard_positive": round(inter / union, 5) if union else 1.0,
        "a_positive": int(pa.sum()),
        "b_positive": int(pb.sum()),
        "shared_positive": inter,
        "frac_a_in_b": round(inter / max(int(pa.sum()), 1), 5),
        "frac_b_in_a": round(inter / max(int(pb.sum()), 1), 5),
    }
    if dist_b is not None and pa.any():
        out["frac_a_within_300m_of_b"] = round(float((dist_b[pa] < NEAR_PX).mean()), 5)
    return out


def gate_candidate(candidate: np.ndarray, grid: Grid, history: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = np.asarray(candidate)
    if candidate.shape != grid.footprint.shape or not grid.scored.any() or not np.isfinite(candidate[grid.scored]).all() or np.any((candidate[grid.scored]<0)|(candidate[grid.scored]>1)):
        raise ValueError("candidate must have finite [0,1] values on a nonempty matching score mask")
    pc = scored_positive(candidate, grid)
    rows = []
    for h in history:
        arr_h = h["array"] if h.get("array") is not None else read_prediction(Path(h["path"]))
        ph = scored_positive(arr_h, grid)
        m = pair_metrics(candidate, arr_h, grid, pa=pc, pb=ph)
        rows.append({"id": h["id"], "lb_score": h.get("lb_score"), **m})
        if h.get("array") is None:
            del arr_h
    rows.sort(key=lambda r: (-r["jaccard_positive"], r["id"]))
    worst = rows[0] if rows else None
    if worst is None:
        verdict = "DISTINCT"
    elif any(row["identical_on_scored_pixels"] for row in rows):
        verdict = "DUPLICATE"
    elif any(row["jaccard_positive"] >= NEAR_DUP_JACCARD and row["positive_support_union_nonempty"] for row in rows):
        verdict = "NEAR_DUPLICATE"
    else:
        verdict = "DISTINCT"
    return {
        "verdict": verdict,
        "candidate_positive_scored_pixels": int(pc.sum()),
        "reference_count": len(rows),
        "reference_history_available": bool(rows),
        "verdict_is_artifact_similarity_only": True,
        "continuous_caveat": "Jaccard uses >0.5 support; empty support does not prove continuous-score similarity. Exact values and absolute differences are also reported.",
        "nearest": rows[:5],
        "threshold_near_duplicate_jaccard": NEAR_DUP_JACCARD,
        "note": (
            "Only pixels outside the known-fault mask and inside the footprint can change a score "
            "(DrivenData forum topic 11516 posts 2 and 4)."
        ),
    }


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text())
