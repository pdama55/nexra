**PRODUCT REQUIREMENTS DOCUMENT**

**Nexra**

_The control plane for AI agent networks._

Governance, policy, and observability that makes multi-agent systems safe to run in production.

| Website | **usenexra.com**                    |
| ------- | ----------------------------------- |
| Version | v_final (TDD-ready)                 |
| Date    | March 2026                          |
| Author  | Parth                               |
| Stage   | Pre-seed / Active build             |
| Status  | Final - no further edits before TDD |

Contents: §1 What Nexra Is · §2 The Problem · §3 Solution Overview · §4 Protocol Context (A2A/MCP) · §5 How It Works · §6 Feature Set · §7 API Specifications · §8 Data Model · §9 Auth & Security · §10 Technical Architecture · §11 Market · §12 ICP · §13 Competitive Landscape · §14 Pricing · §15 AWS Marketplace · §16 48-Hour MVP · §17 GTM · §18 Risks · §19 Milestones · §20 Why Now / Why You

# **§1 - What Nexra Is (Read This First)**

This section exists to eliminate any ambiguity about what Nexra is, what it is not, and why it is framed the way it is. All subsequent sections - including technical specs, API design, data model, GTM, and pricing - follow from these definitions. If a developer reads nothing else before writing code, they read this section.

**Nexra is the control plane for AI agent networks. It sits above the framework and protocol layers - LangGraph, CrewAI, A2A, MCP - and wraps any multi-agent system with a policy engine, spend metering, an immutable audit trail, and circuit breakers. It includes a coordination primitive (agents discover and delegate to other agents at runtime) and a governance layer (that makes that coordination enterprise-safe).**

**The two-layer model - coordination + governance**

Nexra has two layers that are inseparable. They ship together. They are not separate products. This distinction matters for product scope and for how we explain the product to different audiences.

| **Layer**          | **What it does**                                                                                                                                                                                                   | **Why it exists**                                                                                                                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Coordination layer | Agents register capabilities. Agents discover each other at runtime. Agents delegate tasks with scoped context. Agents settle payment automatically. No hardcoded connections required.                            | Without this, agents can't find or hire each other. Every cross-agent interaction requires an engineer to pre-wire it. This is the core product primitive.                        |
| Governance layer   | Policy engine evaluates every delegation. Spend caps enforced per agent. Immutable audit log captures every action. Circuit breakers isolate misbehaving agents. Human-in-the-loop gates for high-risk operations. | Without this, the coordination layer is a liability in enterprise. Agents can delegate to anyone, spend unlimited budget, and leave no record. Compliance teams block deployment. |

The coordination layer is the beating heart of the product. The governance layer is what makes it sellable to companies that have a CISO, a CFO, and an audit requirement. Both ship from day one. Neither works without the other.

**Why the product is framed as a 'control plane' not a 'coordination protocol'**

_Critical context for developers and anyone writing about this product: Google's A2A protocol (open source, free, Linux Foundation governance, 100+ enterprise partners including Anthropic, OpenAI, AWS, Microsoft) already handles agent discovery and task delegation as an open standard. Building Nexra purely as a 'coordination protocol' would mean competing directly with something free. The defensible, fundable product is the hosted, governed, enterprise-ready control plane that includes coordination - not a raw protocol that competes with A2A._

This does NOT mean Nexra abandons the coordination primitive. The six-step flow where agents discover, delegate, execute, settle, and audit is still the core product mechanic. What changed is the framing and the moat: Nexra is positioned as the hosted opinionated implementation of coordination PLUS the governance layer that A2A explicitly does not provide. Same product. Broader, more defensible story.

Analogy: A2A and MCP are the HTTP of agent networks - free, open, ubiquitous. Nexra is Cloudflare - the control plane that makes the protocol safe, observable, and policy-enforced at enterprise scale.

**What Nexra is NOT - hard boundaries for development scope**

These are not edge cases. These are scope decisions that every developer and contributor needs to understand. Building any of the following is out of scope for v1 and v2.

- NOT a communication protocol competing with A2A or MCP - Nexra is built on top of them, not against them
- NOT an agent execution runtime - Nexra does not run, host, or manage agent processes
- NOT a model provider - completely model-agnostic; Claude, GPT-4, Gemini, local models all work
- NOT an orchestration framework - complements LangGraph and CrewAI, does not replace them
- NOT blockchain-based - pure Stripe billing, no crypto settlement in any version
- NOT an agent builder or no-code agent tool - Nexra is the connective tissue for agents that already exist
- NOT only for companies using A2A - works with any agent that can receive a signed HTTP webhook
- NOT a monitoring tool - governance (policies, spend caps) is different from observability (logging, alerting); Nexra is the former with audit logging as a feature
- NOT a cloud provider or infrastructure layer - Nexra is application-layer software that runs on top of standard cloud infrastructure

# **§2 - The Problem**

**PROBLEM 1 - THE COORDINATION WALL (ACUTE TODAY, AFFECTS ANY MULTI-AGENT SETUP)**

Every company deploying more than two or three agents in production hits the same wall. Agents are isolated. Every cross-agent interaction requires an engineer to hardcode the connection before it can happen. The agent network becomes rigid - you can't add new capabilities without rewriting orchestration logic. What was supposed to be flexible AI infrastructure becomes a tangled static graph.

| **Pain point**               | **Detail**                                                                                                                                                                                                                                                            |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No runtime discovery         | Every agent connection is pre-wired at build time or it doesn't exist. A sales agent cannot find a research agent unless an engineer explicitly configured that connection in advance. Adding a third agent means updating every agent that might want to talk to it. |
| No delegation standard       | No agreed-upon mechanism for one agent to hand a task to another with explicit context, budget, and timeout constraints. Today this requires custom code per agent pair.                                                                                              |
| N² integration complexity    | Each new agent requires N new manual integrations with existing agents. A network of 10 agents has up to 90 potential directional connections, all of which must be maintained manually.                                                                              |
| 20-40% engineering time lost | In organizations with 5+ agents in production, 20-40% of AI engineering time goes to orchestration glue code - wiring agents together rather than making them better.                                                                                                 |
| Framework lock-in            | A LangGraph agent cannot dynamically hire a CrewAI agent. A Bedrock agent cannot hire a custom Python agent. Cross-framework coordination is not possible without a shared layer.                                                                                     |
| No trust or reputation layer | When agents can hire other agents, there's no way to know if a given agent is reliable, accurate, or cost-effective. Every hire is blind.                                                                                                                             |

**PROBLEM 2 - THE GOVERNANCE VACUUM (BLOCKS ENTERPRISE DEPLOYMENT)**

A2A and MCP solved the protocol layer. That created a more dangerous second-order problem: enterprises are deploying agent networks with zero controls over what those agents are allowed to do. The protocol works. The agents can talk. But there's nothing governing what they say to each other, what they're allowed to spend, or what they're allowed to do with data.

| **Governance gap**          | **Detail**                                                                                                                                                                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No policy engine            | Agents can delegate to any other agent with no authorization model. There's no concept of 'the sales agent is allowed to hire the research agent but not the payments agent.' All-or-nothing access.       |
| No spend controls           | Agents can spawn sub-agents, each incurring LLM token costs, API call costs, and service fees. No cap. No meter. A runaway agent loop can spend thousands of dollars before anyone notices.                |
| No audit trail              | When an agent takes a costly or incorrect action, there is no standard way to reconstruct what happened - which agent initiated what, what policy was applied, what context was passed, what was returned. |
| No circuit breakers         | A misbehaving agent (wrong output, high failure rate, latency spike) can cascade failures through the entire network with no isolation mechanism.                                                          |
| No compliance posture       | Finance, healthcare, and legal teams are blocking agent deployment until they can demonstrate a record of what agents did and how decisions were made. No existing tool provides this for agent networks.  |
| No typed schema enforcement | A2A Agent Cards describe capabilities in natural language. There's no schema validation layer ensuring agents actually receive and return what was agreed. Silent failures are common.                     |

_Real incident (Replit, July 2025): An AI agent deleted a production database containing 1,200+ records despite explicit 'code and action freeze' instructions from the user. The agent interpreted its task scope too broadly and took irreversible action. Proper authorization scopes and a policy engine enforcing action boundaries at the network layer would have prevented this. This pattern - agents with too much autonomy and no controls - is the default state of most production agent deployments today._

| **MULTI-AGENT INQUIRY SURGE**<br><br>**+1,445%**<br><br>Gartner, Q1 2024 to Q2 2025                       |     | **ENG TIME ON GLUE CODE**<br><br>**20-40%**<br><br>In orgs with 5+ agents in production              |
| --------------------------------------------------------------------------------------------------------- | --- | ---------------------------------------------------------------------------------------------------- |
|                                                                                                           |
| **ENTERPRISES SCALED TO PRODUCTION**<br><br>**23%**<br><br>McKinsey State of AI - most stuck in pilot     |     | **ENTERPRISE APPS WITH AGENTS BY END 2026**<br><br>**40%**<br><br>Gartner (up from <5% in 2025)      |
|                                                                                                           |
| **AI PROJECTS CANCELLED BY 2027**<br><br>**40%**<br><br>Due to uncontrolled cost and complexity - Gartner |     | **MCP SERVERS WITHOUT AUTH**<br><br>**~2,000**<br><br>Exposed with no authentication - Knostic, 2025 |

