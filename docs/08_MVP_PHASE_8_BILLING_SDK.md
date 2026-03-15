# Phase 8 — Stripe Billing & Python SDK

> **TDD Sections**: §16 (Stripe Billing Integration), §17.1 (nexra-py SDK)
>
> **48-Hour Block**: Hours 35–39
>
> **Depends On**: Phase 7 (Budget + Audit) complete.

---

## 1. Prerequisites

- [ ] Full delegation flow working end-to-end
- [ ] BudgetService settle() updating spent_usd
- [ ] AuditService logging all delegation events
- [ ] Stripe account with test mode API keys
- [ ] Stripe Meter created for delegation usage

---

## 2. Objective

- BillingService: record Stripe Meter Events per delegation, Stripe Connect payout stub
- Celery app skeleton with billing worker
- nexra-py SDK: NexraClient with register(), discover(), delegate(), hire()
- SDK published as a local package with pyproject.toml and README

---

## 3. File-by-File Implementation Guide

### 3.1 `services/billing_service.py`

**Path**: `nexra/services/billing_service.py`

```python
import logging
import stripe
from models.organization import Organization
from models.delegation import Delegation
from core.config import get_settings

logger = logging.getLogger("nexra.services.billing")


class BillingService:
    """Stripe billing integration.

    Records usage events via Stripe Metering API after each delegation.
    Handles cross-org payouts via Stripe Connect (stub for MVP).
    """

    def __init__(self) -> None:
        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key
        self.meter_id = settings.stripe_delegation_meter_id

    async def record_delegation_usage(
        self,
        org: Organization,
        delegation: Delegation,
        actual_cost_usd: float,
    ) -> None:
        """Record a usage event with Stripe Metering API.

        Called after delegation settlement. Fire-and-forget — billing
        failures should not block the delegation response.
        """
        if not org.stripe_id:
            logger.warning(f"Org {org.id} has no stripe_id — skipping billing")
            return

        try:
            stripe.billing.MeterEvent.create(
                event_name="nexra_delegation",
                payload={
                    "stripe_customer_id": org.stripe_id,
                    "value": "1",
                },
                timestamp=int(delegation.created_at.timestamp()),
            )
            logger.info(f"Stripe usage event recorded for delegation {delegation.id}")
        except stripe.StripeError as e:
            logger.error(f"Stripe billing error for delegation {delegation.id}: {e}")
            # Do NOT raise — billing failures should not block delegation

    async def trigger_connect_payout(
        self,
        callee_org: Organization,
        amount_usd: float,
        delegation: Delegation,
    ) -> None:
        """Stripe Connect transfer for cross-org delegation revenue.

        Stub for MVP — full implementation in P2 (Phase 13).
        """
        logger.info(
            f"Connect payout stub: ${amount_usd:.4f} to org {callee_org.id} "
            f"for delegation {delegation.id}"
        )
```

### 3.2 `workers/celery_app.py`

**Path**: `nexra/workers/celery_app.py`

```python
from celery import Celery
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "nexra",
    broker=settings.celery_broker,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "workers.billing_worker.*": {"queue": "billing"},
        "workers.webhook_worker.*": {"queue": "webhooks"},
        "workers.anomaly_worker.*": {"queue": "anomaly"},
    },
    beat_schedule={
        # Anomaly detection runs hourly (added in Phase 10)
    },
)
```

### 3.3 `workers/billing_worker.py`

**Path**: `nexra/workers/billing_worker.py`

```python
import logging
import stripe
from workers.celery_app import celery_app
from core.config import get_settings

logger = logging.getLogger("nexra.workers.billing")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def record_stripe_usage(self, stripe_customer_id: str, delegation_id: str, timestamp: int):
    """Background task to record Stripe meter event.

    Retries up to 3 times with 5s delay on failure.
    """
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    try:
        stripe.billing.MeterEvent.create(
            event_name="nexra_delegation",
            payload={
                "stripe_customer_id": stripe_customer_id,
                "value": "1",
            },
            timestamp=timestamp,
        )
        logger.info(f"Stripe usage recorded for delegation {delegation_id}")
    except stripe.StripeError as exc:
        logger.error(f"Stripe error: {exc}")
        raise self.retry(exc=exc)
```

