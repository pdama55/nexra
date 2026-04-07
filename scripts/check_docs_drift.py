#!/usr/bin/env python3
"""Lightweight drift checks for workflow names and dashboard endpoint docs."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    workflow_dir = root / ".github" / "workflows"
    playbook_path = root / "docs" / "99_MASTER_TESTING_PLAYBOOK.md"
    dashboard_phase_path = root / "docs" / "12_P1_DASHBOARD_SIEM_ADAPTERS.md"

    errors: list[str] = []

    expected_workflows = {"convergence-ci.yml", "release-smoke.yml"}
    actual_workflows = {p.name for p in workflow_dir.glob("*.yml")} | {
        p.name for p in workflow_dir.glob("*.yaml")
    }
    missing_workflows = sorted(expected_workflows - actual_workflows)
    if missing_workflows:
        errors.append(
            "Missing expected workflow files: " + ", ".join(missing_workflows)
        )

    playbook = playbook_path.read_text(encoding="utf-8")
    stale_workflow_refs = [
        ".github/workflows/ci.yml",
        ".github/workflows/deploy.yml",
    ]
    for stale in stale_workflow_refs:
        if stale in playbook:
            errors.append(f"Stale workflow reference found in testing playbook: {stale}")
    for expected in sorted(expected_workflows):
        if expected not in playbook:
            errors.append(
                f"Testing playbook missing current workflow reference: .github/workflows/{expected}"
            )

    dashboard_doc = dashboard_phase_path.read_text(encoding="utf-8")
    required_dashboard_endpoints = [
        "/v1/dashboard/volume",
        "/v1/dashboard/cost-breakdown",
        "/v1/dashboard/failure-rates",
        "/v1/dashboard/trust-leaderboard",
        "/v1/dashboard/budget-alerts",
        "/v1/dashboard/network-graph",
    ]
    for endpoint in required_dashboard_endpoints:
        if endpoint not in dashboard_doc:
            errors.append(f"Dashboard phase doc missing endpoint: {endpoint}")
    stale_dashboard_endpoints = [
        "/analytics/usage/volume",
        "/analytics/usage/cost-breakdown",
        "/analytics/usage/failure-rates",
        "/analytics/usage/trust-leaderboard",
        "/analytics/usage/budget-alerts",
        "/analytics/usage/network-graph",
    ]
    for endpoint in stale_dashboard_endpoints:
        if endpoint in dashboard_doc:
            errors.append(f"Dashboard phase doc still references stale endpoint: {endpoint}")

    if errors:
        print("Docs drift check failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("Docs drift check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