# **§3 - Solution Overview**

**Nexra solves both problems simultaneously. The coordination layer eliminates the wiring problem. The governance layer eliminates the control problem. Both are required for enterprise adoption. Neither is sufficient alone.**

**What Nexra delivers per stakeholder**

| **Stakeholder**     | **What Nexra delivers**                                                                                                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Head of AI / ML Eng | Runtime agent discovery and delegation - no more hardcoded connections. Any new agent added to the registry is immediately discoverable by all existing agents. Integration in under an hour via SDK. |
| CTO                 | Observable, cost-controlled, policy-enforced agent network without replacing any existing infrastructure. Works with whatever frameworks the team already uses.                                       |
| CISO                | Immutable record of every agent action, every delegation, every policy decision. Context scoping enforced at API layer - agents cannot access data outside their explicit grants. SOC 2 roadmap.      |
| CFO / VP Finance    | Per-agent, per-workflow cost metering. Budget caps enforced automatically. Monthly CFO-readable reports on AI spend by team, agent type, and workflow. No more surprise AI bills.                     |
| Compliance / Legal  | Audit trail structured for regulators. One-click compliance report exports (SOC 2, GDPR, HIPAA). Human-in-the-loop gates for high-risk operations. Policy engine documents the rules agents follow.   |
| Investor / Board    | A2A and MCP solved the protocol layer. Nexra is Cloudflare for agent networks - the governance and control plane that makes the free open protocols safe to run at enterprise scale.                  |

# **§4 - Protocol Context: A2A and MCP**

This section explains the exact relationship between Nexra and the two major open protocols in the agent space. Every developer working on Nexra must understand this before writing any integration code.

**THE AGENT PROTOCOL STACK**

| **Layer**           | **Technology**                                     | **Status**                                                                 | **Nexra's relationship**                                                                                                                                                                                |
| ------------------- | -------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent execution     | LangGraph, CrewAI, AutoGen, Bedrock Agents, custom | Production-ready, widely deployed by Nexra's ICP today                     | Nexra governs the network they form. Does NOT replace these. First-class integration targets.                                                                                                           |
| Tool connectivity   | MCP (Anthropic → Linux Foundation)                 | Free, open, 97M monthly SDK downloads, widely deployed                     | Nexra is MCP-compatible. Policy can govern MCP tool calls. Nexra exposed as MCP server so MCP-native agents can use governance without code changes.                                                    |
| Agent communication | A2A (Google → Linux Foundation)                    | Free, open, 100+ enterprise partners. NOT yet adopted at Series A-C level. | Nexra is A2A-compatible natively. A2A agents can register without SDK changes. But Nexra does NOT require A2A - works with webhook-capable agents of any type.                                          |
| **Nexra**           | **usenexra.com**                                   | Pre-seed, building now                                                     | **THE PRODUCT. Sits above all layers. Provides registry, discovery, delegation, policy engine, spend metering, audit log, circuit breakers, trust scores. Works with any agent framework or protocol.** |

**WHAT A2A DOES NOT PROVIDE - NEXRA'S EXACT WHITESPACE**

A2A handles agent-to-agent communication as an open protocol. It deliberately does not implement governance or business logic on top of that communication. The following gaps are Nexra's product surface. Every feature Nexra builds maps to one of these.

- No policy engine - who can delegate to whom under what conditions; A2A has no auth model for delegations
- No spend controls - A2A has no concept of budget caps, cost metering, or per-agent spend limits
- No audit log standard - A2A defines message format but not how to record, store, or query what happened
- No circuit breakers - A2A has no mechanism to isolate misbehaving agents or limit delegation chain depth
- No human-in-the-loop gates - A2A has no pause-for-approval pattern built in
- No trust scores - A2A has no reputation or reliability mechanism for agents
- No typed schema enforcement - A2A Agent Cards are natural language descriptions, not machine-validated schemas
- No cross-org billing - A2A defines no payment model; agents can't charge each other using A2A alone

**A2A ADOPTION REALITY - WHY THIS MATTERS FOR DEVELOPMENT PRIORITY**

A2A adoption is currently concentrated in large enterprises: Adobe, S&P Global, Tyson Foods, ServiceNow, Twilio, Gordon Food Service. Only approximately 35% of AI-focused enterprises are actively exploring A2A integration - and that is exploring, not deploying. A2A is listed as 'coming soon' on Azure AI Foundry and Microsoft Copilot Studio.

Nexra's ICP - Series A-C SaaS companies with 5-10 agents in production - is using LangGraph, CrewAI, or custom agent frameworks today. Not A2A. This is a critical product decision:

- Nexra must solve the coordination and governance problem for companies using LangGraph and CrewAI today - this is the primary integration surface
- A2A compatibility is a v1 feature and a future hedge, not the primary integration surface for the first 20 customers
- Primary pitch: 'Nexra works with the frameworks you already use and adds governance.' Not: 'Nexra governs your A2A network.'
- As A2A adoption grows into the mid-market over 12-24 months, Nexra is already the governance layer waiting for them

# **§5 - How It Works**

**THE CORE 6-STEP COORDINATION FLOW**

This is the beating heart of the product. Every feature in Nexra either enables this flow or governs it. Governance does not replace this flow - it wraps it. A developer reading this section should be able to design the minimal API surface needed to support all six steps.

| **Step** | **Name**     | **Full detail**                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1        | Register     | An agent calls POST /agents/register with its capability name, a typed JSON input/output schema, per-call pricing in USD, an SLA object (p99 latency, availability), and a webhook URL where Nexra will forward tasks. Agent is assigned a status of 'probationary' until it builds a trust record. Its description is embedded (text-embedding-3-small) and stored in pgvector for semantic discovery.                              |
| 2        | Discover     | Another agent calls POST /capabilities/discover with a natural language query and/or capability_type filter, plus optional budget_cap and max_latency constraints. Nexra runs cosine similarity over capability embeddings, applies hard filters (capability_type, budget, SLA), and returns ranked matches ordered by composite score: schema fit (50%), trust score (25%), cost (15%), latency SLA (10%). P99 target: under 200ms. |
| 3        | Policy check | Before any delegation is forwarded, Nexra evaluates the org's policy set against the proposed delegation: caller type, callee type, time of day, budget remaining, context scope requested, delegation depth. Each policy evaluates to allow, block, or pause (HiTL gate). Decision and the policy that triggered it are logged to the audit trail regardless of outcome.                                                            |
| 4        | Delegate     | Caller sends POST /delegate with the task payload, explicit context_scope (list of data grant keys), budget_cap_usd, and timeout_ms. Nexra verifies caller budget against cap, issues a scoped delegation JWT (5-min expiry, single-use, contains only the granted context keys), and POSTs the task to the callee's webhook_url with HMAC-SHA256 signature.                                                                         |
| 5        | Execute      | Callee receives the signed webhook, verifies HMAC signature, reads the delegation token, executes the task using only the context it was granted, and POSTs the result back to Nexra's POST /delegations/{id}/complete endpoint. Callee cannot read context outside its granted scope even if it knows the key names.                                                                                                                |
| 6        | Settle       | Nexra meters actual cost (LLM tokens consumed × current price, plus any external API costs callee reports), updates the caller's agent_budgets row, appends an immutable entry to the audit_log table, updates the callee's trust score based on outcome (success/failure, latency vs SLA, cost vs estimate), and queues a Stripe billing event. Result returned to caller synchronously or via callback for async.                  |

**WHAT GOVERNANCE ADDS TO EACH STEP**

Governance is not an add-on. It is integrated into the flow at steps 3 and 6, with effects on every other step.

- Step 1 (Register): Agents start in probationary status with tighter default policy constraints (fewer orgs can hire them, lower budget caps). Escalation to 'active' status requires minimum trust score of 0.70 over 10+ completed delegations.
- Step 2 (Discover): Results are ranked by trust score in addition to schema fit and cost. An agent with a trust score below 0.40 is demoted to last-resort matches regardless of semantic fit. Quarantined agents are excluded entirely.
- Step 3 (Policy): Every delegation is explicitly allowed or blocked. There is no concept of 'default allow.' New org default policy is 'block all cross-agent delegations until a policy is defined.' This is a secure-by-default posture.
- Step 4 (Delegate): Budget cap is enforced at API layer - if the estimated cost of the delegation exceeds the agent's remaining daily budget, the delegation is blocked before the webhook is called. Human-in-the-loop gate fires if cost exceeds the policy's hil_threshold_usd field.
- Step 5 (Execute): Only agents with registered webhook_urls can receive delegations. Callee must verify the HMAC signature - Nexra will not retry a rejected webhook. Callee's access to context is scoped to what caller explicitly granted in context_scope.
- Step 6 (Settle): Audit log is append-only - no update or delete operations exist on this table. Every entry includes the policy_id that governed the delegation, the policy_decision (allow/block/pause), and a hash of the task payload for tamper detection.

**13-STEP TECHNICAL DELEGATION FLOW (FOR TDD)**

