# nexra-sdk

Python SDK for [Nexra](https://usenexra.com) — the control plane for AI agent networks.

## Installation

```bash
pip install nexra-sdk
```

## Quick Start

```python
from nexra_sdk import NexraClient

async with NexraClient(api_key="nx_live_...", agent_id="sales-agent-v1") as client:
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
