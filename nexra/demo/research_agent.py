"""Research Agent Demo — registers with Nexra and handles delegations.

Runs as a FastAPI server that receives webhook calls from Nexra.

Usage:
    export NEXRA_API_KEY=nx_live_...
    export NEXRA_BASE_URL=http://localhost:8000/v1
    python demo/research_agent.py
"""
import asyncio
import hashlib
import hmac
import json
import os
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, HTTPException, Request

from nexra_sdk import NexraAPIError, NexraClient

app = FastAPI(title="Research Agent")

WEBHOOK_SECRET = "whs_research_agent_secret_key_that_is_long_enough"
WEBHOOK_HELP = (
    "Run `./scripts/export_research_webhook_url.sh` after `ngrok http 8001`, then export "
    "`NEXRA_RESEARCH_WEBHOOK_URL` before starting this agent."
)


@app.post("/webhook")
async def handle_delegation(request: Request):
    """Receive delegation webhook from Nexra, process task, return result."""
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
    api_key = os.environ["NEXRA_API_KEY"]
    base_url = os.environ.get("NEXRA_BASE_URL", "http://localhost:8000/v1")
    webhook_url = os.environ.get("NEXRA_RESEARCH_WEBHOOK_URL", "").strip()

    if not webhook_url:
        raise RuntimeError(
            "NEXRA_RESEARCH_WEBHOOK_URL is required and must be HTTPS. "
            + WEBHOOK_HELP
        )

    parsed = urlparse(webhook_url)
    if parsed.scheme.lower() != "https":
        raise RuntimeError(
            "NEXRA_RESEARCH_WEBHOOK_URL must start with https://. "
            + WEBHOOK_HELP
        )

    async with NexraClient(
        api_key=api_key, agent_id="research-agent-v1", base_url=base_url
    ) as client:
        try:
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
                webhook_url=webhook_url,
                webhook_secret=WEBHOOK_SECRET,
            )
            print("[Research Agent] Registered with Nexra.")
        except NexraAPIError as exc:
            if exc.code in {"INVALID_WEBHOOK_URL", "CALLEE_WEBHOOK_FAILED"}:
                raise RuntimeError(
                    f"Research agent registration failed ({exc.code}): {exc.message}. "
                    + WEBHOOK_HELP
                ) from exc
            raise


if __name__ == "__main__":
    try:
        asyncio.run(register())
    except Exception as exc:  # noqa: BLE001
        print(f"[Research Agent] Startup failed: {exc}")
        raise SystemExit(1) from exc

    uvicorn.run(app, host="0.0.0.0", port=8001)
