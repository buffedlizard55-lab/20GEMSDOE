"""Atomic restoration and exact effective-prediction identity regression tests."""
import hashlib
from pathlib import Path

import numpy as np
import pytest
import rasterio

from gems.downloader import assemble_atomic,fetch_atomic,safe_relative
from gems.forensics import Grid,gate_candidate,pair_metrics
from gems.submission import make_filename,scored_fingerprint,write_submission


def digest(b):
    return hashlib.sha256(b).hexdigest()


def test_bad_or_interrupted_download_never_replaces_previous_file(tmp_path):
    dest=tmp_path/"data.tif";dest.write_bytes(b"old file")
    def bad(repo,commit,source,tmp):
        tmp.write_bytes(b"truncated")
    with pytest.raises(RuntimeError):
        fetch_atomic(dest,repo="o/r",commit="a"*40,source="data.tif",sha=digest(b"wanted"),size=6,fetch=bad,retries=1)
    assert dest.read_bytes()==b"old file"
    assert list(tmp_path.iterdir())==[dest]
    def interrupted(repo,commit,source,tmp):
        tmp.write_bytes(b"partial")
        raise OSError("network disconnected")
    with pytest.raises(RuntimeError):
        fetch_atomic(dest,repo="o/r",commit="a"*40,source="data.tif",sha=digest(b"wanted"),size=6,fetch=interrupted,retries=1)
    assert dest.read_bytes()==b"old file"


def test_successful_download_is_cached_but_rechecks_bytes(tmp_path):
    dest=tmp_path/"channel.npy";calls=[]
    def fetch(repo,commit,source,tmp):
        calls.append(source);tmp.write_bytes(b"correct")
    kwargs=dict(repo="o/r",commit="b"*40,source="channel.npy",sha=digest(b"correct"),size=7,fetch=fetch,retries=1)
    assert fetch_atomic(dest,**kwargs)["status"]=="fetched-verified"
    assert fetch_atomic(dest,**kwargs)["status"]=="cached-verified"
    dest.write_bytes(b"corrupt")
    assert fetch_atomic(dest,**kwargs)["status"]=="fetched-verified"
    assert len(calls)==2


def test_ordered_part_assembly_validates_each_and_final_hash(tmp_path):
    a,b=tmp_path/"a",tmp_path/"b";a.write_bytes(b"abc");b.write_bytes(b"def")
    parts=[(a,digest(b"abc"),3),(b,digest(b"def"),3)]
    dest=tmp_path/"out";dest.write_bytes(b"prior")
    with pytest.raises(RuntimeError):
        assemble_atomic(parts[::-1],dest,sha=digest(b"abcdef"),size=6)
    assert dest.read_bytes()==b"prior"
    assert assemble_atomic(parts,dest,sha=digest(b"abcdef"),size=6)["status"]=="assembled-verified"
    assert dest.read_bytes()==b"abcdef"
    b.write_bytes(b"broken")
    other=tmp_path/"other"
    with pytest.raises(RuntimeError):
        assemble_atomic(parts,other,sha=digest(b"abcdef"),size=6)
    assert not other.exists()


@pytest.mark.parametrize("name", ["../escape","/absolute","a/../../b","a\\..\\b",""])
def test_dataset_paths_do_not_escape_destination(name):
    with pytest.raises(ValueError):
        safe_relative(name)


def test_exact_continuous_fingerprint_does_not_round_away_changes():
    fp=np.ones((2,3),bool);cat=np.zeros_like(fp);cat[0,0]=1
    a=np.full(fp.shape,.2,dtype=np.float32);b=a.copy()
    b[1,1]=np.nextafter(b[1,1],np.float32(1))
    assert scored_fingerprint(a,fp,cat)["scored_sha256"]!=scored_fingerprint(b,fp,cat)["scored_sha256"]
    b=a.copy();b[cat]=.9
    assert scored_fingerprint(a,fp,cat)==scored_fingerprint(b,fp,cat)
    with pytest.raises(ValueError):
        scored_fingerprint(np.full(fp.shape,np.nan),fp,cat)


def test_duplicate_gate_checks_all_tied_rows_and_empty_support_is_not_identity():
    fp=np.ones((4,4),bool);g=Grid.from_footprint(fp,np.zeros_like(fp))
    a=np.full(fp.shape,.6);near=np.full(fp.shape,.7)
    result=gate_candidate(a,g,[{"id":"a-near","array":near},{"id":"z-exact","array":a.copy()}])
    assert result["verdict"]=="DUPLICATE"
    lowa=np.full(fp.shape,.01);lowb=np.full(fp.shape,.4)
    result=gate_candidate(lowa,g,[{"id":"continuous-other","array":lowb}])
    assert result["verdict"]=="DISTINCT"
    assert result["nearest"][0]["jaccard_positive"]==1  # empty-threshold support, not equality
    assert not result["nearest"][0]["positive_support_union_nonempty"]
    assert result["nearest"][0]["mean_absolute_scored_difference"]==pytest.approx(.39)
    with pytest.raises(ValueError):
        gate_candidate(np.full(fp.shape,np.nan),g,[])


def test_atomic_writer_preserves_template_and_refuses_overwrite(template_tif,footprint,tmp_path):
    pred=np.where(footprint,np.float32(.1),np.float32(np.nan))
    out=write_submission(pred,template_tif,tmp_path/"strict.tif",strict=True)
    before=digest(out.read_bytes())
    with pytest.raises(FileExistsError):
        write_submission(pred,template_tif,out)
    assert digest(out.read_bytes())==before
    with pytest.raises(ValueError,match="template"):
        write_submission(pred,template_tif,template_tif,overwrite=True)
    pred[np.where(footprint)[0][0],np.where(footprint)[1][0]]=np.inf
    with pytest.raises(ValueError):
        write_submission(pred,template_tif,tmp_path/"invalid.tif",strict=True)
    assert not (tmp_path/"invalid.tif").exists()
    with rasterio.open(out) as d:
        assert d.tags()["SANITIZED_IN_FOOTPRINT_PIXELS"]=="0"


def test_filename_rejects_path_traversal_and_unsafe_identifiers():
    with pytest.raises(ValueError):
        make_filename("../escape","hypothesis","20261001","a"*8)
    with pytest.raises(ValueError):
        make_filename("gems20","hypothesis","today","a"*8)