### 3.4 nexra-py SDK

**Directory**: `nexra/sdk/nexra-py/`

#### `sdk/nexra-py/pyproject.toml`

```toml
[tool.poetry]
name = "nexra"
version = "0.1.0"
description = "Python SDK for Nexra — the control plane for AI agent networks"
authors = ["Parth"]
readme = "README.md"
packages = [{ include = "nexra" }]

[tool.poetry.dependencies]
python = "^3.10"
httpx = "^0.28"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

#### `sdk/nexra-py/nexra/__init__.py`

```python
from nexra.client import NexraClient
from nexra.types import RegisterResult, AgentMatch, DelegationResult

__all__ = ["NexraClient", "RegisterResult", "AgentMatch", "DelegationResult"]
```

#### `sdk/nexra-py/nexra/types.py`

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisterResult:
    agent_id: str
    status: str
    embedding_id: str | None = None
    registered_at: str = ""


@dataclass
class AgentMatch:
    agent_id: str
    name: str
    match_score: float
    trust_score: float
    status: str
    pricing: dict = field(default_factory=dict)
    sla: dict = field(default_factory=dict)
    is_cross_org: bool = False
    capability_type: str = ""


@dataclass
class PolicyResult:
    policy_id: str | None = None
    policy_version: int | None = None
    decision: str = ""


@dataclass
class Usage:
    cost_usd: float = 0.0
    latency_ms: int = 0
    llm_tokens: int | None = None


@dataclass
class DelegationResult:
    delegation_id: str
    status: str
    policy_result: PolicyResult | None = None
    result: Any = None
    usage: Usage | None = None
    poll_url: str | None = None
```

#### `sdk/nexra-py/nexra/client.py`

```python
import httpx
from typing import Any
from nexra.types import RegisterResult, AgentMatch, DelegationResult, PolicyResult, Usage


class NexraClient:
    """Nexra Python SDK client.

    Usage:
        async with NexraClient(api_key='nx_live_...', agent_id='my-agent') as client:
            result = await client.hire(capability='research', task={'company_name': 'Acme'})
    """

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://api.usenexra.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Agent-ID": agent_id,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(headers=self._headers, timeout=timeout)

    async def register(self, **kwargs) -> RegisterResult:
        """Register an agent capability."""
        resp = await self._client.post(f"{self.base_url}/agents/register", json=kwargs)
        resp.raise_for_status()
        data = resp.json()["data"]
        return RegisterResult(**data)

    async def discover(
        self,
        query: str,
        capability_type: str | None = None,
        budget_cap: float | None = None,
        max_latency_ms: int | None = None,
        limit: int = 5,
    ) -> list[AgentMatch]:
        """Discover agent capabilities via semantic search."""
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if capability_type:
            payload["capability_type"] = capability_type
        if budget_cap:
            payload["budget_cap_usd"] = budget_cap
        if max_latency_ms:
            payload["max_latency_ms"] = max_latency_ms

        resp = await self._client.post(f"{self.base_url}/capabilities/discover", json=payload)
        resp.raise_for_status()
        return [AgentMatch(**m) for m in resp.json()["data"]["matches"]]

    async def delegate(
        self,
        agent_id: str,
        task: dict,
        context_scope: list[str] | None = None,
        budget_cap: float = 1.0,
        timeout_ms: int = 30000,
        callback_url: str | None = None,
    ) -> DelegationResult:
        """Delegate a task to a specific agent."""
        resp = await self._client.post(
            f"{self.base_url}/delegate",
            json={
                "callee_agent_id": agent_id,
                "task": task,
                "context_scope": context_scope or [],
                "budget_cap_usd": budget_cap,
                "timeout_ms": timeout_ms,
                "callback_url": callback_url,
            },
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return self._parse_delegation_result(data)

    async def hire(
        self,
        capability: str,
        task: dict,
        context_scope: list[str] | None = None,
        budget_cap: float = 1.0,
    ) -> DelegationResult:
        """Convenience: discover + delegate in one call.

        Finds the best matching agent for the capability and delegates the task.
        """
        matches = await self.discover(capability, budget_cap=budget_cap, limit=1)
        if not matches:
            raise ValueError(f"No agents found for capability: {capability}")
        return await self.delegate(
            agent_id=matches[0].agent_id,
            task=task,
            context_scope=context_scope,
            budget_cap=budget_cap,
        )

    async def get_delegation(self, delegation_id: str) -> DelegationResult:
        """Poll delegation status."""
        resp = await self._client.get(f"{self.base_url}/delegations/{delegation_id}")
        resp.raise_for_status()
        return self._parse_delegation_result(resp.json()["data"])

    def _parse_delegation_result(self, data: dict) -> DelegationResult:
        policy = None
        if data.get("policy_result"):
            policy = PolicyResult(**data["policy_result"])
        usage = None
        if data.get("usage"):
            usage = Usage(**data["usage"])
        return DelegationResult(
            delegation_id=data["delegation_id"],
            status=data["status"],
            policy_result=policy,
            result=data.get("result"),
            usage=usage,
            poll_url=data.get("poll_url"),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._client.aclose()
```

