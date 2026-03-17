#!/usr/bin/env python3
"""Strict integration preflight for VC demo runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_ENV = ROOT_DIR / "nexra" / ".env"


@dataclass
class CheckResult:
    name: str
    required: bool
    passed: bool
    mode: str
    details: str
    latency_ms: float | None = None


def _load_env_defaults(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
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


def _real_checks(base_url: str, required: bool) -> list[CheckResult]:
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
    checks.append(_env_present("sendgrid_key", "SENDGRID_API_KEY", required))
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
    checks.append(_env_present("slack_webhook", "ANOMALY_SLACK_WEBHOOK_URL", required))
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
    checks.append(_env_present("pagerduty_routing", "ANOMALY_PAGERDUTY_ROUTING_KEY", required))
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
    checks.append(_env_present("siem_endpoint", "SIEM_WEBHOOK_ENDPOINT", required))
    if siem_endpoint:
        checks.append(_http_check(
            "siem_ingest",
            "POST",
            siem_endpoint,
            required=required,
            json_body={"event": "preflight", "source": "nexra-vc-demo", "ts": int(time.time())},
            expected_statuses={200, 201, 202, 204},
        ))

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

    _load_env_defaults(APP_ENV)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    required = args.failure_policy == "fail-fast"
    checks: list[CheckResult]

    if args.integrations == "mock":
        if not args.mock_sink_base_url:
            print("--mock-sink-base-url is required in mock mode", file=sys.stderr)
            return 1
        checks = _mock_checks(args.base_url, args.mock_sink_base_url, required=True)
    elif args.integrations == "hybrid":
        checks = _real_checks(args.base_url, required=False)
        if args.mock_sink_base_url:
            checks.extend(_mock_checks(args.base_url, args.mock_sink_base_url, required=False))
    else:
        checks = _real_checks(args.base_url, required=required)

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

    if args.failure_policy == "fail-fast" and failed_any:
        return 1
    if failed_required:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
