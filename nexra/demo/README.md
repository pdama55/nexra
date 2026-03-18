# Nexra Demo — Sales + Research Agent Coordination

## What This Demonstrates

Two AI agents (Sales and Research) coordinate through Nexra with zero hardcoded connections:

1. **Research Agent** registers its capability ("competitive research") with Nexra
2. **Sales Agent** discovers research agents via semantic search
3. **Sales Agent** delegates a research task through Nexra's governance layer
4. Nexra evaluates policy, checks budget, signs webhook, delivers to Research Agent
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

# Terminal 3: Start Research Agent
# Requires HTTPS webhook URL (ngrok or trusted local TLS)
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

`NEXRA_RESEARCH_WEBHOOK_URL` must be HTTPS. HTTP webhook endpoints are rejected by Nexra.

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
