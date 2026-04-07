from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RUN_VC_DEMO = ROOT / "scripts" / "run_vc_demo.sh"
VC_TIMELINE = ROOT / "demo" / "vc_timeline.yaml"
CAP_MATRIX = ROOT / "demo" / "prd_capability_matrix.yaml"
VC_AUTOPLAY = ROOT / "scripts" / "vc_dashboard_autoplay.ts"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_run_vc_demo_defaults_to_mock_integrations() -> None:
    script = RUN_VC_DEMO.read_text(encoding="utf-8")
    assert 'INTEGRATIONS="mock"' in script


def test_timeline_expected_events_have_emit_sources() -> None:
    timeline = _load_yaml(VC_TIMELINE)
    matrix = _load_yaml(CAP_MATRIX)

    expected_events = {
        event
        for act in (timeline.get("acts") or [])
        for event in (act.get("expected_events") or [])
    }

    script = RUN_VC_DEMO.read_text(encoding="utf-8")
    literal_events = set(re.findall(r'emit_event\s+"([^"]+)"', script))
    scenario_pass_events = {
        f"{feat['scenario_id']}_passed"
        for feat in (matrix.get("features") or [])
        if isinstance(feat, dict) and feat.get("scenario_id")
    }

    coverage = literal_events | scenario_pass_events
    missing = sorted(expected_events - coverage)
    assert not missing, f"Timeline events missing emit sources: {missing}"


def test_autoplay_supports_checkpoint_quality_flags() -> None:
    source = VC_AUTOPLAY.read_text(encoding="utf-8")
    assert "--strict-checkpoints" in source
    assert "--summary-path" in source
    assert "--min-checkpoint-coverage" in source


def test_autoplay_maps_policies_panel_to_policies_route() -> None:
    source = VC_AUTOPLAY.read_text(encoding="utf-8")
    assert 'if (key.includes("polic")) return "/policies";' in source


def test_preflight_real_mode_requires_sendgrid_and_pagerduty_env() -> None:
    source = (ROOT / "scripts" / "vc_demo_preflight.py").read_text(encoding="utf-8")
    assert 'SENDGRID_API_KEY' in source
    assert 'ANOMALY_PAGERDUTY_ROUTING_KEY' in source
    assert 'PAGERDUTY_EVENTS_BASE_URL' in source
    assert 'require_real_channel_env=True' in source
