"""Binary-target calibration utilities; no claim of hidden-fault truth recovery.

Murphy (1973), DOI 10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2.
REL-RES+UNC is exact for BIN-COARSENED forecasts, not arbitrary continuous
forecasts. The raw score additionally needs within-bin variance/covariance terms.
Only independently observed, representative outcomes (or a documented sampling
weight design) can establish unconditional probability reliability. Withheld
catalogue positives and synthetic thinning cannot supply verified negatives.
"""
from __future__ import annotations

from typing import Any
import numpy as np
from sklearn.isotonic import IsotonicRegression


def brier_decomposition_murphy1973(prob: np.ndarray, outcome: np.ndarray, n_bins: int = 10,
                                  *, sample_weight: np.ndarray | None = None) -> dict[str, Any]:
    """Weighted reliability diagram and correctly closed binary Brier partition.

    Reject malformed scores/soft targets instead of silently clipping/thresholding.
    Empty bins have null estimates, not invented rates. The 0.70 window never
    silently expands. Weights may implement a documented inclusion design, but
    this utility cannot verify that design or label provenance.
    """
    p, y = np.asarray(prob, float), np.asarray(outcome, float)
    if p.ndim != 1 or y.ndim != 1 or p.shape != y.shape or not p.size:
        raise ValueError("matching nonempty 1D probability and outcome arrays required")
    if not np.isfinite(p).all() or np.any((p<0)|(p>1)) or not np.isfinite(y).all() or not np.isin(y, [0,1]).all():
        raise ValueError("finite [0,1] probabilities and binary observed targets required")
    if isinstance(n_bins, bool) or not isinstance(n_bins, (int, np.integer)) or not 1 <= n_bins <= 1000:
        raise ValueError("n_bins must be an integer in [1,1000]")
    w = np.ones_like(p) if sample_weight is None else np.asarray(sample_weight, float)
    if w.shape != p.shape or not np.isfinite(w).all() or np.any(w<0) or w.sum()<=0:
        raise ValueError("matching finite nonnegative weights with positive total required")
    total = float(w.sum())
    mean = lambda a, m: float(np.dot(w[m], a[m]) / w[m].sum())
    ybar = float(np.dot(w,y)/total)
    raw = float(np.dot(w,(p-y)**2)/total)
    unc = ybar*(1-ybar)
    edges = np.linspace(0,1,n_bins+1)
    idx = np.digitize(p, edges[1:-1], right=False)
    rel = res = ece = mce = variance = covariance = 0.0
    rows = []
    for k in range(n_bins):
        m = idx==k
        weight = float(w[m].sum())
        fraction = weight/total
        pk = ok = gap = None
        if weight>0:
            pk, ok = mean(p,m), mean(y,m)
            gap = ok-pk
            rel += fraction*gap**2
            res += fraction*(ok-ybar)**2
            ece += fraction*abs(gap)
            mce = max(mce,abs(gap))
            variance += float(np.dot(w[m], (p[m]-pk)**2)/total)
            covariance += float(np.dot(w[m], (p[m]-pk)*(y[m]-ok))/total)
        rows.append({"bin_index": k, "range": [float(edges[k]),float(edges[k+1])],
                     "bin_midpoint": float((edges[k]+edges[k+1])/2), "count": int(m.sum()),
                     "weight": weight, "fraction_of_eval": fraction, "mean_predicted_prob": pk,
                     "target_positive_rate": ok, "target_gap_target_minus_predicted": gap})
    partition = rel-res+unc
    correction = variance-2*covariance
    m70 = (p>=0.65)&(p<0.75)
    populated70 = w[m70].sum()>0
    p70, o70 = (mean(p,m70), mean(y,m70)) if populated70 else (None,None)
    return {
        "n_evaluated_pixels": len(p), "total_sample_weight": total,
        "effective_sample_size_kish_not_spatial_independence": float(total**2/np.dot(w,w)),
        "base_target_positive_rate": ybar, "brier_score_exact": raw,
        "brier_score_murphy_partition": partition, "brier_score_bin_coarsened": partition,
        "partition_scope": "REL-RES+UNC is exact for bin-mean forecasts; raw forecasts need the within-bin correction.",
        "within_bin_prediction_variance": variance, "within_bin_prediction_outcome_covariance": covariance,
        "within_bin_correction": correction,
        "brier_score_raw_reconstructed": partition+correction,
        "closure_error_raw": raw-(partition+correction),
        "reliability_REL": rel, "resolution_RES": res, "uncertainty_UNC": unc,
        "expected_calibration_error_ECE": ece, "maximum_calibration_error_MCE": mce,
        "stated_0_70_audit": {"window": "[0.65, 0.75)", "count": int(m70.sum()),
                             "mean_predicted_probability": p70, "target_positive_rate": o70,
                             "target_minus_prediction": o70-p70 if populated70 else None},
        "reliability_diagram_bins": rows,
        "label_provenance_verified_by_function": False,
        "uncertainty_note": "No IID binomial confidence interval: geological pixels cluster and label sampling must be documented.",
    }


class OutOfFoldPUCalibrator:
    """Fold-separated isotonic mapping of supplied observed targets.

    No default guessed labeling frequency. Optional q/c lift uses the SCAR identity
    q=P(S=1|X)=c*P(Y=1|X), not an odds correction. This cannot verify SCAR, hidden
    label provenance or independence of the underlying model from test labels.
    """

    def __init__(self, c_labeling_freq: float | None = None):
        if c_labeling_freq is not None and (not np.isfinite(c_labeling_freq) or not 0<c_labeling_freq<=1):
            raise ValueError("explicit labeling frequency must be in (0,1]")
        self.c_labeling_freq = c_labeling_freq
        self.iso_models_: dict[int, IsotonicRegression] = {}

    def fit_transform_oof(self, raw_prob: np.ndarray, target_hit: np.ndarray,
                          eval_mask: np.ndarray, fold_ids: np.ndarray) -> np.ndarray:
        p, y = np.asarray(raw_prob,float), np.asarray(target_hit,float)
        mask, folds = np.asarray(eval_mask,bool), np.asarray(fold_ids)
        if p.ndim!=1 or y.shape!=p.shape or mask.shape!=p.shape or folds.shape!=p.shape or not mask.any():
            raise ValueError("matching nonempty 1D arrays/mask required")
        if not np.isfinite(p[mask]).all() or np.any((p[mask]<0)|(p[mask]>1)) or not np.isin(y[mask],[0,1]).all():
            raise ValueError("finite [0,1] scores and binary targets required inside evaluation mask")
        if not np.isfinite(folds[mask]).all() or not np.equal(folds[mask],np.floor(folds[mask])).all():
            raise ValueError("integer fold identifiers required")
        ids = np.unique(folds[mask])
        if len(ids)<2:
            raise ValueError("at least two nonempty folds required")
        lifted = p.copy() if self.c_labeling_freq is None else np.clip(p/self.c_labeling_freq,0,1)
        out = np.full(p.shape,np.nan,dtype=np.float32)
        self.iso_models_.clear()
        for fid in ids:
            train, test = mask&(folds!=fid), mask&(folds==fid)
            iso = IsotonicRegression(y_min=0,y_max=1,out_of_bounds="clip")
            iso.fit(lifted[train],y[train])
            self.iso_models_[int(fid)] = iso
            out[test] = iso.transform(lifted[test]).astype(np.float32)
        self.provenance_status_ = "INPUT_ARRAYS_ONLY; underlying label truth and model/split independence are not verified."
        return out

    fit_predict_oof = fit_transform_oof
