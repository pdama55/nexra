#!/usr/bin/env python3
"""Fail CI when API surface changed but OpenAPI snapshot was not updated."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(*args: str) -> str:
    out = subprocess.check_output(["git", *args], text=True)
    return out.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OpenAPI snapshot freshness")
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="Base commit/ref to diff against (default: HEAD~1)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    snapshot_path = "docs/baseline/openapi.snapshot.json"

    try:
        changed = _git("diff", "--name-only", "--diff-filter=ACMR", f"{args.base}...HEAD").splitlines()
    except subprocess.CalledProcessError as exc:
        print(f"Unable to diff against base '{args.base}': {exc}", file=sys.stderr)
        return 1

    changed = [path.strip() for path in changed if path.strip()]
    api_surface_touched = any(
        path == "nexra/api/main.py"
        or path.startswith("nexra/api/routers/")
        or path.startswith("nexra/api/schemas/")
        for path in changed
    )
    snapshot_touched = snapshot_path in changed

    print(f"OpenAPI freshness diff base: {args.base}")
    if not changed:
        print("No changed files in range; freshness check passed.")
        return 0

    if not api_surface_touched:
        print("No API router/schema changes detected; freshness check passed.")
        return 0

    if snapshot_touched:
        print(f"API surface changed and snapshot updated ({snapshot_path}); freshness check passed.")
        return 0

    print("API surface files changed but OpenAPI snapshot was not updated.", file=sys.stderr)
    print("Changed API files:", file=sys.stderr)
    for path in changed:
        if (
            path == "nexra/api/main.py"
            or path.startswith("nexra/api/routers/")
            or path.startswith("nexra/api/schemas/")
        ):
            print(f"  - {path}", file=sys.stderr)
    print(f"Required update missing: {repo_root / snapshot_path}", file=sys.stderr)
    print(
        "Run `cd nexra && ./venv/bin/python ../scripts/check_openapi_snapshot.py` and refresh "
        "`docs/baseline/openapi.snapshot.json` in the same change.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
