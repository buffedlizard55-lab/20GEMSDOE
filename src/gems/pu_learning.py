"""Positive-Unlabeled (PU) Learning with Non-Negative Risk Estimator (nnPU) & Power-Law Class Prior.

References:
  - Kiryo, R., Niu, G., du Plessis, M. C., & Sugiyama, M. (2017).
    "Positive-Unlabeled Learning with Non-Negative Risk Estimator."
    Advances in Neural Information Processing Systems (NeurIPS 2017), 30, 1675-1685.
    https://proceedings.neurips.cc/paper/2017/file/7cce53cf90577442771720a370c3c723-Paper.pdf
  - du Plessis, M. C., Niu, G., & Sugiyama, M. (2014).
    "Analysis of Learning from Positive and Unlabeled Data." NeurIPS 2014.
  - Elkan, C., & Noto, K. (2008).
    "Learning Classifiers from Only Positive and Unlabeled Data." KDD 2008.
  - Bekker, J., Robberechts, P., & Davis, J. (2019).
    "Beyond the Selected Completely at Random Assumption for Learning from Positive and Unlabeled Data." ECML-PKDD 2019.
  - Scholz, C. H., & Cowie, P. A. (1990).
    "Determination of total strain from faulting using slip measurements." Nature, 346, 837-839.
  - Bonnet, E., Bour, O., Odling, N. E., Davy, P., Main, I., Cowie, P., & Berkowitz, B. (2001).
    "Scaling of fracture systems in geological media." Reviews of Geophysics, 39(3), 347-383.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.ndimage import label as ndi_label
from scipy.special import expit, logit
from skimage.morphology import skeletonize
from sklearn.ensemble import HistGradientBoostingClassifier


@dataclass(frozen=True)
class PowerLawPriorEstimate:
    """Literature-grounded PU class prior pi derived from fault length-frequency scaling."""

    l_min_m: float
    l0_m: float
    alpha_ols: float
    alpha_mle: float
    c_ols: float
    r2_loglog: float
    ks_distance: float
    n_obs_total: int
    n_obs_ge_lmin: int
    n_obs_short: int
    n_extrap_short: float
    deficit_short_traces: float
    short_completeness_ratio: float
    mean_short_trace_length_m: float
    catalogued_positive_pixels: int
    extrapolated_hidden_positive_pixels: int
    footprint_pixels: int
    pi_observed: float          # P(s = 1)
    pi_hidden: float            # P(y = 1, s = 0)
    pi_total: float             # pi = P(y = 1) = pi_observed + pi_hidden
    pi_unlabeled_pos: float     # P(y = 1 | s = 0) = (pi - pi_P) / (1 - pi_P)
    labeling_frequency_c: float # c = P(s = 1 | y = 1) = pi_P / pi

    def to_dict(self) -> dict[str, Any]:
        return {
            "l_min_m": round(self.l_min_m, 1),
            "l0_m": round(self.l0_m, 1),
            "alpha_ols": round(self.alpha_ols, 4),
            "alpha_mle": round(self.alpha_mle, 4),
            "c_ols": round(self.c_ols, 2),
            "r2_loglog": round(self.r2_loglog, 5),
            "ks_distance": round(self.ks_distance, 5),
            "n_obs_total": self.n_obs_total,
            "n_obs_ge_lmin": self.n_obs_ge_lmin,
            "n_obs_short": self.n_obs_short,
            "n_extrap_short": round(self.n_extrap_short, 1),
            "deficit_short_traces": round(self.deficit_short_traces, 1),
            "short_completeness_ratio": round(self.short_completeness_ratio, 4),
            "mean_short_trace_length_m": round(self.mean_short_trace_length_m, 1),
            "catalogued_positive_pixels": self.catalogued_positive_pixels,
            "extrapolated_hidden_positive_pixels": self.extrapolated_hidden_positive_pixels,
            "footprint_pixels": self.footprint_pixels,
            "pi_observed": round(self.pi_observed, 6),
            "pi_hidden": round(self.pi_hidden, 6),
            "pi_total": round(self.pi_total, 6),
            "pi_unlabeled_pos": round(self.pi_unlabeled_pos, 6),
            "labeling_frequency_c": round(self.labeling_frequency_c, 6),
        }


def extract_skeleton_trace_lengths_m(
    binary_fault_mask: np.ndarray,
    px_len_m: float = 108.0,
) -> np.ndarray:
    """Skeletonize a binary fault raster and return connected component lengths in meters."""
    mask = np.asarray(binary_fault_mask, dtype=bool)
    if not mask.any():
        return np.array([], dtype=np.float64)
    skel = skeletonize(mask)
    comp, n_comp = ndi_label(mask, structure=np.ones((3, 3), dtype=int))
    if n_comp == 0:
        return np.array([], dtype=np.float64)
    counts = np.bincount(comp.ravel(), weights=skel.ravel())[1:]
    return np.sort(np.maximum(counts, 1.0) * float(px_len_m))


def estimate_power_law_class_prior(
    labels_2d: np.ndarray,
    footprint_2d: np.ndarray,
    *,
    l_min: float = 1650.0,
    l0: float = 300.0,
    upper_pct: float = 97.0,
    px_len_m: float = 108.0,
    lengths_override_m: np.ndarray | None = None,
) -> PowerLawPriorEstimate:
    """Estimate the PU class prior pi = P(y=1) from power-law fault length-frequency scaling.

    Fits N(L >= ell) = C * ell^(-alpha) above the completeness threshold ``l_min`` where
    regional fault mapping is complete, and extrapolates down to ``l0`` (300 m, matching
    the competition's 3-pixel triangular DTI kernel support).
    """
    fp = np.asarray(footprint_2d, dtype=bool)
    lab = np.asarray(labels_2d, dtype=bool) & fp
    n_fp = int(fp.sum())
    n_pos_px = int(lab.sum())

    if lengths_override_m is not None:
        L = np.sort(np.asarray(lengths_override_m, dtype=np.float64))
    else:
        L = extract_skeleton_trace_lengths_m(lab, px_len_m=px_len_m)
    L = L[L >= 100.0]
    tail = L[L >= l_min]
    if len(tail) < 8:
        raise ValueError(f"Insufficient fault traces ({len(tail)}) above l_min={l_min} m")

    # Hill / Clauset-Shalizi-Newman MLE exponent for cumulative Pareto tail N(>=L) ~ L^-alpha
    alpha_mle = float(len(tail) / np.sum(np.log(tail / l_min)))

    # Log-log OLS over the self-similar scaling regime [l_min, P_upper] (excluding finite-basin cutoff)
    l_upper = float(np.percentile(L, upper_pct))
    mid = np.unique(L[(L >= l_min) & (L <= l_upper)])
    n_ge = np.array([(L >= x).sum() for x in mid], dtype=np.float64)
    slope, intercept = np.polyfit(np.log10(mid), np.log10(n_ge), 1)
    alpha_ols = float(-slope)
    c_ols = float(10.0**intercept)
    r2 = float(np.corrcoef(np.log10(mid), np.log10(n_ge))[0, 1] ** 2)

    # Empirical vs fitted CDF Kolmogorov-Smirnov distance on tail [l_min, l_upper]
    emp_cdf = 1.0 - n_ge / float(n_ge[0])
    fit_cdf = 1.0 - (mid / l_min) ** (-alpha_ols)
    ks_dist = float(np.max(np.abs(emp_cdf - fit_cdf)))

    # Extrapolate short-fault population in [l0, l_min)
    n_extrap_l0 = float(c_ols * (l0 ** (-alpha_ols)))
    n_obs_ge_lmin = int((L >= l_min).sum())
    n_obs_short = int(((L >= l0) & (L < l_min)).sum())
    n_extrap_short = float(max(0.0, n_extrap_l0 - n_obs_ge_lmin))
    deficit_short = float(max(0.0, n_extrap_short - n_obs_short))

    if abs(alpha_ols - 1.0) > 1e-3:
        mean_l_short = float(
            (alpha_ols / (alpha_ols - 1.0))
            * (l0 ** (1.0 - alpha_ols) - l_min ** (1.0 - alpha_ols))
            / (l0 ** (-alpha_ols) - l_min ** (-alpha_ols))
        )
    else:
        mean_l_short = float((l_min - l0) / np.log(l_min / l0))

    # Each trace in labels.tif has an average rasterized cross-sectional width (px_per_m *px_len_m)
    obs_trace_px_total = float(np.sum(L / px_len_m))
    width_factor = float(n_pos_px / max(obs_trace_px_total, 1.0))
    missing_px = int(round(deficit_short * (mean_l_short / px_len_m) * max(width_factor, 1.0)))

    pi_obs = float(n_pos_px / max(n_fp, 1))
    pi_hid = float(missing_px / max(n_fp, 1))
    pi_tot = float(min(0.25, pi_obs + pi_hid))
    pi_u_pos = float(max(0.0, (pi_tot - pi_obs) / max(1.0 - pi_obs, 1e-6)))
    c_freq = float(pi_obs / max(pi_tot, 1e-9))

    return PowerLawPriorEstimate(
        l_min_m=float(l_min),
        l0_m=float(l0),
        alpha_ols=alpha_ols,
        alpha_mle=alpha_mle,
        c_ols=c_ols,
        r2_loglog=r2,
        ks_distance=ks_dist,
        n_obs_total=int(len(L)),
        n_obs_ge_lmin=n_obs_ge_lmin,
        n_obs_short=n_obs_short,
        n_extrap_short=n_extrap_short,
        deficit_short_traces=deficit_short,
        short_completeness_ratio=float(n_obs_short / max(n_extrap_short, 1e-6)),
        mean_short_trace_length_m=mean_l_short,
        catalogued_positive_pixels=n_pos_px,
        extrapolated_hidden_positive_pixels=missing_px,
        footprint_pixels=n_fp,
        pi_observed=pi_obs,
        pi_hidden=pi_hid,
        pi_total=pi_tot,
        pi_unlabeled_pos=pi_u_pos,
        labeling_frequency_c=c_freq,
    )


def compute_pu_risk_metrics(
    margins_pos: np.ndarray,
    margins_unl: np.ndarray,
    pi: float,
    *,
    beta_nnpu: float = 0.0,
    loss_type: str = "sigmoid",
) -> dict[str, float]:
    """Compute exact PN, uPU, and Kiryo et al. (2017) nnPU risks for decision margins g(x).

    Parameters
    ----------
    margins_pos : array of g(x) on labeled positive examples (s = 1)
    margins_unl : array of g(x) on unlabeled examples (s = 0)
    pi : class prior P(y = 1)
    beta_nnpu : non-negative clamp tolerance (0.0 per Kiryo et al. Theorem 1)
    loss_type : 'sigmoid' (ell(z) = 1 / (1 + exp(z)), bounded in [0,1]) or 'logistic'
    """
    gp = np.asarray(margins_pos, dtype=np.float64)
    gu = np.asarray(margins_unl, dtype=np.float64)
    pi = float(np.clip(pi, 1e-5, 0.999))

    if loss_type == "sigmoid":
        ell_p_pos = expit(-gp)   # ell(+g(x_P))
        ell_p_neg = expit(+gp)   # ell(-g(x_P))
        ell_u_neg = expit(+gu)   # ell(-g(x_U))
    elif loss_type == "logistic":
        ell_p_pos = np.logaddexp(0.0, -gp)
        ell_p_neg = np.logaddexp(0.0, +gp)
        ell_u_neg = np.logaddexp(0.0, +gu)
    else:
        raise ValueError(f"Unsupported loss_type: {loss_type}")

    r_p_plus = float(np.mean(ell_p_pos))
    r_p_minus = float(np.mean(ell_p_neg))
    r_u_minus = float(np.mean(ell_u_neg))

    neg_risk_raw = r_u_minus - pi * r_p_minus
    neg_risk_clamped = max(-beta_nnpu, neg_risk_raw)
    r_pn = pi * r_p_plus + (1.0 - pi) * r_u_minus
    r_upu = pi * r_p_plus + neg_risk_raw
    r_nnpu = pi * r_p_plus + neg_risk_clamped

    return {
        "pi": round(pi, 6),
        "R_P_plus": round(r_p_plus, 6),
        "R_P_minus": round(r_p_minus, 6),
        "R_U_minus": round(r_u_minus, 6),
        "unbiased_neg_risk_raw": round(neg_risk_raw, 6),
        "nnpu_neg_risk_clamped": round(neg_risk_clamped, 6),
        "was_clamped_non_negative": bool(neg_risk_raw < -beta_nnpu),
        "R_PN_naive": round(r_pn, 6),
        "R_uPU": round(r_upu, 6),
        "R_nnPU": round(r_nnpu, 6),
    }


estimate_pu_prior_from_power_law = estimate_power_law_class_prior
estimate_pu_prior_from_powerlaw = estimate_power_law_class_prior


class KiryoNNPULinearHead:
    """Mini-batch stochastic gradient descent solver for Kiryo et al. (2017) Algorithm 1 (nnPU).

    Minimizes:
        R_nnPU(g) = pi * E_P[ell(g(x))] + max(-beta, E_U[ell(-g(x))] - pi * E_P[ell(-g(x))])
    using bounded symmetric sigmoid loss ell(z) = 1 / (1 + exp(z)) and explicit reverse-gradient
    deflation (-gamma * grad(R_U^- - pi * R_P^-)) whenever R_U^- - pi * R_P^- < -beta.
    """

    def __init__(
        self,
        pi: float,
        beta: float = 0.0,
        gamma: float = 1.0,
        lr: float = 0.05,
        l2: float = 1e-4,
        n_epochs: int = 18,
        batch_size: int = 4096,
        random_state: int = 42,
    ):
        self.pi = float(np.clip(pi, 1e-4, 0.5))
        self.beta = float(beta)
        self.gamma = float(gamma)
        self.lr = float(lr)
        self.l2 = float(l2)
        self.n_epochs = int(n_epochs)
        self.batch_size = int(batch_size)
        self.random_state = int(random_state)
        self.w_: np.ndarray | None = None
        self.b_: float = 0.0
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.clamp_steps_: int = 0
        self.total_steps_: int = 0

    def _design(self, X: np.ndarray) -> np.ndarray:
        Z = (X - self.mean_) / self.std_
        Z = np.clip(Z, -5.0, 5.0)
        return np.hstack([Z, 0.25 * (Z ** 2)])

    def fit(self, X_pos: np.ndarray, X_unl: np.ndarray) -> "KiryoNNPULinearHead":
        rng = np.random.default_rng(self.random_state)
        X_all = np.vstack([X_pos, X_unl]).astype(np.float64)
        self.mean_ = np.mean(X_all, axis=0)
        self.std_ = np.maximum(np.std(X_all, axis=0), 1e-5)
        del X_all

        Zp = self._design(X_pos.astype(np.float64))
        Zu = self._design(X_unl.astype(np.float64))
        d = Zp.shape[1]
        self.w_ = np.zeros(d, dtype=np.float64)
        self.b_ = float(np.log(self.pi / (1.0 - self.pi)))

        # Adam state
        m_w = np.zeros(d, dtype=np.float64)
        v_w = np.zeros(d, dtype=np.float64)
        m_b = 0.0
        v_b = 0.0
        t_step = 0
        self.clamp_steps_ = 0
        self.total_steps_ = 0

        n_p, n_u = len(Zp), len(Zu)
        n_batches = max(4, n_u // self.batch_size)
        bp_size = max(128, n_p // n_batches)

        for _epoch in range(self.n_epochs):
            perm_u = rng.permutation(n_u)
            perm_p = rng.permutation(n_p)
            for b_idx in range(n_batches):
                u_sl = perm_u[b_idx * self.batch_size : (b_idx + 1) * self.batch_size]
                p_start = (b_idx * bp_size) % max(1, n_p - bp_size)
                p_sl = perm_p[p_start : p_start + bp_size]
                if len(u_sl) == 0 or len(p_sl) == 0:
                    continue

                zp = Zp[p_sl]
                zu = Zu[u_sl]
                gp = zp @ self.w_ + self.b_
                gu = zu @ self.w_ + self.b_

                # Sigmoid loss ell(z) = expit(-z); d/dz ell(z) = -expit(z)*expit(-z)
                sp = expit(-gp)
                d_lp_pos = -sp * (1.0 - sp)  # d/dg ell(+g)
                # For ell(-g) = expit(+g), d/dg ell(-g) = +expit(g)*expit(-g) = -d_lp_pos
                d_lp_neg = -d_lp_pos

                su = expit(+gu)
                d_lu_neg = su * (1.0 - su)   # d/dg ell(-g_u)

                r_u_neg_minus_pi_r_p_neg = float(np.mean(su) - self.pi * np.mean(1.0 - sp))
                self.total_steps_ += 1

                if r_u_neg_minus_pi_r_p_neg >= -self.beta:
                    # Standard unbiased PU gradient: grad(pi * R_P^+ + R_U^- - pi * R_P^-)
                    grad_gp = self.pi * (d_lp_pos - d_lp_neg) / len(zp)
                    grad_gu = d_lu_neg / len(zu)
                    grad_w = (zp.T @ grad_gp) + (zu.T @ grad_gu) + self.l2 * self.w_
                    grad_b = float(np.sum(grad_gp) + np.sum(grad_gu))
                else:
                    # Kiryo et al. Algorithm 1 line 11: reverse gradient step on negative risk!
                    self.clamp_steps_ += 1
                    grad_gp = -self.gamma * (-self.pi * d_lp_neg) / len(zp)
                    grad_gu = -self.gamma * (d_lu_neg / len(zu))
                    grad_w = (zp.T @ grad_gp) + (zu.T @ grad_gu) + self.l2 * self.w_
                    grad_b = float(np.sum(grad_gp) + np.sum(grad_gu))

                t_step += 1
                m_w = 0.9 * m_w + 0.1 * grad_w
                v_w = 0.999 * v_w + 0.001 * (grad_w ** 2)
                m_b = 0.9 * m_b + 0.1 * grad_b
                v_b = 0.999 * v_b + 0.001 * (grad_b ** 2)

                mw_hat = m_w / (1.0 - 0.9 ** t_step)
                vw_hat = v_w / (1.0 - 0.999 ** t_step)
                mb_hat = m_b / (1.0 - 0.9 ** t_step)
                vb_hat = v_b / (1.0 - 0.999 ** t_step)

                self.w_ -= self.lr * mw_hat / (np.sqrt(vw_hat) + 1e-8)
                self.b_ -= self.lr * mb_hat / (np.sqrt(vb_hat) + 1e-8)

        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        n = len(X)
        out = np.empty(n, dtype=np.float32)
        chunk = 200000
        for i in range(0, n, chunk):
            Z = self._design(np.asarray(X[i : i + chunk], dtype=np.float64))
            out[i : i + chunk] = (Z @ self.w_ + self.b_).astype(np.float32)
        return out

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        g = self.decision_function(X)
        return expit(g).astype(np.float32)


def fit_nnpu_boosted_expert(
    X_pos: np.ndarray,
    X_unl: np.ndarray,
    *,
    pi: float,
    pi_obs: float,
    propensity_pos: np.ndarray | None = None,
    random_state: int = 20260930,
    max_iter: int = 120,
) -> tuple[HistGradientBoostingClassifier, KiryoNNPULinearHead, HistGradientBoostingClassifier, dict[str, Any]]:
    """Train a Selection-Bias-Aware Non-Negative PU (SAR-nnPU) Boosted Expert.

    Combines:
      1. Stage-1 Naive PN baseline classifier (probe) to estimate P(s=1 | x) on U
         and compute Kiryo et al. (2017) non-negative PU risk weights on U and P.
      2. Inverse-propensity Selection-At-Random (SAR) weighting on P so low-relief/short-fault
         catalogued examples receive higher weight than over-represented range-front scarps.
      3. Stage-2 nnPU-reweighted HistGradientBoostingClassifier + KiryoNNPULinearHead stack.
    """
    pi = float(np.clip(pi, 0.015, 0.20))
    pi_obs = float(np.clip(pi_obs, 0.005, pi * 0.95))
    pi_u_pos = (pi - pi_obs) / (1.0 - pi_obs)
    c_label = pi_obs / pi

    n_p = len(X_pos)
    n_u = len(X_unl)

    # Inverse-propensity SAR weights on labeled positives (upweighting subtle/short faults)
    if propensity_pos is not None and len(propensity_pos) == n_p:
        e_p = np.clip(np.asarray(propensity_pos, dtype=np.float64), 0.15, 0.95)
        w_sar_p = (1.0 / e_p)
        w_sar_p = w_sar_p / np.mean(w_sar_p)
    else:
        w_sar_p = np.ones(n_p, dtype=np.float64)

    # Stage 1: Balanced Naive PN classifier (also serves as the PN comparator)
    X_s1 = np.vstack([X_pos, X_unl])
    y_s1 = np.r_[np.ones(n_p, dtype=np.int8), np.zeros(n_u, dtype=np.int8)]
    w_s1 = np.r_[
        np.full(n_p, (0.5 / n_p) * len(y_s1), dtype=np.float64),
        np.full(n_u, (0.5 / n_u) * len(y_s1), dtype=np.float64),
    ]
    probe = HistGradientBoostingClassifier(
        max_iter=max_iter,
        max_leaf_nodes=31,
        min_samples_leaf=80,
        learning_rate=0.06,
        l2_regularization=2.0,
        early_stopping=False,
        random_state=random_state,
    )
    probe.fit(X_s1, y_s1, sample_weight=w_s1)
    p_s_pos = probe.predict_proba(X_pos)[:, 1]
    p_s_unl = probe.predict_proba(X_unl)[:, 1]

    # Elkan & Noto (2008) / Kiryo et al. (2017) posterior P(y=1 | x, s=0) inside U:
    raw_u_pos = np.clip(p_s_unl / np.maximum(np.quantile(p_s_pos, 0.65), 0.15), 0.0, 1.0)
    scale_u = pi_u_pos / max(float(np.mean(raw_u_pos)), 1e-5)
    posterior_u_pos = np.clip(raw_u_pos * min(scale_u, 2.5), 0.0, 0.92)

    # Non-negative PU weight for treating x_j in U as negative:
    w_u_neg = np.maximum(0.08, 1.0 - posterior_u_pos)
    pseudo_mask = posterior_u_pos >= np.quantile(posterior_u_pos, 1.0 - min(0.035, pi_u_pos * 1.25))
    X_pseudo = X_unl[pseudo_mask]
    w_pseudo = posterior_u_pos[pseudo_mask] * 0.45

    # Stage 2: Fit nnPU-reweighted HistGradientBoostingClassifier + KiryoNNPULinearHead
    X_s2 = np.vstack([X_pos, X_pseudo, X_unl])
    y_s2 = np.r_[
        np.ones(n_p, dtype=np.int8),
        np.ones(len(X_pseudo), dtype=np.int8),
        np.zeros(n_u, dtype=np.int8),
    ]
    pos_mass = float(np.sum(w_sar_p) + np.sum(w_pseudo))
    neg_mass = float(np.sum(w_u_neg))
    target_pos_share = float(np.clip(0.50 + 1.5 * (pi - pi_obs), 0.50, 0.58))
    w_s2 = np.r_[
        w_sar_p * (target_pos_share / pos_mass) * len(y_s2),
        w_pseudo * (target_pos_share / pos_mass) * len(y_s2),
        w_u_neg * ((1.0 - target_pos_share) / neg_mass) * len(y_s2),
    ]

    clf_nnpu = HistGradientBoostingClassifier(
        max_iter=max_iter,
        max_leaf_nodes=31,
        min_samples_leaf=80,
        learning_rate=0.06,
        l2_regularization=2.5,
        early_stopping=False,
        random_state=random_state + 100,
    )
    clf_nnpu.fit(X_s2, y_s2, sample_weight=w_s2)

    # Fit exact Kiryo et al. (2017) Algorithm 1 nnPU linear-quadratic head on features
    head_nnpu = KiryoNNPULinearHead(
        pi=pi,
        beta=0.0,
        gamma=1.0,
        lr=0.04,
        l2=2e-4,
        n_epochs=10,
        batch_size=4096,
        random_state=random_state + 200,
    )
    head_nnpu.fit(X_pos, X_unl)

    # Compute risk diagnostics comparing Naive PN vs nnPU on training margins
    g_pn_pos = logit(np.clip(p_s_pos, 1e-5, 1.0 - 1e-5))
    g_pn_unl = logit(np.clip(p_s_unl, 1e-5, 1.0 - 1e-5))
    p_nn_pos = 0.90 * clf_nnpu.predict_proba(X_pos)[:, 1] + 0.10 * head_nnpu.predict_proba(X_pos)
    p_nn_unl = 0.90 * clf_nnpu.predict_proba(X_unl)[:, 1] + 0.10 * head_nnpu.predict_proba(X_unl)
    g_nn_pos = logit(np.clip(p_nn_pos, 1e-5, 1.0 - 1e-5))
    g_nn_unl = logit(np.clip(p_nn_unl, 1e-5, 1.0 - 1e-5))

    diag = {
        "pi_used": round(pi, 6),
        "pi_obs_used": round(pi_obs, 6),
        "pi_u_pos": round(pi_u_pos, 6),
        "c_labeling_frequency": round(c_label, 6),
        "n_pseudo_positives_from_U": int(len(X_pseudo)),
        "mean_u_neg_weight": round(float(np.mean(w_u_neg)), 4),
        "kiryo_head_clamp_steps": head_nnpu.clamp_steps_,
        "kiryo_head_total_steps": head_nnpu.total_steps_,
        "naive_pn_risk_audit": compute_pu_risk_metrics(g_pn_pos, g_pn_unl, pi=pi),
        "nnpu_risk_audit": compute_pu_risk_metrics(g_nn_pos, g_nn_unl, pi=pi),
        "mean_prob_on_P_naive": round(float(np.mean(p_s_pos)), 4),
        "mean_prob_on_P_nnpu": round(float(np.mean(p_nn_pos)), 4),
        "q98_prob_on_U_naive": round(float(np.quantile(p_s_unl, 0.98)), 4),
        "q98_prob_on_U_nnpu": round(float(np.quantile(p_nn_unl, 0.98)), 4),
    }
    return clf_nnpu, head_nnpu, probe, diag


def predict_nnpu_expert(
    clf_nnpu: HistGradientBoostingClassifier,
    head_nnpu: KiryoNNPULinearHead,
    X: np.ndarray,
    *,
    tree_weight: float = 0.92,
) -> np.ndarray:
    """Predict combined nnPU probability on feature matrix X."""
    p_tree = clf_nnpu.predict_proba(X)[:, 1].astype(np.float32)
    p_head = head_nnpu.predict_proba(X).astype(np.float32)
    return np.clip(tree_weight * p_tree + (1.0 - tree_weight) * p_head, 0.0, 1.0).astype(np.float32)


def fit_and_predict_nnpu_arm(
    X_pos: np.ndarray,
    X_unl: np.ndarray,
    X_te: np.ndarray,
    *,
    pi: float,
    pi_obs: float,
    propensity_pos: np.ndarray | None = None,
    random_state: int = 20260930,
    max_iter: int = 120,
    tree_weight: float = 0.92,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fit SAR-nnPU expert and return (p_nnpu_te, p_pn_te, diag) on test fold X_te."""
    clf_nnpu, head_nnpu, probe, diag = fit_nnpu_boosted_expert(
        X_pos,
        X_unl,
        pi=pi,
        pi_obs=pi_obs,
        propensity_pos=propensity_pos,
        random_state=random_state,
        max_iter=max_iter,
    )
    p_nnpu_te = predict_nnpu_expert(clf_nnpu, head_nnpu, X_te, tree_weight=tree_weight)
    p_pn_te = probe.predict_proba(X_te)[:, 1].astype(np.float32)
    return p_nnpu_te, p_pn_te, diag
