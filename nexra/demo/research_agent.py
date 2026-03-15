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

import uvicorn
from fastapi import FastAPI, HTTPException, Request

from nexra_sdk import NexraClient

app = FastAPI(title="Research Agent")

WEBHOOK_SECRET = "whs_research_agent_secret_key_that_is_long_enough"


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

    async with NexraClient(
        api_key=api_key, agent_id="research-agent-v1", base_url=base_url
    ) as client:
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
            webhook_url=os.environ.get(
                "NEXRA_RESEARCH_WEBHOOK_URL", "https://localhost:8001/webhook"
            ),
            webhook_secret=WEBHOOK_SECRET,
        )
        print("[Research Agent] Registered with Nexra.")


if __name__ == "__main__":
    asyncio.run(register())
    uvicorn.run(app, host="0.0.0.0", port=8001)