The six-step user-facing flow expands to 13 discrete technical steps inside Nexra. Each step is a test surface.

- Caller sends POST /delegate to Nexra API with Authorization header (org API key + X-Agent-ID)
- Nexra validates auth: bcrypt-verify API key, confirm agent_id belongs to org, confirm agent status is 'active' not 'quarantined'
- Nexra evaluates delegation policy set in priority order: find matching policies by caller_type and callee_type, evaluate conditions, return first allow/block/pause decision
- If decision is 'pause' (HiTL gate): write pending_approval record, send webhook/email notification to org's approval_url, return 202 Accepted with delegation_id to caller
- If decision is 'block': write blocked_delegation to audit_log, return 403 with policy_id and reason
- Nexra checks caller's agent_budgets row for current period: if (spent_usd + estimated_cost) > cap_usd, return 402 with remaining budget
- Nexra generates scoped delegation JWT: signed with org secret, contains delegation_id, context_scope\[\], callee_agent_id, exp (now+5min), single-use flag
- Nexra constructs webhook payload: task, delegation token, context grants, timeout. Signs with HMAC-SHA256 using callee's webhook_secret
- Nexra POSTs to callee's registered webhook_url with X-Nexra-Signature header. Timeout: min(caller's requested timeout, 30s default)
- Callee verifies HMAC, executes task, POSTs result to POST /delegations/{id}/complete within timeout
- Nexra receives result: meters actual cost, updates agent_budgets, appends immutable audit_log entry, updates callee trust_score
- Nexra returns result to caller: synchronous response if under 29.9s, or fires caller's callback_url for async
- Stripe billing event queued: per-delegation usage record for caller's subscription. If cross-org: Stripe Connect transfer (80% to callee org, 20% platform fee)

# **§6 - Full Feature Set**

P0 = required for MVP (48-hour build). P1 = required for first paying customer (month 3). P2 = required for enterprise sales (month 6+). Nothing in this table is speculative - each feature maps directly to a customer pain or governance gap defined in §2.

| **Feature**                                                      | **Full description**                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | **Priority** | **Layer** |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | --------- | --- | --- | --- | --- | --- | --- |
| **COORDINATION LAYER**                                           |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |              |           |     |     |     |     |     |     |
| Capability registry                                              | Agents register typed input/output JSON schemas, capability_type enum, per-call pricing in USD, SLA (p99 latency ms, availability decimal), and webhook URL. Each registration generates a text embedding for semantic discovery. Registry is queryable by capability_type (exact match) or semantic query (cosine similarity). Typed schemas address A2A's natural-language-only Agent Card limitation - Nexra enforces machine-readable I/O contracts.                                  | P0           | Coord     |
| Runtime discovery                                                | POST /capabilities/discover: agent queries at runtime by capability_type or natural language description. Returns ranked matches filtered by hard constraints (budget, latency SLA). Ranking: schema match 50%, trust score 25%, cost 15%, latency SLA 10%. P99 latency target: <200ms. Returned matches include agent_id, trust_score, pricing, SLA, and a match_score.                                                                                                                  | P0           | Coord     |
| Task delegation                                                  | POST /delegate: full handshake protocol. Caller specifies task payload, context_scope (explicit data grants), budget_cap_usd, timeout_ms, and optional callback_url for async. Nexra evaluates policy, checks budget, issues scoped JWT, and routes to callee webhook. Both sync (response on completion) and async (callback on completion) modes supported.                                                                                                                             | P0           | Coord     |
| Scoped context passing                                           | Context passed in a delegation is explicitly scoped. Caller specifies context_scope: an array of grant keys. Callee's delegation token grants read access only to those keys. Enforced at API layer - callee cannot request data outside its granted scope even if it knows key names exist. Prevents data exfiltration across agent boundaries.                                                                                                                                          | P0           | Coord     |
| Usage-based billing                                              | Per-delegation cost metering via Stripe Metering API. Actual cost tracked per delegation: LLM tokens × current pricing, plus any external API costs callee reports. Internal (same-org) delegations: billed to plan's delegation allowance. Cross-org delegations: caller pays callee's listed price, Nexra takes 20% platform fee, callee org receives 80% via Stripe Connect.                                                                                                           | P0           | Coord     |
| Framework compatibility                                          | Works with any agent that can receive a signed HTTPS webhook and respond within timeout. Explicit adapters for: LangGraph (Python callback), CrewAI (tool wrapper), AWS Bedrock (SigV4 bridge), A2A-native (direct Agent Card compatibility). Zero framework migration required for any ICP company.                                                                                                                                                                                      | P0           | Coord     |
| A2A native compatibility                                         | Nexra speaks A2A natively on the ingress and egress sides. A2A-compliant agents can register using their Agent Card with no SDK changes. Nexra wraps every A2A interaction with its policy and audit layer. For companies that do adopt A2A, Nexra is already their governance layer.                                                                                                                                                                                                     | P0           | Coord     |
| Async delegation                                                 | Webhook-based async mode for long-running tasks. Caller registers a callback_url; Nexra delivers result when callee completes. Polling also supported via GET /delegations/{id}. Status lifecycle: pending → in_flight → completed \| failed \| timeout \| blocked.                                                                                                                                                                                                                       | P1           | Coord     |
| AWS Bedrock adapter                                              | Auto-detects Bedrock agent endpoints from registration. Handles AWS SigV4 auth transparently. Bidirectional payload mapping between Nexra delegation protocol and Bedrock's InvokeAgent API. Enables companies with AWS Marketplace Bedrock agents to coordinate them through Nexra with zero custom integration code.                                                                                                                                                                    | P1           | Coord     |
| MCP server exposure                                              | Nexra's governance and discovery APIs exposed as MCP tools. MCP-native agents can use Nexra policy enforcement and capability discovery without any non-MCP code. Makes Nexra compatible with the entire MCP ecosystem (97M monthly SDK downloads).                                                                                                                                                                                                                                       | P1           | Coord     |
| Cross-org marketplace                                            | Third-party agents publish public capabilities (is_public: true in registry). Any org discovers and hires them. Callee receives 80% revenue share automatically via Stripe Connect. This is the long-term network effect moat: specialist agents build on top of Nexra because it's where buyers are.                                                                                                                                                                                     | P2           | Coord     |
| **GOVERNANCE LAYER - wraps every step of the coordination flow** |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |              |           |     |     |     |     |     |     |
| Policy engine                                                    | YAML-defined delegation policies. Each policy specifies: allow conditions (caller_type, callee_type, time_of_day, capability_type, data_scope), deny conditions (same fields), and on_violation behavior (block_and_alert \| block_silent \| audit_only \| pause_for_approval). Policies evaluated in priority order. Org default: block all cross-agent delegations until a policy is explicitly defined (secure by default). This is the IAM layer for agent networks.                  | P0           | Gov       |
| Spend metering + caps                                            | Per-agent, per-period budget caps with automatic enforcement. Cap types: daily_cap_usd, monthly_cap_usd, per_delegation_cap_usd. Caps enforced before webhook is called - no surprise bills. Actual cost tracked per delegation including LLM tokens (self-reported by callee in result metadata) and external API costs. Monthly CFO-readable reports: total spend by agent, team, capability type, and workflow.                                                                        | P0           | Gov       |
| Immutable audit log                                              | Append-only PostgreSQL table. Every delegation generates one or more audit_log entries: policy_evaluated, delegation_initiated, delegation_completed (or failed/blocked/timeout). Each entry contains: timestamp, caller_org, caller_agent_id, callee_agent_id, task_hash (SHA-256 of task payload), context_scope_granted, policy_id, policy_decision, cost_usd, latency_ms, outcome. No UPDATE or DELETE operations exist on this table at any abstraction layer. Built for regulators. | P0           | Gov       |
| Cost anomaly detection                                           | Statistical model over rolling 7-day spend baseline per agent. Alert when agent's spend in any hour exceeds 3σ above baseline. Alert channels: Slack webhook, email, PagerDuty. Catches runaway agent loops before they become expensive. Configurable sensitivity (multiplier) per agent.                                                                                                                                                                                                | P0           | Gov       |
| Circuit breakers                                                 | Per-agent failure rate threshold (default: >30% failures in 10-minute window → probationary; >50% → quarantined). Delegation chain depth limit (configurable per org, default: max depth 5). Out-of-scope delegation attempts blocked and logged. Quarantined agents excluded from discovery results and cannot receive delegations until manually re-activated.                                                                                                                          | P1           | Gov       |
| Human-in-the-loop gates                                          | Policy can specify hil_threshold_usd: any delegation estimated to cost above this value triggers a pause-for-approval flow. Approval request sent to org's registered approval_url (webhook) and/or email. Delegation held in 'pending_approval' status for up to 24 hours. Approved delegations proceed; expired delegations are auto-cancelled and logged.                                                                                                                              | P1           | Gov       |
| Agent trust scores                                               | Each agent maintains a trust_score (0.000 to 1.000, 3 decimal places). Score updated after each completed delegation: weighted average of success_rate (40%), sla_compliance (30%), cost_accuracy (20%), policy_violations_inverse (10%). New agents start at 1.000 but in 'probationary' status - policy constraints are tighter. Score below 0.40 triggers automatic probationary status. Score below 0.20 triggers quarantine.                                                         | P1           | Gov       |
| Governance dashboard                                             | Org-level real-time view: agent network graph (nodes = agents, edges = delegation volume), delegation volume over time, cost breakdown by agent and team, failure rates and latency percentiles by agent, policy violation log, most-used capabilities, agents approaching budget limits, trust score leaderboard.                                                                                                                                                                        | P1           | Gov       |
| SIEM export                                                      | Real-time streaming export of audit_log to Splunk, Datadog, Elastic, and generic SIEM via webhook. Audit entries structured as JSON with consistent field names across all event types. Enables enterprise compliance teams to ingest agent network activity into existing security workflows.                                                                                                                                                                                            | P1           | Gov       |
| Schema validation                                                | Typed I/O enforcement on every delegation. Nexra validates caller's task payload against callee's registered input_schema (JSON Schema spec). Validates callee's result against callee's registered output_schema before returning to caller. Catches malformed delegations before they reach callee. This is the gap A2A's natural-language Agent Cards explicitly skip.                                                                                                                 | P2           | Gov       |
| Compliance report exports                                        | One-click structured exports for SOC 2 (all agent actions with timestamps and policy decisions), GDPR (data access audit trail per agent), HIPAA (PHI access log by agent and delegation), and generic internal audit. All agent activity structured for regulators and boards.                                                                                                                                                                                                           | P2           | Gov       |
| Policy version control                                           | Policies stored with full version history. Any policy change creates a new version - old version remains active until cutover. Delegation audit entries reference the exact policy_version that governed them. Enables post-hoc compliance review: 'what policy was in effect when this delegation happened?'                                                                                                                                                                             | P2           | Gov       |

