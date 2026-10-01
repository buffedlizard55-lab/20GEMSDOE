#!/usr/bin/env python3
"""Retired compatibility entry point; the historical H20 packager is disabled.

It did not train the missing H20 OOF models and its calibration target was
synthetic. The delegated compatibility stub exits without writing artifacts.
"""
from evaluate_h19_and_build_submissions import main

if __name__ == "__main__":
    raise SystemExit(main())
