#!/usr/bin/env python3
"""Strict integration preflight for VC demo runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILES = [
    ROOT_DIR / ".env",
    ROOT_DIR / ".env.local",
    ROOT_DIR / "nexra" / ".env",
    ROOT_DIR / "nexra" / ".env.local",
]


@dataclass
class CheckResult:
    name: str
    required: bool
    passed: bool
    mode: str
    details: str
    latency_ms: float | None = None


def _load_env_defaults(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if not key:
                continue
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _http_check(
    name: str,
    method: str,
    url: str,
    *,
    required: bool,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    expected_statuses: set[int] | None = None,
    timeout: float = 15.0,
) -> CheckResult:
    expected = expected_statuses or {200}
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(method, url, headers=headers, json=json_body)
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        if resp.status_code in expected:
            return CheckResult(
                name=name,
                required=required,
                passed=True,
                mode="network",
                details=f"{method} {url} -> {resp.status_code}",
                latency_ms=elapsed,
            )
        return CheckResult(
            name=name,
            required=required,
            passed=False,
            mode="network",
            details=f"{method} {url} -> {resp.status_code}; expected {sorted(expected)}; body={resp.text[:300]}",
            latency_ms=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        return CheckResult(
            name=name,
            required=required,
            passed=False,
            mode="network",
            details=f"{method} {url} failed: {exc}",
            latency_ms=elapsed,
        )


def _env_present(name: str, key: str, required: bool) -> CheckResult:
    value = os.getenv(key, "").strip()
    return CheckResult(
        name=name,
        required=required,
        passed=bool(value),
        mode="env",
        details=f"{key} {'set' if value else 'missing'}",
    )


def _embedding_path_smoke(base_url: str, required: bool) -> list[CheckResult]:
    checks: list[CheckResult] = []
    ts = int(time.time())
    owner_email = f"vc-preflight-{ts}@nexra.local"
    org_payload = {
        "name": f"Nexra VC Preflight {ts}",
        "plan": "starter",
        "owner_email": owner_email,
    }
    org_started = time.perf_counter()
    try:
        with httpx.Client(timeout=20.0) as client:
            org_resp = client.post(f"{base_url.rstrip('/')}/v1/orgs/register", json=org_payload)
            org_elapsed = round((time.perf_counter() - org_started) * 1000, 2)
            if org_resp.status_code != 201:
                checks.append(CheckResult(
                    name="embedding_probe_org_register",
                    required=required,
                    passed=False,
                    mode="api-smoke",
                    details=f"POST /v1/orgs/register -> {org_resp.status_code}; body={org_resp.text[:300]}",
                    latency_ms=org_elapsed,
                ))
                return checks

            try:
                org_json = org_resp.json()
            except Exception as exc:  # noqa: BLE001
                checks.append(CheckResult(
                    name="embedding_probe_org_register",
                    required=required,
                    passed=False,
                    mode="api-smoke",
                    details=f"POST /v1/orgs/register invalid JSON: {exc}",
                    latency_ms=org_elapsed,
                ))
                return checks

            api_key = str(((org_json.get("data") or {}).get("api_key")) or "").strip()
            if not api_key:
                checks.append(CheckResult(
                    name="embedding_probe_org_register",
                    required=required,
                    passed=False,
                    mode="api-smoke",
                    details="POST /v1/orgs/register missing data.api_key in response",
                    latency_ms=org_elapsed,
                ))
                return checks

            checks.append(CheckResult(
                name="embedding_probe_org_register",
                required=required,
                passed=True,
                mode="api-smoke",
                details="POST /v1/orgs/register -> 201",
                latency_ms=org_elapsed,
            ))

            agent_id = f"vc-preflight-probe-{ts}"
            register_body = {
                "agent_id": agent_id,
                "name": "VC Preflight Embedding Probe",
                "description": "Temporary probe agent used to validate embedding registration path.",
                "capability_type": "research",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
                "pricing": {"per_call_usd": 0.01},
                "sla": {"p99_latency_ms": 5000, "availability": 0.99},
                "webhook_url": "https://example.com/vc-preflight/probe",
                "webhook_secret": "vc_preflight_probe_secret_key_long_enough",
                "team": "preflight",
                "is_public": False,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            reg_started = time.perf_counter()
            reg_resp = client.post(
                f"{base_url.rstrip('/')}/v1/agents/register",
                headers=headers,
                json=register_body,
            )
            reg_elapsed = round((time.perf_counter() - reg_started) * 1000, 2)
            if reg_resp.status_code != 200:
                checks.append(CheckResult(
                    name="embedding_probe_agent_register",
                    required=required,
                    passed=False,
                    mode="api-smoke",
                    details=f"POST /v1/agents/register -> {reg_resp.status_code}; body={reg_resp.text[:300]}",
                    latency_ms=reg_elapsed,
                ))
                return checks

            checks.append(CheckResult(
                name="embedding_probe_agent_register",
                required=required,
                passed=True,
                mode="api-smoke",
                details="POST /v1/agents/register -> 200",
                latency_ms=reg_elapsed,
            ))

            fetch_started = time.perf_counter()
            fetch_resp = client.get(
                f"{base_url.rstrip('/')}/v1/agents/{agent_id}",
                headers=headers,
            )
            fetch_elapsed = round((time.perf_counter() - fetch_started) * 1000, 2)
            checks.append(CheckResult(
                name="embedding_probe_agent_readback",
                required=required,
                passed=fetch_resp.status_code == 200,
                mode="api-smoke",
                details=(
                    "GET /v1/agents/{agent_id} -> 200"
                    if fetch_resp.status_code == 200
                    else f"GET /v1/agents/{agent_id} -> {fetch_resp.status_code}; body={fetch_resp.text[:300]}"
                ),
                latency_ms=fetch_elapsed,
            ))

            cleanup_started = time.perf_counter()
            cleanup_resp = client.post(
                f"{base_url.rstrip('/')}/v1/agents/{agent_id}/quarantine",
                headers={**headers, "X-User-Email": owner_email},
            )
            cleanup_elapsed = round((time.perf_counter() - cleanup_started) * 1000, 2)
            checks.append(CheckResult(
                name="embedding_probe_agent_cleanup",
                required=False,
                passed=cleanup_resp.status_code == 200,
                mode="api-smoke",
                details=(
                    "POST /v1/agents/{agent_ref}/quarantine -> 200"
                    if cleanup_resp.status_code == 200
                    else (
                        "POST /v1/agents/{agent_ref}/quarantine "
                        f"-> {cleanup_resp.status_code}; body={cleanup_resp.text[:300]}"
                    )
                ),
                latency_ms=cleanup_elapsed,
            ))
    except Exception as exc:  # noqa: BLE001
        elapsed = round((time.perf_counter() - org_started) * 1000, 2)
        checks.append(CheckResult(
            name="embedding_probe_org_register",
            required=required,
            passed=False,
            mode="api-smoke",
            details=f"Embedding smoke request failed: {exc}",
            latency_ms=elapsed,
        ))
    return checks


def _real_checks(
    base_url: str,
    required: bool,
    *,
    require_real_channel_env: bool,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    checks.append(_http_check(
        "api_health",
        "GET",
        f"{base_url.rstrip('/')}/health",
        required=True,
        expected_statuses={200},
    ))

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    checks.append(_env_present("openai_key", "OPENAI_API_KEY", required))
    if openai_key:
        checks.append(_http_check(
            "openai_models",
            "GET",
            "https://api.openai.com/v1/models",
            required=required,
            headers={"Authorization": f"Bearer {openai_key}"},
            expected_statuses={200},
        ))

    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    checks.append(_env_present("stripe_secret", "STRIPE_SECRET_KEY", required))
    if stripe_key:
        checks.append(_http_check(
            "stripe_account",
            "GET",
            "https://api.stripe.com/v1/account",
            required=required,
            headers={"Authorization": f"Bearer {stripe_key}"},
            expected_statuses={200},
        ))

    sendgrid_key = os.getenv("SENDGRID_API_KEY", "").strip()
    sendgrid_base = os.getenv("SENDGRID_BASE_URL", "https://api.sendgrid.com").rstrip("/")
    checks.append(_env_present("sendgrid_key", "SENDGRID_API_KEY", required=require_real_channel_env))
    if sendgrid_key:
        checks.append(_http_check(
            "sendgrid_account",
            "GET",
            f"{sendgrid_base}/v3/user/account",
            required=required,
            headers={"Authorization": f"Bearer {sendgrid_key}"},
            expected_statuses={200},
        ))

    slack_url = os.getenv("ANOMALY_SLACK_WEBHOOK_URL", "").strip()
    checks.append(_env_present("slack_webhook", "ANOMALY_SLACK_WEBHOOK_URL", required=False))
    if slack_url:
        checks.append(_http_check(
            "slack_webhook_post",
            "POST",
            slack_url,
            required=required,
            json_body={"text": "[Nexra VC preflight] Slack connectivity check"},
            expected_statuses={200},
        ))

    pagerduty_key = os.getenv("ANOMALY_PAGERDUTY_ROUTING_KEY", "").strip()
    pagerduty_base = os.getenv("PAGERDUTY_EVENTS_BASE_URL", "https://events.pagerduty.com").rstrip("/")
    checks.append(
        _env_present(
            "pagerduty_events_base_url",
            "PAGERDUTY_EVENTS_BASE_URL",
            required=require_real_channel_env,
        )
    )
    checks.append(
        _env_present(
            "pagerduty_routing",
            "ANOMALY_PAGERDUTY_ROUTING_KEY",
            required=require_real_channel_env,
        )
    )
    if pagerduty_key:
        checks.append(_http_check(
            "pagerduty_event",
            "POST",
            f"{pagerduty_base}/v2/enqueue",
            required=required,
            json_body={
                "routing_key": pagerduty_key,
                "event_action": "trigger",
                "payload": {
                    "summary": "Nexra VC preflight test event",
                    "source": "nexra.vc.preflight",
                    "severity": "info",
                },
                "dedup_key": f"nexra-vc-preflight-{int(time.time())}",
            },
            expected_statuses={200, 202},
        ))

    siem_endpoint = os.getenv("SIEM_WEBHOOK_ENDPOINT", "").strip()
    checks.append(_env_present("siem_endpoint", "SIEM_WEBHOOK_ENDPOINT", required=False))
    if siem_endpoint:
        checks.append(_http_check(
            "siem_ingest",
            "POST",
            siem_endpoint,
            required=required,
            json_body={"event": "preflight", "source": "nexra-vc-demo", "ts": int(time.time())},
            expected_statuses={200, 201, 202, 204},
        ))

    checks.extend(_embedding_path_smoke(base_url, required))

    return checks


def _mock_checks(base_url: str, mock_sink_base_url: str, required: bool) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(_http_check(
        "api_health",
        "GET",
        f"{base_url.rstrip('/')}/health",
        required=True,
        expected_statuses={200},
    ))
    checks.append(_http_check(
        "mock_sink_health",
        "GET",
        f"{mock_sink_base_url.rstrip('/')}/_health",
        required=required,
        expected_statuses={200},
    ))
    checks.append(CheckResult(
        name="integration_mode",
        required=required,
        passed=True,
        mode="config",
        details="mock mode selected; external integrations mocked by sink",
    ))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="VC demo preflight")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--integrations", choices=["real", "hybrid", "mock"], default="real")
    parser.add_argument("--failure-policy", choices=["fail-fast", "fallback", "skip"], default="fail-fast")
    parser.add_argument("--mock-sink-base-url", default="")
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()

    _load_env_defaults(ENV_FILES)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    required = args.failure_policy == "fail-fast"
    checks: list[CheckResult]

    if args.integrations == "mock":
        if not args.mock_sink_base_url:
            print("--mock-sink-base-url is required in mock mode", file=sys.stderr)
            return 1
        checks = _mock_checks(args.base_url, args.mock_sink_base_url, required=True)
    elif args.integrations == "hybrid":
        checks = _real_checks(
            args.base_url,
            required=False,
            require_real_channel_env=False,
        )
        if args.mock_sink_base_url:
            checks.extend(_mock_checks(args.base_url, args.mock_sink_base_url, required=False))
    else:
        checks = _real_checks(
            args.base_url,
            required=required,
            require_real_channel_env=True,
        )

    failed_required = [c for c in checks if c.required and not c.passed]
    failed_any = [c for c in checks if not c.passed]

    payload = {
        "integrations": args.integrations,
        "failure_policy": args.failure_policy,
        "base_url": args.base_url,
        "required_failed": len(failed_required),
        "failed_total": len(failed_any),
        "checks": [asdict(c) for c in checks],
    }

    out_path = args.results_dir / "preflight.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "failed_total": len(failed_any),
        "required_failed": len(failed_required),
        "out": str(out_path),
    }, indent=2, sort_keys=True))

    if args.failure_policy == "fail-fast" and failed_required:
        return 1
    if failed_required:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
