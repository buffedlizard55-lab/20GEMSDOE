"""H21-2: multi-geothermometer coherence field (preregistered, frozen constants).

Every constant below is frozen in ``docs/research/preregistration_h21_2.md``
before the holdout evaluator is run. Do not change them to tune results; any
post-hoc change voids the preregistration.

Physical idea (INFERENCE, not an established relation): several independent
chemical geothermometers (quartz, chalcedony, Na-K-Ca cation) measured at the
same spring or well give independent estimates of reservoir temperature. Where
two or more estimators agree on a hot reservoir temperature, the site is more
likely to tap a fault-controlled upflow conduit than a site with a single or
mutually inconsistent estimate. Such concordant-upflow sites may sit on
structures absent from the USGS/INGENIOUS fault catalogue.

Grid note: the competition grid is 100 m per cell (3292 x 3730, EPSG:32611),
so SIGMA_PX below is 500 m and the 300 m DTI kernel is 3 cells.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt, gaussian_filter

# ---- Frozen constants (see preregistration_h21_2.md) ------------------------
GEOTHERM_COLUMNS: tuple[str, ...] = ("geothermquartz_c", "geothermchalc_c", "geothermcat_c")
VALID_RANGE_C: tuple[float, float] = (0.0, 350.0)   # outside -> invalid estimate
MIN_ESTIMATORS: int = 2                              # estimators required per cell
T_HOT_MIN_C: float = 120.0                           # moderate-temperature reservoir cutoff
REL_SPREAD_MAX: float = 0.25                         # max (spread / t_med) for coherence
SIGMA_PX: float = 5.0                                # 500 m Gaussian at 100 m/cell
KERNEL_TRUNCATE: float = 3.0                         # 3-sigma kernel support
CONTROL_TEMP_MIN_C: float = 25.0                     # thermal-point control threshold
CONTROL_RANDOM_SEED: int = 4243                      # pseudo-site control seed
CHEMISTRY_LAYER_TOKEN: str = "chemistry"             # layer-name filter
COORD_MAX_OFFSET_PX: float = 1.0                     # QA tolerance for provided row/col
WEIGHT_REF_C: float = T_HOT_MIN_C                    # weight reference temperature


@dataclass(frozen=True)
class SiteTable:
    """Per-cell coherence summary returned by :func:`site_estimates`."""

    row: np.ndarray          # int32 cell rows
    col: np.ndarray          # int32 cell cols
    n_est: np.ndarray        # int32 number of valid estimators (0-3)
    t_med: np.ndarray        # float32 median of estimator medians (degC)
    spread_rel: np.ndarray   # float32 (max-min)/max(t_med, eps)
    agreement: np.ndarray    # float32 in [0, 1]
    eligible: np.ndarray     # bool: n_est>=MIN_ESTIMATORS and t_med>=T_HOT_MIN_C and agreement>0
    weight: np.ndarray       # float32 (t_med / WEIGHT_REF_C) * agreement for eligible cells else 0


def positions_from_utm(
    df: pd.DataFrame, transform, *, qa_max_offset_px: float = COORD_MAX_OFFSET_PX
) -> pd.DataFrame:
    """Compute (row, col) from utm_x/utm_y through the template geotransform.

    The extract's provided row/col is kept only as a QA cross-check; positions
    are always re-derived here so the transform is the single source of truth.
    Rows whose UTM position falls outside the grid are dropped by the caller
    (not here, because the caller knows the grid shape).
    """
    out = df.copy()
    px_width = float(transform.a)
    py_height = float(-transform.e)
    out["row_from_utm"] = np.rint((transform.f - df["utm_y"].to_numpy()) / py_height - 0.5).astype(np.int32)
    out["col_from_utm"] = np.rint((df["utm_x"].to_numpy() - transform.c) / px_width - 0.5).astype(np.int32)
    qa = (
        (out["row_from_utm"] - out["row"]).abs() > qa_max_offset_px
    ) | ((out["col_from_utm"] - out["col"]).abs() > qa_max_offset_px)
    out["coord_qa_mismatch"] = qa.to_numpy()
    return out


def sanitize_geothermometers(df: pd.DataFrame) -> pd.DataFrame:
    """Null out implausible geothermometer estimates and non-finite values."""
    out = df.copy()
    lo, hi = VALID_RANGE_C
    for col in GEOTHERM_COLUMNS:
        v = pd.to_numeric(out[col], errors="coerce")
        v = v.mask(~np.isfinite(v))
        v = v.mask((v < lo) | (v > hi))
        out[col] = v
    return out


def site_estimates(df: pd.DataFrame) -> SiteTable:
    """Aggregate chemistry records to per-cell coherence estimates."""
    eps = np.finfo(np.float64).eps
    groups = df.groupby(["row_from_utm", "col_from_utm"])
    rows, cols, n_est, t_med, spread_rel = [], [], [], [], []
    for (r, c), g in groups:
        est_vals = []
        for col in GEOTHERM_COLUMNS:
            vals = g[col].dropna().to_numpy(dtype=np.float64)
            if vals.size:
                est_vals.append(float(np.median(vals)))
        est = np.asarray(est_vals, dtype=np.float64)
        rows.append(int(r))
        cols.append(int(c))
        n_est.append(int(est.size))
        if est.size:
            med = float(np.median(est))
            t_med.append(med)
            spread_rel.append(float((est.max() - est.min()) / max(med, eps)) if est.size > 1 else 0.0)
        else:
            t_med.append(np.nan)
            spread_rel.append(np.nan)
    n_est_a = np.asarray(n_est, dtype=np.int32)
    t_med_a = np.asarray(t_med, dtype=np.float32)
    spread_a = np.asarray(spread_rel, dtype=np.float32)

    agreement = np.clip(1.0 - spread_a.astype(np.float64) / REL_SPREAD_MAX, 0.0, 1.0)
    eligible = (
        (n_est_a >= MIN_ESTIMATORS)
        & np.isfinite(t_med_a)
        & (t_med_a >= T_HOT_MIN_C)
        & (agreement > 0.0)
    )
    weight = np.where(eligible, (t_med_a.astype(np.float64) / WEIGHT_REF_C) * agreement, 0.0)
    return SiteTable(
        row=np.asarray(rows, dtype=np.int32),
        col=np.asarray(cols, dtype=np.int32),
        n_est=n_est_a,
        t_med=t_med_a,
        spread_rel=spread_a,
        agreement=agreement.astype(np.float32),
        eligible=eligible,
        weight=weight.astype(np.float32),
    )


def _point_field(
    rows: np.ndarray,
    cols: np.ndarray,
    amps: np.ndarray,
    shape: tuple[int, int],
    footprint: np.ndarray,
) -> np.ndarray:
    """Sum of Gaussian kernels over point impulses, max-normalised inside footprint."""
    impulses = np.zeros(shape, dtype=np.float32)
    valid = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1]) & (amps > 0)
    if valid.any():
        np.add.at(impulses, (rows[valid], cols[valid]), amps[valid])
    if not impulses.any():
        return np.zeros(shape, dtype=np.float32)
    field = gaussian_filter(impulses, sigma=SIGMA_PX, truncate=KERNEL_TRUNCATE, mode="constant", cval=0.0)
    field = np.where(footprint, field, 0.0).astype(np.float32)
    peak = float(field.max()) if field.any() else 0.0
    if peak > 0.0:
        field = (field / peak).astype(np.float32)
    return field


def coherence_field(sites: SiteTable, shape: tuple[int, int], footprint: np.ndarray) -> np.ndarray:
    """Preregistered candidate field: weighted kernels at eligible coherent-hot cells only."""
    return _point_field(sites.row, sites.col, sites.weight, shape, footprint)


def thermal_control_cells(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Control C1 cells: any record with measured temp >= CONTROL_TEMP_MIN_C or Hot/Warm class."""
    temp = pd.to_numeric(df["temp_c"], errors="coerce")
    tclass = df["thermalclass"].astype("string").str.strip().str.lower()
    hot_or_warm = ((tclass == "hot") | (tclass == "warm")).fillna(False)
    keep = (temp >= CONTROL_TEMP_MIN_C).fillna(False) | hot_or_warm
    g = df.loc[keep.to_numpy(dtype=bool)]
    cells = g[["row_from_utm", "col_from_utm"]].drop_duplicates()
    return cells["row_from_utm"].to_numpy(np.int32), cells["col_from_utm"].to_numpy(np.int32)


