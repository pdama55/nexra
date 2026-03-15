Nexra Governance Dashboard --- Full Product Specification
=======================================================

**Version:** 1.0\
**Date:** March 2026\
**Author:** Parth\
**Status:** Ready for development\
**Scope:** Full v1 production dashboard --- serves both engineering lead and compliance/CISO buyer\
**Stack:** React SPA, Vercel/Cloudflare Pages, read-only against existing API endpoints

* * * * *

Table of Contents
-----------------

1.  [Overview & Design Philosophy](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#1-overview--design-philosophy)
2.  [User Personas & Access Model](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#2-user-personas--access-model)
3.  [Information Architecture](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#3-information-architecture)
4.  [Global Shell & Navigation](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#4-global-shell--navigation)
5.  [View 1 --- Overview](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#5-view-1--overview)
6.  [View 2 --- Agent Registry](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#6-view-2--agent-registry)
7.  [View 3 --- Delegation Feed](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#7-view-3--delegation-feed)
8.  [View 4 --- Policy Engine](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#8-view-4--policy-engine)
9.  [View 5 --- Spend & Budget](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#9-view-5--spend--budget)
10. [View 6 --- Audit Log](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#10-view-6--audit-log)
11. [View 7 --- Human-in-the-Loop Queue](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#11-view-7--human-in-the-loop-queue)
12. [View 8 --- Trust Scores](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#12-view-8--trust-scores)
13. [View 9 --- Circuit Breakers & Anomalies](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#13-view-9--circuit-breakers--anomalies)
14. [View 10 --- Compliance Export](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#14-view-10--compliance-export)
15. [View 11 --- Settings](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#15-view-11--settings)
16. [API Mapping --- Every Endpoint the Dashboard Reads](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#16-api-mapping--every-endpoint-the-dashboard-reads)
17. [Data Refresh & Real-Time Strategy](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#17-data-refresh--real-time-strategy)
18. [Design System](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#18-design-system)
19. [Role-Based Access Control](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#19-role-based-access-control)
20. [Empty States & Error States](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#20-empty-states--error-states)
21. [Performance Requirements](https://claude.ai/chat/39aaade3-ede8-49c1-a8d6-13669a08edb0#21-performance-requirements)

* * * * *

1\. Overview & Design Philosophy
--------------------------------

The Nexra Governance Dashboard is a read-only (with two exceptions: HiTL approval/reject and agent status override) React SPA that gives engineering leads and compliance officers full visibility into their multi-agent system. It reads exclusively from the existing Nexra API --- no new backend endpoints are required for v1 except `/analytics/usage` and `/spend/summary`, which are already defined in the TDD.

**Two buyers, one dashboard.** The engineering lead uses the dashboard daily to debug delegation failures, monitor trust scores, and watch spend. The CISO uses it monthly to pull audit exports, verify policy coverage, and demonstrate compliance posture. The dashboard must serve both without mode-switching or role-specific views (except for write actions, which are RBAC-gated).

**Design principle: density over decoration.** This is an infrastructure control plane, not a consumer app. The visual language is compact, monochromatic, and table-heavy. Information density is a feature. The engineering lead should be able to scan the full system state in under 30 seconds from the Overview page.

**The dashboard is not a monitoring tool.** It does not replace Datadog, CloudWatch, or Sentry. It surfaces governance data --- policy decisions, spend enforcement, audit trail, trust scores, circuit breaker state --- not infrastructure metrics like CPU or memory.

* * * * *

2\. User Personas & Access Model
--------------------------------

### Persona A --- Engineering Lead ("The Builder")

**Job:** Platform engineer or AI engineering lead at a Series A--C SaaS company. Deployed 5--20 agents in production using LangGraph or CrewAI. Added Nexra to get governance without rewriting the agent stack.

**Opens the dashboard when:** A delegation fails unexpectedly. An agent gets circuit-broken. Spend is higher than expected. A new agent needs to be registered and verified. Debugging why a policy blocked a delegation.

**Cares about:** Delegation feed (real-time), agent status, trust score trends, circuit breaker state, spend vs. cap per agent, policy decision details.

**Does not care about:** Compliance export formats, GDPR fields, SOC 2 evidence packages, HiTL approval workflows (unless they set them up).

### Persona B --- Compliance Lead / CISO ("The Auditor")

**Job:** CISO or compliance lead at a company with a security review process for AI deployments. Wasn't involved in the technical decision to use Nexra but is now responsible for proving the AI system is governed.

**Opens the dashboard when:** Preparing for a SOC 2 audit. Responding to an incident where an AI agent took an unexpected action. Quarterly review of AI spend and policy coverage. Signing off on a new agent going to production.

**Cares about:** Audit log (filterable, exportable), policy version history, spend caps and budget enforcement evidence, HiTL gate configuration, compliance export (CSV/JSON), agent quarantine history.

**Does not care about:** Trust score formula internals, discovery ranking weights, webhook delivery retries, Celery worker state.

### Access Roles

| Role | Description | Write Permissions |
| --- | --- | --- |
| `admin` | Full access. Org owner. | HiTL approve/reject, agent status override, policy create/edit, settings |
| `engineer` | Technical access. | HiTL approve/reject, agent status override |
| `compliance` | Read-only + export. | Audit export, compliance report generation only |
| `viewer` | Read-only. | None |

* * * * *

3\. Information Architecture
----------------------------

```
dashboard.usenexra.com/
├── /                          → Overview (default)
├── /agents                    → Agent Registry
│   └── /agents/:agent_id      → Agent Detail
├── /delegations               → Delegation Feed
│   └── /delegations/:id       → Delegation Detail
├── /policies                  → Policy Engine
│   └── /policies/:id          → Policy Detail + Version History
├── /spend                     → Spend & Budget
├── /audit                     → Audit Log
├── /hitl                      → Human-in-the-Loop Queue
├── /trust                     → Trust Scores
├── /anomalies                 → Circuit Breakers & Anomalies
├── /compliance                → Compliance Export
└── /settings                  → Settings (API keys, webhooks, team)

```

* * * * *

4\. Global Shell & Navigation
-----------------------------

### Layout

Full-height fixed left sidebar (240px) + main content area. No top nav bar --- all navigation is in the sidebar. Sidebar collapses to 64px icon-only mode on screens under 1280px.

### Sidebar Structure

```
[NEXRA wordmark]
─────────────────
Overview          /
─────────────────
Agents            /agents
Delegations       /delegations
Policies          /policies
─────────────────
Spend             /spend
Audit Log         /audit
HiTL Queue        /hitl         [badge: pending count]
─────────────────
Trust Scores      /trust
Anomalies         /anomalies
─────────────────
Compliance        /compliance
Settings          /settings
─────────────────
[Org name]
[Plan badge: Starter / Growth / Enterprise]
[API status indicator: green dot = healthy]

```

**HiTL Queue badge:** When `pending_approval` delegations exist, a red numeric badge appears on the HiTL Queue nav item. This is the only persistent badge in the UI.

**API status indicator:** Pings `GET /health` every 60 seconds. Green = 200. Yellow = degraded (>500ms). Red = non-200 or timeout.

### Global elements

-   **Search bar** (CMD+K): Searches agent IDs, delegation IDs, and audit log event types. Results open inline. Does not trigger API calls on every keystroke --- debounced 300ms, minimum 3 characters.
-   **Time range selector**: Global. Affects all views that show time-bounded data. Options: Last hour / Last 24h / Last 7 days / Last 30 days / Custom range. Default: Last 24h. Persists in localStorage.
-   **Refresh indicator**: Top-right of every view. Shows "Updated Xs ago" and a manual refresh button. Auto-refresh interval shown and configurable.

* * * * *

5\. View 1 --- Overview
---------------------

**URL:** `/`\
**Purpose:** Single-glance system health. 30 seconds to full situational awareness.\
**Primary user:** Engineering lead, daily.\
**Refresh:** Every 30 seconds.

### Layout

Three rows:

**Row 1 --- Stat cards (6 cards, equal width)**

| Card | Metric | Source endpoint |
| --- | --- | --- |
| Active Agents | Count of agents with `status=active` | `GET /agents/registry` |
| Delegations (24h) | Total delegations in time window | `GET /analytics/usage` |
| Success Rate (24h) | `completed / total` as % | `GET /analytics/usage` |
| Blocked (24h) | Count of `delegation_blocked` events | `GET /audit/log?event_type=delegation_blocked` |
| Total Spend (24h) | Sum of `cost_usd` in window | `GET /spend/summary` |
| Pending HiTL | Count of `pending_approval` delegations | `GET /delegations?status=pending_approval` |

Each card: metric name in small-caps, large number, delta vs. previous period (up/down arrow + %). Cards with 0 pending HiTL show green dot; >0 shows red with count.

**Row 2 --- Two columns**

Left (60%): **Delegation volume chart**

-   Line chart. X axis = time (bucketed by hour for 24h view, by day for 7d/30d). Y axis = delegation count.
-   Three series: `completed` (solid line), `blocked` (dashed), `failed` (dotted).
-   No chart library animation. Static render. Recharts.
-   Clicking a data point navigates to `/delegations` filtered to that time window.

Right (40%): **Agent status distribution**

-   Horizontal bar or small table. Rows: Active / Probationary / Quarantined. Count + % of total.
-   Quarantined row highlighted if count > 0.
-   Each row links to `/agents?status=<status>`.

**Row 3 --- Two columns**

Left (50%): **Recent delegation activity**

-   Last 10 delegations. Columns: Time, Caller, Callee, Status, Cost, Latency.
-   Status as colored pill: `completed` = muted green, `blocked` = muted red, `failed` = muted orange, `in_flight` = muted blue, `pending_approval` = muted yellow.
-   Clicking a row navigates to `/delegations/:id`.

Right (50%): **Active alerts**

-   List of unresolved anomalies and circuit breaker events from last 24h.
-   Empty state: "No active alerts" with a checkmark.
-   Each alert: icon (anomaly vs. circuit breaker), agent ID, timestamp, description.
-   Clicking navigates to `/anomalies`.

* * * * *

6\. View 2 --- Agent Registry
---------------------------

**URL:** `/agents`\
**Purpose:** Full inventory of registered agents with status, trust score, and activity.\
**Primary user:** Engineering lead.\
**Refresh:** Manual + every 5 minutes.

### Filters (top bar)

-   Status: All / Active / Probationary / Quarantined (multi-select pill filter)
-   Capability type: All / research / analysis / generation / enrichment / validation / execution / other
-   Search: agent_id or name substring match (client-side after fetch)
-   Sort: Trust score ↑↓ / Delegations (24h) ↑↓ / Registered date ↑↓

### Table columns

| Column | Notes |
| --- | --- |
| Agent ID | Monospace. Clickable → agent detail. |
| Name | Display name from registration. |
| Capability | Enum badge. |
| Status | Colored pill. `active` = green, `probationary` = yellow, `quarantined` = red. |
| Trust Score | Number (0.000--1.000) + mini sparkline of last 30 days. Color: >0.7 normal, 0.4--0.7 yellow, <0.4 red. |
| Delegations (period) | Count in selected time window. |
| Last Active | Relative time (e.g. "3 minutes ago"). |
| Spend (period) | Sum of `cost_usd` for this agent in time window. |
| Actions | "View" link. Admin: "Quarantine" / "Activate" buttons. |

Pagination: 25 rows per page. Cursor-based matching API.

### Agent Detail --- `/agents/:agent_id`

Tabbed layout. Four tabs:

**Tab 1 --- Overview**

-   Registration metadata: agent_id, name, capability_type, webhook_url (masked: `https://your-agent.com/***`), registered_at, updated_at, is_public.
-   Current status with last status change timestamp and reason.
-   Pricing: per_call_usd.
-   SLA: p99_latency_ms, availability.
-   Input schema and output schema rendered as collapsible JSON blocks.

**Tab 2 --- Trust Score**

-   Current score: large number with component breakdown.
-   Four component bars (success_rate × 0.40, sla_compliance × 0.30, cost_accuracy × 0.20, policy_violations_inverse × 0.10). Each bar shows component value and weighted contribution.
-   Historical chart: trust score over last 30 days. Points at each delegation completion.
-   Rolling 30-day stats table: total delegations, completed, failed, timed out, SLA met, SLA breached, policy violations.
-   Status transition history: table of all status changes with timestamp and trigger (auto/manual).

**Tab 3 --- Delegation History**

-   Same table as `/delegations` but pre-filtered to this agent (as caller or callee).
-   Toggled by "As caller" / "As callee" pill.

**Tab 4 --- Audit History**

-   Same table as `/audit` but pre-filtered to `actor_agent_id = this agent`.
-   All event types shown. No filtering needed --- agent scope is narrow enough.

**Admin actions (role-gated)**

-   "Quarantine agent" --- POST `/agents/:id/quarantine`. Requires confirmation modal with reason text field. Writes `agent_quarantined` audit entry.
-   "Activate agent" --- POST `/agents/:id/activate`. Available only when status is probationary or quarantined. Confirmation modal.

* * * * *

7\. View 3 --- Delegation Feed
----------------------------

**URL:** `/delegations`\
**Purpose:** Real-time and historical view of every delegation routed through Nexra.\
**Primary user:** Engineering lead (real-time debugging), compliance (historical investigation).\
**Refresh:** Every 10 seconds for in-flight delegations; otherwise manual.

### Filters

-   Status: All / completed / in_flight / pending_approval / blocked / failed / timed_out (multi-select)
-   Caller agent: dropdown of all registered agents
-   Callee agent: dropdown of all registered agents
-   Time range: inherited from global selector
-   Policy decision: All / allow / block / pause
-   Cost range: min / max USD inputs

### Table columns

| Column | Notes |
| --- | --- |
| Delegation ID | Monospace prefix (first 12 chars). Clickable. |
| Time | Relative + absolute on hover tooltip. |
| Caller | Agent ID, linkable. |
| Callee | Agent ID, linkable. |
| Status | Colored pill. |
| Policy | Policy ID that evaluated this delegation. Linkable to `/policies/:id`. |
| Decision | allow / block / pause badge. |
| Cost | Actual `cost_usd`. "---" if not yet settled. |
| Latency | `latency_ms`. "---" if not yet complete. |
| Depth | Delegation chain depth (integer). Highlighted red if >3. |

Live mode toggle: When enabled, new rows prepend with a subtle fade-in animation. Updates every 10 seconds via polling. Pause button stops prepending without stopping polling (so clicking "pause" and then "resume" shows what accumulated).

### Delegation Detail --- `/delegations/:id`

Full-page detail. Two column layout.

**Left column --- Core details**

```
Delegation ID:     del_01JFXP...
Status:            completed
Created:           2026-03-14 21:04:33 UTC
Completed:         2026-03-14 21:04:35 UTC
Latency:           1,840ms
Depth:             2

Caller:            sales-agent-v1  [link]
Callee:            research-agent-v2  [link]

Task type:         research
Budget cap:        $0.25
Estimated cost:    $0.15
Actual cost:       $0.15
Context scope:     deal_metadata, account_tier

Policy evaluated:  pol_01ABC...  [link]
Policy version:    3
Policy decision:   allow

```

**Right column --- Timeline**

Vertical timeline of every event in this delegation's lifecycle, pulled from `GET /audit/log?delegation_id=:id`:

```
21:04:33.001  delegation_initiated     caller → callee, est. $0.15
21:04:33.050  policy_evaluated         allow (pol_01ABC... v3)
21:04:33.090  webhook_delivered        → https://agent.co/***
21:04:35.001  delegation_completed     actual $0.15, 1840ms, 2400 tokens
21:04:35.010  trust_score_updated      research-agent-v2: 0.881 → 0.884
21:04:35.020  billing_event_queued     Stripe meter event recorded

```

Each timeline event is expandable to show full `details` JSON.

**Result payload** (collapsible): Shows the callee's output. Available only to `admin` and `engineer` roles. Collapsed by default --- one click to expand.

**If status is `blocked`:**

-   Large red banner at top: "POLICY BLOCKED"
-   Reason string from policy evaluation
-   Policy ID and version that blocked it, with link
-   No result payload (none exists)

**If status is `pending_approval`:**

-   HiTL approval widget inline (see View 7 for detail)
-   Countdown timer to approval deadline

* * * * *

8\. View 4 --- Policy Engine
--------------------------

**URL:** `/policies`\
**Purpose:** View, create, and manage governance policies. See which policies are active and what they've blocked.\
**Primary user:** Engineering lead (create/edit), compliance (audit policy history).\
**Refresh:** Manual.

### Policy list

Table with columns: Policy ID, Name, Status (active/inactive), Version, Created, Last evaluated, Block count (period), Delegations covered (period).

"New policy" button (admin only) --- opens a YAML editor modal (see below).

### Policy Detail --- `/policies/:id`

**Header:** Policy name, current version, active/inactive badge, created date, "Edit" button (admin).

**Tab 1 --- Current Policy**

Full YAML display in a read-only code block with syntax highlighting. All conditions rendered as collapsible sections matching the YAML structure:

```
id: pol_01ABC...
name: default-governance
version: 3
rules:
  - condition: estimated_cost_usd > 1.00
    action: pause          # triggers HiTL
  - condition: callee.trust_score < 0.40
    action: block
    reason: "Callee trust score below threshold"
  - condition: context_scope contains "pii"
    action: block
    reason: "PII context not permitted in this org"
  - condition: delegation_depth > 5
    action: block
    reason: "Max delegation depth exceeded"
  default_action: allow

```

**Tab 2 --- Version History**

Table: Version number, created date, created by (user or "system"), change summary (diff of conditions changed), "View" link per version.

Clicking a version shows that version's YAML in a read-only modal with a side-by-side diff against the current version (added lines green, removed lines red).

**Tab 3 --- Evaluation History**

Table of every policy evaluation in the selected time window. Columns: Time, Delegation ID, Decision (allow/block/pause), Matched rule (which condition triggered), Cost at evaluation.

Filtering: Decision type, time range. Useful for compliance to show "this policy blocked X% of delegations."

**Policy editor (admin only)**

Modal with a YAML editor (CodeMirror or Monaco). Schema validation runs client-side before submit --- validates that all conditions use supported operators and all action values are `allow`, `block`, or `pause`. On save, creates a new version (no in-place edits). Confirmation step shows what changed before committing.

* * * * *

9\. View 5 --- Spend & Budget
---------------------------

**URL:** `/spend`\
**Purpose:** Full spend visibility --- per agent, per period, vs. caps. The CFO view.\
**Primary user:** Engineering lead (budget management), compliance (AI spend audit).\
**Refresh:** Every 5 minutes.

### Top stat row (4 cards)

| Card | Metric |
| --- | --- |
| Total Spend (period) | Sum across all agents |
| Avg Cost / Delegation | Total spend / delegation count |
| Highest Spend Agent | Agent ID + spend amount |
| Budget Utilization | Across all agents: spent / cap as % |

### Spend over time chart

Line chart. X = time (same bucketing as global selector). Y = cumulative spend in USD. Option to toggle between cumulative and per-period (hourly/daily bars). Recharts. Clicking a point opens delegation feed filtered to that time window.

### Per-agent spend table

| Column | Notes |
| --- | --- |
| Agent | Agent ID, linkable. |
| Delegations | Count in period. |
| Total Spend | Sum `cost_usd`. |
| Avg Cost | Per delegation. |
| Daily Cap | `daily_budget_cap_usd` from agent record. "---" if not set. |
| Monthly Cap | `monthly_budget_cap_usd`. "---" if not set. |
| Utilization | Spent / cap as progress bar. Red if >80%. |
| Anomalies | Count of `anomaly_detected` events for this agent in period. Badge if >0. |

Sorting by utilization descending by default --- surfaces agents closest to cap first.

### Budget cap management (admin only)

Inline edit: clicking the cap value in the table opens an inline input. Save triggers `PATCH /agents/:id` with updated budget caps. Confirmation step.

### Spend anomaly section

Below the table: list of all `anomaly_detected` audit events in the selected period. Columns: Time, Agent, Current Hour Spend, Baseline Mean, Sigma (×). Color-coded: 3--4σ = yellow, >4σ = red. Each row links to the delegation feed filtered to that agent and time window.

* * * * *

10\. View 6 --- Audit Log
-----------------------

**URL:** `/audit`\
**Purpose:** Immutable, filterable, exportable record of every event. The compliance buyer's primary view.\
**Primary user:** Compliance / CISO.\
**Refresh:** Manual. No auto-refresh (immutable data --- polling adds no value).

### Filters

All filters are AND-combined:

-   **Event type** (multi-select): All event types from TDD §13.1 --- `policy_evaluated`, `delegation_initiated`, `delegation_completed`, `delegation_failed`, `delegation_blocked`, `delegation_timeout`, `agent_quarantined`, `agent_activated`, `budget_exceeded`, `hil_triggered`, `hil_approved`, `hil_expired`, `anomaly_detected`, `circuit_breaker_tripped`
-   **Agent** (searchable dropdown): actor_agent_id or target_agent_id
-   **Delegation ID**: exact match text input
-   **Time range**: inherited from global selector, but overridable here independently
-   **Cost range**: min/max USD (only relevant for `delegation_completed` events)

### Table columns

| Column | Notes |
| --- | --- |
| Time | UTC timestamp, full precision. Sortable descending only (newest first --- immutable append-only log). |
| Event Type | Color-coded by category: delegation events (neutral), blocked/failed (red), governance events (yellow), agent status events (orange), billing events (muted). |
| Actor | `actor_agent_id`. Linkable. "system" for automated events. |
| Target | `target_agent_id`. Linkable. "---" where not applicable. |
| Delegation ID | Monospace prefix. Linkable to `/delegations/:id`. "---" for non-delegation events. |
| Cost | `cost_usd`. "---" where not applicable. |
| Details | Truncated summary of `details` JSONB. Full JSON on row expand. |

Row expansion: clicking a row expands inline to show the full `details` JSON in a syntax-highlighted block. Does not navigate away.

Pagination: 50 rows per page. Cursor-based (matches API). "Load more" button at bottom rather than numbered pages --- feels more appropriate for an append-only log.

### Export

"Export" button (top right). Options:

-   **CSV** --- all fields, current filters applied, up to 10,000 rows. Filename: `nexra_audit_<org_id>_<date_from>_<date_to>.csv`
-   **JSON** --- same data as CSV but in JSON array format.
-   **SOC 2 Report** --- pre-formatted report (see View 10 for detail).

Export is generated client-side from paginated API responses. Progress indicator shown for large exports. Max 10,000 rows per export --- if more rows exist, prompt to narrow time range.

* * * * *

11\. View 7 --- Human-in-the-Loop Queue
-------------------------------------

**URL:** `/hitl`\
**Purpose:** Review and act on delegations that require human approval before proceeding.\
**Primary user:** Engineering lead or admin (time-sensitive --- approvals expire in 24h).\
**Refresh:** Every 30 seconds. Badge on nav item updates in real-time.

### Queue table

Shows all delegations with `status = pending_approval`. Sorted by `approval_deadline` ascending (most urgent first).

| Column | Notes |
| --- | --- |
| Delegation ID | Linkable to full detail. |
| Caller | Agent ID, linkable. |
| Callee | Agent ID, linkable. |
| Estimated Cost | `estimated_cost_usd`. Red if significantly over `hil_threshold_usd`. |
| HiTL Threshold | The threshold that triggered this gate. |
| Task Type | Capability type of the callee. |
| Context Scope | Comma-separated list of context keys requested. |
| Submitted | When the delegation was initiated. |
| Deadline | Time remaining as countdown (e.g. "18h 32m"). Red when <2h. |
| Actions | Approve / Reject buttons (admin and engineer roles only). |

### Approve/Reject flow

Clicking "Approve":

1.  Confirmation modal showing full delegation context: caller, callee, task summary, cost, context scope.
2.  Optional notes field (stored in audit log).
3.  "Confirm approval" button.
4.  POST `/delegations/:id/approve` --- delegation proceeds immediately.
5.  Row removed from queue. Toast notification: "Delegation approved. It will complete shortly."

Clicking "Reject":

1.  Confirmation modal.
2.  Required reason field.
3.  POST `/delegations/:id/reject`.
4.  Row removed from queue. Status in delegation feed updates to `blocked`.

### Expired approvals section

Below the active queue: table of `hil_expired` audit events in the selected period. These are delegations that timed out without human action. Columns: Delegation ID, Caller, Callee, Cost, Submitted, Expired at. Read-only --- no actions available on expired delegations.

### HiTL configuration (admin only, in Settings)

The HiTL threshold is set per policy in YAML --- it is not configured in the dashboard directly. A link to `/policies` is shown with a note explaining where to change the threshold.

* * * * *

12\. View 8 --- Trust Scores
--------------------------

**URL:** `/trust`\
**Purpose:** Full trust score visibility across all agents. Identify agents approaching thresholds.\
**Primary user:** Engineering lead.\
**Refresh:** Every 5 minutes.

### Top threshold alert bar

If any agent has trust_score < 0.40 (at risk of quarantine), a yellow banner appears at the top: "2 agents below quarantine threshold (0.40). Review recommended." Links to the filtered table.

### Trust score table

All agents sorted by trust score ascending by default (worst first).

| Column | Notes |
| --- | --- |
| Agent | Agent ID + name, linkable. |
| Status | Current status badge. |
| Trust Score | Large number. Color: >0.7 = normal, 0.40--0.70 = yellow, <0.40 = red. |
| Success Rate | Component value (contributes 40%). |
| SLA Compliance | Component value (contributes 30%). |
| Cost Accuracy | Component value (contributes 20%). |
| Policy Violations | Component value (contributes 10%). |
| Delegations (30d) | Total in rolling window. |
| Trend | Sparkline of trust score over last 30 days. |
| Threshold proximity | Distance to next threshold: "0.12 from quarantine" or "0.18 to active". |

### Score formula reminder

Static callout below the table header:

```
trust_score = (success_rate × 0.40) + (sla_compliance × 0.30)
            + (cost_accuracy × 0.20) + (policy_violations_inverse × 0.10)

Thresholds:  active → probationary if score < 0.40
             probationary → quarantined if score < 0.20
             probationary → active if score >= 0.70 AND delegations >= 10

```

### Agent trust detail

Clicking an agent row navigates to `/agents/:agent_id#trust` (the trust tab on the agent detail page).

* * * * *

13\. View 9 --- Circuit Breakers & Anomalies
------------------------------------------

**URL:** `/anomalies`\
**Purpose:** Active circuit breaker state and spend anomaly history.\
**Primary user:** Engineering lead.\
**Refresh:** Every 60 seconds.

### Active circuit breakers section

Table of all agents currently in a circuit-breaker-triggered state (status changed to `probationary` or `quarantined` as a result of high failure rate). Pulled from recent `circuit_breaker_tripped` audit events cross-referenced with current agent status.

| Column | Notes |
| --- | --- |
| Agent | Agent ID, linkable. |
| Current Status | probationary / quarantined badge. |
| Failure Rate | At time of trigger. |
| Window | 10-minute window (currently fixed). |
| Triggered At | Timestamp. |
| Pending Delegations Cancelled | Count of delegations blocked at trigger time. |
| Actions | "Review agent" link to agent detail. Admin: "Reactivate" button. |

If no active circuit breakers: "No active circuit breakers" with a checkmark. This is the normal state.

### Spend anomaly history

All `anomaly_detected` audit events in the selected time window.

| Column | Notes |
| --- | --- |
| Time | Timestamp. |
| Agent | Agent ID, linkable. |
| Current Hour Spend | Spend in the detected hour. |
| Baseline Mean | 7-day rolling mean. |
| Baseline Std | 7-day rolling std. |
| Sigma | How many standard deviations above baseline. Color: 3--4σ = yellow, >4σ = red. |
| Resolved | Whether spend returned to normal in the next hour. "Yes" / "No" / "Unknown" (if still in progress). |

### Circuit breaker thresholds

Static info box:

```
Circuit breaker thresholds (configured in policy engine):
  > 30% failure rate in 10 min → status: probationary
  > 50% failure rate in 10 min → status: quarantined

Spend anomaly threshold:
  Current hour spend > 3σ above 7-day hourly baseline → anomaly_detected event
  Minimum 7 days of data required for baseline computation

```

* * * * *

14\. View 10 --- Compliance Export
--------------------------------

**URL:** `/compliance`\
**Purpose:** Generate structured compliance reports for SOC 2, GDPR, HIPAA, and internal governance audits.\
**Primary user:** Compliance / CISO.\
**Refresh:** N/A --- on-demand report generation.

### Report types

**1\. Full Audit Export**

-   All audit log events for a time range.
-   Formats: CSV, JSON.
-   Fields: id, org_id, event_type, actor_agent_id, target_agent_id, delegation_id, cost_usd, details (JSON-encoded), created_at.
-   Max range: 90 days (Growth plan) or configurable (Enterprise).

**2\. Policy Coverage Report**

-   For a time window: every delegation, which policy evaluated it, what decision was made.
-   Demonstrates that 100% of delegations were policy-evaluated.
-   Columns: delegation_id, timestamp, policy_id, policy_version, decision, reason (if blocked).
-   Format: CSV.

**3\. Spend Governance Report**

-   Per-agent spend summary with budget caps, utilization, and anomaly flags.
-   Demonstrates spend controls were in place and enforced.
-   Columns: agent_id, period, total_spend_usd, daily_cap_usd, monthly_cap_usd, budget_exceeded_count, anomaly_count.
-   Format: CSV.

**4\. Agent Status History**

-   Full history of every agent status change: register, activate, quarantine, reactivate.
-   Demonstrates agent lifecycle governance.
-   Pulled from audit log events: `agent_quarantined`, `agent_activated`.
-   Format: CSV.

**5\. HiTL Decision Log**

-   Every delegation that triggered a HiTL gate: outcome, who approved/rejected, timestamp.
-   Demonstrates human oversight of high-cost delegations.
-   Columns: delegation_id, estimated_cost, hil_threshold, triggered_at, outcome (approved/rejected/expired), decided_by, decided_at, notes.
-   Format: CSV.

**6\. SOC 2 Evidence Package**

-   Bundles reports 1--5 into a single ZIP file.
-   Adds a `summary.json` with org metadata, plan, reporting period, and record counts.
-   Filename: `nexra_soc2_evidence_<org_id>_<date_range>.zip`.
-   This is the single deliverable a CISO hands to an auditor.

### Report generation UI

For each report type: a card with description, required inputs (date range, optional filters), and a "Generate" button. Generation runs in the browser via paginated API calls. Progress bar shows % complete for large exports. Download triggers automatically on completion.

**Plan gating:**

-   Starter: Full Audit Export only (7-day max range).
-   Growth: All report types, 90-day max range.
-   Enterprise: All report types, unlimited range, scheduled exports.

* * * * *

15\. View 11 --- Settings
-----------------------

**URL:** `/settings`\
**Purpose:** Org configuration, API key management, team access, webhook configuration.\
**Primary user:** Admin only for writes; all roles can view.

### Tabs

**Tab 1 --- API Keys**

-   Table of active API keys: ID prefix (first 8 chars), name/label, created date, last used, created by.
-   "Create new key" button --- shows generated key once on creation, never again.
-   "Revoke" button per key with confirmation modal.

**Tab 2 --- Team**

-   Table: email, role, joined date, last active.
-   "Invite" button --- email input + role dropdown.
-   Role change dropdown per member (admin only).
-   "Remove" button with confirmation.

**Tab 3 --- Webhooks**

-   Org-level webhook URL for HiTL notifications.
-   Org admin email for HiTL email notifications.
-   SIEM webhook URL (Enterprise only) --- audit log real-time streaming destination.
-   Test button per webhook --- fires a test event and shows response code.

**Tab 4 --- Billing**

-   Current plan badge.
-   Usage this billing period: delegations count vs. plan limit.
-   Stripe customer portal link (opens Stripe-hosted portal in new tab).
-   Upgrade CTA if on Starter.

**Tab 5 --- Organization**

-   Org name, org ID (read-only).
-   Plan details.
-   Audit log retention period (read-only --- set by plan).
-   "Delete organization" (danger zone, admin only) --- requires typing org name to confirm.

* * * * *

16\. API Mapping --- Every Endpoint the Dashboard Reads
-----------------------------------------------------

All read operations use existing TDD-defined endpoints. All write operations are gated by RBAC.

| Dashboard View | API Call | Notes |
| --- | --- | --- |
| Overview --- stat cards | `GET /analytics/usage?window=24h` | Aggregated counts |
| Overview --- delegation chart | `GET /analytics/usage?window=<period>&bucket=hour` | Bucketed time series |
| Overview --- agent status | `GET /agents/registry` | Count by status client-side |
| Overview --- recent activity | `GET /delegations?limit=10&sort=created_at:desc` |  |
| Overview --- alerts | `GET /audit/log?event_type=anomaly_detected,circuit_breaker_tripped&limit=20` |  |
| Agent Registry --- list | `GET /agents/registry?status=<>&capability_type=<>&limit=25&cursor=<>` |  |
| Agent Registry --- detail | `GET /agents/:agent_id` |  |
| Agent --- trust tab | `GET /agents/:agent_id/trust` | TDD §10 |
| Agent --- delegation history | `GET /delegations?caller_agent_id=<>&cursor=<>` |  |
| Agent --- audit history | `GET /audit/log?actor_agent_id=<>&cursor=<>` |  |
| Delegation Feed | `GET /delegations?status=<>&cursor=<>&limit=25` |  |
| Delegation Detail | `GET /delegations/:id` |  |
| Delegation Timeline | `GET /audit/log?delegation_id=<>` |  |
| Policy List | `GET /policies` |  |
| Policy Detail | `GET /policies/:id` |  |
| Policy Evaluation History | `GET /audit/log?event_type=policy_evaluated&policy_id=<>` |  |
| Spend Summary | `GET /spend/summary?window=<period>` |  |
| Spend Per Agent | `GET /spend/summary?breakdown=agent&window=<period>` |  |
| Spend Anomalies | `GET /audit/log?event_type=anomaly_detected` |  |
| Audit Log | `GET /audit/log?event_type=<>&actor_agent_id=<>&date_from=<>&date_to=<>&cursor=<>` |  |
| HiTL Queue | `GET /delegations?status=pending_approval&sort=approval_deadline:asc` |  |
| HiTL Approve | `POST /delegations/:id/approve` | Admin/engineer only |
| HiTL Reject | `POST /delegations/:id/reject` | Admin/engineer only |
| Trust Scores | `GET /agents/registry` + trust data |  |
| Circuit Breakers | `GET /audit/log?event_type=circuit_breaker_tripped` + agent status |  |
| Compliance Export | `GET /audit/log` (paginated, full filter set) | Client-side CSV generation |
| Settings --- API Keys | `GET /org/api-keys` |  |
| Settings --- Team | `GET /org/members` |  |
| Agent Quarantine | `POST /agents/:id/quarantine` | Admin only |
| Agent Activate | `POST /agents/:id/activate` | Admin/engineer only |
| New Policy | `POST /policies` | Admin only |
| Edit Policy | `POST /policies/:id/versions` (new version) | Admin only |
| Health indicator | `GET /health` | Every 60s |

* * * * *

17\. Data Refresh & Real-Time Strategy
--------------------------------------

The dashboard is polling-based, not WebSocket. The existing API does not expose a WebSocket or SSE endpoint. Polling intervals are chosen to balance freshness with API rate limits.

| View / Component | Interval | Notes |
| --- | --- | --- |
| Overview stat cards | 30s | Frequent enough for operational awareness |
| Delegation feed (live mode) | 10s | User-togglable. Only when live mode is on. |
| HiTL queue + nav badge | 30s | Approvals expire in 24h --- 30s is adequate |
| Spend summary | 5 min | Billing data doesn't need second-by-second |
| Agent registry | 5 min | Status changes are infrequent |
| API health indicator | 60s | Minimal overhead |
| Audit log | Manual only | Immutable --- polling adds no value |
| Compliance export | On-demand | Generated fresh on each request |

**Rate limit awareness:** Growth plan is 1,000 req/min. The dashboard at full polling generates approximately 8--12 requests/minute at idle (one request per auto-refreshing component). Well within limits. No rate limit throttling logic needed in v1.

**Stale data indicator:** Each auto-refreshing component shows "Updated Xs ago" in the top-right corner. If a component hasn't successfully refreshed in >2× its interval, the indicator turns yellow.

* * * * *

18\. Design System
------------------

The dashboard is a separate visual context from usenexra.com. The marketing site is black-background editorial. The dashboard is dark-but-not-black, dense, and table-heavy. Reference: Linear, Vercel Analytics, Stripe Dashboard.

### Colors

```
Background primary:    #0F0F0D    (near-black, slightly warm)
Background secondary:  #161614    (cards, panels)
Background tertiary:   #1C1C19    (table rows hover, inputs)
Border:                #2A2A26    (1px borders everywhere)
Border strong:         #3A3A36    (focused inputs, active states)

Text primary:          #E8E6DE    (headings, values)
Text secondary:        #9A9A94    (labels, secondary data)
Text tertiary:         #5A5A56    (placeholders, disabled)
Text muted:            #3A3A36    (very low emphasis)

Status --- active:       #4A7C59    (muted green, not neon)
Status --- probationary: #7C6A2A    (muted amber)
Status --- quarantined:  #7C3A3A    (muted red)
Status --- in_flight:    #2A4A7C    (muted blue)
Status --- blocked:      #7C3A3A
Status --- completed:    #4A7C59
Status --- failed:       #7C5A2A

Accent (CTA only):     #E8E6DE    (off-white button --- no color accent)

```

### Typography

```
Font:           'Berkeley Mono' or 'JetBrains Mono' for data values
                'Geist' or 'Inter' for UI chrome (labels, nav)
                (Geist is acceptable here --- this is a dashboard, not a marketing site)

Monospace uses: All IDs, all UUIDs, delegation IDs, agent IDs, cost values, timestamps
Sans-serif uses: Navigation, labels, descriptions, button text

Type scale:
  Data value (large):  24px / 500
  Data value (medium): 16px / 400
  Table cell:          13px / 400
  Label / caption:     11px / 500 / letter-spacing: 0.08em
  Section heading:     14px / 500
  Page heading:        20px / 500

```

### Component patterns

**Stat card:**

```
┌─────────────────────┐
│ ACTIVE AGENTS       │  ← 11px label, tertiary color, caps
│                     │
│ 14                  │  ← 32px primary text
│ ↑ 2 from yesterday  │  ← 12px secondary, green if positive
└─────────────────────┘
Background: secondary. Border: 1px border color. Radius: 4px. No shadow.

```

**Status pill:**

```
active        → background: #1A2E22,  text: #4A7C59
probationary  → background: #2A2410,  text: #9A7A3A
quarantined   → background: #2A1414,  text: #9A4A4A
in_flight     → background: #141A2A,  text: #3A6A9A
completed     → background: #1A2E22,  text: #4A7C59
blocked       → background: #2A1414,  text: #9A4A4A
pending       → background: #2A2210,  text: #9A8A3A

```

**Table:**

-   Header: 11px label, tertiary text, border-bottom 1px.
-   Row: 13px, 40px height. Hover: background tertiary.
-   Striping: none --- hover state is sufficient.
-   Sortable columns: chevron icon on hover, filled on active sort direction.
-   Sticky header on scroll.

**Code/JSON blocks:**

-   Background: #0A0A08 (slightly darker than page).
-   Font: Berkeley Mono 12px.
-   Syntax highlighting: minimal --- strings off-white, keys secondary, numbers slightly lighter.
-   Copy button top-right corner.

**Empty state:**

-   Centered in the content area.
-   Icon (simple line icon, not illustrated).
-   Heading: "No [entity] found".
-   Subtext: context-specific explanation (e.g. "No delegations matched your filters. Try widening the time range.").
-   Optional CTA if actionable.

* * * * *

19\. Role-Based Access Control
------------------------------

RBAC is enforced both client-side (UI element visibility) and server-side (API returns 403 for unauthorized actions). Client-side gating is UX --- it hides buttons and edit controls. Server-side gating is security --- the dashboard never relies only on hiding elements.

| Action | admin | engineer | compliance | viewer |
| --- | --- | --- | --- | --- |
| View all dashboard views | ✓ | ✓ | ✓ | ✓ |
| Export audit log (CSV/JSON) | ✓ | ✓ | ✓ | --- |
| Generate compliance reports | ✓ | ✓ | ✓ | --- |
| Approve/reject HiTL | ✓ | ✓ | --- | --- |
| Quarantine/activate agent | ✓ | ✓ | --- | --- |
| Create/edit policy | ✓ | --- | --- | --- |
| Manage API keys | ✓ | --- | --- | --- |
| Manage team members | ✓ | --- | --- | --- |
| Configure webhooks | ✓ | --- | --- | --- |
| View billing | ✓ | --- | --- | --- |
| Delete organization | ✓ | --- | --- | --- |

The current user's role is included in the session token (JWT). The dashboard reads the role claim and gates UI elements accordingly.

* * * * *

20\. Empty States & Error States
--------------------------------

### Empty states by view

| View | Empty state message |
| --- | --- |
| Overview --- recent activity | "No delegations yet. Register an agent and make your first delegation." with link to docs. |
| Agent Registry | "No agents registered. Use the SDK to register your first agent." with code snippet. |
| Delegation Feed | "No delegations match your filters." or "No delegations in this time window." |
| Policy Engine | "No policies configured. A default allow-all policy is active." |
| HiTL Queue | "No delegations pending approval." with green checkmark. |
| Audit Log | "No audit events in this time window." |
| Anomalies | "No active circuit breakers. No anomalies detected." with green checkmark. |
| Trust Scores | Empty if no agents. Otherwise always has data once agents exist. |
| Compliance Export | Not applicable --- form is always shown. |

### Error states

**API error (non-200 response):**

-   Inline error banner within the affected component.
-   Message: "Failed to load [component name]. [Error code if available]."
-   Retry button.
-   Does not navigate away or break other components.

**Network error / timeout:**

-   Same pattern as API error.
-   Message: "Connection error. Check your network and retry."

**Auth error (401/403):**

-   Full-page redirect to login.
-   Toast on return: "Your session expired. Please sign in again."

**Rate limit (429):**

-   Component shows: "Rate limit reached. Retrying in Xs."
-   Automatic retry with backoff. Does not surface as an error to the user unless retry fails 3 times.

**Empty export (0 rows):**

-   Modal: "No data matches your export criteria. Try widening your date range or removing filters."
-   Does not trigger a download.

* * * * *

21\. Performance Requirements
-----------------------------

These are dashboard-specific targets. They assume the underlying API meets its SLAs from TDD §24.

| Metric | Target |
| --- | --- |
| Initial page load (LCP) | < 2.0s on 100 Mbps |
| Time to interactive | < 3.0s |
| Overview page full render | < 1.5s after data loads |
| Table render (25 rows) | < 100ms client-side |
| Audit log export (10,000 rows) | < 30s |
| HiTL approve/reject response | < 2s end-to-end (including API round-trip) |
| Client-side filter apply | Instant (< 16ms) --- all filtering is client-side after fetch |

**Bundle size:**

-   No heavy visualization libraries. Recharts only (already ~300KB gzipped).
-   No animation libraries.
-   Total JS bundle target: < 500KB gzipped.

**Caching:**

-   Agent registry cached in React state for the session. Re-fetched on page focus after 5-minute stale threshold.
-   Policy list cached similarly.
-   Delegation feed and audit log: never cached --- always fresh.

* * * * *

*Nexra Governance Dashboard Specification v1.0 --- March 2026 --- Confidential*