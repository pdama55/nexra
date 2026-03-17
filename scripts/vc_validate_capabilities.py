#!/usr/bin/env python3
"""Validate PRD capability coverage contract for VC demo runs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCENARIO_CATALOG: set[str] = {
    "coordination_registry",
    "coordination_discovery",
    "delegation_sync_async",
    "delegation_context_scope",
    "billing_metering",
    "framework_adapters",
    "a2a_registration",
    "governance_policy_engine",
    "governance_budget_caps",
    "governance_audit_immutability",
    "governance_anomaly_detection",
    "protocol_mcp_surface",
    "marketplace_cross_org_hire",
    "marketplace_connect_settlement",
    "governance_circuit_breakers",
    "governance_hitl",
    "governance_trust_scores",
    "dashboard_governance_views",
    "governance_siem_export",
    "governance_schema_validation",
    "compliance_exports",
    "governance_policy_versions",
}

REQUIRED_FIELDS = {
    "feature_id",
    "priority",
    "required_for_vc",
    "proof_type",
    "scenario_id",
    "artifacts",
    "pass_criteria",
}


@dataclass
class ValidationResult:
    feature_id: str
    scenario_id: str
    required_for_vc: bool
    mapped: bool
    scenario_known: bool
    artifacts_declared: bool
    pass_criteria_declared: bool
    scenario_passed: bool | None
    status: str
    errors: list[str]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def _load_summary(path: Path) -> dict[str, bool]:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    scenario_results = raw.get("scenario_results")
    if isinstance(scenario_results, dict):
        return {str(k): bool(v) for k, v in scenario_results.items()}

    scenario_list = raw.get("scenarios")
    if isinstance(scenario_list, list):
        out: dict[str, bool] = {}
        for item in scenario_list:
            if not isinstance(item, dict):
                continue
            sid = item.get("id") or item.get("name")
            if not sid:
                continue
            out[str(sid)] = bool(item.get("passed", False))
        return out

    return {}


def validate(matrix_path: Path, summary_path: Path | None = None) -> tuple[list[ValidationResult], list[str]]:
    data = _load_yaml(matrix_path)
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("matrix.features must be a list")

    summary_map = _load_summary(summary_path) if summary_path else {}

    results: list[ValidationResult] = []
    global_errors: list[str] = []

    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            global_errors.append(f"features[{idx}] must be an object")
            continue

        missing = sorted(REQUIRED_FIELDS - set(feature.keys()))
        feature_id = str(feature.get("feature_id", f"index-{idx}"))
        scenario_id = str(feature.get("scenario_id", ""))
        required = bool(feature.get("required_for_vc", False))

        errors: list[str] = []
        if missing:
            errors.append(f"missing required fields: {', '.join(missing)}")

        mapped = bool(scenario_id)
        if not mapped:
            errors.append("scenario_id is empty")

        scenario_known = scenario_id in SCENARIO_CATALOG
        if mapped and not scenario_known:
            errors.append(f"scenario_id '{scenario_id}' not in VC scenario catalog")

        artifacts = feature.get("artifacts")
        artifacts_declared = isinstance(artifacts, list) and len(artifacts) > 0
        if not artifacts_declared:
            errors.append("artifacts must be a non-empty list")

        pass_criteria = str(feature.get("pass_criteria", "")).strip()
        pass_criteria_declared = bool(pass_criteria)
        if not pass_criteria_declared:
            errors.append("pass_criteria must be non-empty")

        scenario_passed: bool | None = None
        if summary_map and mapped:
            scenario_passed = summary_map.get(scenario_id)
            if required and scenario_passed is not True:
                errors.append(f"required scenario '{scenario_id}' did not pass in summary")

        status = "passed" if not errors else "failed"
        results.append(
            ValidationResult(
                feature_id=feature_id,
                scenario_id=scenario_id,
                required_for_vc=required,
                mapped=mapped,
                scenario_known=scenario_known,
                artifacts_declared=artifacts_declared,
                pass_criteria_declared=pass_criteria_declared,
                scenario_passed=scenario_passed,
                status=status,
                errors=errors,
            )
        )

    return results, global_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VC PRD capability matrix")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("demo/prd_capability_matrix.yaml"),
        help="Path to PRD capability matrix YAML",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON to verify scenario pass/fail",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output JSON path (defaults beside matrix as capability_matrix_result.json)",
    )
    args = parser.parse_args()

    results, global_errors = validate(args.matrix, args.summary)

    required_failed = [r for r in results if r.required_for_vc and r.status != "passed"]
    optional_failed = [r for r in results if (not r.required_for_vc) and r.status != "passed"]

    output = {
        "matrix_path": str(args.matrix),
        "summary_path": str(args.summary) if args.summary else None,
        "global_errors": global_errors,
        "required_total": sum(1 for r in results if r.required_for_vc),
        "required_failed": len(required_failed),
        "optional_failed": len(optional_failed),
        "results": [
            {
                "feature_id": r.feature_id,
                "scenario_id": r.scenario_id,
                "required_for_vc": r.required_for_vc,
                "mapped": r.mapped,
                "scenario_known": r.scenario_known,
                "artifacts_declared": r.artifacts_declared,
                "pass_criteria_declared": r.pass_criteria_declared,
                "scenario_passed": r.scenario_passed,
                "status": r.status,
                "errors": r.errors,
            }
            for r in results
        ],
    }

    out_path = args.out
    if out_path is None:
        out_path = args.matrix.parent / "capability_matrix_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "required_total": output["required_total"],
        "required_failed": output["required_failed"],
        "optional_failed": output["optional_failed"],
        "out": str(out_path),
    }, indent=2, sort_keys=True))

    if global_errors or required_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