# **§7 - API Specifications**

**BASE URL + AUTHENTICATION**

Base URL: <https://api.usenexra.com/v1>

All requests require:

Authorization: Bearer nx*live*&lt;api_key&gt;

Content-Type: application/json

Agent-initiated requests also require:

X-Agent-ID: &lt;agent_id&gt; (registered under the org owning the API key)

Rate limits (Growth plan):

1,000 requests/min per org

100 concurrent delegations in flight

Configurable on Enterprise

**POST /AGENTS/REGISTER**

Register an agent's capability in Nexra's registry. Idempotent on agent_id - re-registration updates the existing record and triggers re-embedding.

POST /agents/register

{

"agent_id": "research-agent-v2", // unique within org

"name": "Competitive Research Agent",

"description": "Researches competitors and market positioning for B2B SaaS companies",

"capability_type": "research", // enum: research | analysis | generation | enrichment | validation | execution | other

"input_schema": { // JSON Schema spec - machine-validated on every delegation

"type": "object",

"required": \["company_name"\],

"properties": {

"company_name": { "type": "string" },

"focus_areas": { "type": "array", "items": { "type": "string" } },

"context": { "type": "string", "nullable": true }

}

},

"output_schema": { // Nexra validates callee result against this before returning

"type": "object",

"required": \["summary", "competitors"\],

"properties": {

"summary": { "type": "string" },

"competitors": { "type": "array", "items": { "type": "object" } },

"sources": { "type": "array", "items": { "type": "string" } }

}

},

"pricing": { "per_call_usd": 0.15 },

"sla": { "p99_latency_ms": 8000, "availability": 0.99 },

"webhook_url": "<https://your-agent.com/nexra/execute>",

"webhook*secret": "whs*...", // used to generate HMAC-SHA256 signature

"is_public": false // true = available to cross-org marketplace

}

Response 201:

{

"agent_id": "research-agent-v2",

"status": "probationary", // transitions to 'active' after trust threshold

"embedding_id": "emb_01JFXP...",

"registered_at": "2026-03-13T21:00:00Z"

}

**POST /CAPABILITIES/DISCOVER**

POST /capabilities/discover

{

"query": "competitive research for B2B SaaS companies", // semantic search

"capability_type": "research", // optional hard filter

"budget_cap_usd": 0.50, // exclude agents above this

"max_latency_ms": 10000, // exclude agents above this SLA

"exclude_agents": \["agent-id-1"\], // optional blocklist

"include_cross_org": false, // set true to search public marketplace

"limit": 5

}

Response 200:

{

"matches": \[

{

"agent_id": "research-agent-v2",

"name": "Competitive Research Agent",

"match_score": 0.94, // composite: schema 50% + trust 25% + cost 15% + latency 10%

"trust_score": 0.91,

"status": "active",

"pricing": { "per_call_usd": 0.15 },

"sla": { "p99_latency_ms": 8000, "availability": 0.99 },

"is_cross_org": false

}

\],

"latency_ms": 87 // P99 target: <200ms

}

**POST /DELEGATE**

POST /delegate

{

"callee_agent_id": "research-agent-v2",

"task": {

"type": "research",

"input": { "company_name": "Acme Corp", "focus_areas": \["pricing", "positioning"\] }

},

"context_scope": \["deal_metadata", "account_tier"\], // explicit data grants - callee can only read these

"budget_cap_usd": 0.25,

"timeout_ms": 12000,

"callback_url": null // null = synchronous; URL = async with callback

}

Response 200 (sync, completed):

{

"delegation_id": "del_01JFXP...",

"status": "completed",

"policy_result": {

"policy_id": "pol_sales-to-research",

"policy_version": 3,

"decision": "allow"

},

"result": {

"summary": "Acme Corp is a mid-market CRM targeting...",

"competitors": \[{ "name": "Rival Corp", "positioning": "..."}\],

"sources": \["https://..."\]

},

"usage": {

"cost_usd": 0.15,

"latency_ms": 1840,

"llm_tokens": 2400

}

}

Error responses:

403 - policy blocked delegation (includes policy_id and reason)

402 - budget cap exceeded (includes remaining_budget_usd)

202 - delegation paused for human approval (includes approval_deadline)

408 - callee timeout

422 - task payload failed input_schema validation

**POST /POLICIES**

POST /policies

{

"name": "sales-to-research",

"description": "Sales agents may hire research agents during business hours with budget controls",

"priority": 10, // lower number = evaluated first

"allow": {

"caller_type": "sales_agent",

"callee_type": "research_agent",

"capability_types": \["research", "analysis"\]

},

"conditions": \[

{ "field": "time_of_day", "operator": "between", "value": \["06:00", "22:00"\] },

{ "field": "caller.budget_remaining_usd", "operator": ">", "value": 0.10 },

{ "field": "context_scope", "operator": "subset_of", "value": \["deal_metadata", "account_tier"\] }

\],

"hil_threshold_usd": 1.00, // pause for human approval if estimated cost exceeds this

"on_violation": "block_and_alert" // block_and_alert | block_silent | audit_only | pause_for_approval

}

**ADDITIONAL ENDPOINTS**

| **Endpoint**                    | **Description**                                                                                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET /delegations/{id}           | Status + result for any delegation. Includes full policy_result, usage, and outcome. Polling endpoint for async delegations.                                                                |
| POST /delegations/{id}/complete | Callee posts result back to Nexra. Requires valid delegation JWT in Authorization header. Nexra validates result against output_schema, meters cost, updates trust score, logs audit entry. |
| POST /delegations/{id}/approve  | Approve a HiTL-gated delegation. Only callable by org admin. Delegation proceeds immediately after approval.                                                                                |
| GET /agents/registry            | List registered agents. Paginated. Query params: capability_type, status (active/probationary/quarantined), is_public. Includes trust_score and basic stats per agent.                      |
| GET /agents/{id}/trust          | Full trust score breakdown for a specific agent: success_rate, sla_compliance, cost_accuracy, policy_violations, delegation_count, last_active.                                             |
| POST /agents/{id}/quarantine    | Manually quarantine an agent. Immediate effect - all in-flight delegations to this agent are failed, agent excluded from discovery, all pending delegations blocked.                        |
| GET /audit/log                  | Full audit log. Paginated (cursor-based, not offset). Filters: agent_id, date_from, date_to, event_type, policy_decision. Exportable as CSV or JSON for SIEM ingest.                        |
| GET /analytics/usage            | Delegation volume, cost, latency percentiles, failure rates. Supports: date range, agent_id, capability_type. Returns time-series data suitable for dashboard charting.                     |
| POST /policies                  | Create delegation policy. Returns policy_id and version 1.                                                                                                                                  |
| PUT /policies/{id}              | Update policy. Creates new version - old version remains referenced in existing audit entries.                                                                                              |
| GET /policies                   | List all policies for org. Includes version history and which delegations each policy has affected.                                                                                         |
| GET /spend/summary              | CFO-facing spend summary. Cost by agent, team, workflow, time period. Includes budget_remaining per agent. Exportable as CSV.                                                               |

# **§8 - Data Model**

**DATABASE: POSTGRESQL 16 + PGVECTOR**

All tables live in a single Postgres schema. pgvector extension required for agent capability embeddings. append-only constraint on audit_log enforced at the database level via trigger (no UPDATE or DELETE permitted on any row). All tables use UUID primary keys (gen_random_uuid()).

\-- Organizations (top-level billing entity)

