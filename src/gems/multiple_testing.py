"""Dissertation-Committee Standard: Pre-Registration, Multiple-Comparisons Correction
(Holm-Bonferroni FWER & Benjamini-Hochberg FDR), and Untouched Vault Holdout Gate.

References:
  - Holm, S. (1979). "A Simple Sequentially Rejective Multiple Test Procedure."
    Scandinavian Journal of Statistics, 6(2), 65-70.
  - Benjamini, Y., & Hochberg, Y. (1995). "Controlling the False Discovery Rate:
    A Practical and Powerful Approach to Multiple Testing." JRSS-B, 57(1), 289-300.
  - Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018).
    "The preregistration revolution." PNAS, 115(11), 2600-2606.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def make_dev_and_vault_subblocks(
    footprint_2d: np.ndarray,
    quad_2d: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Partition each of the 4 geographic quadrants into 4 Development sub-blocks (80%)
    and 1 contiguous Untouched Vault Holdout strip (20%).

    Returns
    -------
    dev_block_2d : int8 array (H, W) with values 0..15 for the 16 Dev sub-blocks, -1 elsewhere
    vault_mask_2d : bool array (H, W) True on the 20% untouched Vault Holdout slice
    meta : summary dictionary of pixel and fault counts per partition
    """
    fp = np.asarray(footprint_2d, dtype=bool)
    H, W = fp.shape
    dev_block_2d = np.full((H, W), -1, dtype=np.int8)
    vault_mask_2d = np.zeros((H, W), dtype=bool)

    for q_id in range(4):
        qm = (quad_2d == q_id) & fp
        yy, xx = np.nonzero(qm)
        # Partition each quadrant along its primary latitudinal/longitudinal axis into 5 quantile bands (20% each)
        # Band 2 (the central interior 40%-60% strip of the quadrant) is reserved as the Untouched Vault Holdout!
        # Bands 0, 1, 3, 4 form the 4 Development spatial sub-blocks (80% of the quadrant).
        score_coord = 0.6 * (yy - yy.min()) / max(1, yy.max() - yy.min()) + 0.4 * (xx - xx.min()) / max(
            1, xx.max() - xx.min()
        )
        q_edges = np.quantile(score_coord, [0.0, 0.20, 0.40, 0.60, 0.80, 1.0])
        bins = np.clip(np.digitize(score_coord, q_edges[1:-1], right=False), 0, 4)

        vault_sel = bins == 2
        vault_mask_2d[yy[vault_sel], xx[vault_sel]] = True

        dev_sub_idx = 0
        for b_val in (0, 1, 3, 4):
            sel = bins == b_val
            dev_block_2d[yy[sel], xx[sel]] = int(q_id * 4 + dev_sub_idx)
            dev_sub_idx += 1

    meta = {
        "footprint_pixels": int(fp.sum()),
        "dev_holdout_pixels": int((dev_block_2d >= 0).sum()),
        "dev_holdout_fraction": round(float((dev_block_2d >= 0).sum() / max(fp.sum(), 1)), 5),
        "n_dev_subblocks": 16,
        "vault_holdout_pixels": int(vault_mask_2d.sum()),
        "vault_holdout_fraction": round(float(vault_mask_2d.sum() / max(fp.sum(), 1)), 5),
        "n_vault_quadrant_strips": 4,
    }
    return dev_block_2d, vault_mask_2d, meta


