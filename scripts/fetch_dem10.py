#!/usr/bin/env python3
"""Compatibility entry point: atomic restoration of pinned label-free DEM10 inputs.

Use full commit SHA 91d6566ecc86141eca9e81c259057678930e596f, not the mutable tag.
The official USGS upstream tile provenance remains in the verified manifest/report;
this command verifies team-hosted derived channel bytes, not a new official fetch.
"""
from restore_data import main

if __name__ == "__main__":
    main(["--dem-only"])