CREATE TABLE organizations (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

name TEXT NOT NULL,

api_key_hash TEXT NOT NULL UNIQUE, -- bcrypt hash of the actual API key

stripe_id TEXT, -- Stripe Customer ID

plan TEXT DEFAULT 'starter' CHECK (plan IN ('starter','growth','enterprise')),

approval_url TEXT, -- webhook for HiTL gate notifications

created_at TIMESTAMPTZ DEFAULT NOW()

);

\-- Agents (registered capabilities within an org)

CREATE TABLE agents (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

agent_id TEXT NOT NULL, -- human-readable, unique per org

name TEXT NOT NULL,

description TEXT NOT NULL,

capability_type TEXT NOT NULL,

input_schema JSONB NOT NULL,

output_schema JSONB NOT NULL,

webhook_url TEXT NOT NULL,

webhook_secret TEXT NOT NULL, -- used to sign outbound webhooks

pricing JSONB NOT NULL, -- { per_call_usd: float }

sla JSONB NOT NULL, -- { p99_latency_ms: int, availability: float }

is_public BOOLEAN DEFAULT FALSE, -- true = visible in cross-org marketplace

embedding VECTOR(1536), -- text-embedding-3-small of name + description

trust_score DECIMAL(4,3) DEFAULT 1.000,

status TEXT DEFAULT 'probationary' CHECK (status IN ('active','probationary','quarantined')),

delegation_count INT DEFAULT 0,

created_at TIMESTAMPTZ DEFAULT NOW(),

updated_at TIMESTAMPTZ DEFAULT NOW(),

UNIQUE (org_id, agent_id)

);

CREATE INDEX agents_embedding_idx ON agents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX agents_capability_type_idx ON agents (capability_type, status);

\-- Delegation policies

CREATE TABLE policies (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

name TEXT NOT NULL,

description TEXT,

priority INT DEFAULT 100, -- lower = evaluated first

rule_yaml TEXT NOT NULL, -- full YAML policy definition

version INT DEFAULT 1,

enabled BOOLEAN DEFAULT TRUE,

created_at TIMESTAMPTZ DEFAULT NOW()

);

\-- Delegations (one row per delegation attempt)

CREATE TABLE delegations (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

caller_org_id UUID NOT NULL REFERENCES organizations(id),

caller_agent_id TEXT NOT NULL,

callee_org_id UUID REFERENCES organizations(id), -- null if same-org

callee_agent_id TEXT NOT NULL,

task JSONB NOT NULL,

task_hash TEXT NOT NULL, -- SHA-256 of task JSON for tamper detection

context_scope TEXT\[\] NOT NULL, -- explicit data grants

policy_id UUID REFERENCES policies(id),

policy_version INT,

policy_decision TEXT CHECK (policy_decision IN ('allow','block','pause')),

status TEXT NOT NULL CHECK (status IN ('pending','in_flight','completed','failed','timeout','blocked','pending_approval')),

result JSONB,

budget_cap_usd DECIMAL(10,4),

estimated_cost_usd DECIMAL(10,4),

actual_cost_usd DECIMAL(10,4),

latency_ms INT,

llm_tokens INT,

callback_url TEXT,

created_at TIMESTAMPTZ DEFAULT NOW(),

completed_at TIMESTAMPTZ

);

CREATE INDEX delegations_caller_idx ON delegations (caller_org_id, caller_agent_id, created_at DESC);

CREATE INDEX delegations_status_idx ON delegations (status, created_at DESC);

\-- Audit log (append-only - enforced by trigger)

CREATE TABLE audit_log (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

delegation_id UUID REFERENCES delegations(id),

org_id UUID NOT NULL REFERENCES organizations(id),

event_type TEXT NOT NULL, -- policy_evaluated | delegation_initiated | delegation_completed | delegation_failed | agent_quarantined | budget_exceeded | hil_triggered | hil_approved

actor_agent_id TEXT,

target_agent_id TEXT,

details JSONB NOT NULL, -- full event payload

cost_usd DECIMAL(10,4),

created_at TIMESTAMPTZ DEFAULT NOW() -- immutable

);

\-- Trigger: prevent UPDATE and DELETE on audit_log

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS TRIGGER AS \$\$

BEGIN RAISE EXCEPTION 'audit_log rows are immutable'; END; \$\$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_audit_immutability BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

\-- Agent budgets (spend tracking per agent per period)

CREATE TABLE agent_budgets (

agent_id TEXT NOT NULL,

org_id UUID NOT NULL REFERENCES organizations(id),

period DATE NOT NULL, -- ISO date of the budget period (daily: the day; monthly: first of month)

period_type TEXT NOT NULL CHECK (period_type IN ('daily','monthly')),

cap_usd DECIMAL(10,4) NOT NULL,

spent_usd DECIMAL(10,4) DEFAULT 0,

updated_at TIMESTAMPTZ DEFAULT NOW(),

PRIMARY KEY (agent_id, org_id, period, period_type)

);

\-- Trust score history (append-only, one row per delegation completion)

CREATE TABLE trust_score_events (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

agent_id TEXT NOT NULL,

org_id UUID NOT NULL REFERENCES organizations(id),

delegation_id UUID REFERENCES delegations(id),

score_before DECIMAL(4,3),

score_after DECIMAL(4,3),

components JSONB NOT NULL, -- { success_rate, sla_compliance, cost_accuracy, policy_violations_inverse }

created_at TIMESTAMPTZ DEFAULT NOW()

);

# **§9 - Auth + Security Model**

**IDENTITY HIERARCHY**

Three levels of identity, each with different trust and scope:

- Organization - top-level billing entity. One API key. All agents and policies belong to an org. API key is bcrypt-hashed in the database. Never stored in plaintext. Never returned after creation.
- Agent - registered under an org. Identified by agent_id string (unique per org). Agent calls use org API key + X-Agent-ID header. Nexra verifies the agent_id belongs to the org owning the API key on every request.
- Delegation token - short-lived JWT issued per delegation. Signed with org's HMAC secret. Contains: delegation_id, callee_agent_id, context_scope\[\], exp (now + 5 minutes), jti (unique per delegation, single-use). Callee must present this token to POST /delegations/{id}/complete. Single-use enforced by Redis TTL on jti.

**OUTBOUND WEBHOOK SECURITY**

Every webhook Nexra sends to a callee's webhook_url is signed using HMAC-SHA256 with the callee's registered webhook_secret. The signature is included in the X-Nexra-Signature header as: sha256=&lt;hex_digest&gt;. Callee MUST verify this signature before executing any task. Nexra does not retry a webhook that returns a 401 or 403 - it fails the delegation and logs to audit trail.

**POLICY ENFORCEMENT ARCHITECTURE**

Policies are evaluated synchronously before any delegation is forwarded. There is no async policy evaluation. Evaluation order: policies sorted by priority (ascending). First policy that matches allow conditions: delegation proceeds. First policy that matches deny conditions: delegation blocked. No matching policy: delegation blocked (secure by default).

Policy conditions are evaluated against a delegation context object containing: caller.agent_type, caller.org_id, caller.budget_remaining_usd, callee.agent_type, callee.trust_score, task.capability_type, context_scope (the requested grants), estimated_cost_usd, time_of_day (UTC), delegation_depth (nesting level).

**TRANSPORT SECURITY**

- All API traffic over TLS 1.3 minimum. TLS 1.2 rejected.
- Webhook delivery: HTTPS only. HTTP webhook_urls rejected at registration time.
- API keys: bcrypt hash rounds = 12. Never logged. Never returned after creation endpoint.
- Rate limiting: 1,000 req/min per org (Growth). Enforced at API gateway layer, not application layer. Returns 429 with Retry-After header.
- CORS: API is not browser-callable directly - no CORS headers. SDK handles all HTTP calls.
- Delegation JWT secret: 256-bit random secret per org, stored encrypted at rest (AES-256-GCM).

**SOC 2 ROADMAP**

- GDPR-compliant data handling from day one: all PII identifiable in schema, deletion propagates to all tables except audit_log (audit_log anonymizes PII on GDPR deletion request)
- Pen test: 6 months post-launch - Cobalt or equivalent
- SOC 2 Type I: 12 months post-launch
- SOC 2 Type II: 18 months post-launch
- Data residency (EU): v2 - separate Postgres instance in eu-west-1

# **§10 - Technical Architecture**

**STACK (MVP → PRODUCTION)**

