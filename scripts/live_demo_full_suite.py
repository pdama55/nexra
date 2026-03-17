#!/usr/bin/env python3
"""Full-platform live demo functional validation suite.

This suite validates API + worker behavior around a running Nexra stack,
including async completion, HiTL, SIEM export, anomaly notifications,
and compliance/reporting surfaces.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "nexra"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _preload_env_defaults(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_preload_env_defaults(APP_DIR / ".env")

from core.crypto import decrypt_aes_gcm, sha256_json  # noqa: E402
from core.jwt import issue_delegation_token  # noqa: E402
from models.delegation import Delegation  # noqa: E402
from models.organization import Organization  # noqa: E402
from services.anomaly_service import AnomalyService  # noqa: E402
from services.siem_service import SIEMService  # noqa: E402


class ScenarioFailure(Exception):
    pass


class ScenarioSkipped(Exception):
    pass


@dataclass
class ScenarioResult:
    name: str
    required: bool = True
    passed: bool = False
    skipped: bool = False
    error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None


@dataclass
class RunnerState:
    api_key: str | None = None
    org_id: str | None = None
    owner_email: str = "admin@nexra.local"
    caller_agent_id: str | None = None
    callee_agent_id: str | None = None
    allow_policy_id: str | None = None
    hitl_policy_id: str | None = None


class SuiteRunner:
    def __init__(
        self,
        *,
        base_url: str,
        results_dir: Path,
        api_key: str | None,
        owner_email: str,
        mock_sink_base_url: str | None,
        enable_stripe_onboard: bool,
        strict: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.results_dir / "http_trace.jsonl"
        self.summary_path = self.results_dir / "summary.json"
        self.report_path = self.results_dir / "report.txt"

        self.mock_sink_base_url = mock_sink_base_url.rstrip("/") if mock_sink_base_url else None
        self.enable_stripe_onboard = enable_stripe_onboard
        self.strict = strict

        env_from_file = load_env_file(APP_DIR / ".env")
        self.database_url = os.getenv("DATABASE_URL") or env_from_file.get("DATABASE_URL")
        self.secret_key_encryption_key = (
            os.getenv("SECRET_KEY_ENCRYPTION_KEY")
            or env_from_file.get("SECRET_KEY_ENCRYPTION_KEY")
        )

        self.state = RunnerState(
            api_key=api_key,
            owner_email=owner_email,
        )
        self.results: list[ScenarioResult] = []
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=45.0)

    async def close(self) -> None:
        await self.client.aclose()

    def auth_headers(
        self,
        *,
        include_user: bool = False,
        agent_id: str | None = None,
    ) -> dict[str, str]:
        if not self.state.api_key:
            raise ScenarioFailure("API key not initialized")
        headers = {
            "Authorization": f"Bearer {self.state.api_key}",
        }
        if include_user:
            headers["X-User-Email"] = self.state.owner_email
        if agent_id:
            headers["X-Agent-ID"] = agent_id
        return headers

    async def run(self) -> int:
        scenarios: list[tuple[str, bool, Any]] = [
            ("health_org_bootstrap", True, self.scenario_health_org_bootstrap),
            ("org_admin_surface", True, self.scenario_org_admin_surface),
            ("agents_and_discovery", True, self.scenario_agents_and_discovery),
            ("policies_lifecycle", True, self.scenario_policies_lifecycle),
            ("delegation_async_callback", True, self.scenario_delegation_async_callback),
            ("hitl_flows", True, self.scenario_hitl_flows),
            ("depth_guardrail", True, self.scenario_depth_guardrail),
            ("audit_and_compliance", True, self.scenario_audit_and_compliance),
            ("analytics_dashboard", True, self.scenario_analytics_dashboard),
            ("siem_export", True, self.scenario_siem_export),
            ("anomaly_fanout", True, self.scenario_anomaly_fanout),
            ("marketplace", False, self.scenario_marketplace),
        ]

        for name, required, fn in scenarios:
            await self.run_scenario(name=name, required=required, fn=fn)

        failed_required = [r for r in self.results if r.required and not (r.passed or r.skipped)]
        failed_optional = [r for r in self.results if (not r.required) and not (r.passed or r.skipped)]

        self.write_summary()
        self.write_report()

        if failed_required:
            return 1
        if failed_optional and self.strict:
            return 1
        return 0

    async def run_scenario(self, *, name: str, required: bool, fn: Any) -> None:
        result = ScenarioResult(name=name, required=required)
        self.results.append(result)
        try:
            await fn()
            result.passed = True
        except ScenarioSkipped as exc:
            result.skipped = True
            result.error = str(exc)
            if required and self.strict:
                result.passed = False
            else:
                result.passed = not required
        except Exception as exc:  # noqa: BLE001
            result.error = str(exc)
            result.passed = False
        finally:
            result.finished_at = datetime.now(UTC).isoformat()

    async def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> tuple[httpx.Response, dict[str, Any] | None]:
        expected_statuses = expected_statuses or {200}
        started = time.perf_counter()
        response = await self.client.request(
            method,
            path,
            headers=headers,
            json=json_body,
            params=params,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        payload: dict[str, Any] | None = None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = None

        trace_row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "method": method,
            "path": path,
            "params": params,
            "status_code": response.status_code,
            "expected_statuses": sorted(expected_statuses),
            "elapsed_ms": elapsed_ms,
            "request_json": json_body,
            "response_json": payload,
            "response_excerpt": response.text[:1000],
        }
        with self.trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trace_row, sort_keys=True))
            fh.write("\n")

        if response.status_code not in expected_statuses:
            raise ScenarioFailure(
                f"{method} {path} returned {response.status_code}, expected {sorted(expected_statuses)}; "
                f"response={response.text[:400]}"
            )

        return response, payload

    async def sink_captures(self, endpoint: str, limit: int = 200) -> list[dict[str, Any]]:
        if not self.mock_sink_base_url:
            return []
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{self.mock_sink_base_url}/_captures",
                params={"endpoint": endpoint, "limit": str(limit)},
            )
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("captures", [])

    async def scenario_health_org_bootstrap(self) -> None:
        await self.call("GET", "/health", expected_statuses={200})

        if not self.state.api_key:
            _, payload = await self.call(
                "POST",
                "/v1/orgs/register",
                json_body={
                    "name": f"Live Demo Suite Org {int(time.time())}",
                    "plan": "growth",
                    "owner_email": self.state.owner_email,
                },
                expected_statuses={201},
            )
            if not payload or "data" not in payload:
                raise ScenarioFailure("org register response missing data envelope")
            data = payload["data"]
            self.state.api_key = str(data["api_key"])
            self.state.org_id = str(data["org_id"])

        _, me_payload = await self.call(
            "GET",
            "/v1/orgs/me",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        if not me_payload or "data" not in me_payload:
            raise ScenarioFailure("/v1/orgs/me missing data envelope")
        me = me_payload["data"]
        self.state.org_id = str(me["org_id"])
        if me.get("owner_email"):
            self.state.owner_email = str(me["owner_email"])

        await self.call(
            "GET",
            "/v1/orgs/session",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

    async def scenario_org_admin_surface(self) -> None:
        _, list_keys = await self.call(
            "GET",
            "/v1/orgs/api-keys",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )
        if not list_keys or "data" not in list_keys:
            raise ScenarioFailure("/v1/orgs/api-keys missing data envelope")

        _, create_key = await self.call(
            "POST",
            "/v1/orgs/api-keys",
            headers=self.auth_headers(include_user=True),
            json_body={"name": "live-suite-secondary"},
            expected_statuses={200},
        )
        key_id = str((create_key or {}).get("data", {}).get("id", ""))
        if not key_id:
            raise ScenarioFailure("secondary API key id missing")

        await self.call(
            "DELETE",
            f"/v1/orgs/api-keys/{key_id}",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

        _, members_payload = await self.call(
            "GET",
            "/v1/orgs/members",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )
        if not members_payload or "data" not in members_payload:
            raise ScenarioFailure("/v1/orgs/members missing data envelope")

        temp_email = f"engineer+{int(time.time())}@example.com"
        _, create_member = await self.call(
            "POST",
            "/v1/orgs/members",
            headers=self.auth_headers(include_user=True),
            json_body={"email": temp_email, "role": "engineer"},
            expected_statuses={200},
        )
        member_id = str((create_member or {}).get("data", {}).get("id", ""))
        if not member_id:
            raise ScenarioFailure("member id missing from create response")

        await self.call(
            "PATCH",
            f"/v1/orgs/members/{member_id}",
            headers=self.auth_headers(include_user=True),
            json_body={"role": "compliance"},
            expected_statuses={200},
        )

        await self.call(
            "DELETE",
            f"/v1/orgs/members/{member_id}",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

        await self.call(
            "PATCH",
            "/v1/orgs/me",
            headers=self.auth_headers(include_user=True),
            json_body={"max_delegation_depth": 5},
            expected_statuses={200},
        )

        if not self.mock_sink_base_url:
            if self.strict:
                raise ScenarioFailure("mock sink base URL is required for webhook tests in strict mode")
            raise ScenarioSkipped("mock sink not configured; skipped webhook test calls")

        await self.call(
            "PATCH",
            "/v1/orgs/webhooks",
            headers=self.auth_headers(include_user=True),
            json_body={
                "approval_url": f"{self.mock_sink_base_url}/mock/approval",
                "notification_url": f"{self.mock_sink_base_url}/mock/notification",
            },
            expected_statuses={200},
        )
        await self.call(
            "POST",
            "/v1/orgs/webhooks/test",
            headers=self.auth_headers(include_user=True),
            json_body={"target": "approval"},
            expected_statuses={200},
        )
        await self.call(
            "POST",
            "/v1/orgs/webhooks/test",
            headers=self.auth_headers(include_user=True),
            json_body={"target": "notification"},
            expected_statuses={200},
        )

        await asyncio.sleep(0.2)
        approval_calls = await self.sink_captures("approval")
        notification_calls = await self.sink_captures("notification")
        if not approval_calls or not notification_calls:
            raise ScenarioFailure("webhook test calls were not captured by mock sink")

    async def scenario_agents_and_discovery(self) -> None:
        suffix = str(int(time.time()))
        caller_id = f"suite-caller-{suffix}"
        callee_id = f"suite-callee-{suffix}"

        caller_payload = {
            "agent_id": caller_id,
            "name": "Suite Caller",
            "description": "Live suite caller agent for deterministic full surface validation",
            "capability_type": "research",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "pricing": {"per_call_usd": 0.1},
            "sla": {"p99_latency_ms": 5000, "availability": 0.99},
            "webhook_url": "https://example.com/suite-caller",
            "webhook_secret": "a" * 32,
            "is_public": False,
        }
        callee_payload = {
            "agent_id": callee_id,
            "name": "Suite Callee",
            "description": "Live suite callee agent for deterministic full surface validation",
            "capability_type": "analysis",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                },
            },
            "pricing": {"per_call_usd": 0.2},
            "sla": {"p99_latency_ms": 7000, "availability": 0.99},
            "webhook_url": "https://example.com/suite-callee",
            "webhook_secret": "b" * 32,
            "is_public": True,
        }

        try:
            await self.call(
                "POST",
                "/v1/agents/register",
                headers=self.auth_headers(),
                json_body=caller_payload,
                expected_statuses={200},
            )
            await self.call(
                "POST",
                "/v1/agents/register",
                headers=self.auth_headers(),
                json_body=callee_payload,
                expected_statuses={200},
            )
        except ScenarioFailure as exc:
            msg = str(exc)
            if "EMBEDDING_SERVICE_UNAVAILABLE" in msg:
                raise ScenarioFailure(
                    "Agent registration failed due to embedding availability. "
                    "Ensure OPENAI_API_KEY in nexra/.env is valid for live demo testing."
                ) from exc
            raise

        a2a_payload = {
            "name": f"Suite A2A {suffix}",
            "description": "A2A card registration path used by live suite",
            "url": "https://example.com/suite-a2a",
            "capabilities": {"research": True},
        }
        await self.call(
            "POST",
            "/v1/agents/register/a2a",
            headers=self.auth_headers(),
            json_body=a2a_payload,
            expected_statuses={200},
        )

        await self.call(
            "GET",
            "/v1/agents/registry",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        await self.call(
            "GET",
            f"/v1/agents/{caller_id}",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        await self.call(
            "GET",
            f"/v1/agents/{callee_id}/trust",
            headers=self.auth_headers(),
            expected_statuses={200},
        )

        _, discovery_payload = await self.call(
            "POST",
            "/v1/capabilities/discover",
            headers=self.auth_headers(agent_id=caller_id),
            json_body={
                "query": "analysis and evaluation tasks",
                "capability_type": "analysis",
                "budget_cap_usd": 1.0,
                "include_cross_org": False,
                "limit": 5,
            },
            expected_statuses={200},
        )
        matches = ((discovery_payload or {}).get("data") or {}).get("matches") or []
        if not isinstance(matches, list):
            raise ScenarioFailure("discover response missing matches list")
        if not matches:
            raise ScenarioFailure("discover did not return any matches after registering callee agent")

        self.state.caller_agent_id = caller_id
        self.state.callee_agent_id = callee_id

    async def scenario_policies_lifecycle(self) -> None:
        create_payload = {
            "name": f"suite-policy-{int(time.time())}",
            "description": "Policy lifecycle validation",
            "priority": 60,
            "allow": {},
            "conditions": [],
            "on_violation": "block_and_alert",
        }
        _, create_resp = await self.call(
            "POST",
            "/v1/policies",
            headers=self.auth_headers(include_user=True),
            json_body=create_payload,
            expected_statuses={200},
        )
        policy_id = str((create_resp or {}).get("data", {}).get("id", ""))
        if not policy_id:
            raise ScenarioFailure("policy id missing from create response")

        await self.call(
            "GET",
            "/v1/policies",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        await self.call(
            "GET",
            f"/v1/policies/{policy_id}",
            headers=self.auth_headers(),
            expected_statuses={200},
        )

        _, updated_resp = await self.call(
            "PUT",
            f"/v1/policies/{policy_id}",
            headers=self.auth_headers(include_user=True),
            json_body={
                "description": "updated by live suite",
                "priority": 61,
            },
            expected_statuses={200},
        )
        updated_policy_id = str((updated_resp or {}).get("data", {}).get("id", ""))
        if not updated_policy_id:
            raise ScenarioFailure("updated policy id missing")

        _, versions_resp = await self.call(
            "GET",
            f"/v1/policies/{updated_policy_id}/versions",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        versions = ((versions_resp or {}).get("data") or {}).get("versions") or []
        if len(versions) < 2:
            raise ScenarioFailure("policy versions endpoint did not return expected history")

        await self.call(
            "DELETE",
            f"/v1/policies/{updated_policy_id}",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

        _, allow_resp = await self.call(
            "POST",
            "/v1/policies",
            headers=self.auth_headers(include_user=True),
            json_body={
                "name": f"suite-allow-{int(time.time())}",
                "description": "active allow policy for flow tests",
                "priority": 100,
                "allow": {},
                "conditions": [],
                "on_violation": "block_and_alert",
            },
            expected_statuses={200},
        )
        self.state.allow_policy_id = str((allow_resp or {}).get("data", {}).get("id", ""))
        if not self.state.allow_policy_id:
            raise ScenarioFailure("active allow policy not created")

    async def scenario_delegation_async_callback(self) -> None:
        if not self.state.caller_agent_id or not self.state.callee_agent_id:
            raise ScenarioFailure("caller/callee agents are not initialized")

        callback_url = f"{self.mock_sink_base_url}/mock/callback" if self.mock_sink_base_url else "http://127.0.0.1:8800/mock/callback"

        _, delegate_resp = await self.call(
            "POST",
            "/v1/delegate",
            headers=self.auth_headers(agent_id=self.state.caller_agent_id),
            json_body={
                "callee_agent_id": self.state.callee_agent_id,
                "task": {"input": {"query": "async flow"}},
                "context_scope": ["deal_metadata"],
                "budget_cap_usd": 2.0,
                "callback_url": callback_url,
            },
            expected_statuses={202},
        )
        data = (delegate_resp or {}).get("data") or {}
        delegation_id = str(data.get("delegation_id", ""))
        if not delegation_id or data.get("status") != "in_flight":
            raise ScenarioFailure("expected delegation status=in_flight for async callback flow")

        token = await issue_completion_token(
            database_url=self.database_url,
            secret_key_encryption_key=self.secret_key_encryption_key,
            delegation_id=delegation_id,
            callee_agent_id=self.state.callee_agent_id,
        )

        await self.call(
            "POST",
            f"/v1/delegations/{delegation_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
            json_body={
                "result": {"answer": "completed by suite"},
                "usage": {"llm_tokens": 15, "external_api_cost_usd": 0.02},
            },
            expected_statuses={200},
        )

        _, status_payload = await self.call(
            "GET",
            f"/v1/delegations/{delegation_id}",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        final_status = ((status_payload or {}).get("data") or {}).get("status")
        if final_status != "completed":
            raise ScenarioFailure(f"delegation {delegation_id} did not reach completed status")

        _, audit_payload = await self.call(
            "GET",
            "/v1/audit/log",
            headers=self.auth_headers(),
            params={"event_type": "callback_delivered", "delegation_id": delegation_id, "limit": 10},
            expected_statuses={200},
        )
        entries = ((audit_payload or {}).get("data") or {}).get("entries") or []
        if not entries:
            raise ScenarioFailure("callback_delivered audit event missing for completed async delegation")

        if self.mock_sink_base_url:
            await asyncio.sleep(0.2)
            callback_calls = await self.sink_captures("callback")
            if not callback_calls:
                raise ScenarioFailure("mock sink did not capture callback delivery")

    async def scenario_hitl_flows(self) -> None:
        if not self.state.caller_agent_id or not self.state.callee_agent_id:
            raise ScenarioFailure("caller/callee agents are not initialized")

        _, hitl_policy_resp = await self.call(
            "POST",
            "/v1/policies",
            headers=self.auth_headers(include_user=True),
            json_body={
                "name": f"suite-hitl-{int(time.time())}",
                "description": "force pause for HiTL flow",
                "priority": 1,
                "allow": {},
                "conditions": [],
                "hil_threshold_usd": 0.01,
                "on_violation": "block_and_alert",
            },
            expected_statuses={200},
        )
        self.state.hitl_policy_id = str((hitl_policy_resp or {}).get("data", {}).get("id", ""))
        if not self.state.hitl_policy_id:
            raise ScenarioFailure("failed to create HiTL policy")

        _, pause_resp = await self.call(
            "POST",
            "/v1/delegate",
            headers=self.auth_headers(agent_id=self.state.caller_agent_id),
            json_body={
                "callee_agent_id": self.state.callee_agent_id,
                "task": {"input": {"query": "hitl approve path"}},
                "context_scope": ["deal_metadata"],
                "budget_cap_usd": 1.0,
                "callback_url": (
                    f"{self.mock_sink_base_url}/mock/callback"
                    if self.mock_sink_base_url
                    else "http://127.0.0.1:8800/mock/callback"
                ),
            },
            expected_statuses={202},
        )
        pause_data = (pause_resp or {}).get("data") or {}
        approval_id = str(pause_data.get("delegation_id", ""))
        if pause_data.get("status") != "pending_approval":
            raise ScenarioFailure("expected pending_approval status for HiTL policy")

        await self.call(
            "POST",
            f"/v1/delegations/{approval_id}/approve",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200, 202},
        )

        token = await issue_completion_token(
            database_url=self.database_url,
            secret_key_encryption_key=self.secret_key_encryption_key,
            delegation_id=approval_id,
            callee_agent_id=self.state.callee_agent_id,
        )
        await self.call(
            "POST",
            f"/v1/delegations/{approval_id}/complete",
            headers={"Authorization": f"Bearer {token}"},
            json_body={
                "result": {"answer": "approved complete"},
                "usage": {"llm_tokens": 5},
            },
            expected_statuses={200},
        )

        _, second_pause_resp = await self.call(
            "POST",
            "/v1/delegate",
            headers=self.auth_headers(agent_id=self.state.caller_agent_id),
            json_body={
                "callee_agent_id": self.state.callee_agent_id,
                "task": {"input": {"query": "hitl reject path"}},
                "context_scope": ["deal_metadata"],
                "budget_cap_usd": 1.0,
                "callback_url": (
                    f"{self.mock_sink_base_url}/mock/callback"
                    if self.mock_sink_base_url
                    else "http://127.0.0.1:8800/mock/callback"
                ),
            },
            expected_statuses={202},
        )
        second_id = str(((second_pause_resp or {}).get("data") or {}).get("delegation_id", ""))
        await self.call(
            "POST",
            f"/v1/delegations/{second_id}/reject",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

        _, hitl_audit = await self.call(
            "GET",
            "/v1/audit/log",
            headers=self.auth_headers(),
            params={"event_type": "hil_triggered", "limit": 20},
            expected_statuses={200},
        )
        hitl_entries = ((hitl_audit or {}).get("data") or {}).get("entries") or []
        if not hitl_entries:
            raise ScenarioFailure("hil_triggered audit events not found")

        if self.mock_sink_base_url:
            await asyncio.sleep(0.2)
            approval_calls = await self.sink_captures("approval")
            if not approval_calls:
                if self.strict:
                    raise ScenarioFailure("expected HiTL approval webhook capture in strict mode")

    async def scenario_depth_guardrail(self) -> None:
        if not self.state.caller_agent_id or not self.state.callee_agent_id:
            raise ScenarioFailure("caller/callee agents are not initialized")

        await self.call(
            "PATCH",
            "/v1/orgs/me",
            headers=self.auth_headers(include_user=True),
            json_body={"max_delegation_depth": 1},
            expected_statuses={200},
        )

        if self.state.hitl_policy_id:
            await self.call(
                "DELETE",
                f"/v1/policies/{self.state.hitl_policy_id}",
                headers=self.auth_headers(include_user=True),
                expected_statuses={200},
            )

        async def create_depth_delegation(parent_id: str | None) -> str:
            body = {
                "callee_agent_id": self.state.callee_agent_id,
                "task": {"input": {"query": f"depth-parent-{parent_id or 'root'}"}},
                "context_scope": [],
                "budget_cap_usd": 1.0,
                "callback_url": f"{self.mock_sink_base_url}/mock/callback" if self.mock_sink_base_url else "http://127.0.0.1:8800/mock/callback",
            }
            if parent_id:
                body["parent_delegation_id"] = parent_id
            _, resp = await self.call(
                "POST",
                "/v1/delegate",
                headers=self.auth_headers(agent_id=self.state.caller_agent_id),
                json_body=body,
                expected_statuses={202},
            )
            return str(((resp or {}).get("data") or {}).get("delegation_id", ""))

        root_id = await create_depth_delegation(None)
        depth_1_id = await create_depth_delegation(root_id)

        _, too_deep_resp = await self.call(
            "POST",
            "/v1/delegate",
            headers=self.auth_headers(agent_id=self.state.caller_agent_id),
            json_body={
                "callee_agent_id": self.state.callee_agent_id,
                "task": {"input": {"query": "too deep"}},
                "context_scope": [],
                "budget_cap_usd": 1.0,
                "parent_delegation_id": depth_1_id,
            },
            expected_statuses={400},
        )
        err_code = ((too_deep_resp or {}).get("error") or {}).get("code")
        if err_code != "MAX_DEPTH_EXCEEDED":
            raise ScenarioFailure(f"expected MAX_DEPTH_EXCEEDED, got {err_code}")

    async def scenario_audit_and_compliance(self) -> None:
        await self.call(
            "GET",
            "/v1/audit/log",
            headers=self.auth_headers(),
            params={"format": "json", "limit": 50},
            expected_statuses={200},
        )
        csv_resp, _ = await self.call(
            "GET",
            "/v1/audit/log",
            headers=self.auth_headers(),
            params={"format": "csv"},
            expected_statuses={200},
        )
        if "text/csv" not in csv_resp.headers.get("content-type", ""):
            raise ScenarioFailure("audit CSV export did not return text/csv")

        for report_type in ("soc2", "gdpr", "hipaa"):
            _, report_payload = await self.call(
                "GET",
                f"/v1/compliance/report/{report_type}",
                headers=self.auth_headers(),
                expected_statuses={200},
            )
            if ((report_payload or {}).get("data") or {}).get("report_type") != report_type:
                raise ScenarioFailure(f"compliance report_type mismatch for {report_type}")

        package_resp, _ = await self.call(
            "GET",
            "/v1/compliance/export/package",
            headers=self.auth_headers(include_user=True),
            params={"set": "soc2_core"},
            expected_statuses={200},
        )
        required_files = {
            "audit_log.csv",
            "policy_coverage.csv",
            "spend_governance.csv",
            "agent_status_history.csv",
            "hitl_decision_log.csv",
            "manifest.json",
        }
        with zipfile.ZipFile(io.BytesIO(package_resp.content), mode="r") as archive:
            names = set(archive.namelist())
        if not required_files.issubset(names):
            missing = sorted(required_files - names)
            raise ScenarioFailure(f"compliance package missing files: {missing}")

    async def scenario_analytics_dashboard(self) -> None:
        if not self.state.caller_agent_id:
            raise ScenarioFailure("caller agent not initialized")

        await self.call(
            "GET",
            "/v1/analytics/usage",
            headers=self.auth_headers(),
            params={"window": "last_24h"},
            expected_statuses={200},
        )
        await self.call(
            "GET",
            "/v1/spend/summary",
            headers=self.auth_headers(),
            params={"window": "last_7d", "breakdown": "all"},
            expected_statuses={200},
        )
        spend_export_resp, _ = await self.call(
            "GET",
            "/v1/spend/summary/export",
            headers=self.auth_headers(),
            params={"window": "last_7d", "breakdown": "all"},
            expected_statuses={200},
        )
        if "text/csv" not in spend_export_resp.headers.get("content-type", ""):
            raise ScenarioFailure("spend summary export did not return text/csv")

        await self.call(
            "POST",
            "/v1/spend/budget-cap",
            headers=self.auth_headers(include_user=True),
            json_body={
                "agent_id": self.state.caller_agent_id,
                "period_type": "daily",
                "cap_usd": 50.0,
            },
            expected_statuses={200},
        )

        dashboard_paths = [
            "/v1/dashboard/volume",
            "/v1/dashboard/cost-breakdown",
            "/v1/dashboard/failure-rates",
            "/v1/dashboard/trust-leaderboard",
            "/v1/dashboard/budget-alerts",
            "/v1/dashboard/network-graph",
        ]
        for path in dashboard_paths:
            await self.call("GET", path, headers=self.auth_headers(), expected_statuses={200})

    async def scenario_siem_export(self) -> None:
        if not self.mock_sink_base_url:
            if self.strict:
                raise ScenarioFailure("mock sink is required for SIEM validation in strict mode")
            raise ScenarioSkipped("mock sink not configured; skipping SIEM export assertions")

        await self.call(
            "POST",
            "/v1/siem/config",
            headers=self.auth_headers(include_user=True),
            json_body={
                "target": "generic",
                "endpoint": f"{self.mock_sink_base_url}/mock/siem",
                "enabled": True,
                "event_types": [],
            },
            expected_statuses={200},
        )
        await self.call(
            "GET",
            "/v1/siem/config",
            headers=self.auth_headers(),
            expected_statuses={200},
        )

        exported_count = await export_siem_events(self.database_url)
        if exported_count <= 0:
            raise ScenarioFailure("SIEM export worker did not export any events")

        _, config_after = await self.call(
            "GET",
            "/v1/siem/config",
            headers=self.auth_headers(),
            expected_statuses={200},
        )
        cursor = ((config_after or {}).get("data") or {}).get("cursor")
        if not cursor:
            raise ScenarioFailure("SIEM config cursor not updated after export")

        await asyncio.sleep(0.2)
        siem_calls = await self.sink_captures("siem")
        if not siem_calls:
            raise ScenarioFailure("mock sink did not capture SIEM export payload")

    async def scenario_anomaly_fanout(self) -> None:
        if not self.state.caller_agent_id or not self.state.callee_agent_id or not self.state.org_id:
            raise ScenarioFailure("anomaly prerequisites missing")

        await seed_anomaly_spike(
            database_url=self.database_url,
            org_id=self.state.org_id,
            caller_agent_id=self.state.caller_agent_id,
            callee_agent_id=self.state.callee_agent_id,
        )

        anomalies = await run_anomaly_detection(self.database_url)
        if not anomalies:
            raise ScenarioFailure("anomaly detector returned no anomalies after deterministic seed")

        _, audit_payload = await self.call(
            "GET",
            "/v1/audit/log",
            headers=self.auth_headers(),
            params={
                "event_type": "anomaly_detected",
                "target_agent_id": self.state.callee_agent_id,
                "limit": 20,
            },
            expected_statuses={200},
        )
        entries = ((audit_payload or {}).get("data") or {}).get("entries") or []
        if not entries:
            raise ScenarioFailure("anomaly_detected audit event missing")

        if not self.mock_sink_base_url:
            if self.strict:
                raise ScenarioFailure("mock sink required for anomaly fanout assertions in strict mode")
            raise ScenarioSkipped("mock sink not configured; skipped channel capture assertions")

        await asyncio.sleep(0.4)
        slack_calls = await self.sink_captures("slack")
        email_calls = await self.sink_captures("sendgrid")
        pager_calls = await self.sink_captures("pagerduty")

        if not email_calls or not pager_calls:
            msg = (
                "expected email and pagerduty fanout captures. "
                "Ensure bootstrap mode sets SENDGRID_* and PAGERDUTY_EVENTS_BASE_URL/ANOMALY_PAGERDUTY_ROUTING_KEY."
            )
            if self.strict:
                raise ScenarioFailure(msg)
            raise ScenarioSkipped(msg)

        if not slack_calls and self.strict:
            raise ScenarioFailure("expected at least one Slack fanout capture in strict mode")

    async def scenario_marketplace(self) -> None:
        await self.call(
            "GET",
            "/v1/marketplace/connect-status",
            headers=self.auth_headers(),
            expected_statuses={200},
        )

        if not self.enable_stripe_onboard:
            raise ScenarioSkipped("connect-onboard is optional; enable with --enable-stripe-onboard")

        await self.call(
            "POST",
            "/v1/marketplace/connect-onboard",
            headers=self.auth_headers(include_user=True),
            expected_statuses={200},
        )

    def write_summary(self) -> None:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "base_url": self.base_url,
            "results": [
                {
                    "name": item.name,
                    "required": item.required,
                    "passed": item.passed,
                    "skipped": item.skipped,
                    "error": item.error,
                    "started_at": item.started_at,
                    "finished_at": item.finished_at,
                }
                for item in self.results
            ],
        }
        self.summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def write_report(self) -> None:
        lines = [
            "Nexra Live Demo Full Suite Report",
            f"Generated: {datetime.now(UTC).isoformat()}",
            f"Base URL: {self.base_url}",
            "",
        ]
        for item in self.results:
            if item.passed and not item.skipped:
                status = "PASS"
            elif item.skipped:
                status = "SKIP"
            else:
                status = "FAIL"
            req = "required" if item.required else "optional"
            line = f"[{status}] {item.name} ({req})"
            if item.error:
                line += f" :: {item.error}"
            lines.append(line)

        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def issue_completion_token(
    *,
    database_url: str | None,
    secret_key_encryption_key: str | None,
    delegation_id: str,
    callee_agent_id: str,
) -> str:
    if not database_url:
        raise ScenarioFailure("DATABASE_URL is required for delegation token helper")
    if not secret_key_encryption_key:
        raise ScenarioFailure("SECRET_KEY_ENCRYPTION_KEY is required for delegation token helper")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await session.execute(
                select(Delegation, Organization)
                .join(Organization, Organization.id == Delegation.caller_org_id)
                .where(Delegation.id == uuid.UUID(delegation_id))
            )
            row = result.first()
            if row is None:
                raise ScenarioFailure(f"delegation {delegation_id} not found for token issuance")
            delegation, org = row
            org_secret = decrypt_aes_gcm(org.jwt_secret_enc, secret_key_encryption_key)
            return issue_delegation_token(
                org_secret,
                str(delegation.id),
                callee_agent_id,
                delegation.context_scope or [],
            )
    finally:
        await engine.dispose()


async def seed_anomaly_spike(
    *,
    database_url: str | None,
    org_id: str,
    caller_agent_id: str,
    callee_agent_id: str,
) -> None:
    if not database_url:
        raise ScenarioFailure("DATABASE_URL is required for anomaly seed helper")

    org_uuid = uuid.UUID(org_id)
    now = datetime.now(UTC)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with session_factory() as session:
            historical_costs = [
                Decimal("0.8200"),
                Decimal("0.9100"),
                Decimal("1.0300"),
                Decimal("1.1100"),
                Decimal("0.9700"),
            ]
            for idx in range(30):
                created = now - timedelta(hours=idx + 2)
                task = {"seed": "anomaly-history", "idx": idx}
                cost = historical_costs[idx % len(historical_costs)]
                session.add(
                    Delegation(
                        caller_org_id=org_uuid,
                        caller_agent_id=caller_agent_id,
                        callee_org_id=org_uuid,
                        callee_agent_id=callee_agent_id,
                        task=task,
                        task_hash=sha256_json(task),
                        context_scope=[],
                        policy_decision="allow",
                        status="completed",
                        workflow="anomaly-seed",
                        estimated_cost_usd=cost,
                        actual_cost_usd=cost,
                        created_at=created,
                        completed_at=created + timedelta(minutes=1),
                    )
                )

            current_task = {"seed": "anomaly-current", "ts": int(now.timestamp())}
            session.add(
                Delegation(
                    caller_org_id=org_uuid,
                    caller_agent_id=caller_agent_id,
                    callee_org_id=org_uuid,
                    callee_agent_id=callee_agent_id,
                    task=current_task,
                    task_hash=sha256_json(current_task),
                    context_scope=[],
                    policy_decision="allow",
                    status="completed",
                    workflow="anomaly-seed",
                    estimated_cost_usd=Decimal("250.0000"),
                    actual_cost_usd=Decimal("250.0000"),
                    created_at=now - timedelta(minutes=10),
                    completed_at=now - timedelta(minutes=9),
                )
            )

            await session.commit()
    finally:
        await engine.dispose()


async def export_siem_events(database_url: str | None) -> int:
    if not database_url:
        raise ScenarioFailure("DATABASE_URL is required for SIEM export helper")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            service = SIEMService(session)
            configs = await service.list_enabled_configs()
            exported = 0
            for config in configs:
                exported += await service.export_next_batch(config)
            return exported
    finally:
        await engine.dispose()


async def run_anomaly_detection(database_url: str | None) -> list[dict[str, object]]:
    if not database_url:
        raise ScenarioFailure("DATABASE_URL is required for anomaly detection helper")

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            service = AnomalyService(session)
            return await service.detect_spend_anomalies()
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full live demo functional suite")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--owner-email", default="admin@nexra.local")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--mock-sink-base-url", default=None)
    parser.add_argument("--enable-stripe-onboard", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()

    runner = SuiteRunner(
        base_url=args.base_url,
        results_dir=args.results_dir,
        api_key=args.api_key,
        owner_email=args.owner_email,
        mock_sink_base_url=args.mock_sink_base_url,
        enable_stripe_onboard=args.enable_stripe_onboard,
        strict=args.strict,
    )
    try:
        return await runner.run()
    finally:
        await runner.close()


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
