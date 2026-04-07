from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = ROOT / "scripts" / "check_docs_drift.py"


def test_docs_drift_check_tracks_current_workflows_and_dashboard_endpoints() -> None:
    source = CHECK_SCRIPT.read_text(encoding="utf-8")
    assert "convergence-ci.yml" in source
    assert "release-smoke.yml" in source
    assert "/v1/dashboard/volume" in source
    assert "/v1/dashboard/network-graph" in source
