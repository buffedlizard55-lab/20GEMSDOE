"""Persistent, fail-closed research-run locks and committed-protocol checks.

These software guards do not establish geological ground truth or restore blinding
of previously inspected labels. Final confirmation needs genuinely independent data.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .validator import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def committed_protocol(root: Path, files: Iterable[Path]) -> dict:
    """Require exact committed files before touching outcomes; no dirty-source runs."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    hashes = {}
    for path in files:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        saved = subprocess.check_output(["git", "show", f"{head}:{rel}"], cwd=root)
        if saved != path.read_bytes():
            raise RuntimeError(f"Uncommitted protocol/source change: {rel}; commit and push before evaluation")
        hashes[rel] = sha256_file(path)
    # A local commit alone is weaker than a published preregistration. Require the
    # current branch's remote tracking ref to contain HEAD, without any network access.
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
    check = subprocess.run(["git", "merge-base", "--is-ancestor", head, f"refs/remotes/origin/{branch}"], cwd=root, capture_output=True)
    if check.returncode:
        raise RuntimeError("Protocol HEAD is not in the pushed session branch; push before evaluation")
    return {"commit_before_results": head, "branch": branch, "sha256": hashes}


class SingleUseRun:
    """One global consumption per ledger path, including errors and process crashes.

    O_EXCL provides an atomic cross-process lock. Persist the ledger in versioned
    evidence; never delete it to make a second experiment look like a first one.
    """

    def __init__(self, path: Path, candidate_id: str, bindings: dict):
        self.path = Path(path)
        self.candidate_id = candidate_id
        self.bindings = bindings

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.record = {
            "schema_version": 1,
            "candidate_id": self.candidate_id,
            "consumed_utc": utc_now(),
            "status": "CONSUMED_STARTED",
            "bindings": self.bindings,
            "warning": "Software reuse guard only; not proof of independently unseen labels.",
        }
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError as exc:
            raise RuntimeError(f"Run already consumed: {self.path}; no automatic reset or --force") from exc
        with os.fdopen(fd, "w") as handle:
            json.dump(self.record, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return self

    def __exit__(self, exc_type, exc, tb):
        self.record.update(
            status="CONSUMED_FAILED" if exc_type else "CONSUMED_COMPLETED",
            finished_utc=utc_now(),
        )
        if exc_type:
            self.record["error"] = str(exc)
        # No retry if a write fails: the original O_EXCL marker is still consumed.
        with self.path.open("w") as handle:
            json.dump(self.record, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return False


class FinalConfirmationGate(SingleUseRun):
    """A globally single-use ledger bound to an independent final-label manifest.

    Label provenance still needs scientific review; a string is not verification.
    Refuses catalogue-withholding, synthetic targets and previously evaluated data.
    """

    def __init__(self, path: Path, candidate_id: str, bindings: dict, manifest: dict):
        required = ("labels_sha256", "split_sha256", "candidate_sha256", "protocol_sha256")
        if any(not isinstance(bindings.get(k), str) or len(bindings[k]) != 64 or
               any(c not in "0123456789abcdef" for c in bindings[k]) for k in required):
            raise ValueError("Final gate requires full SHA-256 label/split/candidate/protocol bindings")
        if manifest.get("target_kind") != "independently_adjudicated_fault_presence":
            raise ValueError("Final gate requires independent adjudication, not catalogue or synthetic truth")
        if manifest.get("previously_evaluated") is not False or manifest.get("used_for_training_or_selection") is not False:
            raise ValueError("Final data already evaluated or used for training/selection")
        if manifest.get("labels_sha256") != bindings["labels_sha256"] or not manifest.get("source_url"):
            raise ValueError("Label provenance/hash missing or inconsistent")
        super().__init__(path, candidate_id, {**bindings, "label_manifest": manifest})
