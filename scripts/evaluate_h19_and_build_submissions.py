#!/usr/bin/env python3
"""Retired H19/H20 evaluator and submission packager.

This legacy runner is intentionally disabled. Its stored H20 calibration report
used a synthetic proxy target, its saved holdout values are not reproducible from
the incomplete OOF caches in this checkout, the same stored "Vault" slice was
used for two candidates, and its packaging code could overwrite/delete current
research artifacts while restoring withdrawn recommendation and filename claims.
No model evaluation or file write is performed by this compatibility stub.

Use scripts/evaluate_h21_seismic_ridge.py only for its preregistered spatial-
transfer proxy experiment. That script does not create a submission or establish
hidden-fault performance.
"""
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="print why the legacy H19/H20 workflow is disabled, without writing files",
    )
    args = parser.parse_args(argv)
    message = (
        "DISABLED: this historical workflow used a synthetic H20 calibration target, "
        "unreproduced known-catalogue holdout values, and a reused stored holdout slice. "
        "It is not authorized to train, package, overwrite, or recommend a submission. "
        "See docs/research/preregistration_h20.md, evidence/calibration_brier_report.json, "
        "and registry/irregularities.json (F25-F29)."
    )
    if args.status:
        print(message)
        return 0
    parser.error(message + " Use --status to display this notice; no execution mode is available.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
