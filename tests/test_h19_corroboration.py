"""Audit regressions for historical H20 hypotheses, reported metrics and local research artifacts.

These tests preserve evidence labels and format checks; they do not independently validate
hidden-fault performance or establish that the historical metrics are reproducible.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from gems.footprint import load_footprint
from gems.hypotheses import HYPOTHESIS_SPECS, fit_power_law_population, synthesize_h20_nnpu_corroborated
from gems.paths import DATA_DIR, DOWNLOADS_DIR, EVIDENCE_DIR, SITE_DATA_DIR, TEMPLATE_PATH
from gems.submission import check_variants


def test_preregistered_hypotheses_complete() -> None:
    assert len(HYPOTHESIS_SPECS) == 5
    ids = [h.id for h in HYPOTHESIS_SPECS]
    assert ids == ["H20-1", "H20-2", "H20-3", "H20-4", "H20-5"]
    for h in HYPOTHESIS_SPECS:
        assert h.layers and h.physical_signature and h.why_unmapped_not_catalogued
        assert h.differs_from_prior_repos and h.external_sources
        assert len(h.lines_satisfied) + len(h.lines_not_satisfied) == 4


def test_power_law_scaling_report() -> None:
    rep = json.loads((EVIDENCE_DIR / "power_law_scaling_report.json").read_text())
    vec = rep["source_vector"]
    rast = rep["source_raster_skeleton"]
    assert vec["traces_in_grid"] == 1125
    assert rast["connected_traces_in_footprint"] == 3199
    assert rast["positive_pixels_in_footprint"] == 60988
    f1800 = rast["fits_by_l_min"]["1800"]
    assert 1.70 <= f1800["alpha_ols"] <= 1.80
    assert f1800["r2_loglog"] >= 0.99
    assert f1800["predicted_unmapped_short_traces"] > 20000
    f1650 = rast["fits_by_l_min"]["1650"]
    assert 0.023 <= f1650["predicted_missing_footprint_fraction"] <= 0.026


def test_backward_thermal_geochem_report() -> None:
    rep = json.loads((EVIDENCE_DIR / "backward_thermal_geochem_report.json").read_text())
    ds = rep["datasets"]
    ws = ds["gdr1391_wellspring"]
    pr = ds["gdr1391_2m_temperature_probes"]
    pa = ds["gdr1391_paleo_geothermal_deposits"]
    assert ws["total_records_in_footprint"] == 27092
    assert ws["thermal_or_geochem_anomalies"] == 7859
    assert ws["orphan_gt_500m_fraction"] > 0.70
    assert pr["total_stations_in_footprint"] == 3038
    assert pr["anomalous_f2mdab_ge_1_5c"] == 687
    assert pr["orphan_gt_500m_fraction"] > 0.80
    assert pa["total_sites_in_footprint"] == 372
    assert pa["orphan_gt_500m_fraction"] > 0.70


def test_dem1m_high_prior_openness_lrm_ci_artifacts() -> None:
    audit = json.loads((EVIDENCE_DIR / "ci" / "dem1m_tile_audit.json").read_text())
    assert audit["ok"] is True
    assert audit["tiles_requested"] == 8
    assert audit["tiles_succeeded"] == 8
    assert audit["total_covered_footprint_cells_100m"] == 71974
    npz = np.load(EVIDENCE_DIR / "ci" / "dem1m_high_prior_openness_lrm.npz")
    for k in ("cov_fp_indices", "lrm_abs_max", "lrm_grad_max", "openness_asymm_max", "openness_dipole_max"):
        assert k in npz
        assert len(npz[k]) == 71974


def test_historical_holdout_and_corridor_ledgers_are_not_submission_evidence() -> None:
    res = json.loads((EVIDENCE_DIR / "spatial_holdout_results.json").read_text())
    assert res["audit_status"] == "HISTORICAL_UNREPRODUCED_KNOWN_CATALOGUE_PROXY_NO_SUBMISSION_RECOMMENDATION"
    assert res["submission_recommendation"] is False
    assert "not hidden competition labels" in res["evaluation_scope"].lower()
    s = res["summary"]
    for key in ("H20_1_SAR_nnPU_MultiLine_Corroborated", "H20_5_Calibrated_Continuous_SoftTail_nnpu"):
        assert s[key]["evidence_status"] == "historical, unreproduced known-catalogue proxy"
        assert s[key]["submission_eligible"] is False
        assert s[key]["submission_recommendation"] is False

    corridors = json.loads((EVIDENCE_DIR / "candidate_corroboration_ledger.json").read_text())
    assert len(corridors) >= 16
    assert all(c["status"] == "MODEL_CANDIDATE_NOT_OBSERVED_OR_VERIFIED_FAULT" for c in corridors)
    assert all(c["submission_eligible"] is False for c in corridors)
    assert not any(c["disposition"].startswith("PROMOTED") for c in corridors)


def test_research_artifact_files_pass_local_format_checks_without_promotion(real_data) -> None:
    manifest = json.loads((SITE_DATA_DIR / "submissions.json").read_text())
    by_key = {c["key"]: c for c in manifest["candidates"]}
    assert set(by_key.keys()) == {"h20-1", "h20-5"}
    assert manifest["claims"]["score_predicted"] is False

    fp = load_footprint()
    for key in ("h20-1", "h20-5"):
        c = by_key[key]
        assert c["gate_eligible"] is False
        assert "not recommended" in c["title"].lower()
        tif_path = DOWNLOADS_DIR / c["files"]["tif"]["name"]
        fin_path = DOWNLOADS_DIR / c["files"]["tif_allfinite"]["name"]
        zip_path = DOWNLOADS_DIR / c["files"]["zip"]["name"]
        assert tif_path.exists() and fin_path.exists() and zip_path.exists()

        chk_nan = check_variants(tif_path, TEMPLATE_PATH)
        chk_fin = check_variants(fin_path, TEMPLATE_PATH)
        assert chk_nan["ok_to_upload"] is True and not chk_nan["hard_failures"]
        assert chk_fin["ok_to_upload"] is True and not chk_fin["hard_failures"]
        assert chk_nan["official_format_compliant"] is True

        with rasterio.open(tif_path) as src:
            arr = src.read(1)
            assert src.shape == (3730, 3292)
            assert str(src.crs) == "EPSG:32611"
            assert src.dtypes == ("float32",)
            inside = arr[fp]
            outside = arr[~fp]
            assert np.isfinite(inside).all()
            assert float(inside.min()) >= 0.0 and float(inside.max()) <= 1.0
            assert np.isnan(outside).all()
