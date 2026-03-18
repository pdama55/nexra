# Phase 9 — Deployment & Demo

> **TDD Sections**: §21 (Deployment — Railway MVP), §22 (48-Hour MVP Build Execution)
>
> **48-Hour Block**: Hours 39–48
>
> **Depends On**: Phase 8 (Billing + SDK) complete — full MVP functional.

---

## 1. Prerequisites

- [ ] Full delegation round-trip working locally (register → discover → delegate → complete → settle)
- [ ] All unit tests passing (T-001 through T-023)
- [ ] Docker Compose environment healthy
- [ ] nexra-py SDK functional
- [ ] Stripe test mode billing events recording

---

## 2. Objective

- Deploy MVP to Railway with PostgreSQL, Redis, and API service
- Create two demo agents (sales + research) that coordinate through Nexra
- Write a demo script that shows the full flow in 90 seconds
- Create a launch checklist for production readiness
- Verify all Definition of Done criteria from `00_MASTER_DEVELOPMENT_ORDER.md`

---

## 3. File-by-File Implementation Guide

### 3.1 `demo/sales_agent.py`

**Path**: `nexra/demo/sales_agent.py`

A simulated sales agent that discovers and hires a research agent through Nexra.

```python
"""Sales Agent Demo — discovers and hires a research agent via Nexra.

Usage:
    export NEXRA_API_KEY=nx_live_...
    export NEXRA_BASE_URL=http://localhost:8000/v1
    python demo/sales_agent.py
"""
import asyncio
import os
from nexra_sdk import NexraClient


async def main():
    api_key = os.environ["NEXRA_API_KEY"]
    base_url = os.environ.get("NEXRA_BASE_URL", "http://localhost:8000/v1")

    async with NexraClient(api_key=api_key, agent_id="sales-agent-v1", base_url=base_url) as client:
        # Step 1: Register self
        print("[Sales Agent] Registering with Nexra...")
        await client.register(
            agent_id="sales-agent-v1",
            name="Sales Agent",
            description="Enterprise B2B sales agent that qualifies leads and prepares deal proposals",
            capability_type="execution",
            input_schema={"type": "object", "required": ["company_name"], "properties": {"company_name": {"type": "string"}}},
            output_schema={"type": "object", "required": ["proposal"], "properties": {"proposal": {"type": "string"}}},
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/sales/webhook",
            webhook_secret="whs_sales_agent_secret_key_that_is_long_enough",
        )
        print("[Sales Agent] Registered successfully.")

        # Step 2: Discover research agents
        print("[Sales Agent] Discovering research agents...")
        matches = await client.discover(
            query="competitive research and market analysis for B2B SaaS companies",
            capability_type="research",
            budget_cap=0.50,
            limit=3,
        )
        print(f"[Sales Agent] Found {len(matches)} research agents:")
        for m in matches:
            print(f"  - {m.agent_id} (score: {m.match_score:.3f}, trust: {m.trust_score:.3f})")

        if not matches:
            print("[Sales Agent] No research agents found. Exiting.")
            return

        # Step 3: Delegate research task
        best = matches[0]
        print(f"\n[Sales Agent] Delegating to {best.agent_id}...")
        result = await client.delegate(
            agent_id=best.agent_id,
            task={
                "input": {
                    "company_name": "Acme Corp",
                    "focus_areas": ["pricing", "competitors", "market_size"],
                }
            },
            context_scope=["deal_metadata"],
            budget_cap=0.50,
        )

        print(f"[Sales Agent] Delegation {result.delegation_id}: {result.status}")
        if result.result:
            print(f"[Sales Agent] Research result: {result.result}")
        if result.usage:
            print(f"[Sales Agent] Cost: ${result.usage.cost_usd:.4f}, Latency: {result.usage.latency_ms}ms")


if __name__ == "__main__":
    asyncio.run(main())
```

### 3.2 `demo/research_agent.py`

**Path**: `nexra/demo/research_agent.py`

A simulated research agent that registers and handles incoming delegations.