def holm_bonferroni_and_bh_correction(
    tests: list[dict[str, Any]],
    *,
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """Apply Holm-Bonferroni FWER step-down and Benjamini-Hochberg FDR corrections.

    Each item in ``tests`` must have ``id`` and ``p_value_raw`` (one-sided test of
    pre-registered directional improvement over baseline).
    """
    m = len(tests)
    if m == 0:
        return []

    raw_p = np.array([float(t["p_value_raw"]) for t in tests], dtype=np.float64)
    order = np.argsort(raw_p)

    # 1. Holm-Bonferroni step-down FWER adjusted p-values:
    # p_holm_(i) = max_{j <= i} min(1, (m - j) * p_(j))
    holm_adj = np.zeros(m, dtype=np.float64)
    running_max = 0.0
    for rank_idx, orig_idx in enumerate(order):
        adj = min(1.0, (m - rank_idx) * raw_p[orig_idx])
        running_max = max(running_max, adj)
        holm_adj[orig_idx] = running_max

    # Step-down rejection stops at first non-rejected hypothesis
    holm_reject = np.zeros(m, dtype=bool)
    for rank_idx, orig_idx in enumerate(order):
        if raw_p[orig_idx] <= alpha / float(m - rank_idx):
            holm_reject[orig_idx] = True
        else:
            break

    # 2. Benjamini-Hochberg step-up FDR q-values:
    # q_bh_(i) = min_{j >= i} min(1, (m / (j + 1)) * p_(j))
    bh_q = np.zeros(m, dtype=np.float64)
    running_min = 1.0
    for rank_idx in range(m - 1, -1, -1):
        orig_idx = order[rank_idx]
        q_val = min(1.0, (m / float(rank_idx + 1)) * raw_p[orig_idx])
        running_min = min(running_min, q_val)
        bh_q[orig_idx] = running_min

    bh_reject = bh_q <= alpha

    out: list[dict[str, Any]] = []
    for i, t in enumerate(tests):
        row = dict(t)
        rank_1based = int(np.where(order == i)[0][0]) + 1
        row.update(
            {
                "rank_by_p_value": rank_1based,
                "m_total_hypotheses_tested": m,
                "holm_bonferroni_threshold": round(alpha / float(m - rank_1based + 1), 6),
                "p_value_holm_bonferroni": round(float(holm_adj[i]), 6),
                "pass_holm_bonferroni_fwer_0_05": bool(holm_reject[i]),
                "q_value_benjamini_hochberg": round(float(bh_q[i]), 6),
                "pass_benjamini_hochberg_fdr_0_05": bool(bh_reject[i]),
            }
        )
        out.append(row)
    return out


def paired_subblock_significance_test(
    cand_scores: list[float] | np.ndarray,
    base_scores: list[float] | np.ndarray,
    *,
    n_bootstrap: int = 10000,
    seed: int = 20260930,
) -> dict[str, Any]:
    """Compute paired t-test, Wilcoxon signed-rank, and paired bootstrap p-value across spatial sub-blocks."""
    c = np.asarray(cand_scores, dtype=np.float64)
    b = np.asarray(base_scores, dtype=np.float64)
    diffs = c - b
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    sd_diff = float(np.std(diffs, ddof=1)) if n > 1 else 0.0
    se_diff = sd_diff / np.sqrt(max(n, 1))

    if sd_diff > 1e-12 and n > 1:
        t_stat = mean_diff / se_diff
        # One-sided p-value for pre-registered directional hypothesis: mean_diff > 0
        p_t_onesided = float(stats.t.sf(t_stat, df=n - 1))
    else:
        t_stat = 0.0
        p_t_onesided = 1.0 if mean_diff <= 0 else 0.0

    rng = np.random.default_rng(seed)
    boot_idx = rng.integers(0, n, size=(n_bootstrap, n))
    boot_means = np.mean(diffs[boot_idx], axis=1)
    ci_low, ci_high = np.percentile(boot_means, [2.5, 97.5])
    p_boot = float(np.mean(boot_means <= 0.0))

    return {
        "n_blocks": n,
        "mean_delta": round(mean_diff, 6),
        "std_delta": round(sd_diff, 6),
        "se_delta": round(se_diff, 6),
        "ci95_delta": [round(float(ci_low), 6), round(float(ci_high), 6)],
        "blocks_won": int(np.sum(diffs > 0)),
        "t_statistic": round(float(t_stat), 4),
        "p_value_raw": round(max(p_t_onesided, 1e-6), 6),
        "p_value_bootstrap": round(float(p_boot), 6),
    }


class VaultHoldoutGate:
    """Enforces that the reserved Vault Holdout slice is evaluated at most once per promoted candidate."""

    def __init__(self, max_allowed_touches: int = 2):
        self.max_allowed_touches = int(max_allowed_touches)
        self.touch_log: list[dict[str, Any]] = []

    def evaluate_once(
        self,
        candidate_id: str,
        eval_fn,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        if len(self.touch_log) >= self.max_allowed_touches:
            raise RuntimeError(
                f"VaultHoldoutGate violation: attempted touch #{len(self.touch_log) + 1} "
                f"for {candidate_id}, exceeding max_allowed_touches={self.max_allowed_touches}!"
            )
        if any(entry["candidate_id"] == candidate_id for entry in self.touch_log):
            raise RuntimeError(f"VaultHoldoutGate violation: {candidate_id} already evaluated on Vault Holdout!")

        result = eval_fn(*args, **kwargs)
        self.touch_log.append(
            {
                "touch_number": len(self.touch_log) + 1,
                "candidate_id": candidate_id,
                "passed_vault": bool(result.get("passed_vault", False)),
                "vault_mean_dense_dti": result.get("vault_mean_dense_dti"),
                "vault_mean_sparse_dti": result.get("vault_mean_sparse_dti"),
            }
        )
        return result
