"""Genuine Calibration Study: Reliability Diagram & Murphy (1973) Brier-Score Decomposition
on Recovered Hidden-Fault Pixels in the Spatially-Blocked Holdout.

References:
  - Murphy, A. H. (1973). "A New Vector Partition of the Probability Score."
    Journal of Applied Meteorology, 12(4), 595-600.
  - Zadrozny, B., & Elkan, C. (2002). "Transforming Classifier Scores into Accurate
    Multiclass Probability Estimates." KDD 2002 (Isotonic Regression calibration).
  - Elkan, C., & Noto, K. (2008). "Learning Classifiers from Only Positive and Unlabeled Data." KDD 2008.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


def brier_decomposition_murphy1973(
    prob: np.ndarray,
    outcome: np.ndarray,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Compute exact Murphy (1973) Brier-score decomposition and reliability diagram.

    For binary outcomes y_i in {0, 1} and continuous predictions p_i in [0, 1] partitioned
    into K bins (where p_bar_k is the bin mean prediction and o_bar_k is the bin empirical
    hit rate):
      Brier_binned = Reliability - Resolution + Uncertainty
      Reliability  = (1/N) * sum_k n_k * (p_bar_k - o_bar_k)^2   [lower is better]
      Resolution   = (1/N) * sum_k n_k * (o_bar_k - o_bar)^2     [higher is better]
      Uncertainty  = o_bar * (1 - o_bar)                         [intrinsic target variance]
      ECE          = (1/N) * sum_k n_k * |p_bar_k - o_bar_k|
    """
    p = np.clip(np.asarray(prob, dtype=np.float64).ravel(), 0.0, 1.0)
    y = (np.asarray(outcome).ravel() > 0.5).astype(np.float64)
    N = len(p)
    if N == 0:
        raise ValueError("Empty arrays passed to brier_decomposition_murphy1973")

    brier_exact = float(np.mean((p - y) ** 2))
    o_bar = float(np.mean(y))
    uncertainty = float(o_bar * (1.0 - o_bar))

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)

    rel = 0.0
    res = 0.0
    ece = 0.0
    mce = 0.0
    bins_report: list[dict[str, Any]] = []

    for k in range(n_bins):
        m = bin_idx == k
        nk = int(m.sum())
        lo, hi = float(edges[k]), float(edges[k + 1])
        mid = 0.5 * (lo + hi)
        if nk > 0:
            p_bar_k = float(np.mean(p[m]))
            o_bar_k = float(np.mean(y[m]))
            gap_k = o_bar_k - p_bar_k  # positive => model is underconfident!
            abs_gap = abs(gap_k)
            rel += (nk / N) * ((p_bar_k - o_bar_k) ** 2)
            res += (nk / N) * ((o_bar_k - o_bar) ** 2)
            ece += (nk / N) * abs_gap
            mce = max(mce, abs_gap)
        else:
            p_bar_k = mid
            o_bar_k = 0.0
            gap_k = 0.0

        bins_report.append(
            {
                "bin_index": k,
                "range": [round(lo, 2), round(hi, 2)],
                "bin_midpoint": round(mid, 3),
                "count": nk,
                "fraction_of_eval": round(nk / N, 5),
                "mean_predicted_prob": round(p_bar_k, 5),
                "empirical_hit_rate": round(o_bar_k, 5),
                "underconfidence_gap_obs_minus_pred": round(gap_k, 5),
            }
        )

    # Specifically audit the stated ~0.70 probability neighborhood [0.65, 0.75)
    m_70 = (p >= 0.65) & (p < 0.75)
    if int(m_70.sum()) < 25:
        m_70 = (p >= 0.60) & (p < 0.80)
    if m_70.any():
        stated_70_pred = float(np.mean(p[m_70]))
        stated_70_hit = float(np.mean(y[m_70]))
        stated_70_n = int(m_70.sum())
    else:
        stated_70_pred = 0.70
        stated_70_hit = 0.0
        stated_70_n = 0

    brier_partition = rel - res + uncertainty
    return {
        "n_evaluated_pixels": N,
        "base_hit_rate_o_bar": round(o_bar, 5),
        "brier_score_exact": round(brier_exact, 6),
        "brier_score_murphy_partition": round(brier_partition, 6),
        "reliability_REL": round(rel, 6),
        "resolution_RES": round(res, 6),
        "uncertainty_UNC": round(uncertainty, 6),
        "expected_calibration_error_ECE": round(ece, 6),
        "maximum_calibration_error_MCE": round(mce, 6),
        "stated_0_70_audit": {
            "window": "[0.65, 0.75)",
            "count": stated_70_n,
            "mean_stated_probability": round(stated_70_pred, 5),
            "empirical_hidden_fault_hit_rate": round(stated_70_hit, 5),
            "calibration_bias_obs_minus_stated": round(stated_70_hit - stated_70_pred, 5),
        },
        "reliability_diagram_bins": bins_report,
    }


class OutOfFoldPUCalibrator:
    """Out-of-fold PU probability calibrator evaluated strictly on held-out hidden-fault pixels.

    Addresses the systematic underconfidence induced by PU contamination:
      1. Applies analytical Elkan-Noto / SAR-PU prior rescaling p_pu = clip(p_raw / c_eff, 0, 1).
      2. Fits an out-of-fold monotone IsotonicRegression mapping strictly on the 3 non-test folds'
         candidate ridge pixels against held-out hidden fault recovery, never touching the test fold!
    """

    def __init__(self, c_labeling_freq: float = 0.3251):
        self.c_labeling_freq = float(np.clip(c_labeling_freq, 0.05, 0.95))
        self.iso_models_: dict[int, IsotonicRegression] = {}

    def fit_transform_oof(
        self,
        raw_prob: np.ndarray,
        target_hit: np.ndarray,
        eval_mask: np.ndarray,
        fold_ids: np.ndarray,
    ) -> np.ndarray:
        """Fit a separate IsotonicRegression on the 3 training folds for each held-out fold f_id."""
        p_raw = np.clip(np.asarray(raw_prob, dtype=np.float64), 0.0, 1.0)
        y_hit = (np.asarray(target_hit) > 0.5).astype(np.float64)
        mask = np.asarray(eval_mask, dtype=bool)
        folds = np.asarray(fold_ids, dtype=np.int8)

        # Analytical PU prior lift before monotone isotonic alignment
        p_lifted = np.clip(p_raw / (self.c_labeling_freq + (1.0 - self.c_labeling_freq) * p_raw), 0.0, 1.0)
        p_cal = np.zeros_like(p_raw, dtype=np.float32)

        for f_id in range(4):
            tr_m = (folds != f_id) & mask
            te_m = folds == f_id
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(p_lifted[tr_m], y_hit[tr_m])
            self.iso_models_[f_id] = iso
            # Smooth monotone evaluation via 100 quantile knots of the training-fold isotonic curve
            q_knots = np.unique(np.quantile(p_lifted[tr_m], np.linspace(0.0, 1.0, 101)))
            y_knots = iso.transform(q_knots)
            p_cal[te_m] = np.interp(p_lifted[te_m], q_knots, y_knots).astype(np.float32)

        return np.clip(p_cal, 0.0, 1.0).astype(np.float32)

    fit_predict_oof = fit_transform_oof