```python
"""Research Agent Demo — registers with Nexra and handles delegations.

This agent runs as a simple FastAPI server that receives webhook calls from Nexra.

Usage:
    export NEXRA_API_KEY=nx_live_...
    export NEXRA_BASE_URL=http://localhost:8000/v1
    python demo/research_agent.py
"""
import asyncio
import os
import json
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from nexra_sdk import NexraClient

app = FastAPI(title="Research Agent")

WEBHOOK_SECRET = "whs_research_agent_secret_key_that_is_long_enough"


@app.post("/webhook")
async def handle_delegation(request: Request):
    """Receive delegation webhook from Nexra, process task, return result."""
    # Verify HMAC signature
    # IMPORTANT: Nexra signs the payload with json.dumps(sorted_keys=True, separators=(",",":"))
    # and sends it as raw bytes via content= (not json=). So request.body() IS the canonical form.
    signature = request.headers.get("X-Nexra-Signature", "")
    body = await request.body()
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    delegation_id = payload["delegation_id"]
    task = payload["task"]

    print(f"[Research Agent] Received delegation {delegation_id}")
    print(f"[Research Agent] Task: {json.dumps(task, indent=2)}")

    # Simulate research work
    company = task.get("input", {}).get("company_name", "Unknown")
    result = {
        "result": {
            "summary": f"Competitive analysis for {company}",
            "competitors": ["Competitor A", "Competitor B", "Competitor C"],
            "market_size_usd": 2_500_000_000,
            "pricing_insight": f"{company} is priced 15% above market average",
            "recommendation": "Focus on value-based pricing and enterprise features",
        },
        "usage": {
            "llm_tokens": 1250,
        },
    }

    print(f"[Research Agent] Returning result for {delegation_id}")
    return result


async def register():
    """Register the research agent with Nexra on startup."""
    api_key = os.environ["NEXRA_API_KEY"]
    base_url = os.environ.get("NEXRA_BASE_URL", "http://localhost:8000/v1")

    async with NexraClient(api_key=api_key, agent_id="research-agent-v1", base_url=base_url) as client:
        await client.register(
            agent_id="research-agent-v1",
            name="Research Agent",
            description="Performs competitive research, market analysis, and pricing intelligence for B2B SaaS companies",
            capability_type="research",
            input_schema={
                "type": "object",
                "required": ["company_name"],
                "properties": {
                    "company_name": {"type": "string"},
                    "focus_areas": {"type": "array", "items": {"type": "string"}},
                },
            },
            output_schema={
                "type": "object",
                "required": ["summary"],
                "properties": {
                    "summary": {"type": "string"},
                    "competitors": {"type": "array"},
                    "market_size_usd": {"type": "number"},
                },
            },
            pricing={"per_call_usd": 0.15},
            sla={"p99_latency_ms": 8000, "availability": 0.99},
            # HTTPS-only: use an ngrok/tunnel URL or trusted local TLS endpoint.
            # Helper:
            #   ngrok http 8001
            #   eval "$(./scripts/export_research_webhook_url.sh)"
            webhook_url=os.environ["NEXRA_RESEARCH_WEBHOOK_URL"],
            webhook_secret=WEBHOOK_SECRET,
        )
        print("[Research Agent] Registered with Nexra.")


if __name__ == "__main__":
    asyncio.run(register())
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 3.3 `demo/README.md`

**Path**: `nexra/demo/README.md`

```markdown
# Nexra Demo — Sales + Research Agent Coordination

## What This Demonstrates

Two AI agents (Sales and Research) coordinate through Nexra with zero hardcoded connections:

1. **Research Agent** registers its capability ("competitive research") with Nexra
2. **Sales Agent** discovers research agents via semantic search
3. **Sales Agent** delegates a research task through Nexra's governance layer
4. Nexra evaluates policy → checks budget → signs webhook → delivers to Research Agent
5. **Research Agent** returns results through Nexra
6. **Sales Agent** receives the research report

## Setup

```bash
# Terminal 1: Start Nexra
cd nexra && docker compose -f docker/docker-compose.yml up

# Terminal 2: Run migrations + create org
cd nexra && alembic upgrade head

# Create an org and get the API key (returned ONCE — save it!)
curl -X POST http://localhost:8000/v1/orgs/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Org", "plan": "growth"}'
# Response: { "data": { "org_id": "...", "api_key": "nx_live_..." } }
# SAVE the api_key — it is shown only once

# Terminal 3: Start Research Agent
ngrok http 8001
eval "$(./scripts/export_research_webhook_url.sh)"
export NEXRA_API_KEY=nx_live_...
export NEXRA_BASE_URL=http://localhost:8000/v1
python demo/research_agent.py

# Terminal 4: Run Sales Agent
export NEXRA_API_KEY=nx_live_...
export NEXRA_BASE_URL=http://localhost:8000/v1
python demo/sales_agent.py
```

