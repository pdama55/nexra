# nexra-sdk

Python SDK for [Nexra](https://usenexra.com) — the control plane for AI agent networks.

## Installation

`nexra-sdk` is not currently published on public PyPI.

Install from source (current recommended path):

```bash
pip install /absolute/path/to/nexra/sdk/nexra-py
```

If your organization publishes internal packages, install from your private index:

```bash
pip install --index-url https://<your-index>/simple nexra-sdk
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
- `register_a2a(**agent_card)` — Register an A2A agent card
- `discover(query, capability_type, budget_cap, max_latency_ms, limit)` — Semantic discovery
- `delegate(agent_id, task, context_scope, budget_cap, timeout_ms, callback_url)` — Delegate to specific agent
- `hire(capability, task, context_scope, budget_cap)` — Discover + delegate in one call
- `get_delegation(delegation_id)` — Poll delegation status
