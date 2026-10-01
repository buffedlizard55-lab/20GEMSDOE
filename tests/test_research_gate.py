from __future__ import annotations

import json

import numpy as np
import pytest

from gems.lineaments import fill_and_guard, hessian_line_response, scalar_low_control
from gems.multiple_testing import exact_paired_signflip_test, holm_bonferroni_and_bh_correction
from gems.research_gate import FinalConfirmationGate, SingleUseRun


def test_persistent_single_shot_is_global_and_consumed_even_on_failure(tmp_path):
    path = tmp_path / "run.json"
    with pytest.raises(ValueError, match="failed run"):
        with SingleUseRun(path, "A", {"protocol": "frozen"}):
            raise ValueError("failed run")
    assert json.loads(path.read_text())["status"] == "CONSUMED_FAILED"
    with pytest.raises(RuntimeError, match="already consumed"):
        with SingleUseRun(path, "B", {}):
            pass


def test_final_gate_blocks_synthetic_or_reused_data_and_requires_full_hashes(tmp_path):
    hashes = {k: "a" * 64 for k in ("labels_sha256", "split_sha256", "candidate_sha256", "protocol_sha256")}
    manifest = {"target_kind": "synthetic", "previously_evaluated": False,
                "used_for_training_or_selection": False, "labels_sha256": "a" * 64, "source_url": "https://example.org"}
    with pytest.raises(ValueError, match="independent adjudication"):
        FinalConfirmationGate(tmp_path / "final.json", "A", hashes, manifest)
    manifest["target_kind"] = "independently_adjudicated_fault_presence"
    manifest["previously_evaluated"] = True
    with pytest.raises(ValueError, match="already evaluated"):
        FinalConfirmationGate(tmp_path / "final.json", "A", hashes, manifest)
    manifest["previously_evaluated"] = False
    with FinalConfirmationGate(tmp_path / "final.json", "A", hashes, manifest):
        pass
    with pytest.raises(RuntimeError, match="already consumed"):
        with FinalConfirmationGate(tmp_path / "final.json", "B", hashes, manifest):
            pass


def test_exact_signflip_no_pseudoreplication_and_frozen_family_size():
    test = exact_paired_signflip_test([0.2] * 4, [0.1] * 4)
    assert test["p_value_raw"] == 1 / 16
    assert exact_paired_signflip_test([0.1] * 4, [0.2] * 4)["p_value_raw"] == 1
    assert exact_paired_signflip_test([0.1] * 4, [0.1] * 4)["p_value_raw"] == 1
    corrected = holm_bonferroni_and_bh_correction([
        {"id": f"H{x}", "p_value_raw": test["p_value_raw"] if x == 0 else 1.0} for x in range(5)
    ])
    assert corrected[0]["m_total_hypotheses_tested"] == 5
    assert corrected[0]["p_value_holm_bonferroni"] == 0.3125
    assert not corrected[0]["pass_holm_fwer"]


@pytest.mark.parametrize("p", [float("nan"), -0.1, 1.1])
def test_correction_rejects_invalid_p(p):
    with pytest.raises(ValueError):
        holm_bonferroni_and_bh_correction([{"id": "X", "p_value_raw": p}])


def test_trough_operator_detects_correct_polarity_not_a_blob_or_boundary():
    yy, xx = np.mgrid[:121, :121]
    line = -np.exp(-((xx - 60) ** 2) / (2 * 3**2)).astype(np.float32)
    fp = np.ones(line.shape, dtype=bool)
    filled, interior, meta = fill_and_guard(line, fp)
    trough, _ = hessian_line_response(filled, interior, polarity="trough", sigmas=(2, 4))
    bright, _ = hessian_line_response(filled, interior, polarity="ridge", sigmas=(2, 4))
    assert trough[60, 60] > bright[60, 60] + 0.2
    assert trough[~interior].sum() == 0
    assert np.isfinite(trough).all() and trough.min() >= 0 and trough.max() <= 1
    blob = -np.exp(-((xx - 60)**2 + (yy - 60)**2) / (2 * 3**2)).astype(np.float32)
    blob_response, _ = hessian_line_response(blob, interior, sigmas=(2, 4))
    assert blob_response[60, 60] < trough[60, 60]
    flat, _ = hessian_line_response(np.ones(fp.shape, np.float32), interior)
    assert not flat.any()


def test_invalid_cells_filled_before_derivatives_and_control_is_bounded():
    x = np.zeros((100, 100), np.float32)
    x[40, 40] = -np.finfo(np.float32).max
    x[50, 50] = np.nan
    filled, interior, meta = fill_and_guard(x, np.ones(x.shape, bool))
    assert meta["invalid_inside_cells"] == 2 and np.isfinite(filled).all()
    assert scalar_low_control(filled, interior).sum() == 0