| **Component**       | **MVP (48h build)**                                                                 | **Production (Month 6)**                                                                       |
| ------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| API                 | FastAPI (Python 3.12). Uvicorn worker. Single process.                              | FastAPI behind Nginx. Multiple workers. Health checks on /health.                              |
| Database            | PostgreSQL 16 + pgvector. Railway managed Postgres.                                 | AWS RDS PostgreSQL 16 Multi-AZ + pgvector. Read replica for analytics queries.                 |
| Cache / token store | Redis (Railway). JWT single-use enforcement + rate limit counters.                  | AWS ElastiCache Redis Cluster. Separate instance for rate limits vs token store.               |
| Embeddings          | OpenAI text-embedding-3-small via API. Stored in pgvector VECTOR(1536).             | Same. Batch re-embed on registration update. Pre-warm IVFFlat index on deploy.                 |
| Policy engine       | Python YAML parser + custom rule evaluator (pure Python, no external dependencies). | Same engine. Add policy caching per org (Redis TTL 60s) to reduce DB reads.                    |
| Billing             | Stripe Metering API (usage records). Stripe Connect for cross-org revenue share.    | Same. Add Stripe Connect payout dashboard for callee orgs.                                     |
| Auth                | bcrypt API key verification. python-jose JWT for delegation tokens.                 | Same. Add org-level API key rotation, key scoping (read-only keys for analytics).              |
| Webhook delivery    | Direct HTTPX async call. Single retry on 5xx.                                       | Celery + Redis queue. Exponential backoff. 3 retries. Dead letter queue for failed deliveries. |
| SDK                 | nexra-py (Python). nexra-ts (TypeScript). Thin wrappers around REST API.            | Same. Add LangGraph adapter, CrewAI tool wrapper, Bedrock SigV4 bridge.                        |
| Deploy              | Railway (single service).                                                           | AWS ECS Fargate. ALB. Separate task definitions for API and Celery workers.                    |
| Monitoring          | Railway logs + Sentry error tracking.                                               | Datadog APM. CloudWatch metrics. PagerDuty for P0 alerts (5xx spike, delegation queue depth).  |

**DISCOVERY RANKING - COMPOSITE SCORE ALGORITHM**

Every discovery result is ranked by a composite score computed in the database layer (not application layer - to avoid N+1 queries). Score formula:

composite_score = (

(cosine_similarity(query_embedding, agent.embedding) \* 0.50)

\+ (agent.trust_score \* 0.25)

\+ ((1 - (agent.pricing.per_call_usd / max_price_in_result_set)) \* 0.15)

\+ ((1 - (agent.sla.p99_latency_ms / max_latency_in_result_set)) \* 0.10)

)

Hard filters applied BEFORE scoring (excluded from result set entirely):

\- agent.status = 'quarantined'

\- agent.status = 'probationary' AND org policy restricts probationary agents

\- agent.pricing.per_call_usd > budget_cap_usd

\- agent.sla.p99_latency_ms > max_latency_ms

\- agent_id IN exclude_agents

\- is_public = false AND callee.org_id != caller.org_id

**SDK DESIGN - NEXRA-PY**

from nexra import NexraClient

client = NexraClient(api*key='nx_live*...', agent_id='sales-agent-v1')

\# Discover + delegate in one call (most common pattern)

result = await client.hire(

capability='research',

task={ 'company_name': 'Acme Corp', 'focus_areas': \['pricing'\] },

context_scope=\['deal_metadata'\],

budget_cap=0.25

)

\# Nexra handles: discover → policy check → delegate → settle

\# Or separate discover + delegate

agents = await client.discover('competitive research B2B SaaS', budget_cap=0.50)

delegation = await client.delegate(

agent_id=agents\[0\].agent_id,

task={ ... },

context_scope=\['deal_metadata'\]

)

# **§11 - Market Size**

| **AGENTIC AI MARKET 2025**<br><br>**\$7.1-7.8B**<br><br>Global - all companies building/deploying agents |     | **ENTERPRISES SUCCESSFULLY SCALED AGENTS**<br><br>**23%**<br><br>McKinsey - most stuck in pilot purgatory |
| -------------------------------------------------------------------------------------------------------- | --- | --------------------------------------------------------------------------------------------------------- |
|                                                                                                          |
| **AGENTIC AI MARKET 2030**<br><br>**\$52B+**<br><br>44% CAGR - MachineLearnMastery / Gartner             |     | **MULTI-AGENT INQUIRY SURGE**<br><br>**+1,445%**<br><br>Gartner Q1 2024 → Q2 2025                         |
|                                                                                                          |
| **ENTERPRISE APPS WITH AI AGENTS 2026**<br><br>**40%**<br><br>Gartner - up from <5% in 2025              |     | **AGENTIC COMMERCE OPPORTUNITY**<br><br>**\$3-5T**<br><br>McKinsey - economic value of agent networks     |

**TAM - All companies deploying AI agents**

The \$7.1B agentic AI market in 2025 encompasses all companies building, deploying, or buying AI agent infrastructure. Nexra addresses the coordination and governance layer for any company deploying multiple agents in production - this is the entire market minus single-agent deployments.

**SAM - Companies that need Nexra today**

Series A-C SaaS companies (roughly \$5M-\$100M ARR) with 5+ agents in production using any framework. They feel the coordination wall today. They are blocked by compliance teams today. They do not require A2A adoption. This market exists right now.

**Why governance expands the buyer and ACV**

The engineering buyer (Head of AI) can approve \$5K-\$20K/year for infrastructure that saves engineering time. The compliance buyer (CISO, CCO) can approve \$50K-\$500K/year for tools that give them an audit trail. The finance buyer (CFO, VP Finance) actively seeks AI spend visibility after several years of uncontrolled AI cost growth. Nexra addresses all three. That is why ACV can scale from \$12K (Growth plan, engineering buyer) to \$60K+ (Enterprise with compliance buyer).

# **§12 - Ideal Customer Profile**

**PRIMARY ICP**

| **COMPANY**<br><br>**Series A-C SaaS**<br><br>\$5M-\$100M ARR, 50-500 employees                        |     | **CHAMPION**<br><br>**Head of AI / ML Eng**<br><br>Owns agent infra, feels the pain daily                 |
| ------------------------------------------------------------------------------------------------------ | --- | --------------------------------------------------------------------------------------------------------- |
|                                                                                                        |
| **AGENT THRESHOLD**<br><br>**5+ agents in production**<br><br>Hitting coordination wall; any framework |     | **ECONOMIC BUYER**<br><br>**CTO or VP Engineering**<br><br>Signs infra spend; motivated by eng efficiency |

Qualifying questions for discovery calls:

- How many distinct agents do you have running in production right now?
- When your sales agent needs research data, how does that handoff happen today?
- If your CEO asked you for a complete log of every action your agents took last month, how long would it take you to produce that?
- Has your compliance, legal, or finance team asked you to justify AI spend or audit agent behavior? What did you tell them?
- What does your orchestration glue code look like? Is it a maintenance burden?

**SECONDARY ICP - GOVERNANCE-FIRST BUYER**

Regulated industries (fintech, healthtech, legaltech) where compliance teams are actively blocking agent deployment until there is an auditable record of what agents did. These companies often have fewer agents but pay significantly more (2-5x ACV) because the governance story unlocks deployment that was blocked. Sales cycle starts with CISO or CCO, not engineering.

**COMPANIES TO EXPLICITLY TARGET VIA FOREFRONT PORTFOLIO**

Phil Nadel's portfolio at Forefront Venture Partners (200+ companies) contains companies across exactly this ICP. Prioritize: B2B SaaS companies in Forefront portfolio that have raised Series A-C, are in fintech, legaltech, HR tech, or sales tech (highest agent deployment rate), and have public product pages mentioning AI.

**ANTI-ICP - DO NOT TARGET IN V1**

- Companies with 1-2 agents: coordination pain not acute; come back in 6 months
- Pure enterprise (Fortune 500): long sales cycles, security reviews, on-prem requirements - not v1 scope
- Non-technical buyers without an engineering champion: need engineering champion to close
- Companies without agent deployments in production: not ready; put in nurture
- Web3/crypto-native companies expecting blockchain settlement: out of scope by design

# **§13 - Competitive Landscape**

No direct competitor at the Series A-C ICP level today. The competitive risk is from incumbents building down from enterprise, not from startups building up from the same ICP. Here is the honest breakdown.

| **Competitor**              | **What they do**                                                                                                              | **What they don't do**                                                                                                                                                         | **Nexra vs them**                                                                                                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Google A2A                  | Free open protocol for agent-to-agent communication. Discovery, task delegation, message lifecycle. 100+ enterprise partners. | No policy engine. No spend controls. No audit log. No circuit breakers. Protocol only - no hosted governance runtime.                                                          | Nexra is built ON TOP of A2A, not against it. A2A is the protocol. Nexra is the governance layer. A2A not yet adopted at Series A-C level - Nexra solves the problem today for the ICP that exists today. |
| Anthropic MCP               | Free open protocol for agent-to-tool connectivity. 97M monthly downloads. Widely deployed.                                    | Tool connectivity only - not agent-to-agent coordination. No governance layer.                                                                                                 | Nexra is MCP-compatible. Enforces policy on MCP tool calls and A2A delegations simultaneously. Being MCP-compatible means the entire MCP ecosystem can use Nexra governance.                              |
| LangGraph / CrewAI          | Orchestration frameworks for building and running agent workflows. Widely deployed by Nexra's ICP.                            | Static topology - connections defined at build time. Within-ecosystem only. No runtime discovery, no governance, no billing. Can't coordinate LangGraph ↔ CrewAI or ↔ Bedrock. | Nexra governs what they build. Most of Nexra's first customers will be using these today. Complementary - not competitive.                                                                                |
| AWS Bedrock AgentCore       | Native A2A and agent execution within AWS ecosystem. AWS Marketplace agent catalog.                                           | AWS-ecosystem only. Cannot govern Azure, GCP, or custom agents. No cross-cloud policy. No independent audit trail.                                                             | Cloud and framework agnostic. Governs Bedrock agents alongside Azure agents, LangGraph agents, and custom agents in one unified policy layer. Multi-cloud is the key differentiator.                      |
| Datadog                     | Infrastructure monitoring. Application performance management. Can log HTTP requests including agent traffic.                 | No agent semantics. Sees HTTP requests, not delegation intent, policy decisions, trust scores, or context scope. No ability to block a delegation based on policy.             | Datadog observes. Nexra governs. You cannot write a Datadog monitor that blocks a delegation. Nexra is control-plane; Datadog is data-plane.                                                              |
| Kong / Zuplo (API gateways) | Generic HTTP governance applied to API traffic. Rate limiting, auth, routing.                                                 | Request-aware, not agent-aware. Cannot evaluate delegation intent, trust scores, context scope grants, or spending policies. No agent registry.                                | Agent-aware control plane vs request-aware proxy. Nexra understands what delegations mean - intent, budget, policy, trust. A gateway sees a POST request; Nexra sees a delegation.                        |
| Mem0 / Zep                  | Agent memory and context persistence. \$XM funded.                                                                            | Not a coordination or governance layer. No delegation, no policy, no billing.                                                                                                  | Complementary - Nexra can pass Mem0/Zep memory as part of context_scope grants in a delegation.                                                                                                           |

