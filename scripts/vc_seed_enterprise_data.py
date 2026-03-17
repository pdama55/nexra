#!/usr/bin/env python3
"""Seed multi-org enterprise demo data for VC showcase runs."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "nexra"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


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


_load_env_defaults(APP_DIR / ".env")

from core.crypto import sha256_json  # noqa: E402
from models.agent import Agent  # noqa: E402
from models.agent_budget import AgentBudget  # noqa: E402
from models.audit_log import AuditLog  # noqa: E402
from models.delegation import Delegation  # noqa: E402
from models.organization import Organization  # noqa: E402
from models.trust_score_event import TrustScoreEvent  # noqa: E402


@dataclass
class OrgSeed:
    name: str
    owner_email: str
    org_id: str
    api_key: str


class SeedError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=45.0)

    def close(self) -> None:
        self.client.close()

    def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        expected: set[int] | None = None,
    ) -> dict[str, Any]:
        expected = expected or {200}
        resp = self.client.request(method, path, headers=headers, json=json_body)
        if resp.status_code not in expected:
            raise SeedError(f"{method} {path} -> {resp.status_code}: {resp.text[:400]}")
        try:
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise SeedError(f"{method} {path}: invalid JSON response ({exc})") from exc
        if "data" not in payload:
            raise SeedError(f"{method} {path}: missing data envelope")
        return payload["data"]


def _auth_headers(api_key: str, *, email: str | None = None, agent_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if email:
        headers["X-User-Email"] = email
    if agent_id:
        headers["X-Agent-ID"] = agent_id
    return headers


def create_org(api: ApiClient, name: str, plan: str, owner_email: str) -> OrgSeed:
    data = api.call(
        "POST",
        "/v1/orgs/register",
        json_body={"name": name, "plan": plan, "owner_email": owner_email},
        expected={201},
    )
    return OrgSeed(name=name, owner_email=owner_email, org_id=str(data["org_id"]), api_key=str(data["api_key"]))


def configure_org(api: ApiClient, org: OrgSeed, approval_url: str, notification_url: str, max_depth: int) -> None:
    api.call(
        "PATCH",
        "/v1/orgs/me",
        headers=_auth_headers(org.api_key, email=org.owner_email),
        json_body={
            "approval_url": approval_url,
            "notification_url": notification_url,
            "max_delegation_depth": max_depth,
        },
        expected={200},
    )


def create_allow_policy(api: ApiClient, org: OrgSeed, name: str) -> str:
    data = api.call(
        "POST",
        "/v1/policies",
        headers=_auth_headers(org.api_key, email=org.owner_email),
        json_body={
            "name": name,
            "description": "VC seed allow policy",
            "priority": 50,
            "allow": {},
            "conditions": [],
            "on_violation": "block_and_alert",
            "hil_threshold_usd": 250.0,
        },
        expected={200},
    )
    return str(data["id"])


def register_agent(api: ApiClient, org: OrgSeed, *, agent_id: str, capability_type: str, team: str, is_public: bool) -> None:
    api.call(
        "POST",
        "/v1/agents/register",
        headers=_auth_headers(org.api_key),
        json_body={
            "agent_id": agent_id,
            "name": agent_id.replace("-", " ").title(),
            "description": f"{agent_id} enterprise capability agent",
            "capability_type": capability_type,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "payload": {"type": "object"},
                },
                "required": ["query"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["summary"],
            },
            "webhook_url": f"https://example.com/{agent_id}/webhook",
            "webhook_secret": f"{agent_id}_secret_key_that_is_long_enough_for_signing",
            "team": team,
            "pricing": {"per_call_usd": round(random.uniform(0.05, 0.35), 3)},
            "sla": {"p99_latency_ms": random.choice([3000, 5000, 8000, 12000]), "availability": 0.99},
            "is_public": is_public,
        },
        expected={200},
    )


def register_a2a(api: ApiClient, org: OrgSeed) -> str:
    name = "A2A VC Specialist"
    data = api.call(
        "POST",
        "/v1/agents/register/a2a",
        headers=_auth_headers(org.api_key),
        json_body={
            "name": name,
            "description": "Cross-org A2A card for VC demo",
            "url": "https://example.com/a2a/vc-specialist",
            "capabilities": ["research", "analysis"],
            "p99_latency_ms": 7000,
            "availability": 0.995,
            "per_call_usd": 0.21,
            "is_public": True,
            "webhook_secret": "a2a_vc_specialist_secret_key_which_is_long",
        },
        expected={200},
    )
    return str(data["agent_id"])


async def seed_historical_data(
    database_url: str,
    buyer_org: OrgSeed,
    vendor_org: OrgSeed,
    compliance_org: OrgSeed,
    buyer_agents: list[str],
    vendor_agents: list[str],
    *,
    days: int,
    per_day: int,
) -> dict[str, Any]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(UTC)
    inserted_delegations = 0
    inserted_audit = 0

    async with session_factory() as session:
        org_rows = await session.execute(
            Organization.__table__.select().where(
                Organization.id.in_(
                    [
                        uuid.UUID(buyer_org.org_id),
                        uuid.UUID(vendor_org.org_id),
                        uuid.UUID(compliance_org.org_id),
                    ]
                )
            )
        )
        if len(org_rows.fetchall()) < 3:
            raise SeedError("failed to resolve all seeded organizations in DB")

        rng = random.Random(42)
        for day_offset in range(days, -1, -1):
            day_start = now - timedelta(days=day_offset)
            for idx in range(per_day):
                created_at = day_start.replace(hour=rng.randint(7, 20), minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)
                caller_agent = buyer_agents[idx % len(buyer_agents)]
                callee_agent = vendor_agents[idx % len(vendor_agents)]

                status_roll = rng.random()
                if status_roll < 0.76:
                    status = "completed"
                    decision = "allow"
                elif status_roll < 0.84:
                    status = "failed"
                    decision = "allow"
                elif status_roll < 0.9:
                    status = "timeout"
                    decision = "allow"
                else:
                    status = "blocked"
                    decision = "block"

                task = {
                    "input": {
                        "query": f"seeded-work-item-{day_offset}-{idx}",
                        "payload": {"deal_size": rng.randint(10000, 500000), "region": rng.choice(["us", "eu", "apac"])},
                    }
                }
                task_hash = sha256_json(task)
                estimated_cost = Decimal(str(round(rng.uniform(0.05, 0.5), 4)))
                actual_cost = estimated_cost if status == "completed" else Decimal("0")
                latency_ms = rng.randint(900, 12000) if status in {"completed", "failed", "timeout"} else None

                delegation_id = uuid.uuid4()
                delegation = Delegation(
                    id=delegation_id,
                    caller_org_id=uuid.UUID(buyer_org.org_id),
                    caller_agent_id=caller_agent,
                    callee_org_id=uuid.UUID(vendor_org.org_id),
                    callee_agent_id=callee_agent,
                    task=task,
                    task_hash=task_hash,
                    context_scope=["deal_metadata", "account_tier"],
                    policy_decision=decision,
                    status=status,
                    budget_cap_usd=Decimal("1.5000"),
                    estimated_cost_usd=estimated_cost,
                    actual_cost_usd=actual_cost,
                    latency_ms=latency_ms,
                    llm_tokens=rng.randint(400, 5000) if status == "completed" else None,
                    callback_url="https://example.com/callback/vc",
                    workflow=rng.choice(["sales", "procurement", "risk", "support"]),
                    delegation_depth=rng.randint(0, 2),
                    created_at=created_at,
                    completed_at=created_at + timedelta(seconds=rng.randint(3, 30)) if status in {"completed", "failed", "timeout"} else None,
                    result={"summary": "seeded result"} if status == "completed" else None,
                )
                session.add(delegation)
                await session.flush()
                inserted_delegations += 1

                session.add(
                    AuditLog(
                        delegation_id=delegation_id,
                        org_id=uuid.UUID(buyer_org.org_id),
                        event_type="delegation_initiated",
                        actor_agent_id=caller_agent,
                        target_agent_id=callee_agent,
                        details={"seeded": True, "task_hash": task_hash},
                        cost_usd=None,
                        created_at=created_at,
                    )
                )
                inserted_audit += 1

                if status == "completed":
                    session.add(
                        AuditLog(
                            delegation_id=delegation_id,
                            org_id=uuid.UUID(buyer_org.org_id),
                            event_type="delegation_completed",
                            actor_agent_id=caller_agent,
                            target_agent_id=callee_agent,
                            details={"seeded": True, "completion_mode": "seed"},
                            cost_usd=actual_cost,
                            created_at=created_at + timedelta(seconds=2),
                        )
                    )
                    inserted_audit += 1
                    session.add(
                        AuditLog(
                            delegation_id=delegation_id,
                            org_id=uuid.UUID(buyer_org.org_id),
                            event_type="marketplace_payout",
                            actor_agent_id=caller_agent,
                            target_agent_id=callee_agent,
                            details={
                                "seeded": True,
                                "gross_amount_usd": float(actual_cost),
                                "platform_fee_rate": 0.20,
                                "settled_count": 1,
                            },
                            cost_usd=actual_cost,
                            created_at=created_at + timedelta(seconds=3),
                        )
                    )
                    inserted_audit += 1
                elif status == "blocked":
                    session.add(
                        AuditLog(
                            delegation_id=delegation_id,
                            org_id=uuid.UUID(buyer_org.org_id),
                            event_type="delegation_blocked",
                            actor_agent_id=caller_agent,
                            target_agent_id=callee_agent,
                            details={"seeded": True, "reason": "policy deny"},
                            cost_usd=None,
                            created_at=created_at + timedelta(seconds=1),
                        )
                    )
                    inserted_audit += 1

                if idx % 7 == 0:
                    session.add(
                        AuditLog(
                            delegation_id=delegation_id,
                            org_id=uuid.UUID(buyer_org.org_id),
                            event_type="anomaly_detected",
                            actor_agent_id=caller_agent,
                            target_agent_id=callee_agent,
                            details={"seeded": True, "threshold": 3.0, "current_hour_spend": float(actual_cost + Decimal('2.0'))},
                            cost_usd=actual_cost,
                            created_at=created_at + timedelta(seconds=4),
                        )
                    )
                    inserted_audit += 1

        for agent_id in buyer_agents + vendor_agents:
            score_after = Decimal(str(round(rng.uniform(0.72, 0.98), 3)))
            score_before = Decimal(str(max(0.001, float(score_after) - 0.05)))
            session.add(
                TrustScoreEvent(
                    agent_id=agent_id,
                    org_id=uuid.UUID(buyer_org.org_id if agent_id in buyer_agents else vendor_org.org_id),
                    delegation_id=None,
                    score_before=score_before,
                    score_after=score_after,
                    components={
                        "success_rate": float(score_after),
                        "sla_compliance": float(score_after),
                        "cost_accuracy": float(score_after),
                        "policy_violations_inverse": float(score_after),
                    },
                )
            )

        for agent_id in buyer_agents:
            for period_type, period_date in (("daily", now.date()), ("monthly", now.date().replace(day=1))):
                await session.merge(
                    AgentBudget(
                        agent_id=agent_id,
                        org_id=uuid.UUID(buyer_org.org_id),
                        period=period_date,
                        period_type=period_type,
                        cap_usd=Decimal("999999"),
                        spent_usd=Decimal(str(round(rng.uniform(20, 250), 4))),
                    )
                )

        agent_result = await session.execute(Agent.__table__.select().where(Agent.org_id == uuid.UUID(buyer_org.org_id)))
        for row in agent_result.fetchall():
            await session.execute(
                Agent.__table__.update().where(Agent.id == row.id).values(
                    status="active",
                    trust_score=Decimal("0.910"),
                    delegation_count=120,
                )
            )

        await session.commit()

    await engine.dispose()
    return {
        "inserted_delegations": inserted_delegations,
        "inserted_audit_events": inserted_audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed enterprise VC demo data")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed-per-day", type=int, default=10)
    parser.add_argument("--owner-email", default="admin@nexra.local")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required for vc_seed_enterprise_data.py", file=sys.stderr)
        return 1

    args.results_dir.mkdir(parents=True, exist_ok=True)
    captures_base = os.getenv("NEXRA_MOCK_SINK_BASE_URL", "http://127.0.0.1:8800").rstrip("/")

    api = ApiClient(args.base_url)
    try:
        buyer = create_org(api, "VC Buyer Enterprise", "enterprise", args.owner_email)
        vendor = create_org(api, "VC Vendor Marketplace", "growth", args.owner_email)
        compliance = create_org(api, "VC Compliance Org", "enterprise", args.owner_email)

        configure_org(api, buyer, f"{captures_base}/mock/approval", f"{captures_base}/mock/notification", 6)
        configure_org(api, vendor, f"{captures_base}/mock/approval", f"{captures_base}/mock/notification", 5)
        configure_org(api, compliance, f"{captures_base}/mock/approval", f"{captures_base}/mock/notification", 4)

        create_allow_policy(api, buyer, "vc-buyer-allow")
        create_allow_policy(api, vendor, "vc-vendor-allow")
        create_allow_policy(api, compliance, "vc-compliance-allow")

        buyer_agents = [
            "buyer-sales", "buyer-ops", "buyer-risk", "buyer-finance"
        ]
        vendor_agents = [
            "vendor-research", "vendor-analytics", "vendor-execution", "vendor-support"
        ]
        compliance_agents = [
            "compliance-gdpr", "compliance-soc2", "compliance-hipaa", "compliance-audit"
        ]

        for agent_id, capability in zip(buyer_agents, ["execution", "analysis", "validation", "analysis"], strict=True):
            register_agent(api, buyer, agent_id=agent_id, capability_type=capability, team="buyer", is_public=False)

        for agent_id, capability in zip(vendor_agents, ["research", "analysis", "execution", "enrichment"], strict=True):
            register_agent(api, vendor, agent_id=agent_id, capability_type=capability, team="vendor", is_public=True)

        for agent_id, capability in zip(compliance_agents, ["validation", "analysis", "validation", "analysis"], strict=True):
            register_agent(api, compliance, agent_id=agent_id, capability_type=capability, team="compliance", is_public=False)

        a2a_agent = register_a2a(api, vendor)
        vendor_agents.append(a2a_agent)

    finally:
        api.close()

    seeded = httpx.Client(base_url=args.base_url, timeout=30.0)
    try:
        discover_resp = seeded.post(
            "/v1/capabilities/discover",
            headers={
                "Authorization": f"Bearer {buyer.api_key}",
                "X-Agent-ID": buyer_agents[0],
                "Content-Type": "application/json",
            },
            json={"query": "research and analysis", "include_cross_org": True, "limit": 5},
        )
        if discover_resp.status_code not in {200}:
            raise SeedError(f"post-seed cross-org discover failed: {discover_resp.status_code} {discover_resp.text[:300]}")
    finally:
        seeded.close()

    historical = __import__("asyncio").run(
        seed_historical_data(
            database_url,
            buyer,
            vendor,
            compliance,
            buyer_agents,
            vendor_agents,
            days=args.days,
            per_day=args.seed_per_day,
        )
    )

    profile = {
        "created_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "orgs": {
            "buyer": {"org_id": buyer.org_id, "api_key": buyer.api_key, "owner_email": buyer.owner_email, "agents": buyer_agents},
            "vendor": {"org_id": vendor.org_id, "api_key": vendor.api_key, "owner_email": vendor.owner_email, "agents": vendor_agents},
            "compliance": {"org_id": compliance.org_id, "api_key": compliance.api_key, "owner_email": compliance.owner_email, "agents": compliance_agents},
        },
        "history": historical,
    }

    out_path = args.results_dir / "vc_org_profile.json"
    out_path.write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "history": historical}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
