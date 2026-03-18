from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts" / "run_dashboard_stress.sh"
LOAD = ROOT / "scripts" / "dashboard_api_load.py"
PARITY = ROOT / "scripts" / "dashboard_parity_sweep.ts"


def test_runner_exposes_required_cli_flags() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "--duration-min" in source
    assert "--integrations" in source
    assert "--peak-vus" in source
    assert "--sweep-interval-sec" in source
    assert "--failure-mode" in source
    assert "--results-dir" in source


def test_runner_writes_required_artifacts() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    for artifact in (
        "stress_summary.json",
        "stress_report.md",
        "endpoint_metrics.json",
        "ui_parity_results.json",
        "frontend_errors.jsonl",
        "api_failures.jsonl",
    ):
        assert artifact in source


def test_load_harness_has_expected_endpoint_surface() -> None:
    source = LOAD.read_text(encoding="utf-8")
    for endpoint in (
        "/v1/analytics/usage",
        "/v1/agents/registry",
        "/v1/delegations",
        "/v1/audit/log",
        "/v1/spend/summary",
        "/v1/policies",
        "/v1/orgs/me",
        "/v1/orgs/session",
        "/v1/orgs/api-keys",
        "/v1/orgs/members",
        "/v1/orgs/webhooks",
        "/v1/siem/config",
        "/v1/marketplace/connect-status",
    ):
        assert endpoint in source


def test_parity_sweep_covers_all_required_routes() -> None:
    source = PARITY.read_text(encoding="utf-8")
    for route in (
        "overview",
        "agents",
        "agent_detail",
        "delegations",
        "delegation_detail",
        "policies",
        "policy_detail",
        "spend",
        "audit",
        "hitl",
        "trust",
        "anomalies",
        "compliance",
        "settings",
    ):
        assert route in source
