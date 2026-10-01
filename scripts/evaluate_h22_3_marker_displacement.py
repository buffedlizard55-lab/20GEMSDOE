#!/usr/bin/env python3
"""One preregistered dual-marker displacement screen; no submission packaging."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from gems.holdout import Holdout, gate  # noqa: E402
from gems.marker_matching import paired_marker_displacement  # noqa: E402
from gems.multiple_testing import exact_paired_signflip_test, holm_bonferroni_and_bh_correction  # noqa: E402
from gems.paths import DATA_DIR,EVIDENCE_DIR  # noqa: E402
from gems.research_gate import SingleUseRun,committed_protocol,utc_now  # noqa: E402
from gems.validator import sha256_file  # noqa: E402
from evaluate_h22_2_magnetic_low import PINS,REFERENCES,FAMILY  # noqa: E402

ID="H22-3"
RESULT=EVIDENCE_DIR/"h22_3_marker_displacement_holdout.json"
LOCK=EVIDENCE_DIR/"runs/h22_3_once.json"
PREREG=ROOT/"docs/research/preregistration_h22_3.md"
RAD_SHA="c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682"
RAD_META_SHA="d917fd08f89c160d2a0ba91af9c3321c8c8b5677fcdba39b10e684384cbc7488"


def block_mean(x):
    h,w=x.shape
    if h%2 or w%2:
        raise ValueError("frozen block mean requires an even template grid")
    return x.reshape(h//2,2,w//2,2).mean(axis=(1,3)).astype(np.float32)


def upsample(x):
    return np.repeat(np.repeat(x,2,axis=0),2,axis=1)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    if RESULT.exists() or LOCK.exists():
        parser.error("H22-3 consumed; no second outcome access or retuning")
    source_paths=[PREREG,Path(__file__),ROOT/"scripts/evaluate_h22_2_magnetic_low.py",
                  ROOT/"src/gems/marker_matching.py",ROOT/"src/gems/holdout.py",ROOT/"src/gems/metric.py",
                  ROOT/"src/gems/multiple_testing.py",ROOT/"src/gems/research_gate.py"]
    protocol=committed_protocol(ROOT,source_paths)
    expected={**PINS,"external/geodawn_rad_u8.tif":RAD_SHA,"external/geodawn_rad.json":RAD_META_SHA}
    hashes={name:sha256_file(DATA_DIR/name) for name in expected}
    if hashes!=expected:
        raise RuntimeError("frozen input SHA mismatch")
    for name,sha in REFERENCES.items():
        if sha256_file(EVIDENCE_DIR/name)!=sha:
            raise RuntimeError("reference SHA mismatch")
    prior_result=EVIDENCE_DIR/"h22_2_magnetic_low_holdout.json"
    prior=json.loads(prior_result.read_text())
    if prior["candidate_id"]!="H22-2" or prior["decision"]!="REJECT_NO_RETUNING":
        raise RuntimeError("previous frozen-family result changed")
    with SingleUseRun(LOCK,ID,{"protocol":protocol,"inputs":hashes,"comparator_hashes":REFERENCES,
                              "previous_family_result_sha256":sha256_file(prior_result)}):
        with rasterio.open(DATA_DIR/"sample_submission.tif") as d:
            fp=np.isfinite(d.read(1));grid=(d.shape,d.crs,d.transform)
        with rasterio.open(DATA_DIR/"training_features.tif") as d:
            if (d.shape,d.crs,d.transform)!=grid or d.tags(2).get("band_name")!="rtp":
                raise RuntimeError("RTP band/grid mismatch")
            rtp=d.read(2).astype(np.float32)
        with rasterio.open(DATA_DIR/"external/geodawn_rad_u8.tif") as d:
            if (d.shape,d.crs,d.transform)!=grid or d.descriptions[0]!="K":
                raise RuntimeError("radiometric K grid/description mismatch")
            k=d.read(1).astype(np.float32)
        common=fp&np.isfinite(rtp)&(rtp>-1e20)&(k>0)
        coarse_valid=block_mean(common.astype(np.float32))==1
        a,b=block_mean(np.where(common,rtp,0)),block_mean(np.where(common,k,0))
        print("Computing fixed paired-marker transform and controls (no labels used)...",flush=True)
        score,controls,meta=paired_marker_displacement(a,b,coarse_valid)
        full=upsample(score)
        del a,b,rtp,k
        with rasterio.open(DATA_DIR/"labels.tif") as d:
            if (d.shape,d.crs,d.transform)!=grid:
                raise RuntimeError("catalogue grid mismatch")
            labels=(d.read(1)>0)&fp
        evaluator=Holdout(fp,labels,budget=.025,sparse_seed_offset=0)
        idx=evaluator.fp_idx
        candidate=evaluator.evaluate(full.ravel()[idx])
        evaluated_controls={name:evaluator.evaluate(upsample(value).ravel()[idx]) for name,value in controls.items()}
        continuous=evaluator.score_mask(full)
        h16=json.loads((EVIDENCE_DIR/"spatial_holdout_h16_results.json").read_text())["summary"]["H16_1_SeamFree_MultiScale_Synthesis"]
        old=json.loads((EVIDENCE_DIR/"spatial_holdout_results.json").read_text())["summary"]
        dense,sparse=old["H20_1_SAR_nnPU_MultiLine_Corroborated"],old["H20_5_Calibrated_Continuous_SoftTail_nnpu"]
        historical={"mean_dense_dti":dense["mean_dense_dti"],"fold_dense":dense["fold_dense"],
                    "mean_sparse_dti":sparse["mean_sparse_dti"],"fold_sparse":sparse["fold_sparse"]}
        gh16,gh20=gate(candidate,h16),gate(candidate,historical)
        control_pass=all(candidate["mean_sparse_dti"]>x["mean_sparse_dti"] for x in evaluated_controls.values())
        practical=gh16["passed"] and gh20["passed"] and control_pass
        test=exact_paired_signflip_test(candidate["fold_sparse"],h16["fold_sparse"])
        p_previous=prior["multiplicity"]["raw_exact_signflip_test"]["p_value_raw"]
        rows=[{"id":name,"p_value_raw":test["p_value_raw"] if name==ID else p_previous if name=="H22-2" else 1.,
               "status":"evaluated" if name in (ID,"H22-2") else "pending; p=1"} for name in FAMILY]
        corrected=holm_bonferroni_and_bh_correction(rows)
        significant=next(x for x in corrected if x["id"]==ID)["pass_holm_fwer"]
        report={"schema_version":2,"generated_utc":utc_now(),"candidate_id":ID,
                "status":"EXPLORATORY_REUSED_KNOWN_CATALOGUE_SPATIAL_TRANSFER_PROXY",
                "preregistration":protocol,"input_sha256":hashes,
                "software_versions":{p:importlib.metadata.version(p) for p in ("numpy","scipy","rasterio")},
                "observations":{"magnetic":"competition RTP band 2", "radiometric":"encoded K texture, not physical concentration or K/Th ratio",
                                "common_valid_native_pixels":int(common.sum()),"native_footprint_pixels":int(fp.sum())},
                "transform_metadata":meta,
                "evaluation":{"candidate":candidate,**evaluated_controls,"continuous_confidence_dti_descriptive_only":continuous},
                "comparisons":{"vs_h16":gh16,"vs_historical_h20_thresholds":gh20,
                               "sparse_beats_both_controls":control_pass,"practical_screen_passed":practical},
                "multiplicity":{"family_ids_frozen_before_first_test":list(FAMILY),
                                "primary_endpoint":"Sparse proxy DTI vs H16-1", "raw_exact_signflip_test":test,
                                "holm_and_bh":corrected,"passes_holm_fwer":significant},
                "final_confirmation":{"status":"BLOCKED_NO_NEW_INDEPENDENT_LABELS","touched":False},
                "slot_recommendation":False,"submission_artifact_created":False,"submission_slot_spent":False,
                "decision":"REJECT_NO_RETUNING" if not practical else "PROXY_SCREEN_ONLY_BLOCKED_INDEPENDENT_CONFIRMATION",
                "limitations":["Known catalogue and synthetic sparse components are not hidden outcomes or verified negatives.",
                               "The region predominantly contains extensional faults; lateral-offset matching may miss normal faults.",
                               "Encoded radiometric values lack retained per-channel dequantization limits; correlation uses texture only.",
                               "Smooth oblique textures have same-side controls, but periodic/nonunique markers can still produce ambiguous matches.",
                               "Both channels share the aerial survey: correlated flight-line/processing errors can imitate geological matching.",
                               "Working-grid diagonal/cardinal physical step lengths differ; orientation discretization is coarse.",
                               "Four reused adjacent blocks cannot pass Holm at 0.05 or establish independent generalization.",
                               "No measured displacement or calibrated probability is claimed; no model blend, artifact or slot is authorized."]}
        with RESULT.open("x") as f:
            f.write(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"candidate":ID,"dense":candidate["mean_dense_dti"],"sparse":candidate["mean_sparse_dti"],
                      "practical_screen_passed":practical,"holm_passed":significant,"decision":report["decision"],"slot_spent":False},indent=2))


if __name__=="__main__":
    main()
