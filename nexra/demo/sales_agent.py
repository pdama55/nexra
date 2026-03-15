"""Sales Agent Demo — discovers and hires a research agent via Nexra.

Usage:
    export NEXRA_API_KEY=nx_live_...
    export NEXRA_BASE_URL=http://localhost:8000/v1
    python demo/sales_agent.py
"""
import asyncio
import json
import os

from nexra_sdk import NexraClient


async def main():
    api_key = os.environ["NEXRA_API_KEY"]
    base_url = os.environ.get("NEXRA_BASE_URL", "http://localhost:8000/v1")

    async with NexraClient(
        api_key=api_key, agent_id="sales-agent-v1", base_url=base_url
    ) as client:
        print("[Sales Agent] Registering with Nexra...")
        await client.register(
            agent_id="sales-agent-v1",
            name="Sales Agent",
            description="Enterprise B2B sales agent that qualifies leads and prepares deal proposals",
            capability_type="execution",
            input_schema={
                "type": "object",
                "required": ["company_name"],
                "properties": {"company_name": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["proposal"],
                "properties": {"proposal": {"type": "string"}},
            },
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/sales/webhook",
            webhook_secret="whs_sales_agent_secret_key_that_is_long_enough",
        )
        print("[Sales Agent] Registered successfully.")

        print("[Sales Agent] Discovering research agents...")
        matches = await client.discover(
            query="competitive research and market analysis for B2B SaaS companies",
            capability_type="research",
            budget_cap=0.50,
            limit=3,
        )
        print(f"[Sales Agent] Found {len(matches)} research agents:")
        for m in matches:
            print(
                f"  - {m.agent_id} (score: {m.match_score:.3f}, trust: {m.trust_score:.3f})"
            )

        if not matches:
            print("[Sales Agent] No research agents found. Exiting.")
            return

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
            print(f"[Sales Agent] Research result: {json.dumps(result.result, indent=2)}")
        if result.usage:
            print(
                f"[Sales Agent] Cost: ${result.usage.cost_usd:.4f}, "
                f"Latency: {result.usage.latency_ms}ms"
            )


if __name__ == "__main__":
    asyncio.run(main())
