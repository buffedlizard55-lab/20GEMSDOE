"""Final-review regressions: source-health failure propagation and frozen evidence."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from gems.cache import load_bundle,metadata_path,save_bundle
from gems.paths import ROOT
from gems.downloader import fetch_atomic,safe_relative


def source_module():
    spec=importlib.util.spec_from_file_location('review_source_health',ROOT/'scripts/source_health.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_source_health_failure_is_not_reported_as_success(tmp_path,monkeypatch):
    m=source_module();dest=tmp_path/'health.json'
    monkeypatch.setattr(sys,'argv',['source_health','--output',str(dest)])
    monkeypatch.setattr(m.time,'sleep',lambda x:None)
    def fake_probe(url):
        assert not m.blocked_host(url)
        return {'url':url,'ok':False,'status':404,'error':'test unavailable'}
    monkeypatch.setattr(m,'probe',fake_probe)
    assert m.main()==1
    report=json.loads(dest.read_text())
    assert report['results'] and report['skipped_drivendata']


def test_source_health_blocks_contest_hosts_and_redirects():
    import urllib.error
    import urllib.request
    m=source_module()
    assert m.blocked_host('https://community.drivendata.org:443/example')
    assert not m.blocked_host('https://drivendata.org.unrelated.example/')
    with pytest.raises(ValueError):m.probe('https://www.drivendata.org/example')
    with pytest.raises(urllib.error.HTTPError):
        m.SafeRedirect().redirect_request(urllib.request.Request('https://example.org/'),None,302,'redirect',{},'https://www.drivendata.org/example')


def test_bad_zip_cache_is_a_miss_even_if_metadata_sha_matches_corrupt_bytes(tmp_path):
    path=tmp_path/'cache.npz';save_bundle(path,{'a':np.arange(10)},{} )
    path.write_bytes(path.read_bytes()[:32])
    meta=json.loads(metadata_path(path).read_text());meta['array_file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    metadata_path(path).write_text(json.dumps(meta))
    assert load_bundle(path,{}) is None


@pytest.mark.parametrize('name',['.','a?ref=main','a#fragment','a\x00bad'])
def test_downloader_rejects_ambiguous_or_query_paths(name):
    with pytest.raises(ValueError):safe_relative(name)


def test_full_commit_required_even_for_cached_valid_bytes(tmp_path):
    p=tmp_path/'file';p.write_bytes(b'known')
    with pytest.raises(ValueError):
        fetch_atomic(p,repo='o/r',commit='main',source='file',sha=hashlib.sha256(b'known').hexdigest(),size=5)


def test_frozen_H22_reports_match_additive_correction_and_remain_rejected():
    note=json.loads((ROOT/'evidence/h22_metric_schema_annotations.json').read_text())
    for r in note['reports']:
        data=(ROOT/r['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==r['sha256']
        d=json.loads(data)
        assert d['decision']=='REJECT_NO_RETUNING' and not d['submission_artifact_created']
    assert note['one_shot_results_not_rerun'] and note['primary_binary_decisions_unchanged']


def test_historical_tests_no_longer_offer_force_rerun():
    for name in ['evaluate_h21_seismic_ridge.py','evaluate_h21_2_geotherm_coherence.py']:
        r=subprocess.run([sys.executable,str(ROOT/'scripts'/name),'--help'],capture_output=True,text=True)
        assert r.returncode==0 and '--force' not in r.stdout
        r=subprocess.run([sys.executable,str(ROOT/'scripts'/name)],capture_output=True,text=True)
        assert r.returncode!=0 and 'consumed' in r.stderr


def test_zip_export_is_atomic_and_cannot_destroy_its_source(tmp_path,monkeypatch):
    from gems.submission import zip_single
    source=tmp_path/'source.tif';source.write_bytes(b'controlled test bytes')
    with pytest.raises(ValueError):zip_single(source,source,overwrite=True)
    assert source.read_bytes()==b'controlled test bytes'
    out=zip_single(source)
    before=out.read_bytes()
    with pytest.raises(FileExistsError):zip_single(source)
    import gems.submission as mod
    def interrupted(*args,**kwargs):raise OSError('interrupted packaging')
    monkeypatch.setattr(mod.zipfile.ZipFile,'writestr',interrupted)
    with pytest.raises(OSError):zip_single(source,out,overwrite=True)
    assert out.read_bytes()==before and source.read_bytes()==b'controlled test bytes'
    assert sorted(p.name for p in tmp_path.iterdir())==['source.tif','source.zip']