## Expected Output

```
[Sales Agent] Registering with Nexra...
[Sales Agent] Registered successfully.
[Sales Agent] Discovering research agents...
[Sales Agent] Found 1 research agents:
  - research-agent-v1 (score: 0.923, trust: 1.000)
[Sales Agent] Delegating to research-agent-v1...
[Research Agent] Received delegation abc123
[Research Agent] Returning result for abc123
[Sales Agent] Delegation abc123: completed
[Sales Agent] Research result: {summary: "Competitive analysis for Acme Corp", ...}
[Sales Agent] Cost: $0.1500, Latency: 342ms
```
```

---

## 4. Railway Deployment

### 4.1 Railway Configuration

The `railway.toml` was created in Phase 1. Deployment steps:

1. **Create Railway project** with 3 services: API, PostgreSQL, Redis
2. **Set environment variables** in Railway dashboard (all from `.env.example`)
3. **Deploy** via `railway up` or GitHub integration
4. **Run migrations** via Railway CLI: `railway run alembic upgrade head`

### 4.2 Production Dockerfile Verification

Verify the Phase 1 Dockerfile works for Railway:

```bash
# Build and test locally
docker build -f docker/Dockerfile -t nexra-api .
docker run --env-file .env -p 8000:8000 nexra-api

# Verify health
curl http://localhost:8000/health
```

### 4.3 Railway Environment Variables

Set these in Railway dashboard:

```
DATABASE_URL=postgresql+asyncpg://<railway-provided>
REDIS_URL=redis://<railway-provided>
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_DELEGATION_METER_ID=mtr_...
SECRET_KEY_ENCRYPTION_KEY=<64-hex-chars>
ENVIRONMENT=production
LOG_LEVEL=WARNING
SENTRY_DSN=https://...@sentry.io/...
```

---

## 5. Launch Checklist

Before declaring MVP complete, verify every item:

### Infrastructure
- [ ] Railway API service is running and healthy
- [ ] Railway PostgreSQL is provisioned and connected
- [ ] Railway Redis is provisioned and connected
- [ ] `/health` returns 200 with all components healthy
- [ ] Sentry is receiving error events (trigger a test error)

### Functionality
- [ ] POST /agents/register creates agent with embedding
- [ ] POST /capabilities/discover returns ranked results
- [ ] POST /policies creates YAML-based policy
- [ ] POST /delegate executes full 13-step flow
- [ ] Policy block returns 403 with policy_id
- [ ] Budget exceeded returns 402 with remaining_budget_usd
- [ ] Schema validation failure returns 422
- [ ] Audit log contains entries for every delegation
- [ ] UPDATE/DELETE on audit_log raises exception
- [ ] Stripe usage event fires after settlement
- [ ] nexra-py SDK `hire()` completes full round-trip

### Demo
- [ ] Research agent registers and handles webhooks
- [ ] Sales agent discovers and delegates through Nexra
- [ ] Policy change (allow → block) takes effect immediately
- [ ] Demo runs in under 90 seconds

### Security
- [ ] API keys are bcrypt hashed (no plaintext in DB)
- [ ] JWT secrets are AES-256-GCM encrypted
- [ ] HMAC signatures verified on webhooks
- [ ] Rate limiting active (test with burst requests)
- [ ] /docs disabled in production

### Tests
- [ ] All unit tests pass (T-001 through T-023)
- [ ] 80%+ line coverage on service layer

---

## 6. Guardrails

1. **DO NOT** deploy with `ENVIRONMENT=development` in production.
2. **DO NOT** leave `/docs` enabled in production (already disabled via config).
3. **DO NOT** use test Stripe keys in production.
4. **DO NOT** commit `.env` to git.
5. **DO NOT** skip the migration step on Railway.

---

## 7. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-DEPLOY-001 | Deploy | Railway health check passes | /health returns 200 |
| T-DEPLOY-002 | Deploy | Migrations run on Railway | alembic upgrade head succeeds |
| T-DEMO-001 | Demo | Research agent registers | Agent in DB with embedding |
| T-DEMO-002 | Demo | Sales agent discovers research agent | matches array non-empty |
| T-DEMO-003 | Demo | Full delegation round-trip | status=='completed', result present |
| T-DEMO-004 | Demo | Policy block takes effect immediately | Change policy → next delegation blocked |
| T-023 | E2E | Full round-trip: register → discover → delegate → complete → settle | All audit entries, budget updated, Stripe event |