_Nexra's moat is the data flywheel: every delegation builds trust scores. Trust scores drive better discovery outcomes. Better discovery outcomes bring more agents. More agents make the marketplace more valuable. This network effect is not replicable by a protocol or a monitoring tool._

# **§14 - Pricing**

| **Starter**                                                                                                                                                                                                 | **Growth**                                                                                                                                                                                                                                                                                                                                | **Enterprise**                                                                                                                                                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **\$0 / month**<br><br>Evaluation + early adoption                                                                                                                                                          | **\$499 / month**<br><br>**Production teams - most popular**                                                                                                                                                                                                                                                                              | **Custom**<br><br>Compliance / high-volume                                                                                                                                                                                                                                 |
| • 5 registered agents<br><br>• 500 delegations / month<br><br>• \$0.005 / delegation above limit<br><br>• 3 policies max<br><br>• 7-day audit log<br><br>• Basic spend dashboard<br><br>• Internal org only | • Unlimited agents<br><br>• 10,000 delegations / month<br><br>• \$0.003 / delegation above limit<br><br>• Unlimited policies<br><br>• 90-day audit log + SIEM export<br><br>• Full governance dashboard<br><br>• Circuit breakers + HiTL gates<br><br>• Cross-org marketplace<br><br>• Cost anomaly alerts<br><br>• Slack + email support | • Volume delegation pricing<br><br>• 99.9% uptime SLA<br><br>• SSO / SAML<br><br>• Custom data retention<br><br>• SOC 2 Type II (roadmap)<br><br>• Compliance report exports<br><br>• Policy version control<br><br>• Dedicated Slack channel<br><br>• On-prem option (v3) |

**Cross-org revenue share mechanics**

When a public agent (is_public: true) is hired cross-org, the calling org pays the callee's listed per_call_usd price. Nexra's platform fee is 20%. The callee org receives 80% via automatic Stripe Connect transfer. Payouts are monthly. Callee orgs must complete Stripe Connect onboarding (standard KYC) before receiving payouts.

| **GROSS MARGIN TARGET**<br><br>**80%+**<br><br>Infrastructure costs <20% of revenue at scale         |     | **PAYBACK PERIOD TARGET**<br><br>**< 6 months**<br><br>2 eng-hrs/wk saved → Growth plan paid in 3 months |
| ---------------------------------------------------------------------------------------------------- | --- | -------------------------------------------------------------------------------------------------------- |
|                                                                                                      |
| **TARGET ACV RANGE**<br><br>**\$6K-\$60K+**<br><br>Starter free → Growth \$6K/yr → Enterprise \$60K+ |     | **YEAR 1 ARR TARGET**<br><br>**\$2M**<br><br>~50 customers at ~\$40K average ACV                         |

# **§15 - AWS Marketplace Integration**

_Strategic context: AWS Marketplace launched an AI Agents & Tools category in July 2025 with Anthropic as a partner. Companies are now buying 3-10 pre-built Bedrock agents from this marketplace. None of those agents can coordinate with each other. None have governance. Nexra is the missing control plane that makes AWS Marketplace agent purchases composable and auditable._

**INTEGRATION MODE 1 - NEXRA AS COORDINATOR FOR BEDROCK AGENTS (P1, V1.5)**

Companies register their AWS Marketplace Bedrock agents in Nexra's registry just like any other agent. Nexra's Bedrock adapter handles the integration details transparently.

- Auto-detection: when a webhook_url points to a Bedrock endpoint pattern (runtime.sagemaker.amazonaws.com or bedrock-agent-runtime.\*), Nexra switches to Bedrock adapter mode
- Auth: Nexra handles SigV4 signing for Bedrock API calls using the org's registered AWS credentials (stored encrypted at rest)
- Payload mapping: Nexra maps its delegation protocol to Bedrock's InvokeAgent API request/response format bidirectionally
- Result: a company can buy 5 agents from AWS Marketplace and have them coordinating through Nexra within an hour, with full governance

**INTEGRATION MODE 2 - NEXRA LISTED ON AWS MARKETPLACE (P2, V2)**

List Nexra itself as a product on AWS Marketplace. Companies subscribe using their existing AWS billing account. This eliminates the need for a separate vendor contract, procurement process, or new credit card. Dramatically reduces sales friction for AWS-native companies.

**AWS GTM ACTIONS (IN PRIORITY ORDER)**

- Apply to AWS Activate immediately after MVP goes live - \$100K credits + co-sell motion with AWS account teams
- Identify 2-3 AWS Marketplace agent vendors (companies selling Bedrock agents) and approach them about 'Nexra-compatible' labeling on their marketplace pages - mutual benefit, free distribution
- AWS Partner Network (APN) co-sell - AWS account teams know which enterprise customers are buying multiple Marketplace agents; warm intros via AWS co-sell program
- ETHDenver contacts: AWS was at ETHDenver 2026. Any contacts from that network are warm intros to AWS Marketplace partnerships team
- List Nexra on AWS Marketplace in v2 - negotiate marketplace listing after reaching \$10K MRR to demonstrate product-market fit

# **§16 - 48-Hour MVP Build Plan**

Goal: ship a working API, a demo showing two agents coordinating through Nexra with a policy enforced in real time, a Python SDK, and a waitlist page - all in 48 hours. This is the minimum needed to start customer conversations and post on X/LinkedIn.

| **Window**  | **Milestone**          | **Exact deliverables**                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hours 0-6   | Registry + auth        | POST /agents/register working. GET /agents/registry working. Postgres schema created (agents, organizations tables only). bcrypt API key verification. Basic auth middleware. Python SDK skeleton (NexraClient class, register method).                                                                                                                                                                                                     |
| Hours 6-16  | Discovery + delegation | POST /capabilities/discover with pgvector cosine similarity. POST /delegate with basic policy evaluation (single hardcoded policy, then YAML parser). HMAC-signed webhook delivery via HTTPX. Delegation token (JWT) issuance. Audit log table + basic log write on each delegation.                                                                                                                                                        |
| Hours 16-28 | Demo scenario          | Two Claude-based agents: (1) Sales Agent that needs competitive intelligence, (2) Research Agent that provides it. Sales agent queries discover, gets Research agent back, calls delegate. Policy blocks if time is outside 6am-10pm. Policy allows during business hours. Record 90-second demo video showing: zero hardcoded connection, policy evaluated and logged in real time, full delegation round-trip. This video is the product. |
| Hours 28-36 | SDK + spend metering   | nexra-py SDK: client.hire() convenience method (discover + delegate in one call). client.register(), client.discover(). Stripe Metering API integration: usage record per delegation. agent_budgets table + cap enforcement in delegation flow. README with quickstart.                                                                                                                                                                     |
| Hours 36-44 | Deploy + waitlist      | Railway deploy. Environment variables configured. Health check endpoint. usenexra.com landing page with waitlist form (Typeform or simple HTML + Airtable). Open source on GitHub with MIT license. Demo video embedded on landing page.                                                                                                                                                                                                    |
| Hours 44-48 | Launch                 | Post on X with demo video (engineering angle). Post on LinkedIn (governance + engineering angle). Submit to HN Show HN (technical, honest, brief). DM 20 AI engineering leads at Series A-C companies who have posted about multi-agent pain. Email Phil Nadel at Forefront.                                                                                                                                                                |

**DEMO SCRIPT (90 SECONDS)**

The demo video is the most important deliverable of the 48 hours. Every other output supports it. This is the exact script:

