"""Regression coverage for fail-closed decoding, endian/predictor and browser export."""
import json
import shutil
import struct
import subprocess

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems.paths import ROOT,SITE_DATA_DIR
from gems.submission import check_variants

NODE=shutil.which("node")
pytestmark=pytest.mark.skipif(NODE is None,reason="Node required for browser-module tests")
MODULE=ROOT/"docs/js/gems-tiff.js"
FP=SITE_DATA_DIR/"footprint.bin"


def node(code,*args):
    r=subprocess.run([NODE,"-e",code,str(MODULE),str(FP),*map(str,args)],capture_output=True,text=True,timeout=120)
    assert r.returncode==0,r.stdout+r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def pred(footprint):
    rows=np.arange(footprint.shape[0],dtype=np.float32)[:,None]
    vals=np.broadcast_to((rows%103)/102,footprint.shape)
    return np.where(footprint,vals,np.nan).astype(np.float32)


def write(path,pred,template_tif,**kw):
    with rasterio.open(template_tif) as d:
        profile=d.profile.copy()
    profile.update(kw)
    with rasterio.open(path,"w",**profile) as d:
        d.write(pred,1)
    return path


def check(path):
    return node("const G=require(process.argv[1]),fs=require('fs');(async()=>{const fp=await G.decodeFootprint(fs.readFileSync(process.argv[2])); console.log(JSON.stringify(await G.checkFile(fs.readFileSync(process.argv[3]),fp)));})().catch(e=>{console.error(e);process.exit(1)});",path)


@pytest.mark.parametrize("encoding", [dict(compress="none",ENDIANNESS="BIG"),dict(compress="lzw",ENDIANNESS="BIG"),
                                      dict(compress="deflate",predictor=3,ENDIANNESS="BIG"),
                                      dict(compress="lzw",predictor=3),dict(compress="deflate",predictor=3,tiled=True,blockxsize=256,blockysize=256)])
def test_endian_and_predictor_encodings_match_numpy(tmp_path,pred,footprint,template_tif,encoding):
    p=write(tmp_path/"encoding.tif",pred,template_tif,**encoding)
    r=check(p)
    assert r["ok"],r
    assert r["stats"]["mass"]==pytest.approx(float(pred[footprint].sum(dtype=np.float64)),rel=1e-8)
    assert r["stats"]["positives"]==int((pred[footprint]>0).sum())


def test_metadata_only_or_unverified_mask_can_never_pass():
    p=next((ROOT/"docs/downloads").glob("*-nan.tif"))
    r=node("const G=require(process.argv[1]),fs=require('fs');(async()=>{const i=G.parseTiff(fs.readFileSync(process.argv[3]));const fp=await G.decodeFootprint(fs.readFileSync(process.argv[2]));const a=G.preflight(null,i,fp),b=G.preflight(new Float32Array(i.width*i.height),i,null);console.log(JSON.stringify([a,b]));})()",p)
    for result in r:
        assert not result["ok"] and {"footprint_nan","range"}<=set(result["hardFailures"])


def mutate_tag(data,tag,mutate):
    data=bytearray(data);le=data[:2]==b"II";order="<" if le else ">"
    ifd=struct.unpack_from(order+"I",data,4)[0];count=struct.unpack_from(order+"H",data,ifd)[0]
    for i in range(count):
        at=ifd+2+12*i
        if struct.unpack_from(order+"H",data,at)[0]==tag:
            mutate(data,at,order)
            return bytes(data)
    raise AssertionError(f"tag {tag} missing")


def test_truncated_blocks_and_missing_strips_fail_closed(tmp_path,pred,template_tif):
    original=write(tmp_path/"original.tif",pred,template_tif,compress="lzw")
    raw=original.read_bytes()
    def truncate_count(d,at,order):
        n=struct.unpack_from(order+"I",d,at+4)[0]
        typ=struct.unpack_from(order+"H",d,at+2)[0]
        assert typ in (3,4), "StripByteCounts SHORT/LONG required"
        width,fmt=(2,"H") if typ==3 else (4,"I")
        offset=at+8 if n*width<=4 else struct.unpack_from(order+"I",d,at+8)[0]
        last=offset+(n-1)*width
        value=struct.unpack_from(order+fmt,d,last)[0]
        struct.pack_into(order+fmt,d,last,value-1)
    short=tmp_path/"short.tif";short.write_bytes(mutate_tag(raw,279,truncate_count))
    result=check(short)
    assert not result["ok"] and "read" in result["hardFailures"]
    assert "missing end code" in next(c["detail"] for c in result["checks"] if c["id"]=="read")
    def remove_strip(d,at,order):
        count=struct.unpack_from(order+"I",d,at+4)[0];struct.pack_into(order+"I",d,at+4,count-1)
    missing=tmp_path/"missing.tif";missing.write_bytes(mutate_tag(raw,273,remove_strip))
    result=check(missing)
    assert not result["ok"] and "read" in result["hardFailures"]
    unreadable=tmp_path/"broken.tif";unreadable.write_bytes(b"II*\x00\xff\xff\xff\xff")
    assert check(unreadable)["hardFailures"]==["parse"]


