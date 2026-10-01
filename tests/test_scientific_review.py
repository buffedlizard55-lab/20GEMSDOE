"""Synthetic numerical unit tests ONLY, never empirical GEMS calibration evidence."""
from pathlib import Path
import json

import numpy as np
import pytest
from scipy.integrate import quad

from gems.cache import cache_fingerprint, load_bundle, metadata_path, save_bundle
from gems.calibration import OutOfFoldPUCalibrator, brier_decomposition_murphy1973
from gems.holdout import Holdout, gate, thin_components
from gems.pu_learning import (KiryoNNPULinearHead, compute_pu_risk_metrics,
                              fit_nnpu_boosted_expert, pu_risk_and_grad, truncated_pareto_mean)


@pytest.mark.parametrize("loss", ["logistic", "sigmoid"])
@pytest.mark.parametrize("distribution", ["marginal", "catalogue_complement"])
def test_actual_nnpu_gradient_finite_difference(loss, distribution):
    p, u = np.array([0.2,1.1]), np.array([-0.3,0.4,0.8])
    kwargs = {"loss_type":loss,"unlabeled_distribution":distribution}
    if distribution=="catalogue_complement":
        kwargs["pi_observed"] = 0.05
    r,gp,gu = pu_risk_and_grad(p,u,0.2,**kwargs)
    assert r["unbiased_neg_risk_raw"]>0
    for a,gradient,which in ((p,gp,0),(u,gu,1)):
        for i in range(len(a)):
            left, right = a.copy(), a.copy()
            left[i]-=1e-6
            right[i]+=1e-6
            argsleft = (left,u) if which==0 else (p,left)
            argsright = (right,u) if which==0 else (p,right)
            derivative=(pu_risk_and_grad(*argsright,0.2,**kwargs)[0]["R_nnPU"]-
                        pu_risk_and_grad(*argsleft,0.2,**kwargs)[0]["R_nnPU"])/(2e-6)
            assert derivative==pytest.approx(gradient[i],abs=1e-7)


def test_complement_formula_not_marginal_formula():
    p,u=np.array([1.0,2.0]),np.array([-1.0,0.0])
    r=compute_pu_risk_metrics(p,u,0.2,loss_type="logistic",unlabeled_distribution="catalogue_complement",pi_observed=0.05)
    assert r["unbiased_neg_risk_raw"]==pytest.approx(0.95*np.logaddexp(0,u).mean()-0.15*np.logaddexp(0,p).mean())
    with pytest.raises(ValueError):
        compute_pu_risk_metrics(p,u,0.2,unlabeled_distribution="catalogue_complement")
    with pytest.raises(ValueError):
        compute_pu_risk_metrics(p,u,0.2,pi_observed=0.05)


def test_kiryo_reverse_step_is_not_clamped_risk_gradient():
    p,u=np.array([10.0]),np.array([-10.0])
    r,gp,gu=pu_risk_and_grad(p,u,0.4,loss_type="logistic",reverse_gradient=True)
    assert r["reverse_gradient_step"] and gp[0]>0 and gu[0]<0
    assert r["R_nnPU"]>=0 and r["unbiased_neg_risk_raw"]<0
    r2,gp2,gu2=pu_risk_and_grad(p,u,0.4,loss_type="logistic")
    assert gp2[0]<0 and gu2[0]==0 and not r2["reverse_gradient_step"]


@pytest.mark.parametrize("pi", [-0.1,0,1,1.1,np.nan,np.inf])
def test_bad_prior_is_not_silently_clipped(pi):
    with pytest.raises(ValueError):
        KiryoNNPULinearHead(pi)


def test_small_dataset_has_no_empty_fake_minibatches_and_fit_is_repeatable():
    p=np.array([[1.,1.],[2.,1.],[3.,1.]])
    u=np.column_stack([np.arange(-5.,0),np.ones(5)])
    kwargs={"pi":0.3,"n_epochs":3,"batch_size":4096,"loss_type":"logistic",
            "unlabeled_distribution":"catalogue_complement","pi_observed":0.1}
    a,b=KiryoNNPULinearHead(**kwargs).fit(p,u),KiryoNNPULinearHead(**kwargs).fit(p,u)
    assert a.total_steps_==3
    np.testing.assert_array_equal(a.w_,b.w_)
    assert np.isfinite(a.predict_proba(u)).all()
    assert a.predict_proba(np.zeros((0,2))).shape==(0,)
    with pytest.raises(ValueError):
        a.fit(np.zeros((0,2)),u)
    with pytest.raises(RuntimeError,match="Retired"):
        fit_nnpu_boosted_expert(None,None,None,None)


@pytest.mark.parametrize("alpha", [0.7,1.0,1.000000001,1.4,2.0])
def test_truncated_pareto_mean_matches_numerical_integral(alpha):
    lo,hi=300.,1650.
    z=lo**(-alpha)-hi**(-alpha)
    expected=quad(lambda x:alpha*x**(-alpha)/z,lo,hi)[0]
    assert truncated_pareto_mean(alpha,lo,hi)==pytest.approx(expected,rel=1e-8)


