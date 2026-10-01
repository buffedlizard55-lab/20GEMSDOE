"""Immutable, atomic, checksum-verified restoration through the team's GitHub bridge.

Does not download/poll DrivenData. Bridge integrity != official-host authenticity.
No default-branch clones, optional unused-model dependencies or unverified copies.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import time
from typing import Callable

from .validator import sha256_file

Fetch = Callable[[str, str, str, Path], None]


def valid_file(path: Path, sha: str, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size and sha256_file(path) == sha


def gh_raw(repo: str, commit: str, source: str, dest: Path) -> None:
    if len(commit)!=40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("GitHub source must use a full immutable commit SHA")
    with dest.open("wb") as f:
        subprocess.run(["gh","api",f"repos/{repo}/contents/{source}?ref={commit}","-H","Accept: application/vnd.github.raw"],
                       stdout=f,check=True,timeout=240)
        f.flush()
        os.fsync(f.fileno())


def safe_relative(name: str) -> Path:
    p=PurePosixPath(name)
    if not name or not p.parts or p.is_absolute() or ".." in p.parts or "\\" in name or not re.fullmatch(r"[A-Za-z0-9_./@+-]+",name):
        raise ValueError("unsafe dataset path")
    return Path(*p.parts)


def fetch_atomic(dest: Path, *, repo: str, commit: str, source: str, sha: str, size: int,
                 fetch: Fetch = gh_raw, retries: int = 3) -> dict:
    """Install ONLY verified bytes; interrupted/bad downloads preserve old files."""
    safe_relative(source)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not re.fullmatch(r"[0-9a-f]{40}",commit):
        raise ValueError("valid repository and full immutable commit SHA required even for cache hits")
    if len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha) or size<1 or retries<1:
        raise ValueError("valid expected SHA/size and retry count required")
    dest=Path(dest)
    if valid_file(dest,sha,size):
        return {"sha256":sha,"bytes":size,"status":"cached-verified"}
    dest.parent.mkdir(parents=True,exist_ok=True)
    last=None
    for attempt in range(retries):
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(dir=dest.parent,suffix=".download",delete=False) as f:
                tmp=Path(f.name)
            fetch(repo,commit,source,tmp)
            if not valid_file(tmp,sha,size):
                raise RuntimeError(f"checksum/size mismatch for {source}; untrusted bytes NOT installed")
            os.replace(tmp,dest)
            return {"sha256":sha,"bytes":size,"status":"fetched-verified"}
        except (OSError,subprocess.SubprocessError,RuntimeError) as e:
            last=e
            if attempt+1<retries:
                time.sleep(2**attempt)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
    raise RuntimeError(f"Failed pinned download {repo}@{commit}:{source}. Existing bytes preserved. If GitHub reports authentication failure, reconnect GitHub in Arena. {last}") from last


def assemble_atomic(parts: list[tuple[Path,str,int]], dest: Path, *, sha: str, size: int) -> dict:
    """Explicit ordered parts, each validated; final SHA checked before replacement."""
    if valid_file(dest,sha,size):
        return {"sha256":sha,"bytes":size,"status":"cached-verified"}
    if not parts or sum(p[2] for p in parts)!=size:
        raise ValueError("missing parts or total size mismatch")
    for path,want,n in parts:
        if not valid_file(path,want,n):
            raise RuntimeError(f"invalid/missing assembly part {path}")
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent,suffix=".assembled",delete=False) as f:
            tmp=Path(f.name)
            for part,_,_ in parts:
                with part.open("rb") as src:
                    shutil.copyfileobj(src,f,length=1<<20)
            f.flush();os.fsync(f.fileno())
        if not valid_file(tmp,sha,size):
            raise RuntimeError("assembled file SHA mismatch; old target preserved")
        os.replace(tmp,dest)
        return {"sha256":sha,"bytes":size,"status":"assembled-verified"}
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def restore_core(pins: dict, data_dir: Path, bridge_cache: Path) -> list[dict]:
    p=pins["core"]
    # The embedded manifest records are themselves versioned with the code. Fetch
    # and verify the original manifest too; the raw manifest is never trusted anew.
    fetch_atomic(bridge_cache/"manifest.json",repo=p["repo"],commit=p["commit"],source="data/bridge/manifest.json",
                 sha=p["manifest_sha256"],size=p["manifest_bytes"])
    manifest=json.loads((bridge_cache/"manifest.json").read_text())
    if manifest["files"]!=p["files"]:
        raise RuntimeError("bridge manifest differs from frozen file pins")
    rows=[]
    for file in p["files"]:
        dest=data_dir/safe_relative(file["canonical"])
        if valid_file(dest,file["sha256"],file["bytes"]):
            result={"sha256":file["sha256"],"bytes":file["bytes"],"status":"cached-verified"}
        elif file.get("parts"):
            parts=[]
            for part in file["parts"]:
                path=bridge_cache/safe_relative(part["name"])
                fetch_atomic(path,repo=p["repo"],commit=p["commit"],source="data/bridge/"+part["name"],sha=part["sha256"],size=part["bytes"])
                parts.append((path,part["sha256"],part["bytes"]))
            result=assemble_atomic(parts,dest,sha=file["sha256"],size=file["bytes"])
        else:
            result=fetch_atomic(dest,repo=p["repo"],commit=p["commit"],source="data/bridge/"+file["name"],sha=file["sha256"],size=file["bytes"])
        rows.append({"file":file["canonical"],"source_repo":p["repo"],"source_commit":p["commit"],**result})
    return rows


def restore_external(pins: dict,data_dir: Path) -> list[dict]:
    p=pins["external"]
    rows=[]
    for file in p["files"]:  # metadata is verified independently of raster cache
        result=fetch_atomic(data_dir/safe_relative(file["canonical"]),repo=p["repo"],commit=p["commit"],
                            source=file["source_path"],sha=file["sha256"],size=file["bytes"])
        rows.append({"file":file["canonical"],"source_repo":p["repo"],"source_commit":p["commit"],**result})
    return rows


def restore_dem10(pins: dict,data_dir: Path) -> tuple[list[dict],dict]:
    p=pins["dem10"];folder=data_dir/"dem10"
    fetch_atomic(folder/"manifest.json",repo=p["repo"],commit=p["commit"],source="manifest.json",sha=p["manifest_sha256"],size=p["manifest_bytes"])
    manifest=json.loads((folder/"manifest.json").read_text())
    expected={"dem10_"+s for s in ("slope_max","slope_mean","slope_std","hgm20_max","hgm50_max","hgm200_mean",
                                   "steep_ratio_max","resid_std","resid_range","curv_absmax","onesided","onesided3","valid_frac")}
    channels=manifest["channels"]
    if len(channels)!=13 or set(channels)!=expected or manifest["footprint_pixels"]!=5167373 or manifest["template_sha256"]!=pins["core"]["files"][2]["sha256"]:
        raise RuntimeError("unexpected DEM10 manifest template/channels")
    def channel(c):
        import numpy as np
        stats=manifest["channel_stats"][c]
        result=fetch_atomic(folder/f"{c}.f32.npy",repo=p["repo"],commit=p["commit"],source=f"{c}.f32.npy",sha=stats["sha256"],size=stats["bytes"])
        arr=np.load(folder/f"{c}.f32.npy",mmap_mode="r",allow_pickle=False)
        if arr.shape!=(5167373,) or arr.dtype!=np.float32 or not np.isfinite(arr).all():
            raise RuntimeError(f"invalid DEM10 array shape/dtype/values: {c}")
        return {"channel":c,**result}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(channel,channels))
    return rows,manifest