#### `sdk/nexra-py/README.md`

```markdown
# nexra-py

Python SDK for [Nexra](https://usenexra.com) — the control plane for AI agent networks.

## Installation

```bash
pip install nexra
```

## Quick Start

```python
from nexra import NexraClient

async with NexraClient(api_key="nx_live_...", agent_id="sales-agent-v1") as client:
    # Discover + delegate in one call
    result = await client.hire(
        capability="research",
        task={"company_name": "Acme Corp", "focus_areas": ["pricing"]},
        context_scope=["deal_metadata"],
        budget_cap=0.25,
    )
    print(result.result)
```

## API Reference

### `NexraClient(api_key, agent_id, base_url, timeout)`

- `register(**kwargs)` — Register an agent capability
- `discover(query, capability_type, budget_cap, max_latency_ms, limit)` — Semantic discovery
- `delegate(agent_id, task, context_scope, budget_cap, timeout_ms, callback_url)` — Delegate to specific agent
- `hire(capability, task, context_scope, budget_cap)` — Discover + delegate in one call
- `get_delegation(delegation_id)` — Poll delegation status
```

---

## 4. Integration with Delegation Flow

Wire BillingService into the delegation settlement step:

After `BudgetService.settle()` in Step 13 of the delegation flow, call:
```python
billing_service = BillingService()
await billing_service.record_delegation_usage(org, delegation, actual_cost)
```

For production, queue this as a Celery task instead of calling inline:
```python
from workers.billing_worker import record_stripe_usage
record_stripe_usage.delay(org.stripe_id, str(delegation.id), int(delegation.created_at.timestamp()))
```

---

## 5. Guardrails

1. **DO NOT** let Stripe billing failures block the delegation response. Billing is fire-and-forget.
2. **DO NOT** hardcode Stripe API keys. Always use `get_settings().stripe_secret_key`.
3. **DO NOT** expose the SDK's internal httpx client. Users interact only through NexraClient methods.
4. **DO NOT** include `api_key` in any SDK error messages or logs.
5. **DO NOT** use synchronous httpx in the SDK. All methods are async.

---

## 6. Test Cases

| Test ID | Category | Description | Mock Setup | Assertion |
|---------|----------|-------------|------------|-----------|
| T-BILL-001 | Billing | Usage event recorded after delegation | Mock stripe.billing.MeterEvent.create | Called once with correct params |
| T-BILL-002 | Billing | Stripe error does not raise | Mock Stripe → raise StripeError | No exception propagated |
| T-BILL-003 | Billing | No stripe_id → skip billing | Org without stripe_id | No Stripe call made |
| T-SDK-001 | SDK | register() sends correct payload | Mock httpx | POST to /agents/register with all fields |
| T-SDK-002 | SDK | discover() returns AgentMatch list | Mock httpx | List of AgentMatch objects |
| T-SDK-003 | SDK | delegate() sends correct payload | Mock httpx | POST to /delegate with all fields |
| T-SDK-004 | SDK | hire() calls discover then delegate | Mock httpx | Two HTTP calls made |
| T-SDK-005 | SDK | hire() with no matches raises ValueError | Mock discover → empty | ValueError raised |
| T-SDK-006 | SDK | Context manager closes client | Use async with | aclose() called |