def test_nonzero_tiepoint_index_and_rotation_are_checked(tmp_path,pred,template_tif):
    original=write(tmp_path/"original.tif",pred,template_tif,compress="lzw")
    def tiepoint(d,at,order):
        offset=struct.unpack_from(order+"I",d,at+8)[0];struct.pack_into(order+"d",d,offset,7.)
    shifted=tmp_path/"shifted.tif";shifted.write_bytes(mutate_tag(original.read_bytes(),33922,tiepoint))
    assert "geotransform" in check(shifted)["hardFailures"]
    rotated=write(tmp_path/"rotated.tif",pred,template_tif,compress="lzw",transform=Affine(100,.5,243350,0,-100,4508550))
    assert "geotransform" in check(rotated)["hardFailures"]


def test_mask_uleb128_and_sha_corruption_rejected():
    r=node("const G=require(process.argv[1]),fs=require('fs');(async()=>{const errors=[];for(const b of [[128],[3],[0,0,4]]){try{G.decodeMaskRuns(new Uint8Array(b),4);errors.push(false)}catch(e){errors.push(true)}}const bytes=fs.readFileSync(process.argv[2]);bytes[0]^=1;try{await G.decodeFootprint(bytes);errors.push(false)}catch(e){errors.push(true)}console.log(JSON.stringify(errors))})()")
    assert r==[True,True,True,True]


def test_browser_writer_roundtrips_in_python_and_never_changes_inside_values(tmp_path,footprint,template_tif):
    source=next((ROOT/"docs/downloads").glob("*continuous*-allfinite.tif"));target=tmp_path/"export.tif"
    r=node("const G=require(process.argv[1]),fs=require('fs');(async()=>{const fp=await G.decodeFootprint(fs.readFileSync(process.argv[2]));const raw=fs.readFileSync(process.argv[3]);const checked=await G.checkFile(raw,fp,{includeRaster:true});if(!checked.ok)throw Error('source failed');const bytes=G.writeSubmission(checked.raster,fp);fs.writeFileSync(process.argv[4],bytes);const out=await G.checkFile(bytes,fp);console.log(JSON.stringify(out));})().catch(e=>{console.error(e);process.exit(1)});",source,target)
    assert r["ok"] and r["officialFormatCompliant"]
    assert check_variants(target,template_tif)["official_format_compliant"]
    with rasterio.open(source) as a,rasterio.open(target) as b:
        x,y=a.read(1),b.read(1)
        np.testing.assert_array_equal(x[footprint],y[footprint])
        assert np.isnan(y[~footprint]).all()


def test_verified_mask_cannot_be_forged_or_mutated_without_detection():
    p=next((ROOT/"docs/downloads").glob("*-nan.tif"))
    r=node("const G=require(process.argv[1]),fs=require('fs');(async()=>{const fp=await G.decodeFootprint(fs.readFileSync(process.argv[2]));const info=G.parseTiff(fs.readFileSync(process.argv[3]));const x=await G.readRaster(fs.readFileSync(process.argv[3]),info);const fake=fp.slice();fake.gemsFootprintSha256=G.EXPECT.footprintSha256;const a=G.preflight(x,info,fake);let z=fp.indexOf(0),o=fp.indexOf(1);fp[z]=1;fp[o]=0;const b=G.preflight(x,info,fp);console.log(JSON.stringify([a.ok,b.ok]));})()",p)
    assert r==[False,False]


def test_outside_range_is_rejected_consistently(tmp_path,pred,footprint,template_tif):
    values=pred.copy();values[~footprint]=2
    p=write(tmp_path/"bad-outside.tif",values,template_tif,compress="lzw")
    assert "outside_range" in check(p)["hardFailures"]
    assert not check_variants(p,template_tif)["format_check_passed"]
