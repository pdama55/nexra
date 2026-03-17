#!/usr/bin/env python3
"""VC flagship demo runner with PRD capability mapping and artifact packaging."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "nexra"
SDK_DIR = APP_DIR / "sdk" / "nexra-py"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from nexra_sdk.adapters.bedrock import BedrockNexraBridge  # noqa: E402


@dataclass
class Scenario:
    id: str
    passed: bool
    error: str | None = None
    details: dict[str, Any] | None = None


class VCClient:
    def __init__(self, *, base_url: str, trace_path: Path) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=45.0)
        self.trace_path = trace_path

    def close(self) -> None:
        self.client.close()

    def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        expected: set[int] | None = None,
    ) -> tuple[httpx.Response, dict[str, Any] | None]:
        expected = expected or {200}
        started = time.perf_counter()
        response = self.client.request(method, path, headers=headers, json=json_body, params=params)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        payload: dict[str, Any] | None = None
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = None

        row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "method": method,
            "path": path,
            "params": params,
            "status_code": response.status_code,
            "expected_statuses": sorted(expected),
            "elapsed_ms": elapsed_ms,
            "request_json": json_body,
            "response_json": payload,
            "response_excerpt": response.text[:1000],
        }
        with self.trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")

        if response.status_code not in expected:
            raise RuntimeError(
                f"{method} {path} returned {response.status_code}, expected {sorted(expected)}; body={response.text[:400]}"
            )
        return response, payload


def _auth(api_key: str, *, email: str | None = None, agent_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if email:
        headers["X-User-Email"] = email
    if agent_id:
        headers["X-Agent-ID"] = agent_id
    return headers


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": datetime.now(UTC).isoformat(), **event}, sort_keys=True))
        fh.write("\n")


def _baseline_to_matrix(summary: dict[str, Any]) -> dict[str, bool]:
    rows: list[dict[str, Any]] = []
    for key in ("scenarios", "results"):
        value = summary.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))

    baseline = {
        str(item.get("name")): bool(item.get("passed", False))
        for item in rows
        if item.get("name") is not None
    }
    return {
        "coordination_registry": baseline.get("agents_and_discovery", False),
        "coordination_discovery": baseline.get("agents_and_discovery", False),
        "delegation_sync_async": baseline.get("delegation_async_callback", False),
        "delegation_context_scope": baseline.get("delegation_async_callback", False),
        "a2a_registration": baseline.get("agents_and_discovery", False),
        "governance_policy_engine": baseline.get("policies_lifecycle", False),
        "governance_audit_immutability": baseline.get("audit_and_compliance", False),
        "governance_anomaly_detection": baseline.get("anomaly_fanout", False),
        "governance_hitl": baseline.get("hitl_flows", False),
        "governance_trust_scores": baseline.get("agents_and_discovery", False),
        "dashboard_governance_views": baseline.get("analytics_dashboard", False),
        "governance_siem_export": baseline.get("siem_export", False),
        "compliance_exports": baseline.get("audit_and_compliance", False),
        "governance_policy_versions": baseline.get("policies_lifecycle", False),
        "billing_metering": baseline.get("analytics_dashboard", False),
    }


class BedrockLiveClient:
    def __init__(self, base_url: str, api_key: str, caller_agent_id: str, callback_url: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.caller_agent_id = caller_agent_id
        self.callback_url = callback_url

    async def discover(self, **kwargs: Any) -> list[SimpleNamespace]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=45.0) as client:
            resp = await client.post(
                "/v1/capabilities/discover",
                headers=_auth(self.api_key, agent_id=self.caller_agent_id),
                json={
                    "query": kwargs.get("query", "research"),
                    "limit": int(kwargs.get("limit", 3)),
                    "include_cross_org": False,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            return [
                SimpleNamespace(
                    agent_id=item["agent_id"],
                    name=item.get("name", item["agent_id"]),
                    match_score=float(item.get("match_score", 0.0)),
                )
                for item in ((payload.get("data") or {}).get("matches") or [])
            ]

    async def delegate(self, **kwargs: Any) -> SimpleNamespace:
        body: dict[str, Any] = {
            "callee_agent_id": kwargs.get("agent_id"),
            "task": kwargs.get("task", {"input": {"query": "bedrock bridge"}}),
            "context_scope": ["deal_metadata"],
            "budget_cap_usd": float(kwargs.get("budget_cap", 0.5)),
            "timeout_ms": 12000,
            "include_cross_org": False,
        }
        if self.callback_url:
            body["callback_url"] = self.callback_url

        async with httpx.AsyncClient(base_url=self.base_url, timeout=45.0) as client:
            resp = await client.post(
                "/v1/delegate",
                headers=_auth(self.api_key, agent_id=self.caller_agent_id),
                json=body,
            )
            if resp.status_code not in {200, 202}:
                raise RuntimeError(f"delegate via bedrock bridge failed: {resp.status_code} {resp.text[:300]}")
            payload = (resp.json().get("data") or {})
            return SimpleNamespace(
                delegation_id=str(payload.get("delegation_id")),
                status=str(payload.get("status")),
                result=payload.get("result"),
            )


async def _run_bedrock_bridge(
    *,
    base_url: str,
    api_key: str,
    caller_agent: str,
    default_callee: str,
    callback_url: str | None = None,
) -> tuple[bool, str]:
    bridge = BedrockNexraBridge(BedrockLiveClient(base_url, api_key, caller_agent, callback_url))

    discover_event = {
        "apiPath": "/discover",
        "parameters": [{"name": "query", "value": "research and analysis"}],
        "requestBody": {"content": {"application/json": {}}},
    }
    discover_resp = await bridge.handle_action_group(discover_event)
    if int(discover_resp["response"]["httpStatusCode"]) != 200:
        return False, "discover path did not return HTTP 200"

    discover_body = json.loads(discover_resp["response"]["responseBody"]["application/json"]["body"])
    callee = default_callee
    if discover_body and isinstance(discover_body, list):
        callee = str(discover_body[0].get("agent_id") or callee)

    delegate_event = {
        "apiPath": "/delegate",
        "parameters": [],
        "requestBody": {
            "content": {
                "application/json": {
                    "properties": {
                        "agent_id": callee,
                        "task": {"input": {"query": "bedrock bridge live"}},
                        "budget_cap": 0.6,
                    }
                }
            }
        },
    }
    delegate_resp = await bridge.handle_action_group(delegate_event)
    if int(delegate_resp["response"]["httpStatusCode"]) != 200:
        return False, "delegate path did not return HTTP 200"

    return True, "bedrock bridge discover+delegate succeeded"


def _run_live_suite(
    *,
    base_url: str,
    results_dir: Path,
    api_key: str,
    owner_email: str,
    mock_sink_base_url: str | None,
    strict: bool,
    enable_stripe_onboard: bool,
) -> tuple[int, Path, Path]:
    baseline_dir = results_dir / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(APP_DIR / "venv" / "bin" / "python"),
        str(ROOT_DIR / "scripts" / "live_demo_full_suite.py"),
        "--base-url",
        base_url,
        "--api-key",
        api_key,
        "--owner-email",
        owner_email,
        "--results-dir",
        str(baseline_dir),
    ]
    if mock_sink_base_url:
        cmd += ["--mock-sink-base-url", mock_sink_base_url]
    if strict:
        cmd.append("--strict")
    if enable_stripe_onboard:
        cmd.append("--enable-stripe-onboard")

    run_log = results_dir / "baseline_run.log"
    with run_log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=str(ROOT_DIR), stdout=fh, stderr=subprocess.STDOUT, check=False)

    return proc.returncode, baseline_dir / "summary.json", run_log


def _load_matrix_required(matrix_path: Path) -> dict[str, bool]:
    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    features = payload.get("features", []) if isinstance(payload, dict) else []
    required: dict[str, bool] = {}
    for feat in features:
        if not isinstance(feat, dict):
            continue
        sid = str(feat.get("scenario_id", "")).strip()
        if not sid:
            continue
        required[sid] = bool(feat.get("required_for_vc", False))
    return required


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VC flagship demo suite")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:5173")
    parser.add_argument("--org-profile", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--capability-matrix", type=Path, default=Path("demo/prd_capability_matrix.yaml"))
    parser.add_argument("--mock-sink-base-url", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--enable-stripe-onboard", action="store_true")
    args = parser.parse_args()

    args.results_dir.mkdir(parents=True, exist_ok=True)
    trace_path = args.results_dir / "http_trace.jsonl"
    event_path = args.results_dir / "integration_events.jsonl"

    profile = _load_json(args.org_profile)
    buyer = ((profile.get("orgs") or {}).get("buyer") or {})
    vendor = ((profile.get("orgs") or {}).get("vendor") or {})

    buyer_key = str(buyer.get("api_key") or "")
    vendor_key = str(vendor.get("api_key") or "")
    buyer_email = str(buyer.get("owner_email") or "admin@nexra.local")
    buyer_agents = list(buyer.get("agents") or [])
    vendor_agents = list(vendor.get("agents") or [])

    if not buyer_key or not buyer_agents:
        raise SystemExit("org profile missing buyer API key/agents")

    _append_event(event_path, {"event": "vc_suite_start", "base_url": args.base_url})

    baseline_exit, baseline_summary_path, baseline_log_path = _run_live_suite(
        base_url=args.base_url,
        results_dir=args.results_dir,
        api_key=buyer_key,
        owner_email=buyer_email,
        mock_sink_base_url=args.mock_sink_base_url,
        strict=args.strict,
        enable_stripe_onboard=args.enable_stripe_onboard,
    )
    _append_event(
        event_path,
        {
            "event": "baseline_suite_finished",
            "exit_code": baseline_exit,
            "summary": str(baseline_summary_path),
            "log": str(baseline_log_path),
        },
    )

    if not baseline_summary_path.exists():
        raise SystemExit(f"baseline summary missing: {baseline_summary_path}")

    baseline_summary = _load_json(baseline_summary_path)
    scenario_results = _baseline_to_matrix(baseline_summary)
    scenario_objects: list[Scenario] = []

    client = VCClient(base_url=args.base_url, trace_path=trace_path)
    try:
        primary_agent = str(buyer_agents[0])
        secondary_agent = str(buyer_agents[1]) if len(buyer_agents) > 1 else primary_agent
        vendor_agent = str(vendor_agents[0]) if vendor_agents else ""

        # MCP tool surface
        try:
            client.call("GET", "/v1/mcp/tools", headers=_auth(buyer_key), expected={200})
            client.call(
                "POST",
                "/v1/mcp/tools/discover",
                headers=_auth(buyer_key, agent_id=primary_agent),
                json_body={"query": "research and analysis", "include_cross_org": True, "limit": 5},
                expected={200},
            )
            client.call(
                "GET",
                "/v1/mcp/tools/governance/read",
                headers=_auth(buyer_key),
                expected={200},
            )
            scenario_results["protocol_mcp_surface"] = True
            scenario_objects.append(Scenario("protocol_mcp_surface", True))
        except Exception as exc:  # noqa: BLE001
            scenario_results["protocol_mcp_surface"] = False
            scenario_objects.append(Scenario("protocol_mcp_surface", False, str(exc)))

        # Bedrock bridge runnable path
        try:
            ok, msg = asyncio.run(
                _run_bedrock_bridge(
                    base_url=args.base_url,
                    api_key=buyer_key,
                    caller_agent=primary_agent,
                    default_callee=vendor_agent or primary_agent,
                    callback_url=(args.mock_sink_base_url + "/mock/callback") if args.mock_sink_base_url else None,
                )
            )
            scenario_results["framework_adapters"] = ok
            scenario_objects.append(Scenario("framework_adapters", ok, None if ok else msg))
        except Exception as exc:  # noqa: BLE001
            scenario_results["framework_adapters"] = False
            scenario_objects.append(Scenario("framework_adapters", False, str(exc)))

        # Budget cap enforcement
        try:
            client.call(
                "POST",
                "/v1/delegate",
                headers=_auth(buyer_key, agent_id=primary_agent),
                json_body={
                    "callee_agent_id": primary_agent,
                    "task": {"input": {"query": "budget guard"}},
                    "context_scope": [],
                    "budget_cap_usd": 0.0001,
                    "timeout_ms": 5000,
                },
                expected={402},
            )
            scenario_results["governance_budget_caps"] = True
            scenario_objects.append(Scenario("governance_budget_caps", True))
        except Exception as exc:  # noqa: BLE001
            scenario_results["governance_budget_caps"] = False
            scenario_objects.append(Scenario("governance_budget_caps", False, str(exc)))

        # Schema validation (invalid task)
        try:
            client.call(
                "POST",
                "/v1/delegate",
                headers=_auth(buyer_key, agent_id=primary_agent),
                json_body={
                    "callee_agent_id": primary_agent,
                    "task": {"input": {"payload": {"bad": True}}},
                    "context_scope": [],
                    "budget_cap_usd": 1.0,
                    "timeout_ms": 5000,
                },
                expected={422},
            )
            scenario_results["governance_schema_validation"] = True
            scenario_objects.append(Scenario("governance_schema_validation", True))
        except Exception as exc:  # noqa: BLE001
            scenario_results["governance_schema_validation"] = False
            scenario_objects.append(Scenario("governance_schema_validation", False, str(exc)))

        # Cross-org marketplace hire
        try:
            if not vendor_key:
                raise RuntimeError("vendor org API key missing from org profile")

            unique_vendor_agent = f"vendor-vc-{int(time.time())}"
            client.call(
                "POST",
                "/v1/agents/register",
                headers=_auth(vendor_key),
                json_body={
                    "agent_id": unique_vendor_agent,
                    "name": "Vendor VC Demo Agent",
                    "description": "Cross-org marketplace demo target",
                    "capability_type": "research",
                    "input_schema": {
                        "type": "object",
                        "required": ["query"],
                        "properties": {"query": {"type": "string"}},
                    },
                    "output_schema": {
                        "type": "object",
                        "required": ["summary"],
                        "properties": {"summary": {"type": "string"}},
                    },
                    "webhook_url": "https://example.com/vc-webhook",
                    "webhook_secret": "whs_vc_demo_vendor_secret_key_long_enough",
                    "pricing": {"per_call_usd": 0.09},
                    "sla": {"availability": 0.99, "p99_latency_ms": 4000},
                    "is_public": True,
                },
                expected={200},
            )

            resp, delegation_payload = client.call(
                "POST",
                "/v1/delegate",
                headers=_auth(buyer_key, agent_id=primary_agent),
                json_body={
                    "callee_agent_id": unique_vendor_agent,
                    "task": {"input": {"query": "cross org hire"}},
                    "context_scope": ["deal_metadata"],
                    "budget_cap_usd": 1.5,
                    "timeout_ms": 12000,
                    "callback_url": (args.mock_sink_base_url or "https://example.com") + "/mock/callback",
                    "include_cross_org": True,
                },
                expected={200, 202},
            )
            scenario_results["marketplace_cross_org_hire"] = resp.status_code in {200, 202}
            scenario_objects.append(Scenario("marketplace_cross_org_hire", True, details={"callee_agent_id": unique_vendor_agent}))
            _append_event(
                event_path,
                {
                    "event": "cross_org_delegation",
                    "callee_agent_id": unique_vendor_agent,
                    "status": ((delegation_payload or {}).get("data") or {}).get("status"),
                    "delegation_id": ((delegation_payload or {}).get("data") or {}).get("delegation_id"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            scenario_results["marketplace_cross_org_hire"] = False
            scenario_objects.append(Scenario("marketplace_cross_org_hire", False, str(exc)))

        # Marketplace connect settlement evidence
        try:
            client.call("GET", "/v1/marketplace/connect-status", headers=_auth(buyer_key), expected={200})
            if args.enable_stripe_onboard:
                client.call(
                    "POST",
                    "/v1/marketplace/connect-onboard",
                    headers=_auth(buyer_key, email=buyer_email),
                    expected={200},
                )

            _, audit_payload = client.call(
                "GET",
                "/v1/audit/log",
                headers=_auth(buyer_key),
                params={"event_type": "marketplace_payout", "limit": 20},
                expected={200},
            )
            entries = ((audit_payload or {}).get("data") or {}).get("entries") or []
            if not entries:
                raise RuntimeError("no marketplace_payout audit entries found")
            scenario_results["marketplace_connect_settlement"] = True
            scenario_objects.append(Scenario("marketplace_connect_settlement", True))
        except Exception as exc:  # noqa: BLE001
            scenario_results["marketplace_connect_settlement"] = False
            scenario_objects.append(Scenario("marketplace_connect_settlement", False, str(exc)))

        # Circuit breaker (manual quarantine path)
        try:
            client.call(
                "POST",
                f"/v1/agents/{primary_agent}/quarantine",
                headers=_auth(buyer_key, email=buyer_email),
                expected={200},
            )
            client.call(
                "POST",
                "/v1/delegate",
                headers=_auth(buyer_key, agent_id=secondary_agent),
                json_body={
                    "callee_agent_id": primary_agent,
                    "task": {"input": {"query": "should fail due to quarantine"}},
                    "context_scope": [],
                    "budget_cap_usd": 1.0,
                    "timeout_ms": 5000,
                },
                expected={403, 404},
            )
            scenario_results["governance_circuit_breakers"] = True
            scenario_objects.append(Scenario("governance_circuit_breakers", True))
        except Exception as exc:  # noqa: BLE001
            scenario_results["governance_circuit_breakers"] = False
            scenario_objects.append(Scenario("governance_circuit_breakers", False, str(exc)))

    finally:
        client.close()

    # Ensure all matrix scenario IDs exist in summary map
    required_map = _load_matrix_required(args.capability_matrix)
    for scenario_id in required_map:
        scenario_results.setdefault(scenario_id, False)

    summary_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "dashboard_url": args.dashboard_url,
        "org_profile": str(args.org_profile),
        "baseline_exit_code": baseline_exit,
        "baseline_summary": str(baseline_summary_path),
        "scenario_results": scenario_results,
        "scenarios": [
            {
                "id": s.id,
                "passed": s.passed,
                "error": s.error,
                "details": s.details or {},
            }
            for s in scenario_objects
        ],
    }
    summary_path = args.results_dir / "summary.json"
    _write_json(summary_path, summary_payload)

    matrix_result_path = args.results_dir / "capability_matrix_result.json"
    validator_cmd = [
        str(APP_DIR / "venv" / "bin" / "python"),
        str(ROOT_DIR / "scripts" / "vc_validate_capabilities.py"),
        "--matrix",
        str(args.capability_matrix),
        "--summary",
        str(summary_path),
        "--out",
        str(matrix_result_path),
    ]
    validator = subprocess.run(validator_cmd, cwd=str(ROOT_DIR), check=False, capture_output=True, text=True)
    _append_event(
        event_path,
        {
            "event": "capability_validator",
            "exit_code": validator.returncode,
            "stdout": validator.stdout.strip(),
            "stderr": validator.stderr.strip(),
        },
    )

    matrix_result = _load_json(matrix_result_path) if matrix_result_path.exists() else {}
    required_failed = int(matrix_result.get("required_failed", 9999))

    report_lines = [
        "# Nexra VC Demo Suite Report",
        f"- Generated: {datetime.now(UTC).isoformat()}",
        f"- Base URL: {args.base_url}",
        f"- Baseline suite exit: {baseline_exit}",
        f"- Required capability failures: {required_failed}",
        "",
        "## Scenario Results",
    ]
    for sid in sorted(scenario_results):
        report_lines.append(f"- [{'PASS' if scenario_results[sid] else 'FAIL'}] {sid}")

    report_path = args.results_dir / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    strict_fail = args.strict and (baseline_exit != 0 or required_failed > 0)
    if strict_fail:
        return 1
    if baseline_exit != 0:
        return baseline_exit
    if required_failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
