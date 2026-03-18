#!/usr/bin/env python3
"""Dashboard-backed API stress harness.

Generates sustained authenticated load against endpoints used by the internal dashboard
and writes endpoint-level reliability + latency metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _latency_quantiles(samples: list[float]) -> dict[str, float]:
    if not samples:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
    ordered = sorted(samples)
    size = len(ordered)

    def pct(p: float) -> float:
        idx = max(0, min(size - 1, int(round((size - 1) * p))))
        return round(float(ordered[idx]), 2)

    return {
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
    }


def _validate_shape(name: str, payload: Any) -> str | None:
    if not isinstance(payload, dict) or "data" not in payload:
        return f"{name}: missing data envelope"
    data = payload["data"]

    if name == "analytics_usage":
        required = {"total_delegations", "completed", "blocked", "total_cost_usd"}
        if not isinstance(data, dict) or not required.issubset(data.keys()):
            return f"{name}: missing keys {sorted(required)}"
        return None

    if name == "agents_registry":
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            return f"{name}: data.agents missing list"
        return None

    if name == "delegations_list":
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            return f"{name}: data.items missing list"
        return None

    if name == "audit_log":
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            return f"{name}: data.entries missing list"
        return None

    if name == "spend_summary":
        if not isinstance(data, dict):
            return f"{name}: data not dict"
        if "totals" not in data or "summary" not in data:
            return f"{name}: expected totals/summary fields"
        return None

    if name == "policies_list":
        if not isinstance(data, dict) or not isinstance(data.get("policies"), list):
            return f"{name}: data.policies missing list"
        return None

    if name in {"org_me", "org_session", "siem_config", "marketplace_connect_status", "org_webhooks"}:
        if not isinstance(data, dict):
            return f"{name}: data not dict"
        return None

    if name in {"org_api_keys", "org_members"}:
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            return f"{name}: data.items missing list"
        return None

    return None


@dataclass
class EndpointStats:
    name: str
    total_requests: int = 0
    success_2xx: int = 0
    success_4xx: int = 0
    non_2xx_4xx: int = 0
    timeout_count: int = 0
    shape_validation_failures: int = 0
    _latency_samples: list[float] = field(default_factory=list)
    _latency_sample_cap: int = 5000

    def add_latency(self, latency_ms: float) -> None:
        if len(self._latency_samples) < self._latency_sample_cap:
            self._latency_samples.append(latency_ms)
            return
        idx = random.randint(0, self.total_requests)
        if idx < self._latency_sample_cap:
            self._latency_samples[idx] = latency_ms

    def to_dict(self) -> dict[str, Any]:
        non_2xx_4xx_rate = (self.non_2xx_4xx / self.total_requests) if self.total_requests else 0.0
        timeout_rate = (self.timeout_count / self.total_requests) if self.total_requests else 0.0
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "success_2xx": self.success_2xx,
            "success_4xx": self.success_4xx,
            "non_2xx_4xx": self.non_2xx_4xx,
            "non_2xx_4xx_rate": round(non_2xx_4xx_rate, 6),
            "timeout_count": self.timeout_count,
            "timeout_rate": round(timeout_rate, 6),
            "shape_validation_failures": self.shape_validation_failures,
            "latency": _latency_quantiles(self._latency_samples),
        }


class StressLoadRunner:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        user_email: str,
        duration_min: int,
        peak_vus: int,
        error_rate_threshold: float,
        timeout_s: float,
        results_dir: Path,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.duration_min = duration_min
        self.peak_vus = peak_vus
        self.error_rate_threshold = error_rate_threshold
        self.timeout_s = timeout_s
        self.results_dir = results_dir
        self.metrics_path = results_dir / "endpoint_metrics.json"
        self.failures_path = results_dir / "api_failures.jsonl"

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "X-User-Email": user_email,
            "Content-Type": "application/json",
        }
        self.stats: dict[str, EndpointStats] = {}
        self._lock = asyncio.Lock()

    def _target_vus(self, elapsed_s: float, total_s: float) -> int:
        # 5-segment curve: 10 -> 25 -> peak -> 25 -> 10
        seg = total_s / 5.0
        low = _clamp(round(self.peak_vus * 0.25), 1, self.peak_vus)
        med = _clamp(round(self.peak_vus * 0.625), 1, self.peak_vus)
        targets = [low, med, self.peak_vus, med, low]
        idx = min(4, int(elapsed_s // seg) if seg > 0 else 4)
        return targets[idx]

    async def _write_failure(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            with self.failures_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True))
                fh.write("\n")

    async def _record(
        self,
        *,
        name: str,
        status_code: int | None,
        latency_ms: float | None,
        timed_out: bool,
        shape_error: str | None,
    ) -> None:
        async with self._lock:
            stat = self.stats.setdefault(name, EndpointStats(name=name))
            stat.total_requests += 1
            if timed_out:
                stat.timeout_count += 1
            if status_code is not None:
                if 200 <= status_code < 300:
                    stat.success_2xx += 1
                elif 400 <= status_code < 500:
                    stat.success_4xx += 1
                else:
                    stat.non_2xx_4xx += 1
            if shape_error:
                stat.shape_validation_failures += 1
            if latency_ms is not None:
                stat.add_latency(latency_ms)

    async def _endpoint_catalog(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        agents_resp = await client.get("/v1/agents/registry", headers=self.headers, params={"limit": 50})
        agents_payload = agents_resp.json() if agents_resp.headers.get("content-type", "").lower().startswith("application/json") else {}
        agent_rows = ((agents_payload.get("data") or {}).get("agents") or []) if isinstance(agents_payload, dict) else []
        first_agent = str(agent_rows[0].get("agent_id")) if agent_rows else None

        deleg_resp = await client.get(
            "/v1/delegations",
            headers=self.headers,
            params={"limit": 1, "sort": "created_at:desc"},
        )
        deleg_payload = deleg_resp.json() if deleg_resp.headers.get("content-type", "").lower().startswith("application/json") else {}
        deleg_rows = ((deleg_payload.get("data") or {}).get("items") or []) if isinstance(deleg_payload, dict) else []
        first_delegation = str(deleg_rows[0].get("id")) if deleg_rows else None

        policy_resp = await client.get("/v1/policies", headers=self.headers)
        policy_payload = policy_resp.json() if policy_resp.headers.get("content-type", "").lower().startswith("application/json") else {}
        policy_rows = ((policy_payload.get("data") or {}).get("policies") or []) if isinstance(policy_payload, dict) else []
        first_policy = str(policy_rows[0].get("id")) if policy_rows else None

        catalog: list[dict[str, Any]] = [
            {"name": "analytics_usage", "method": "GET", "path": "/v1/analytics/usage", "params": {"window": "last_24h"}},
            {"name": "agents_registry", "method": "GET", "path": "/v1/agents/registry", "params": {"limit": 50}},
            {
                "name": "delegations_list",
                "method": "GET",
                "path": "/v1/delegations",
                "params": {"limit": 25, "sort": "created_at:desc"},
            },
            {"name": "audit_log", "method": "GET", "path": "/v1/audit/log", "params": {"limit": 50}},
            {
                "name": "spend_summary",
                "method": "GET",
                "path": "/v1/spend/summary",
                "params": {"window": "last_24h", "breakdown": "all"},
            },
            {"name": "policies_list", "method": "GET", "path": "/v1/policies", "params": {}},
            {"name": "org_me", "method": "GET", "path": "/v1/orgs/me", "params": {}},
            {"name": "org_session", "method": "GET", "path": "/v1/orgs/session", "params": {}},
            {"name": "org_api_keys", "method": "GET", "path": "/v1/orgs/api-keys", "params": {}},
            {"name": "org_members", "method": "GET", "path": "/v1/orgs/members", "params": {}},
            {"name": "org_webhooks", "method": "GET", "path": "/v1/orgs/webhooks", "params": {}},
            {"name": "siem_config", "method": "GET", "path": "/v1/siem/config", "params": {}},
            {"name": "marketplace_connect_status", "method": "GET", "path": "/v1/marketplace/connect-status", "params": {}},
        ]

        if first_agent:
            catalog.append({"name": "agent_detail", "method": "GET", "path": f"/v1/agents/{first_agent}", "params": {}})
            catalog.append(
                {"name": "agent_trust", "method": "GET", "path": f"/v1/agents/{first_agent}/trust", "params": {}}
            )
        if first_delegation:
            catalog.append(
                {"name": "delegation_detail", "method": "GET", "path": f"/v1/delegations/{first_delegation}", "params": {}}
            )
        if first_policy:
            catalog.append({"name": "policy_detail", "method": "GET", "path": f"/v1/policies/{first_policy}", "params": {}})

        return catalog

    async def _worker(
        self,
        *,
        worker_idx: int,
        client: httpx.AsyncClient,
        start_ts: float,
        total_s: float,
        catalog: list[dict[str, Any]],
    ) -> None:
        deadline = start_ts + total_s
        while True:
            now = time.time()
            if now >= deadline:
                return

            elapsed = now - start_ts
            target_vus = self._target_vus(elapsed, total_s)
            if worker_idx >= target_vus:
                await asyncio.sleep(0.25)
                continue

            endpoint = random.choice(catalog)
            name = str(endpoint["name"])
            method = str(endpoint["method"])
            path = str(endpoint["path"])
            params = dict(endpoint.get("params") or {})

            started = time.perf_counter()
            status_code: int | None = None
            shape_error: str | None = None
            timed_out = False
            latency_ms: float | None = None
            failure_payload: dict[str, Any] | None = None

            try:
                response = await client.request(method, path, headers=self.headers, params=params)
                status_code = response.status_code
                latency_ms = round((time.perf_counter() - started) * 1000, 2)

                payload: Any = None
                if "application/json" in response.headers.get("content-type", "").lower():
                    try:
                        payload = response.json()
                    except Exception:  # noqa: BLE001
                        payload = None

                if response.status_code >= 500:
                    failure_payload = {
                        "timestamp": _iso_now(),
                        "type": "server_error",
                        "endpoint": name,
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "latency_ms": latency_ms,
                        "response_excerpt": response.text[:300],
                    }
                elif 200 <= response.status_code < 300:
                    shape_error = _validate_shape(name, payload)
                    if shape_error:
                        failure_payload = {
                            "timestamp": _iso_now(),
                            "type": "shape_validation_failure",
                            "endpoint": name,
                            "method": method,
                            "path": path,
                            "status_code": response.status_code,
                            "latency_ms": latency_ms,
                            "error": shape_error,
                        }
            except httpx.TimeoutException:
                timed_out = True
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                failure_payload = {
                    "timestamp": _iso_now(),
                    "type": "timeout",
                    "endpoint": name,
                    "method": method,
                    "path": path,
                    "latency_ms": latency_ms,
                }
            except Exception as exc:  # noqa: BLE001
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                failure_payload = {
                    "timestamp": _iso_now(),
                    "type": "request_exception",
                    "endpoint": name,
                    "method": method,
                    "path": path,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                }

            await self._record(
                name=name,
                status_code=status_code,
                latency_ms=latency_ms,
                timed_out=timed_out,
                shape_error=shape_error,
            )
            if failure_payload:
                await self._write_failure(failure_payload)
            await asyncio.sleep(0.03)

    async def _exercise_endpoint_once(self, client: httpx.AsyncClient, endpoint: dict[str, Any]) -> None:
        """Ensure each endpoint is observed at least once before random sampling starts."""
        name = str(endpoint["name"])
        method = str(endpoint["method"])
        path = str(endpoint["path"])
        params = dict(endpoint.get("params") or {})

        started = time.perf_counter()
        status_code: int | None = None
        shape_error: str | None = None
        timed_out = False
        latency_ms: float | None = None
        failure_payload: dict[str, Any] | None = None

        try:
            response = await client.request(method, path, headers=self.headers, params=params)
            status_code = response.status_code
            latency_ms = round((time.perf_counter() - started) * 1000, 2)

            payload: Any = None
            if "application/json" in response.headers.get("content-type", "").lower():
                try:
                    payload = response.json()
                except Exception:  # noqa: BLE001
                    payload = None

            if response.status_code >= 500:
                failure_payload = {
                    "timestamp": _iso_now(),
                    "type": "server_error",
                    "endpoint": name,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "response_excerpt": response.text[:300],
                }
            elif 200 <= response.status_code < 300:
                shape_error = _validate_shape(name, payload)
                if shape_error:
                    failure_payload = {
                        "timestamp": _iso_now(),
                        "type": "shape_validation_failure",
                        "endpoint": name,
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "latency_ms": latency_ms,
                        "error": shape_error,
                    }
        except httpx.TimeoutException:
            timed_out = True
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            failure_payload = {
                "timestamp": _iso_now(),
                "type": "timeout",
                "endpoint": name,
                "method": method,
                "path": path,
                "latency_ms": latency_ms,
            }
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            failure_payload = {
                "timestamp": _iso_now(),
                "type": "request_exception",
                "endpoint": name,
                "method": method,
                "path": path,
                "latency_ms": latency_ms,
                "error": str(exc),
            }

        await self._record(
            name=name,
            status_code=status_code,
            latency_ms=latency_ms,
            timed_out=timed_out,
            shape_error=shape_error,
        )
        if failure_payload:
            await self._write_failure(failure_payload)

    async def run(self) -> tuple[int, dict[str, Any]]:
        total_s = max(60.0, float(self.duration_min * 60))
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.failures_path.write_text("", encoding="utf-8")

        timeout = httpx.Timeout(connect=self.timeout_s, read=self.timeout_s, write=self.timeout_s, pool=self.timeout_s)
        start_ts = time.time()

        async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
            catalog = await self._endpoint_catalog(client)
            for endpoint in catalog:
                await self._exercise_endpoint_once(client, endpoint)
            workers = [
                asyncio.create_task(
                    self._worker(
                        worker_idx=i,
                        client=client,
                        start_ts=start_ts,
                        total_s=total_s,
                        catalog=catalog,
                    )
                )
                for i in range(self.peak_vus)
            ]
            await asyncio.gather(*workers)

        endpoint_rows = {name: stat.to_dict() for name, stat in sorted(self.stats.items())}
        critical_endpoints: list[str] = []
        for name, row in endpoint_rows.items():
            if row["total_requests"] < 1:
                critical_endpoints.append(f"{name}: no requests executed")
                continue
            if row["non_2xx_4xx_rate"] > self.error_rate_threshold:
                critical_endpoints.append(
                    f"{name}: non_2xx_4xx_rate={row['non_2xx_4xx_rate']:.4f} > {self.error_rate_threshold:.4f}"
                )

        summary = {
            "generated_at": _iso_now(),
            "base_url": self.base_url,
            "duration_min": self.duration_min,
            "peak_vus": self.peak_vus,
            "error_rate_threshold": self.error_rate_threshold,
            "endpoint_count": len(endpoint_rows),
            "endpoints": endpoint_rows,
            "critical_endpoint_failures": critical_endpoints,
        }
        self.metrics_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

        return (1 if critical_endpoints else 0), summary


async def _amain(args: argparse.Namespace) -> int:
    runner = StressLoadRunner(
        base_url=args.base_url,
        api_key=args.api_key,
        user_email=args.user_email,
        duration_min=args.duration_min,
        peak_vus=args.peak_vus,
        error_rate_threshold=args.error_rate_threshold,
        timeout_s=args.timeout_s,
        results_dir=args.results_dir,
    )
    rc, summary = await runner.run()
    print(
        json.dumps(
            {
                "endpoint_metrics": str(runner.metrics_path),
                "api_failures": str(runner.failures_path),
                "critical_endpoint_failures": len(summary["critical_endpoint_failures"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard-backed API stress load runner")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--user-email", default="admin@nexra.local")
    parser.add_argument("--duration-min", type=int, default=90)
    parser.add_argument("--peak-vus", type=int, default=40)
    parser.add_argument("--error-rate-threshold", type=float, default=0.01)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
