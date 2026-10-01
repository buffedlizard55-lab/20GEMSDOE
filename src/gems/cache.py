"""Hash-bound local NumPy caches. Missing/stale/tampered metadata means cache miss.

Caches are performance conveniences, never provenance of independent labels.
Write data first and metadata last; an interrupted write cannot validate old bytes.
"""
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
import zipfile
from typing import Any

import numpy as np
from .validator import sha256_file


def cache_fingerprint(inputs: dict[str, Path], source_files: dict[str, Path], *,
                      parameters: dict[str, Any], packages=("numpy", "scipy", "scikit-learn", "rasterio")) -> dict:
    return {"schema_version": 1, "inputs_sha256": {k:sha256_file(Path(v)) for k,v in sorted(inputs.items())},
            "source_sha256": {k:sha256_file(Path(v)) for k,v in sorted(source_files.items())},
            "parameters": parameters,
            "software": {p:importlib.metadata.version(p) for p in packages}}


def _canonical(x):
    return json.dumps(x,sort_keys=True,allow_nan=False,separators=(",",":"))


def metadata_path(path: Path) -> Path:
    return Path(str(path)+".provenance.json")


def load_bundle(path: Path, expected: dict) -> dict[str, np.ndarray] | None:
    """Return only a fully verified NPZ bundle. A cache miss requests rebuilding."""
    path = Path(path)
    try:
        meta = json.loads(metadata_path(path).read_text())
        if _canonical(meta["fingerprint"]) != _canonical(expected) or meta["array_file_sha256"] != sha256_file(path):
            return None
        with np.load(path,allow_pickle=False) as z:
            if sorted(z.files) != sorted(meta["arrays"]):
                return None
            data = {k:z[k] for k in z.files}
        for k,a in data.items():
            if list(a.shape)!=meta["arrays"][k]["shape"] or str(a.dtype)!=meta["arrays"][k]["dtype"]:
                return None
        return data
    except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile):
        return None


def save_bundle(path: Path, arrays: dict[str, np.ndarray], fingerprint: dict) -> None:
    path = Path(path)
    if not arrays or any(not isinstance(k,str) or not k or np.asarray(v).dtype.hasobject for k,v in arrays.items()):
        raise ValueError("nonempty named non-object arrays required")
    _canonical(fingerprint)  # fail before touching valid cache
    path.parent.mkdir(parents=True,exist_ok=True)
    data_tmp = meta_tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,suffix=".npz",delete=False) as f:
            data_tmp = Path(f.name)
            np.savez(f,**arrays)
            f.flush()
            os.fsync(f.fileno())
        meta = {"fingerprint":fingerprint,"array_file_sha256":sha256_file(data_tmp),
                "arrays":{k:{"shape":list(np.asarray(a).shape),"dtype":str(np.asarray(a).dtype)} for k,a in arrays.items()}}
        with tempfile.NamedTemporaryFile(dir=path.parent,suffix=".json",mode="w",delete=False) as f:
            meta_tmp = Path(f.name)
            f.write(json.dumps(meta,indent=2,allow_nan=False)+"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(data_tmp,path)
        os.replace(meta_tmp,metadata_path(path))
    finally:
        for p in (data_tmp,meta_tmp):
            if p is not None:
                p.unlink(missing_ok=True)
