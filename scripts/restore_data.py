#!/usr/bin/env python3
"""Restore current required core/external/DEM inputs, verifying every SHA-256.

Pinned team bridge transport; no independent DrivenData archive access implied.
Unused historical 5GEMSDOE contexts are NOT fetched. Ignored files may vanish after
an Arena snapshot; rerunning this command is idempotent and verifies the cache.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from gems.downloader import restore_core,restore_dem10,restore_external  # noqa: E402


def data_folder():
    if os.environ.get("GEMS_DATA_DIR"):
        p=Path(os.environ["GEMS_DATA_DIR"]).expanduser()
        p=p if p.is_absolute() else ROOT/p
    else:
        backing=ROOT/".cache/gems_data";backing.mkdir(parents=True,exist_ok=True)
        p=ROOT/"data"
        if not p.exists() and not p.is_symlink():
            p.symlink_to(".cache/gems_data",target_is_directory=True)
    p.mkdir(parents=True,exist_ok=True)
    return p


def write_report(path,report):
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    os.replace(temp,path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dem-only",action="store_true",help="Only restore/check the pinned 13 DEM channels (fetch_dem10 compatibility)")
    args=parser.parse_args(argv)
    pins=json.loads((ROOT/"registry/data_inputs.json").read_text())
    folder=data_folder();(ROOT/"evidence").mkdir(exist_ok=True)
    with (folder/".restore.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        core=external=[]
        if not args.dem_only:
            print("[1/3] Verify/restore three core competition bridge rasters...",flush=True)
            core=restore_core(pins,folder,ROOT/".cache/bridge")
            print("[2/3] Verify/restore lidar + radiometric/extension rasters AND metadata...",flush=True)
            external=restore_external(pins,folder)
        print("[3/3] Verify/restore all 13 label-free DEM10 channels...",flush=True)
        channels,manifest=restore_dem10(pins,folder)
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
        p=pins["dem10"]
        dem_report={"generated_utc":now,"source_repo":p["repo"],"source_tag":p["historical_tag"],
                    "source_tag_commit":p["commit"],"fetch_ref":"immutable full commit, not mutable tag",
                    "manifest_sha256":p["manifest_sha256"],"upstream_product":manifest["product"],
                    "upstream_product_catalog":manifest["product_catalog"],
                    "upstream_tiles":{k:{"url":v["url"],"sha256":v["sha256"],"bytes":v["bytes"]} for k,v in manifest["tiles"].items()},
                    "upstream_tiles_refetched_this_run":False,"template_sha256":manifest["template_sha256"],
                    "footprint_pixels":manifest["footprint_pixels"],"vector_order":manifest["vector_order"],
                    "grid":manifest["grid"],"channels":channels,"labels_used":False}
        write_report(ROOT/"evidence/dem10_fetch_verification.json",dem_report)
        if not args.dem_only:
            report={"schema_version":1,"generated_utc":now,"data_directory":str(folder),
                    "provenance_scope":pins["provenance_scope"],"official_archive_independently_compared":False,
                    "core":core,"external":external,"dem10_channels":channels,
                    "all_required_bytes_sha256_verified":True,"atomic_downloads":True,
                    "optional_unused_contexts_fetched":False,"drivendata_automated_access":False}
            write_report(ROOT/"evidence/data_restore_verification.json",report)
        print(f"Verified {len(core)} core, {len(external)} external raster/metadata files, {len(channels)} DEM channels. No unused contexts fetched.")


if __name__=="__main__":
    main()
