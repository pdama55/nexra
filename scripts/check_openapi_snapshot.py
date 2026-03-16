#!/usr/bin/env python3
"""Fail if the generated OpenAPI schema diverges from the baseline snapshot."""

from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Any


def _set_default_env() -> None:
    defaults = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/nexra",
        "REDIS_URL": "redis://localhost:6379/0",
        "OPENAI_API_KEY": "test-openai-key",
        "STRIPE_SECRET_KEY": "test-stripe-key",
        "STRIPE_WEBHOOK_SECRET": "test-stripe-whsec",
        "STRIPE_DELEGATION_METER_ID": "meter_test",
        "SECRET_KEY_ENCRYPTION_KEY": "a" * 64,
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def _canonical(spec: dict[str, Any]) -> str:
    return json.dumps(spec, sort_keys=True, indent=2) + "\n"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    snapshot_path = root / "docs" / "baseline" / "openapi.snapshot.json"
    if not snapshot_path.exists():
        print(f"Missing OpenAPI snapshot: {snapshot_path}")
        return 1

    _set_default_env()

    from api.main import app  # noqa: WPS433

    current = app.openapi()
    expected = json.loads(snapshot_path.read_text())

    current_canonical = _canonical(current)
    expected_canonical = _canonical(expected)
    if current_canonical == expected_canonical:
        print("OpenAPI snapshot check passed")
        return 0

    diff = difflib.unified_diff(
        expected_canonical.splitlines(),
        current_canonical.splitlines(),
        fromfile=str(snapshot_path),
        tofile="generated_openapi",
        lineterm="",
    )
    print("OpenAPI snapshot mismatch detected:")
    for line in diff:
        print(line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