def random_pseudo_sites(n: int, footprint: np.ndarray, seed: int = CONTROL_RANDOM_SEED) -> tuple[np.ndarray, np.ndarray]:
    """Control C2: ``n`` unique cells drawn uniformly without replacement from footprint cells."""
    yy, xx = np.nonzero(footprint)
    rng = np.random.default_rng(seed)
    n = min(int(n), yy.size)
    pick = rng.choice(yy.size, size=n, replace=False)
    return yy[pick].astype(np.int32), xx[pick].astype(np.int32)


def unit_field(rows: np.ndarray, cols: np.ndarray, shape: tuple[int, int], footprint: np.ndarray) -> np.ndarray:
    """Unit-amplitude kernel field over the given cells (controls C1 and C2)."""
    return _point_field(rows, cols, np.ones(len(rows), dtype=np.float32), shape, footprint)


def catalogue_transfer_field(known_outside_fold: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Control C3: Gaussian decay of distance to catalogue faults outside the held fold.

    A descriptive sampling-bias ceiling for the held fold: how well does "be near
    the catalogue mapped elsewhere" transfer into this quadrant at the same
    kernel scale and budget? Not a promotion candidate.
    """
    dist = distance_transform_edt(~known_outside_fold)
    field = np.exp(-(dist**2) / (2.0 * SIGMA_PX**2)).astype(np.float32)
    field = np.where(footprint, field, 0.0).astype(np.float32)
    peak = float(field.max()) if field.any() else 0.0
    if peak > 0.0:
        field = (field / peak).astype(np.float32)
    return field
