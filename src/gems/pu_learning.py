"""Actual non-negative PU risk, with explicit sampling semantics and prior scenarios.

Kiryo et al. (2017): https://proceedings.neurips.cc/paper/2017/hash/7cce53cf90577442771720a370c3c723-Abstract.html
Author implementation: https://github.com/kiryor/nnPUlearning/blob/master/pu_loss.py

Catalogue zeros are UNLABELED. The original Kiryo U sample is drawn from the
marginal X population. If U instead contains only S=0 pixels and mu=P(S=1),
R_neg = (1-mu) E_U[l(-g)] - (pi-mu) E_P[l(-g)]. Using the marginal formula
unchanged on S=0 data is not unbiased. Representative-positive/SCAR and prior
assumptions remain unverified for geological catalogues; code cannot repair that.

Power-law estimates below are sensitivity scenarios, never observed prevalence.
Historical H20 reports/artifacts are preserved separately and are not reproduced
or validated by this corrected implementation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.ndimage import label as ndi_label
from scipy.special import expit
from skimage.morphology import skeletonize


def _prior_coefficients(pi: float, unlabeled_distribution: str, pi_observed: float | None) -> tuple[float, float]:
    if not np.isfinite(pi) or not 0 < pi < 1:
        raise ValueError("pi=P(Y=1) must be finite in (0,1); no silent clipping")
    if unlabeled_distribution == "marginal":
        if pi_observed is not None:
            raise ValueError("pi_observed only applies to catalogue_complement sampling")
        return 1.0, float(pi)
    if unlabeled_distribution != "catalogue_complement":
        raise ValueError("unlabeled_distribution must be marginal or catalogue_complement")
    if pi_observed is None or not np.isfinite(pi_observed) or not 0 <= pi_observed <= pi:
        raise ValueError("catalogue_complement requires 0 <= pi_observed <= pi")
    return 1.0 - float(pi_observed), float(pi) - float(pi_observed)


def _loss_terms(g: np.ndarray, kind: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    s = expit(g)
    if kind == "sigmoid":
        d = s * (1 - s)
        return expit(-g), s, -d, d
    if kind == "logistic":
        return np.logaddexp(0, -g), np.logaddexp(0, g), s - 1, s
    raise ValueError("loss_type must be sigmoid or logistic")


def pu_risk_and_grad(
    margins_pos: np.ndarray, margins_unl: np.ndarray, pi: float, *,
    unlabeled_distribution: str = "marginal", pi_observed: float | None = None,
    loss_type: str = "logistic", beta: float = 0.0, gamma: float = 1.0,
    reverse_gradient: bool = False,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Risk and margin gradients; optional Kiryo Algorithm-1 reverse update.

    With ``reverse_gradient=False`` gradients differentiate the canonical nnPU
    risk (negative component clamped at zero). With True, a negative component
    below -beta triggers descent on -gamma*R_neg as in the authors' algorithm.
    That reverse update is not the derivative of the displayed clamped risk.
    Sigmoid-loss scores are classification confidence, not calibrated posteriors.
    """
    gp, gu = np.asarray(margins_pos, dtype=float), np.asarray(margins_unl, dtype=float)
    if gp.ndim != 1 or gu.ndim != 1 or not gp.size or not gu.size or not np.isfinite(gp).all() or not np.isfinite(gu).all():
        raise ValueError("nonempty finite 1D positive and unlabeled margins required")
    if not np.isfinite(beta) or beta < 0 or not np.isfinite(gamma) or gamma <= 0:
        raise ValueError("beta>=0 and gamma>0 required")
    a, b = _prior_coefficients(float(pi), unlabeled_distribution, pi_observed)
    lp, lpn, dp, dpn = _loss_terms(gp, loss_type)
    _, lun, _, dun = _loss_terms(gu, loss_type)
    positive = float(pi * lp.mean())
    negative = float(a * lun.mean() - b * lpn.mean())
    reversed_step = bool(reverse_gradient and negative < -beta)
    if reversed_step:
        grad_p, grad_u = gamma * b * dpn / len(gp), -gamma * a * dun / len(gu)
        update_objective = -gamma * negative
    elif reverse_gradient or negative > 0:
        grad_p, grad_u = (pi * dp - b * dpn) / len(gp), a * dun / len(gu)
        update_objective = positive + negative
    else:
        grad_p, grad_u = pi * dp / len(gp), np.zeros_like(gu)
        update_objective = positive
    risk = {
        "pi": float(pi), "pi_observed": pi_observed, "unlabeled_distribution": unlabeled_distribution,
        "loss_type": loss_type, "R_P_plus": float(lp.mean()), "R_P_minus": float(lpn.mean()),
        "R_U_minus": float(lun.mean()), "unlabeled_coefficient": a, "positive_subtraction_coefficient": b,
        "unbiased_neg_risk_raw": negative, "nnpu_neg_risk_clamped": max(0, negative),
        "was_clamped_non_negative": negative < 0, "R_uPU": positive + negative,
        "R_nnPU": positive + max(0, negative), "reverse_gradient_step": reversed_step,
        "algorithm_update_objective": update_objective,
        "assumptions": "Representative positives (SCAR or independently corrected selection), specified prior, matching population sampling; not verified here.",
    }
    if unlabeled_distribution == "marginal":
        # Diagnostic naive PN surrogate treating marginal U as clean negatives.
        risk["R_PN_naive"] = float(pi * lp.mean() + (1 - pi) * lun.mean())
    else:
        mu = float(pi_observed)
        risk["R_PN_naive"] = float(mu * lp.mean() + (1 - mu) * lun.mean())
    return risk, grad_p, grad_u