def test_continuous_brier_requires_within_bin_correction():
    r=brier_decomposition_murphy1973(np.array([.1,.4]),np.array([0,1]),n_bins=1)
    assert r["brier_score_exact"]==pytest.approx(.185)
    assert r["brier_score_bin_coarsened"]==pytest.approx(.3125)
    assert r["within_bin_correction"]==pytest.approx(-.1275)
    assert r["brier_score_raw_reconstructed"]==pytest.approx(r["brier_score_exact"])
    assert abs(r["closure_error_raw"])<1e-12
    assert r["stated_0_70_audit"]["target_positive_rate"] is None


def test_weighted_brier_partition_closes_and_empty_bins_are_null():
    r=brier_decomposition_murphy1973(np.array([.05,.15,.75,1.]),np.array([0,1,1,0]),n_bins=10,
                                    sample_weight=np.array([1.,7.,3.,2.]))
    assert abs(r["closure_error_raw"])<1e-12
    empty=next(b for b in r["reliability_diagram_bins"] if b["count"]==0)
    assert empty["mean_predicted_prob"] is None and empty["target_positive_rate"] is None


@pytest.mark.parametrize("p,y,bins", [([np.nan],[0],10),([1.1],[0],10),([.2],[.3],10),([.2],[0,1],10),([.2],[0],0),([.2],[0],2.5)])
def test_calibration_rejects_bad_inputs_instead_of_creating_targets(p,y,bins):
    with pytest.raises(ValueError):
        brier_decomposition_murphy1973(np.array(p),np.array(y),bins)


def test_calibrator_does_not_use_labels_outside_eval_mask():
    p=np.array([.1,.2,.5,.8,np.nan])
    y=np.array([0,0,1,1,np.nan])
    mask=np.array([1,1,1,1,0],bool)
    a=OutOfFoldPUCalibrator().fit_transform_oof(p,y,mask,np.array([5,6,5,6,-1]))
    assert np.isfinite(a[mask]).all() and np.isnan(a[~mask]).all()
    with pytest.raises(ValueError):
        OutOfFoldPUCalibrator(c_labeling_freq=0)


def test_hash_cache_rejects_absent_metadata_and_tampering(tmp_path):
    inputfile=tmp_path/"input"
    inputfile.write_text("trusted")
    fp=cache_fingerprint({"input":inputfile},{},parameters={"folds":[0,1]},packages=())
    path=tmp_path/"cache.npz"
    assert load_bundle(path,fp) is None
    save_bundle(path,{"a":np.arange(4,dtype=np.float32)},fp)
    np.testing.assert_array_equal(load_bundle(path,fp)["a"],np.arange(4))
    bad=dict(fp,parameters={"folds":[2,3]})
    assert load_bundle(path,bad) is None
    meta=json.loads(metadata_path(path).read_text())
    meta["arrays"]["a"]["shape"]=[9]
    metadata_path(path).write_text(json.dumps(meta))
    assert load_bundle(path,fp) is None
    save_bundle(path,{"a":np.arange(4)},fp)
    with path.open("ab") as f:
        f.write(b"tamper")
    assert load_bundle(path,fp) is None


def test_holdout_empty_truth_and_zero_budget_do_not_emit_whole_fold():
    fp=np.ones((20,20),bool)
    lab=np.zeros_like(fp)
    assert not thin_components(lab,.2,42).any()
    h=Holdout(fp,lab,budget=.0001)
    p=np.zeros(fp.sum())
    assert not h.emit(p).any()
    assert not h.emit_quadrant(p,0,k_override=0).any()
    with pytest.raises(ValueError):
        h.to_2d(np.ones(10))


def test_continuous_scores_report_mass_not_truncated_pixel_count():
    fp=np.ones((20,20),bool)
    lab=np.zeros_like(fp);lab[5,5]=1;lab[5,15]=1;lab[15,5]=1;lab[15,15]=1
    r=Holdout(fp,lab).score_mask(np.full(fp.shape,.1))
    assert r["prediction_kind"]=="continuous_scores"
    assert r["mean_dense_dti"]>0 and r["continuous_scores_thresholded"] is False
    for fold in r["folds"].values():
        assert fold["emitted_px"] is None
        assert fold["prediction_mass"]==pytest.approx(.1*fold["nonzero_prediction_pixels"])
    assert sum(f["nonzero_prediction_pixels"] for f in r["folds"].values())==400


def test_gate_rejects_mismatched_fold_vectors():
    a={"mean_dense_dti":.2,"mean_sparse_dti":.1,"fold_dense":[.2]*4,"fold_sparse":[.1]*4}
    bad=dict(a,fold_sparse=[.1]*3)
    with pytest.raises(ValueError):
        gate(bad,a)
