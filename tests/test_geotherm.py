"""Unit tests for the preregistered H21-2 geothermometer-coherence transform."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from affine import Affine

from gems.geotherm import (
    CONTROL_RANDOM_SEED,
    GEOTHERM_COLUMNS,
    REL_SPREAD_MAX,
    SIGMA_PX,
    T_HOT_MIN_C,
    catalogue_transfer_field,
    coherence_field,
    positions_from_utm,
    random_pseudo_sites,
    sanitize_geothermometers,
    site_estimates,
    thermal_control_cells,
    unit_field,
)

TF = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def _df(records):
    return pd.DataFrame(records)


def test_sanitize_bounds_and_nonfinite():
    df = _df(
        {
            "geothermquartz_c": [25.0, -5.0, 400.0, np.nan, np.inf],
            "geothermchalc_c": [0.0, 350.0, 350.1, np.nan, 10.0],
            "geothermcat_c": [np.nan, np.nan, np.nan, np.nan, np.nan],
        }
    )
    out = sanitize_geothermometers(df)
    q = out["geothermquartz_c"].to_numpy()
    assert q[0] == 25.0
    assert np.isnan(q[1]) and np.isnan(q[2]) and np.isnan(q[3]) and np.isnan(q[4])
    c = out["geothermchalc_c"].to_numpy()
    assert c[0] == 0.0 and c[1] == 350.0  # bounds are inclusive
    assert np.isnan(c[2])


def test_positions_from_utm_and_qa_flag():
    # Cell (row=10, col=20): expected center x = 243350 + 20.5*100, y = 4508550 - 10.5*100
    df = _df({"row": [10, 10], "col": [20, 20],
              "utm_x": [243350.0 + 2050.0, 243350.0 + 2050.0 + 300.0],
              "utm_y": [4508550.0 - 1050.0, 4508550.0 - 1050.0 - 300.0]})
    out = positions_from_utm(df, TF)
    assert out.loc[0, "row_from_utm"] == 10 and out.loc[0, "col_from_utm"] == 20
    assert not out.loc[0, "coord_qa_mismatch"]
    # second point shifts >1 px -> QA mismatch flagged
    assert out.loc[1, "coord_qa_mismatch"]


def _sites(records):
    df = positions_from_utm(sanitize_geothermometers(_df(records)), TF)
    return site_estimates(df)


def test_site_estimates_median_per_estimator_and_eligibility():
    # One cell with two quartz samples and one chalcedony sample, all coherent & hot.
    df = _df(
        {
            "row": [1, 1, 1],
            "col": [2, 2, 2],
            "utm_x": [243350.0 + 250.0] * 3,
            "utm_y": [4508550.0 - 150.0] * 3,
            "geothermquartz_c": [140.0, 160.0, np.nan],
            "geothermchalc_c": [np.nan, np.nan, 130.0],
            "geothermcat_c": [np.nan, np.nan, np.nan],
        }
    )
    s = _sites(df.to_dict("list") | {"temp_c": [np.nan] * 3, "thermalclass": [None] * 3, "layer": ["spring_chemistry_20220808"] * 3})
    assert s.n_est[0] == 2
    assert s.t_med[0] == pytest.approx((150.0 + 130.0) / 2.0, abs=1e-3)
    assert s.spread_rel[0] == pytest.approx((150.0 - 130.0) / 140.0, rel=1e-4)
    assert s.eligible[0]


def test_eligibility_rules():
    def cell(quartz, chalc, cat=np.nan):
        recs = {"row": [1], "col": [1], "utm_x": [243600.0], "utm_y": [4508400.0],
                "geothermquartz_c": [quartz], "geothermchalc_c": [chalc], "geothermcat_c": [cat]}
        return _sites(recs)

    # single estimator -> not eligible regardless of temperature
    s = cell(200.0, np.nan)
    assert s.n_est[0] == 1 and not s.eligible[0]
    # exactly at spread boundary -> agreement == 0 -> not eligible
    # spread/med == s  <=>  b = a*(2+s)/(2-s) for two estimators a < b
    t2 = T_HOT_MIN_C * (2.0 + REL_SPREAD_MAX) / (2.0 - REL_SPREAD_MAX)
    s = cell(T_HOT_MIN_C, t2)
    a, b = T_HOT_MIN_C, t2
    med = (a + b) / 2.0
    assert (b - a) / med == pytest.approx(REL_SPREAD_MAX, rel=1e-6)
    assert s.agreement[0] == pytest.approx(0.0, abs=1e-6)
    assert not s.eligible[0]
    # just under the boundary and above the temperature cutoff -> eligible
    s = cell(140.0, 150.0)
    assert s.eligible[0]
    expected_w = (145.0 / T_HOT_MIN_C) * (1.0 - (10.0 / 145.0) / REL_SPREAD_MAX)
    assert s.weight[0] == pytest.approx(expected_w, rel=1e-4)
    # cold but coherent -> not eligible
    s = cell(90.0, 95.0)
    assert not s.eligible[0] and s.weight[0] == 0.0


def test_coherence_field_normalisation_and_decay():
    shape = (101, 101)
    fp = np.ones(shape, dtype=bool)
    recs = {"row": [50], "col": [50], "utm_x": [243350.0 + 5050.0], "utm_y": [4508550.0 - 5050.0],
            "geothermquartz_c": [150.0], "geothermchalc_c": [140.0], "geothermcat_c": [np.nan]}
    s = _sites(recs)
    fld = coherence_field(s, shape, fp)
    assert fld[50, 50] == pytest.approx(1.0, abs=1e-6)
    assert fld[50, 50 + int(3 * SIGMA_PX) + 2] == 0.0  # beyond kernel support
    assert 0.0 < fld[50, 50 + 1] < 1.0
    # outside-footprint cells are zero
    fp2 = np.ones(shape, dtype=bool)
    fp2[:, 60:] = False
    fld2 = coherence_field(s, shape, fp2)
    assert np.all(fld2[:, 60:] == 0.0)
    # determinism
    assert np.array_equal(fld, coherence_field(s, shape, fp))


def test_empty_field_is_all_zero():
    shape = (20, 20)
    fp = np.ones(shape, dtype=bool)
    s = _sites({"row": [1], "col": [1], "utm_x": [243450.0], "utm_y": [4508450.0],
                "geothermquartz_c": [200.0], "geothermchalc_c": [np.nan], "geothermcat_c": [np.nan]})
    fld = coherence_field(s, shape, fp)
    assert not fld.any()


def test_thermal_control_selection_normalises_spelling():
    df = _df(
        {
            "row": [1, 2, 3, 4],
            "col": [1, 2, 3, 4],
            "utm_x": [243500.0, 243600.0, 243700.0, 243800.0],
            "utm_y": [4508400.0, 4508300.0, 4508200.0, 4508100.0],
            "temp_c": [np.nan, 24.9, 25.0, np.nan],
            "thermalclass": ["Hot ", None, None, "Cold"],
        }
    )
    out = positions_from_utm(df, TF)
    rows, cols = thermal_control_cells(out)
    got = set(zip(rows.tolist(), cols.tolist()))
    assert got == {(1, 1), (3, 3)}  # 'Hot ' counts; temp 25.0 counts; 24.9 and 'Cold' do not


def test_random_pseudo_sites_deterministic_unique():
    fp = np.zeros((50, 50), dtype=bool)
    fp[5:45, 5:45] = True
    r1, c1 = random_pseudo_sites(100, fp, seed=CONTROL_RANDOM_SEED)
    r2, c2 = random_pseudo_sites(100, fp, seed=CONTROL_RANDOM_SEED)
    assert len(r1) == 100 and len(set(zip(r1.tolist(), c1.tolist()))) == 100
    assert np.array_equal(r1, r2) and np.array_equal(c1, c2)
    assert fp[r1, c1].all()


def test_unit_and_catalogue_fields():
    shape = (30, 30)
    fp = np.ones(shape, dtype=bool)
    fld = unit_field(np.array([15], dtype=np.int32), np.array([15], dtype=np.int32), shape, fp)
    assert fld[15, 15] == pytest.approx(1.0)
    known = np.zeros(shape, dtype=bool)
    known[5, :] = True
    cat = catalogue_transfer_field(known, fp)
    assert cat[5, 10] == pytest.approx(1.0)
    assert cat[15, 10] < 0.2  # 10 px = 2*sigma decay
    assert cat.max() == pytest.approx(1.0)


def test_geotherm_column_order_is_frozen():
    assert GEOTHERM_COLUMNS == ("geothermquartz_c", "geothermchalc_c", "geothermcat_c")
