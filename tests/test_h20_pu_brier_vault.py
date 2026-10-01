"""Unit and integration tests for 20GEMSDOE Positive-Unlabeled (SAR-nnPU) risk estimation,
Murphy (1973) Brier-score decomposition & out-of-fold calibration, Holm-Bonferroni / BH
multiple-comparisons correction, and single-shot Vault Holdout enforcement.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from gems.calibration import OutOfFoldPUCalibrator, brier_decomposition_murphy1973
from gems.multiple_testing import (
    VaultHoldoutGate,
    holm_bonferroni_and_bh_correction,
    make_dev_and_vault_subblocks,
    paired_subblock_significance_test,
)
from gems.paths import EVIDENCE_DIR
from gems.pu_learning import (
    KiryoNNPULinearHead,
    compute_pu_risk_metrics,
    estimate_power_law_class_prior,
)


def test_kiryo_nnpu_risk_clamps_negative_unbiased_risk() -> None:
    # Construct a case where E_U[l_-] - pi * E_P[l_-] < 0 so uPU is negative while nnPU clamps to 0
    logits_p = np.full(100, +3.0, dtype=np.float32)  # high l_-(g) = expit(+g) on P
    logits_u = np.full(500, -3.0, dtype=np.float32)  # low l_-(g) = expit(+g) on U
    res = compute_pu_risk_metrics(logits_p, logits_u, pi=0.25)
    assert res["unbiased_neg_risk_raw"] < 0.0
    assert res["nnpu_neg_risk_clamped"] == 0.0
    assert res["was_clamped_non_negative"] is True
    assert res["R_nnPU"] >= 0.0


def test_kiryo_nnpu_linear_head_separates_synthetic_pu_data() -> None:
    rng = np.random.default_rng(20260930)
    x_pos = rng.normal(loc=1.5, scale=0.8, size=(300, 6)).astype(np.float32)
    x_neg = rng.normal(loc=-1.0, scale=0.8, size=(1200, 6)).astype(np.float32)
    x_hid = rng.normal(loc=1.4, scale=0.8, size=(200, 6)).astype(np.float32)
    X_unl = np.vstack([x_neg, x_hid])
    X_all = np.vstack([x_pos, X_unl])

    head = KiryoNNPULinearHead(pi=500.0 / 1700.0, lr=0.05, n_epochs=25, batch_size=256)
    head.fit(x_pos, X_unl)
    probs = head.predict_proba(X_all)
    assert probs.shape == (1700,)
    assert float(probs[:300].mean()) > float(probs[300:1500].mean()) + 0.25
    assert float(probs[1500:].mean()) > float(probs[300:1500].mean()) + 0.20


def test_murphy_1973_brier_decomposition_identity_and_calibration() -> None:
    rng = np.random.default_rng(42)
    y_true = rng.binomial(1, 0.35, size=5000).astype(np.float64)
    p_pred = np.clip(0.35 + 0.25 * (y_true - 0.35) + rng.normal(0.0, 0.1, size=5000), 0.01, 0.99)
    res = brier_decomposition_murphy1973(p_pred, y_true, n_bins=10)
    # Murphy (1973) exact binned identity: Brier_partition = REL - RES + UNC
    lhs = res["brier_score_murphy_partition"]
    rhs = res["reliability_REL"] - res["resolution_RES"] + res["uncertainty_UNC"]
    assert lhs == pytest.approx(rhs, abs=1e-5)
    assert res["brier_score_exact"] == pytest.approx(lhs, abs=5e-3)
    assert 0.0 <= res["expected_calibration_error_ECE"] <= 1.0


def test_out_of_fold_pu_calibrator_reduces_reliability_error() -> None:
    rng = np.random.default_rng(7)
    n = 4000
    true_p = rng.uniform(0.05, 0.95, size=n)
    y = rng.binomial(1, true_p).astype(np.float32)
    # Underconfident raw scores compressed by factor 0.45
    raw_s = (0.45 * true_p).astype(np.float32)
    eval_mask = np.ones(n, dtype=bool)
    fold_ids = np.repeat(np.arange(4, dtype=np.int8), n // 4)
    cal = OutOfFoldPUCalibrator(c_labeling_freq=0.45)
    cal_p = cal.fit_transform_oof(raw_s, y, eval_mask, fold_ids)
    before = brier_decomposition_murphy1973(raw_s, y, n_bins=10)
    after = brier_decomposition_murphy1973(cal_p, y, n_bins=10)
    assert after["reliability_REL"] < before["reliability_REL"] * 0.25
    assert after["expected_calibration_error_ECE"] < before["expected_calibration_error_ECE"] * 0.35


def test_holm_bonferroni_and_vault_holdout_single_touch_gate() -> None:
    tests = [
        {"id": "T1", "p_value_raw": 0.0004},
        {"id": "T2", "p_value_raw": 0.0003},
        {"id": "T3", "p_value_raw": 0.0380},
        {"id": "T4", "p_value_raw": 0.8500},
    ]
    corrected = holm_bonferroni_and_bh_correction(tests, alpha=0.05)
    by_id = {r["id"]: r for r in corrected}
    assert by_id["T2"]["pass_holm_bonferroni_fwer_0_05"] is True
    assert by_id["T1"]["pass_holm_bonferroni_fwer_0_05"] is True
    assert by_id["T4"]["pass_holm_bonferroni_fwer_0_05"] is False

    # Verify VaultHoldoutGate allows at most 1 touch per candidate and blocks repeated touches
    gate = VaultHoldoutGate(max_allowed_touches=2)
    fp = np.ones((40, 40), dtype=bool)
    quad = np.zeros((40, 40), dtype=np.int8)
    quad[:20, 20:] = 1
    quad[20:, :20] = 2
    quad[20:, 20:] = 3
    dev_b, vault_m, meta = make_dev_and_vault_subblocks(fp, quad)
    assert meta["n_dev_subblocks"] == 16
    assert 0.18 <= meta["vault_holdout_fraction"] <= 0.22

    def dummy_eval() -> dict:
        return {"passed_vault": True, "vault_mean_dense_dti": 0.192, "vault_mean_sparse_dti": 0.070}

    out = gate.evaluate_once("cand_A", dummy_eval)
    assert out["passed_vault"] is True
    with pytest.raises(RuntimeError, match="already evaluated"):
        gate.evaluate_once("cand_A", dummy_eval)


def test_published_20gemsdoe_pu_brier_and_committee_reports() -> None:
    pu = json.loads((EVIDENCE_DIR / "pu_prior_and_risk_report.json").read_text())
    assert 0.035 <= pu["global_power_law_prior"]["pi_total"] <= 0.039
    assert 0.30 <= pu["global_power_law_prior"]["labeling_frequency_c"] <= 0.34

    brier = json.loads((EVIDENCE_DIR / "calibration_brier_report.json").read_text())
    raw_m = brier["models"]["Raw_MultiLine_Corroborated_PreCalibration"]
    cal_m = brier["models"]["OOF_PU_Isotonic_Calibrated_SAR_nnPU_H20_5"]
    assert cal_m["reliability_REL"] < raw_m["reliability_REL"] * 0.02
    assert cal_m["expected_calibration_error_ECE"] < 0.01
    b70 = cal_m["stated_0_70_audit"]
    assert b70["count"] > 10000
    assert 0.66 <= b70["mean_stated_probability"] <= 0.72
    assert 0.64 <= b70["empirical_hidden_fault_hit_rate"] <= 0.72

    comm = json.loads((EVIDENCE_DIR / "dissertation_committee_audit.json").read_text())
    mc = {r["id"]: r for r in comm["multiple_comparisons_table"]}
    assert mc["H20-1_Primary_Dense_vs_H16-1"]["pass_holm_bonferroni_fwer_0_05"] is True
    assert mc["H20-1_Primary_Sparse_vs_H16-1"]["pass_holm_bonferroni_fwer_0_05"] is True
    v = comm["vault_holdout_gate"]["results"]
    assert v["H20-1_SAR_nnPU_Primary"]["passed_vault"] is True
    assert v["H20-5_Calibrated_Continuous_Secondary"]["passed_vault"] is True
