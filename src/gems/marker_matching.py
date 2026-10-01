"""H22-3: dual-marker cross-fault profile displacement, NOT generic edge strength.

Kinematic prototype: texture on opposite flanks matches better at the SAME nonzero
lag in two independent observations than without a shift. This can also reflect
lithology, flight-line/processing artifacts or transported material; it is not
measured fault slip. Fixed parameters and failure rule live in the preregistration.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve, distance_transform_edt, gaussian_filter

DIRECTIONS = ((1,0), (1,1), (0,1), (-1,1))  # working-grid (row,column) tangent
LAGS = (-3,-2,2,3)
FLANK = 2
HALF_LENGTH = 5
GUARD = 25  # excludes wrap, convolution, smoothing and invalid-source support
MIN_CORRELATION = 0.5
VARIANCE_FLOOR = 0.01


def _shift(x, dr, dc):
    return np.roll(x,shift=(dr,dc),axis=(0,1))


def _kernel(dr,dc):
    k=np.zeros((2*HALF_LENGTH+1,2*HALF_LENGTH+1),np.float32)
    for s in range(-HALF_LENGTH,HALF_LENGTH+1):
        k[HALF_LENGTH+s*dr,HALF_LENGTH+s*dc]=1/(2*HALF_LENGTH+1)
    return k


def _standardize(x, valid):
    nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True)
    filled=x[tuple(nearest)].astype(np.float32)
    lo,hi=np.quantile(filled[valid],[0.01,0.99])
    clipped=np.clip(filled,lo,hi)
    sd=float(clipped[valid].std())
    if sd<1e-6:
        return np.zeros_like(x,dtype=np.float32)
    z=(clipped-float(clipped[valid].mean()))/sd
    return gaussian_filter(z,0.8,mode="nearest").astype(np.float32)


def paired_marker_displacement(marker_a, marker_b, valid):
    """Return [0,1] joint nonzero-lag improvement and label-free controls.

    Work on a 200 m block-averaged grid. Cardinal and diagonal primitive directions
    have different physical step lengths (200/283 m); this is disclosed, not tuned.
    Both markers must have local texture and cross-flank correlation >0.5 at the
    same signed lag. Each nonzero lag is contrasted with its own zero-lag match
    AND equal-separation pairs on both same sides (smooth oblique-texture null).
    """
    a,b=np.asarray(marker_a,np.float32),np.asarray(marker_b,np.float32)
    valid=np.asarray(valid,bool)
    if a.ndim!=2 or a.shape!=b.shape or a.shape!=valid.shape or not valid.any():
        raise ValueError("matching nonempty 2D marker arrays and valid mask required")
    valid=valid&np.isfinite(a)&np.isfinite(b)
    if not valid.any():
        raise ValueError("no common valid observations")
    interior=distance_transform_edt(np.pad(valid,1,constant_values=False))[1:-1,1:-1]>GUARD
    if not interior.any():
        raise ValueError("source/edge guard leaves no interior observations")
    a,b=_standardize(a,valid),_standardize(b,valid)
    score=np.zeros(a.shape,np.float32)
    zero_control=np.zeros_like(score)
    grad_a=np.hypot(*np.gradient(a))
    grad_b=np.hypot(*np.gradient(b))
    edge=np.sqrt(grad_a*grad_b)
    q=float(np.quantile(edge[interior],0.99))
    edge_control=np.where(interior,np.clip(edge/max(q,1e-6),0,1),0).astype(np.float32)
    for tr,tc in DIRECTIONS:
        nr,nc=-tc,tr
        k=_kernel(tr,tc)
        marker_gains=[]
        marker_zero=[]
        for x in (a,b):
            pair_gains=[]
            for left_offset,right_offset in ((FLANK,-FLANK),(3*FLANK,FLANK),(-FLANK,-3*FLANK)):
                plus,minus=_shift(x,left_offset*nr,left_offset*nc),_shift(x,right_offset*nr,right_offset*nc)
                mp,mm=convolve(plus,k,mode="nearest"),convolve(minus,k,mode="nearest")
                vp=np.maximum(convolve(plus*plus,k,mode="nearest")-mp*mp,0)
                vm=np.maximum(convolve(minus*minus,k,mode="nearest")-mm*mm,0)
                corr0=np.clip((convolve(plus*minus,k,mode="nearest")-mp*mm)/np.sqrt(np.maximum(vp*vm,1e-12)),-1,1)
                if left_offset==FLANK:
                    marker_zero.append(np.maximum(corr0,0))
                gains={}
                for lag in LAGS:
                    shifted=_shift(minus,lag*tr,lag*tc)
                    shifted_mean=_shift(mm,lag*tr,lag*tc)
                    shifted_var=_shift(vm,lag*tr,lag*tc)
                    denom=np.sqrt(np.maximum(vp*shifted_var,1e-12))
                    corr=np.clip((convolve(plus*shifted,k,mode="nearest")-mp*shifted_mean)/denom,-1,1)
                    textured=(vp>VARIANCE_FLOOR)&(shifted_var>VARIANCE_FLOOR)
                    gains[lag]=np.where(textured&(corr>MIN_CORRELATION),np.maximum(corr-corr0,0)/2,0).astype(np.float32)
                pair_gains.append(gains)
            # Smooth oblique bedding/textures also gain under an along-profile
            # shift. Subtract that same-lag gain measured on BOTH same-side pairs.
            marker_gains.append({lag:np.maximum(pair_gains[0][lag]-np.maximum(pair_gains[1][lag],pair_gains[2][lag]),0)
                                 for lag in LAGS})
        zero=np.sqrt(marker_zero[0]*marker_zero[1])
        np.maximum(zero_control,np.where(interior,zero,0),out=zero_control)
        for lag in LAGS:
            joint=np.sqrt(marker_gains[0][lag]*marker_gains[1][lag]).astype(np.float32)
            np.maximum(score,np.where(interior,joint,0),out=score)
    return score, {"zero_lag_control":zero_control,"generic_dual_edge_control":edge_control}, {
        "directions_row_col":DIRECTIONS,"nonzero_signed_lags":LAGS,"flank_steps":FLANK,
        "half_profile_steps":HALF_LENGTH,"working_grid_cell_m":200,"guard_steps":GUARD,
        "variance_floor":VARIANCE_FLOOR,"minimum_correlation":MIN_CORRELATION,"same_side_control_offsets":[[6,2],[-2,-6]],
        "common_valid_cells":int(valid.sum()),"guarded_interior_cells":int(interior.sum()),
        "output_semantics":"Uncalibrated matching-improvement confidence; not measured displacement or fault probability."}
