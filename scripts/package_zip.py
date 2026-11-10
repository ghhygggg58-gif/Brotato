#!/usr/bin/env python3
"""Packages the clean playable Brotato Python folder into dist/Brotato-Python.zip."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from download_brotato import _write_clean_zip, _zip_from_local_repo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build standalone Brotato-Python.zip bundle.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "dist" / "Brotato-Python.zip",
        help="Output zip path (default: dist/Brotato-Python.zip)",
    )
    args = parser.parse_args()

    raw_zip = _zip_from_local_repo(ROOT)
    count = _write_clean_zip(raw_zip, args.out)
    print(f"Built {args.out.resolve()} ({count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