- Show: two Python files open - sales_agent.py and research_agent.py. No imports connecting them to each other.
- Run: sales_agent.py. It calls client.hire(capability='research', ...). Terminal shows: 'Querying Nexra registry...'
- Show: Nexra logs in real time: 'Policy \[sales-to-research\] evaluated: ALLOW. Delegating to research-agent-v2...'
- Show: research_agent.py receives the webhook, executes, returns result.
- Show: sales_agent.py receives the result. Print the deal analysis output.
- Show: audit log in the database - one entry, full details, policy_id, cost, latency.
- Change the time condition in the policy to block. Re-run. Show: 'Policy \[sales-to-research\] evaluated: BLOCK. Reason: outside allowed hours.'
- No hardcoded connection. No imports between agents. Policy change took 10 seconds.

# **§17 - Go-to-Market: First 10 Customers**

Goal in the first 30 days: 10 engineering or compliance leads willing to have a 30-minute conversation. 3 willing to integrate a real agent. 1 willing to pay.

**DISTRIBUTION CHANNELS (PRIORITY ORDER)**

| **Channel**                             | **Target outcome**                     | **Tactics**                                                                                                                                                                                       |
| --------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Forefront Venture Partners (Phil Nadel) | 3-5 warm intros to exact ICP           | Email Phil with demo video day 1. Ask specifically for intros to portfolio companies with 5+ agents in production. He has done 200+ deals - several are in exactly this ICP.                      |
| Harlem Capital (HCP)                    | 1-2 warm intros to portfolio companies | Follow up with everyone from the interview process. VCs know which portfolio companies are hitting AI governance walls. The '24/7 Employee' deck established credibility in the agentic AI space. |
| X / Twitter                             | 20+ inbound leads from demo video      | Post demo video with engineering angle. Search for engineers posting about LangGraph pain, A2A governance gaps, agent glue code. Reply with genuine insight. DM with demo link.                   |
| HN Show HN                              | Technical credibility + 5-10 signups   | Brief, honest 2-sentence pitch. Link to demo. No hype. Engineers respect straightforward descriptions of real problems.                                                                           |
| LinkedIn                                | Governance + compliance buyers         | Post with compliance angle: 'Your agents are making decisions. Do you have a record of what they decided?' Tag enterprise AI leaders. IBM network is warm - use it.                               |
| IBM (summer internship)                 | 3-5 enterprise customer conversations  | 12 weeks inside enterprise AI deployments. Direct validation research. Warm intros to decision makers. IBM itself may be a customer or partner.                                                   |
| Direct outreach                         | 10 targeted leads                      | Find 10 companies on LinkedIn with 'AI Engineer' or 'ML Platform' job postings. Post on your feed. These companies are building agent infra and feeling the pain.                                 |
| AWS angle                               | AWS-native companies                   | 'Nexra makes your AWS Marketplace agents work together, with full governance.' Attaches Nexra to a purchase the company has already made.                                                         |

**KILL SIGNALS - WHEN TO PIVOT**

If any of these patterns emerge after genuine outreach, do not double down on the same approach. Investigate and reframe.

- Zero calls after 50 outreaches → the framing is wrong, not the product; try different problem language
- Everyone says LangGraph is fine and they don't feel coordination pain → pain not acute enough at current agent count; come back when they hit 10+ agents
- Everyone blocked by security before even seeing a demo → governance-only is the wedge; lead with audit trail and policy engine, not coordination
- Everyone says AWS will build this → position explicitly as multi-cloud layer; AWS can't govern Azure or custom agents
- Every deal requires on-prem → enterprise-only market; pivot pricing and ICP accordingly

# **§18 - Risks + Mitigations**

| **Risk**                                                 | **Likelihood**      | **Full mitigation**                                                                                                                                                                                                                                 |
| -------------------------------------------------------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AWS or Google ships a hosted control plane on top of A2A | High - 12-18 months | Speed is the primary defense. Get one enterprise customer under contract before they ship. Multi-cloud positioning is the durable moat - AWS cannot govern Azure agents. 'Works everywhere' cannot be shipped by AWS.                               |
| A2A protocol changes break Nexra compatibility           | Medium              | A2A is under Linux Foundation governance with 100+ enterprise partners - major breaking changes require broad consensus and are slow. Track the spec via GitHub. Run integration tests on every A2A release in CI.                                  |
| Pain not acute enough - LangGraph 'good enough'          | Medium              | Qualify hard on agent count before any demo. Only pitch to orgs with 5+ agents in production. Governance angle (CISO, CFO) unlocks a different buyer who isn't using LangGraph at all.                                                              |
| Security concerns block enterprise adoption              | Medium              | Context scoping and policy engine are P0 core features - not v2 features. Lead with security story in every enterprise pitch. SOC 2 roadmap communicated from day one. HMAC-signed webhooks and scoped JWTs demonstrate security-first engineering. |
| Solo founder bandwidth                                   | Real                | Scope MVP ruthlessly - registry, delegation, basic policy, audit log only. No dashboard, no cross-org marketplace, no Bedrock adapter in v1. Use IBM summer to do customer discovery without writing code.                                          |
| IBM internship competes for time during summer           | Real                | 12 weeks inside enterprise agent deployments is customer discovery, not a distraction. Every conversation with an IBM client about AI governance is a sales call. Nexra development continues nights/weekends.                                      |
| Compliance buyers move slowly - long sales cycles        | Medium              | Two-track sales: engineering buyer (fast, \$499/mo self-serve) and compliance buyer (slow, \$50K+ contract). Engineering buyer is the wedge. Compliance buyer is the upsell after the engineer has deployed and loves it.                           |
| Cross-org marketplace fails to reach critical mass       | Low in v1           | Marketplace is P2 - not required for v1 or first customer. Internal-org coordination is sufficient value for the first 20 customers. Marketplace is the long-term network effect play, not the wedge.                                               |

# **§19 - Milestones**

| **When** | **Milestone**               | **Definition of done**                                                                                                                                                                       |
| -------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Week 1   | MVP live + launched         | Registry, discovery, delegation, basic policy engine, audit log. Railway deployed. Demo video posted. GitHub open source. usenexra.com waitlist. Phil Nadel emailed.                         |
| Month 1  | 10 leads, 3 calls           | 10 people on waitlist who are engineers or compliance leads. 3 people willing to do a 30-min call. At least 1 real agent registered by a company that is not you.                            |
| Month 3  | First paying customer       | One company on Growth (\$499/mo). Circuit breakers and governance dashboard shipped. Bedrock adapter in beta with at least one AWS customer. Trust score system live.                        |
| Month 6  | \$10K MRR                   | ~20 customers. Full governance module live (SIEM, HiTL gates, compliance exports). First compliance-led sale (CISO or CCO as economic buyer, \$10K+ ACV). AWS Marketplace listing applied.   |
| Month 12 | \$50K MRR or pivot decision | ~100 customers. First enterprise contract (>\$50K ACV). Seed raise (\$1-2M) initiated or direction decision made based on what the market is actually buying. Cross-org marketplace in beta. |

# **§20 - Why Now + Why You**

**WHY NOW**

Multi-agent systems went from experiment to production standard in 2025. Gartner reported a 1,445% surge in multi-agent inquiries from Q1 2024 to Q2 2025. A2A and MCP solved the protocol layer. That immediately created the governance vacuum Nexra fills. The O'Reilly 'governance gap' article was published in February 2026. The McKinsey State of AI report in late 2025 identified governance as the primary reason enterprises are stuck in pilot purgatory. The window for a control plane product is now - before AWS and Google build governance into their platforms from above.

Critically, the market does not require A2A adoption to be ready. The Series A-C SaaS ICP is using LangGraph and CrewAI today and hitting the coordination wall today. Nexra addresses the problem that exists right now for companies that exist right now.

**WHY YOU**

| **Edge**                                 | **Why it matters for Nexra**                                                                                                                                                                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Built AuditGuard at ETHDenver (Feb 2026) | AuditGuard was an autonomous agent marketplace where agents discover, bid on, execute, and settle audits on Hedera - structurally identical to Nexra's coordination primitive. You've built this. Most people pitching this space have never built it. |
| IBM Consulting (summer 2026)             | 12 weeks inside enterprise AI deployments at IBM's Silicon Valley Lab. Direct access to companies wrestling with agent governance right now. Customer discovery while getting paid. Potential first enterprise customer or warm intros.                |
| Barclays Quant (summer 2027)             | Credibility with technical and compliance buyers that a typical 19-year-old founder does not have. 'Built by someone heading to a quant role at Barclays' is a different signal than a generic startup.                                                |
| Forefront Venture Partners               | 200+ portfolio company deal flow under Phil Nadel. Many are in the exact Nexra ICP (Series A-C SaaS). Direct access to warm leads - not cold outreach.                                                                                                 |
| Federal Reserve Python pipeline          | 3,000+ line quantitative research pipeline. Demonstrates the technical depth to build production infrastructure, not just a weekend hackathon project.                                                                                                 |
| Purdue IBE program                       | Integrated Business and Engineering - dual perspective on both the technical and business sides of the product. Rare for a student founder.                                                                                                            |
| Low burn, long runway                    | Building while in school: no payroll, no rent for an office, no VC pressure. Runway is measured in years, not months. Can take the time to build the right product without racing to hit a fundraising milestone.                                      |

Nexra - usenexra.com - Confidential - March 2026 - v_final (TDD-ready)