def compute_pu_risk_metrics(
    margins_pos: np.ndarray, margins_unl: np.ndarray, pi: float, *,
    beta_nnpu: float = 0.0, loss_type: str = "sigmoid",
    unlabeled_distribution: str = "marginal", pi_observed: float | None = None,
) -> dict[str, Any]:
    """Canonical nnPU metrics, with explicit marginal vs S=0 sampling."""
    return pu_risk_and_grad(margins_pos, margins_unl, pi, loss_type=loss_type,
                            unlabeled_distribution=unlabeled_distribution, pi_observed=pi_observed,
                            beta=beta_nnpu)[0]


class KiryoNNPULinearHead:
    """CPU Adam solver on linear/quadratic features and the actual PU objective.

    Default bounded sigmoid loss retains legacy API behavior. Prefer logistic loss
    for probability-oriented studies, but even expit(logistic margins) is NOT
    empirically calibrated without independent observed outcomes. No tree/pseudo-
    label blend or heuristic propensity is represented as an nnPU estimator.
    """

    def __init__(self, pi: float, beta: float = 0.0, gamma: float = 1.0, lr: float = 0.05,
                 l2: float = 1e-4, n_epochs: int = 18, batch_size: int = 4096,
                 random_state: int = 42, *, loss_type: str = "sigmoid",
                 unlabeled_distribution: str = "marginal", pi_observed: float | None = None):
        _prior_coefficients(pi, unlabeled_distribution, pi_observed)
        if loss_type not in ("sigmoid", "logistic"):
            raise ValueError("unsupported loss_type")
        if not np.isfinite([beta, gamma, lr, l2]).all() or beta < 0 or gamma <= 0 or lr <= 0 or l2 < 0:
            raise ValueError("invalid optimization parameters")
        if not isinstance(n_epochs, int) or n_epochs < 1 or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("positive integer epochs and batch_size required")
        self.pi, self.beta, self.gamma, self.lr, self.l2 = float(pi), beta, gamma, lr, l2
        self.n_epochs, self.batch_size, self.random_state = n_epochs, batch_size, random_state
        self.loss_type, self.unlabeled_distribution, self.pi_observed = loss_type, unlabeled_distribution, pi_observed
        self.w_ = self.mean_ = self.std_ = None
        self.b_ = 0.0
        self.clamp_steps_ = self.total_steps_ = 0

    @staticmethod
    def _validate(X: np.ndarray) -> np.ndarray:
        x = np.asarray(X, dtype=float)
        if x.ndim != 2 or not x.shape[1] or not np.isfinite(x).all():
            raise ValueError("finite 2D feature matrix required")
        return x

    def _design(self, X: np.ndarray) -> np.ndarray:
        z = np.clip((X - self.mean_) / self.std_, -5, 5)
        return np.hstack([z, 0.25 * z**2])

    def fit(self, X_pos: np.ndarray, X_unl: np.ndarray) -> "KiryoNNPULinearHead":
        p, u = self._validate(X_pos), self._validate(X_unl)
        if not len(p) or not len(u) or p.shape[1] != u.shape[1]:
            raise ValueError("matching nonempty positive/unlabeled matrices required")
        x = np.vstack([p, u])
        self.mean_, self.std_ = x.mean(axis=0), np.maximum(x.std(axis=0), 1e-5)
        del x
        zp, zu = self._design(p), self._design(u)
        del p, u
        self.w_ = np.zeros(zp.shape[1])
        self.b_ = float(np.log(self.pi / (1 - self.pi)))
        m, v = np.zeros_like(self.w_), np.zeros_like(self.w_)
        mb = vb = 0.0
        self.total_steps_ = self.clamp_steps_ = 0
        rng = np.random.default_rng(self.random_state)
        n_batches = int(np.ceil(len(zu) / self.batch_size))
        p_batch = min(self.batch_size, max(1, int(np.ceil(len(zp) / n_batches))))
        for _ in range(self.n_epochs):
            perm = rng.permutation(len(zu))
            for start in range(0, len(zu), self.batch_size):
                iu = perm[start:start + self.batch_size]
                ip = rng.choice(len(zp), size=p_batch, replace=False)
                bp, bu = zp[ip], zu[iu]
                risk, gp, gu = pu_risk_and_grad(
                    bp @ self.w_ + self.b_, bu @ self.w_ + self.b_, self.pi,
                    loss_type=self.loss_type, unlabeled_distribution=self.unlabeled_distribution,
                    pi_observed=self.pi_observed, beta=self.beta, gamma=self.gamma, reverse_gradient=True,
                )
                gw, gb = bp.T @ gp + bu.T @ gu + self.l2 * self.w_, float(gp.sum() + gu.sum())
                self.total_steps_ += 1
                self.clamp_steps_ += int(risk["reverse_gradient_step"])
                t = self.total_steps_
                m, v = 0.9*m + 0.1*gw, 0.999*v + 0.001*gw**2
                mb, vb = 0.9*mb + 0.1*gb, 0.999*vb + 0.001*gb**2
                self.w_ -= self.lr * (m / (1 - 0.9**t)) / (np.sqrt(v / (1 - 0.999**t)) + 1e-8)
                self.b_ -= self.lr * (mb / (1 - 0.9**t)) / (np.sqrt(vb / (1 - 0.999**t)) + 1e-8)
        self.training_assumptions_ = "Prior scenario and representative-positive assumption, not empirically validated."
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        if self.w_ is None:
            raise RuntimeError("fit must run before prediction")
        x = self._validate(X)
        if x.shape[1] != len(self.mean_):
            raise ValueError("feature count mismatch")
        out = np.empty(len(x), dtype=np.float32)
        for i in range(0, len(x), 100000):
            out[i:i+100000] = self._design(x[i:i+100000]) @ self.w_ + self.b_
        return out

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Expit scores in [0,1]; not a claim of observed probability calibration."""
        return expit(self.decision_function(X)).astype(np.float32)


@dataclass(frozen=True)
class PowerLawPriorEstimate:
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
    pi_observed: float
    pi_hidden: float
    pi_total: float
    pi_unlabeled_pos: float
    labeling_frequency_c: float
    length_source: str
    estimator_version: str = "pareto_mle_scenario_v2"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": "MODEL_BASED_PRIOR_SCENARIO_NOT_OBSERVED_PREVALENCE",
                "assumptions": ["Tail completeness at specified cutoff is assumed, not proved.",
                                "Pareto scaling persists to specified lower length; metric support does not establish that cutoff.",
                                "Trace segmentation/clipping and spatial dependence alter the length distribution.",
                                "Observed raster-pixels-per-trace-meter transfers to hidden traces; overlaps ignored."]}


def extract_skeleton_trace_lengths_m(binary_fault_mask: np.ndarray, px_len_m: float = 108.0) -> np.ndarray:
    """Legacy connected-component approximation; NOT geological trace lengths."""
    mask = np.asarray(binary_fault_mask, dtype=bool)
    if mask.ndim != 2 or not np.isfinite(px_len_m) or px_len_m <= 0:
        raise ValueError("2D mask and positive pixel-length approximation required")
    if not mask.any():
        return np.array([], dtype=float)
    skel = skeletonize(mask)
    comp, _ = ndi_label(mask, structure=np.ones((3, 3), int))
    counts = np.bincount(comp.ravel(), weights=skel.ravel())[1:]
    return np.sort(np.maximum(counts, 1) * px_len_m)


def truncated_pareto_mean(alpha: float, lower: float, upper: float) -> float:
    if not np.isfinite([alpha, lower, upper]).all() or alpha <= 0 or not 0 < lower < upper:
        raise ValueError("positive alpha and 0<lower<upper required")
    # Scale by lower to avoid dimensioned large powers. Correct alpha=1 limit:
    # lower * log(r) / (1-1/r), not the logarithmic mean (old implementation).
    r = upper / lower
    if abs(alpha - 1) < 1e-8:
        return float(lower * np.log(r) / (1 - 1/r))
    return float(lower * alpha / (alpha - 1) * (-np.expm1((1-alpha)*np.log(r))) / (-np.expm1(-alpha*np.log(r))))


def estimate_power_law_class_prior(
    labels_2d: np.ndarray, footprint_2d: np.ndarray, *, l_min: float = 1650.0,
    l0: float = 300.0, upper_pct: float = 97.0, px_len_m: float = 108.0,
    lengths_override_m: np.ndarray | None = None,
) -> PowerLawPriorEstimate:
    """Pareto-MLE extrapolation scenario; OLS retained only as a diagnostic.

    Prefer official vector ``lengths_override_m``. Raster components are a legacy
    approximation. Neither fit determines hidden fault prevalence without strong
    unvalidated completeness and length-to-raster assumptions. No arbitrary pi cap.
    """
    fp, lab = np.asarray(footprint_2d, bool), np.asarray(labels_2d, bool)
    if fp.ndim != 2 or fp.shape != lab.shape or not fp.any() or not 0 < l0 < l_min or not 0 < upper_pct < 100:
        raise ValueError("nonempty matching 2D masks, 0<l0<l_min, valid upper percentile required")
    lab = lab & fp
    lengths = (extract_skeleton_trace_lengths_m(lab, px_len_m) if lengths_override_m is None
               else np.asarray(lengths_override_m, float))
    if lengths.ndim != 1 or not len(lengths) or not np.isfinite(lengths).all() or np.any(lengths <= 0):
        raise ValueError("nonempty finite positive trace lengths required")
    lengths = np.sort(lengths)
    tail = lengths[lengths >= l_min]
    denom = float(np.log(tail / l_min).sum())
    if len(tail) < 8 or denom <= 0:
        raise ValueError("insufficient/nonvarying Pareto tail")
    alpha = len(tail) / denom
    upper = np.percentile(lengths, upper_pct)
    mid = np.unique(lengths[(lengths >= l_min) & (lengths <= upper)])
    if len(mid) < 2:
        raise ValueError("insufficient distinct lengths for OLS diagnostic")
    n_ge = len(lengths) - np.searchsorted(lengths, mid, side="left")
    slope, intercept = np.polyfit(np.log10(mid), np.log10(n_ge), 1)
    r2 = float(np.corrcoef(np.log10(mid), np.log10(n_ge))[0, 1]**2)
    empirical_lo = np.arange(len(tail)) / len(tail)
    empirical_hi = np.arange(1, len(tail)+1) / len(tail)
    fitted = 1 - (tail / l_min)**(-alpha)
    ks = float(max(np.max(np.abs(fitted-empirical_lo)), np.max(np.abs(fitted-empirical_hi))))
    extrap = float(len(tail) * ((l_min / l0)**alpha - 1))
    short = int(((lengths >= l0) & (lengths < l_min)).sum())
    deficit = max(0.0, extrap-short)
    mean_length = truncated_pareto_mean(alpha, l0, l_min)
    # Scenario conversion calibrated to actual known pixels and supplied lengths;
    # no invented >1 width floor and no silently clipped total prevalence.
    pixels_per_meter = lab.sum() / lengths.sum()
    missing = int(round(deficit * mean_length * pixels_per_meter))
    obs, hidden = float(lab.sum()/fp.sum()), float(missing/fp.sum())
    total = obs+hidden
    if not 0 < total < 1:
        raise ValueError("extrapolation implies an impossible prior; inspect model/units, do not clip")
    return PowerLawPriorEstimate(
        l_min, l0, float(-slope), alpha, float(10**intercept), r2, ks, len(lengths), len(tail), short,
        extrap, deficit, short/extrap if extrap else 1.0, mean_length, int(lab.sum()), missing, int(fp.sum()),
        obs, hidden, total, hidden/(1-obs), obs/total,
        "official_vector_override" if lengths_override_m is not None else "raster_component_approximation",
    )


estimate_pu_prior_from_power_law = estimate_power_law_class_prior
estimate_pu_prior_from_powerlaw = estimate_power_law_class_prior


def fit_nnpu_boosted_expert(*args, **kwargs):
    raise RuntimeError("Retired H20 pseudo-label/tree heuristic was not the nnPU objective. Use KiryoNNPULinearHead with explicit sampling semantics.")


def predict_nnpu_expert(*args, **kwargs):
    raise RuntimeError("Retired H20 heuristic stack; no calibrated probability or actual nnPU claim is valid.")


def fit_and_predict_nnpu_arm(*args, **kwargs):
    raise RuntimeError("Retired H20 heuristic stack. The corrected CPU nnPU experiment has its own frozen protocol and report.")
