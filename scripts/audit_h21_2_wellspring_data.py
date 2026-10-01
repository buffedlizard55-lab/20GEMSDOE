#!/usr/bin/env python3
"""Pre-preregistration QA audit of the GDR 1391 wellspring chemistry extract.

This audit examines ONLY schema-level facts: row counts, layer membership, unit
plausibility, missingness, duplicate sampling per raster cell, thermalclass
spelling variants, coordinate consistency against the competition template
geotransform, and the already-published overall distance-to-known-fault
distribution (a sampling-bias descriptor taken from the committed CI evidence).

It deliberately does NOT compute any fold-level information, any overlap with
the label raster, any candidate score field, or any DTI. Running it therefore
cannot tune the H21-2 preregistration against holdout outcomes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.paths import DATA_DIR, EVIDENCE_DIR  # noqa: E402

CSV_PATH = ROOT / "evidence" / "ci" / "gdr_wellspring_in_footprint.csv"
OUT_PATH = EVIDENCE_DIR / "h21_2_wellspring_audit.json"
GEOTHERM_COLS = ["geothermquartz_c", "geothermchalc_c", "geothermcat_c"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stats(s: pd.Series) -> dict:
    s = s.dropna()
    return {
        "n": int(len(s)),
        "min": round(float(s.min()), 2) if len(s) else None,
        "p25": round(float(s.quantile(0.25)), 2) if len(s) else None,
        "median": round(float(s.median()), 2) if len(s) else None,
        "p75": round(float(s.quantile(0.75)), 2) if len(s) else None,
        "max": round(float(s.max()), 2) if len(s) else None,
    }


def main() -> int:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(CSV_PATH)
    df = pd.read_csv(CSV_PATH)
    n_rows = len(df)

    layers = df["layer"].value_counts().to_dict()
    cells = df[["row", "col"]].drop_duplicates()
    per_cell = df.groupby(["row", "col"]).size()

    # Unit plausibility (degrees Celsius). Does not alter data; counts only.
    units = {}
    for c in ["temp_c", *GEOTHERM_COLS]:
        s = df[c].dropna()
        units[c] = {
            **stats(s),
            "n_below_0C": int((s < 0).sum()),
            "n_above_350C": int((s > 350).sum()),
        }

    geotherm_availability = {
        "records_with_ge1_geothermometer": int((df[GEOTHERM_COLS].notna().sum(axis=1) >= 1).sum()),
        "records_with_ge2_geothermometers": int((df[GEOTHERM_COLS].notna().sum(axis=1) >= 2).sum()),
        "records_with_3_geothermometers": int((df[GEOTHERM_COLS].notna().sum(axis=1) == 3).sum()),
        "chemistry_layer_records": int(df["layer"].str.contains("chemistry").sum()),
    }
    chem = df[df["layer"].str.contains("chemistry")]
    chem_avail = chem[GEOTHERM_COLS].notna().sum(axis=1)
    cell_max_estimators = chem.assign(k=chem_avail).groupby(["row", "col"])["k"].max()
    cells_with_ge2 = int((cell_max_estimators >= 2).sum())
    geotherm_availability["chemistry_cells_with_ge2_estimators"] = cells_with_ge2

    thermalclass_raw = df["thermalclass"].value_counts(dropna=False).to_dict()
    normalized = (
        df["thermalclass"].astype("string").str.strip().str.lower().value_counts(dropna=False).to_dict()
    )
    spelling_variants = sorted({str(v) for v in df["thermalclass"].dropna().unique()})

    # Coordinate consistency: expected pixel center from template geotransform.
    with rasterio.open(DATA_DIR / "sample_submission.tif") as ds:
        tr = ds.transform
        tmpl_shape = (ds.height, ds.width)
    exp_x = tr.c + (df["col"] + 0.5) * tr.a
    exp_y = tr.f + (df["row"] + 0.5) * tr.e
    dx = (df["utm_x"] - exp_x).abs()
    dy = (df["utm_y"] - exp_y).abs()
    coord_check = {
        "n_rows_checked": n_rows,
        "max_abs_x_offset_m": round(float(dx.max()), 2),
        "max_abs_y_offset_m": round(float(dy.max()), 2),
        "rows_beyond_half_cell_50m": int(((dx > 50.0) | (dy > 50.0)).sum()),
        "template_shape_hw": list(tmpl_shape),
        "row_minmax": [int(df["row"].min()), int(df["row"].max())],
        "col_minmax": [int(df["col"].min()), int(df["col"].max())],
    }

    # Sampling-bias descriptor (already published in CI evidence; NOT an outcome).
    dist = {}
    for layer, g in df.groupby("layer"):
        d = g["dist_known_fault_px"].dropna()
        dist[layer] = {
            **stats(d),
            "frac_within_10px_1km": round(float((d <= 10).mean()), 4) if len(d) else None,
            "frac_beyond_30px_3km": round(float((d >= 30).mean()), 4) if len(d) else None,
        }

    report = {
        "audit_of": str(CSV_PATH.relative_to(ROOT)),
        "input_sha256": sha256(CSV_PATH),
        "row_count": n_rows,
        "layer_counts": {k: int(v) for k, v in layers.items()},
        "unique_raster_cells": int(len(cells)),
        "records_per_cell": {
            "median": float(per_cell.median()),
            "p90": float(per_cell.quantile(0.9)),
            "max": int(per_cell.max()),
        },
        "unit_plausibility_degC": units,
        "geothermometer_availability": geotherm_availability,
        "thermalclass": {
            "raw_variants": {str(k): int(v) for k, v in thermalclass_raw.items()},
            "normalized_counts": {str(k): int(v) for k, v in normalized.items()},
            "distinct_spellings": spelling_variants,
            "note": "Whitespace/case variants exist (e.g. 'Hot '); any downstream use must normalize.",
        },
        "coordinate_consistency_vs_template": coord_check,
        "sampling_bias_distance_to_catalogue_px": dist,
        "excluded_by_design": [
            "no fold or quadrant assignment",
            "no overlap with labels.tif",
            "no candidate field construction",
            "no DTI or score of any kind",
        ],
        "interpretation_limits": (
            "Field semantics/units come from GDR 1391 layer/column names ('*_c' = degrees Celsius); "
            "sample dates, analytical-batch comparability, and well depth-dependence are NOT resolved "
            "by this audit. Bottom-hole well temperatures increase with depth regardless of faults; "
            "measured temperature is therefore not interchangeable with a chemical geothermometer."
        ),
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"wrote": str(OUT_PATH.relative_to(ROOT)),
                      "rows": n_rows,
                      "cells_with_ge2_estimators": cells_with_ge2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
