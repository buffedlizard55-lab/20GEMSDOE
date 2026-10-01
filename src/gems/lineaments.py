"""Label-free magnetic trough geometry (H22-2), not calibrated fault probabilities.

Frozen parameters/interpretation: docs/research/preregistration_h22_2.md.
The demagnetization mechanism already exists in H16-4; only this operator is new.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter

SIGMAS = (2.0, 4.0, 8.0)
BETA = 0.5
EDGE_GUARD_PX = 32


def fill_and_guard(signal: np.ndarray, footprint: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    x = np.asarray(signal, dtype=np.float32)
    fp = np.asarray(footprint, dtype=bool)
    if x.ndim != 2 or x.shape != fp.shape or not fp.any():
        raise ValueError("signal and nonempty footprint must be matching 2D arrays")
    invalid = ~np.isfinite(x) | (x < -1e20)
    valid = fp & ~invalid
    if not valid.any():
        raise ValueError("no valid source cells")
    nearest = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = x[tuple(nearest)].astype(np.float32, copy=False)
    interior = distance_transform_edt(fp) > EDGE_GUARD_PX
    if not interior.any():
        raise ValueError("edge guard leaves no interior cells")
    return filled, interior, {
        "invalid_inside_cells": int((fp & invalid).sum()),
        "interior_cells": int(interior.sum()),
        "edge_guard_cells": int((fp & ~interior).sum()),
        "fill": "nearest valid footprint value (labels not used)",
    }


def hessian_line_response(
    signal: np.ndarray,
    interior: np.ndarray,
    *,
    polarity: str = "trough",
    sigmas: tuple[float, ...] = SIGMAS,
    beta: float = BETA,
) -> tuple[np.ndarray, dict]:
    """Frangi-style scale-normalized Hessian response, bright ridge or dark trough.

    ``C`` uses feature values only. No fault labels, catalogue proximity, target
    calibration or test metrics enter normalization. Arrays are float32 throughout.
    """
    x = np.asarray(signal, dtype=np.float32)
    inside = np.asarray(interior, dtype=bool)
    if x.ndim != 2 or x.shape != inside.shape or not inside.any() or not np.isfinite(x).all():
        raise ValueError("finite signal and nonempty matching interior required")
    if polarity not in ("trough", "ridge") or beta <= 0 or not np.isfinite(beta):
        raise ValueError("invalid polarity or beta")
    if not sigmas or any(s <= 0 or not np.isfinite(s) for s in sigmas):
        raise ValueError("positive finite sigmas required")
    x = x - np.float32(np.median(x[inside]))
    if polarity == "trough":
        x = -x
    score = np.zeros(x.shape, dtype=np.float32)
    meta = {}
    eps = np.finfo(np.float32).eps
    for sigma in sigmas:
        hxx = gaussian_filter(x, sigma, order=(0, 2), mode="nearest", truncate=4.0) * sigma**2
        hxy = gaussian_filter(x, sigma, order=(1, 1), mode="nearest", truncate=4.0) * sigma**2
        hyy = gaussian_filter(x, sigma, order=(2, 0), mode="nearest", truncate=4.0) * sigma**2
        trace = hxx + hyy
        disc = np.sqrt(np.maximum((hxx - hyy)**2 + 4 * hxy**2, 0.0))
        a, b = 0.5 * (trace + disc), 0.5 * (trace - disc)
        a_small = np.abs(a) <= np.abs(b)
        small, large = np.where(a_small, a, b), np.where(a_small, b, a)
        strength = np.sqrt(small**2 + large**2)
        c = float(np.quantile(strength[inside], 0.90))
        if c > eps:
            ratio = np.abs(small) / (np.abs(large) + eps)
            response = np.where(
                (large < 0) & inside,
                np.exp(-ratio**2 / (2 * beta**2)) * (1 - np.exp(-strength**2 / (2 * c**2))),
                0,
            ).astype(np.float32)
            np.maximum(score, response, out=score)
        meta[str(sigma)] = {"C_q90_strength": c}
        del hxx, hxy, hyy, trace, disc, a, b, a_small, small, large, strength
    return score, meta


def scalar_low_control(signal: np.ndarray, interior: np.ndarray) -> np.ndarray:
    """Fixed label-free scalar-low control, shifted to the same [0,1] score range."""
    vals = signal[interior]
    lo, hi = float(vals.min()), float(vals.max())
    score = np.zeros(signal.shape, dtype=np.float32)
    if hi > lo:
        score[interior] = np.clip((hi - vals) / (hi - lo), 0, 1)
    return score
