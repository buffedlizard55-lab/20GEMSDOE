#!/usr/bin/env python3
"""Retired compatibility entry point for the historical H20 workflow.

The former target name overstated what this wrapper did: it delegated to a legacy
H19/H20 evaluator that required missing OOF caches and could package unsupported
submission claims. That runner is disabled. No training or file writes occur.
"""
from evaluate_h19_and_build_submissions import main

if __name__ == "__main__":
    raise SystemExit(main())
