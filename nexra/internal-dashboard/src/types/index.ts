// ─── TypeScript Interfaces ───
// Mirrors backend Pydantic schemas and API responses.

// ── Organizations ──
export interface Organization {
  id: string;
  name: string;
  plan: 'starter' | 'growth' | 'enterprise';
  approval_url: string | null;
  created_at: string;
}

// ── Agents ──
export interface Agent {
  id: string;
  org_id: string;
  agent_id: string;
  name: string;
  description: string;
  capability_type: CapabilityType;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  webhook_url: string;
  pricing: { per_call_usd: number };
  sla: { p99_latency_ms: number; availability: number };
  is_public: boolean;
  trust_score: number;
  status: AgentStatus;
  delegation_count: number;
  created_at: string;
  updated_at: string;
}

export type AgentStatus = 'active' | 'probationary' | 'quarantined';
export type CapabilityType = 'research' | 'analysis' | 'generation' | 'enrichment' | 'validation' | 'execution' | 'other';

// ── Trust Score ──
export interface TrustBreakdown {
  trust_score: number;
  success_rate: number;
  sla_compliance: number;
  cost_accuracy: number;
  policy_violations_inverse: number;
  delegation_count: number;
  last_active: string | null;
}

export interface TrustScoreEvent {
  id: string;
  agent_id: string;
  delegation_id: string;
  score_before: number;
  score_after: number;
  components: {
    success_rate: number;
    sla_compliance: number;
    cost_accuracy: number;
    policy_violations_inverse: number;
  };
  created_at: string;
}

// ── Delegations ──
export interface Delegation {
  id: string;
  caller_org_id: string;
  caller_agent_id: string;
  callee_org_id: string | null;
  callee_agent_id: string;
  task: Record<string, unknown>;
  task_hash: string;
  context_scope: string[];
  policy_id: string | null;
  policy_version: number | null;
  policy_decision: PolicyDecision | null;
  status: DelegationStatus;
  result: Record<string, unknown> | null;
  budget_cap_usd: number | null;
  estimated_cost_usd: number | null;
  actual_cost_usd: number | null;
  latency_ms: number | null;
  llm_tokens: number | null;
  callback_url: string | null;
  created_at: string;
  completed_at: string | null;
}

export type DelegationStatus = 'pending' | 'in_flight' | 'completed' | 'failed' | 'timeout' | 'blocked' | 'pending_approval';
export type PolicyDecision = 'allow' | 'block' | 'pause';

// ── Policies ──
export interface Policy {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  priority: number;
  rule_yaml: string;
  version: number;
  enabled: boolean;
  created_at: string;
}

// ── Audit Log ──
export interface AuditEntry {
  id: string;
  delegation_id: string | null;
  org_id: string;
  event_type: AuditEventType;
  actor_agent_id: string | null;
  target_agent_id: string | null;
  details: Record<string, unknown>;
  cost_usd: number | null;
  created_at: string;
}

export type AuditEventType =
  | 'policy_evaluated'
  | 'delegation_initiated'
  | 'delegation_completed'
  | 'delegation_failed'
  | 'delegation_blocked'
  | 'delegation_timeout'
  | 'agent_quarantined'
  | 'agent_activated'
  | 'budget_exceeded'
  | 'hil_triggered'
  | 'hil_approved'
  | 'hil_expired'
  | 'anomaly_detected'
  | 'circuit_breaker_tripped';

// ── Agent Budget ──
export interface AgentBudget {
  agent_id: string;
  org_id: string;
  period: string;
  period_type: 'daily' | 'monthly';
  cap_usd: number;
  spent_usd: number;
}

// ── Analytics ──
export interface UsageStats {
  total_delegations: number;
  completed: number;
  failed: number;
  blocked: number;
  timed_out: number;
  success_rate: number;
  total_cost_usd: number;
  avg_latency_ms: number;
}

export interface UsageBucket {
  timestamp: string;
  completed: number;
  blocked: number;
  failed: number;
  total: number;
}

export interface SpendSummary {
  total_spend_usd: number;
  delegation_count: number;
  avg_cost_per_delegation: number;
  highest_spend_agent: { agent_id: string; spend_usd: number } | null;
  budget_utilization: number;
}

export interface AgentSpend {
  agent_id: string;
  delegation_count: number;
  total_spend_usd: number;
  avg_cost_usd: number;
  daily_cap_usd: number | null;
  monthly_cap_usd: number | null;
  utilization: number;
  anomaly_count: number;
}

// ── Paginated Response ──
export interface PaginatedResponse<T> {
  items: T[];
  cursor: string | null;
  has_more: boolean;
  total_count?: number;
}

// ── Health ──
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  components: {
    database: 'ok' | 'error';
    redis: 'ok' | 'error';
  };
  latency_ms: number;
}

// ── RBAC ──
export type UserRole = 'admin' | 'engineer' | 'compliance' | 'viewer';

export interface UserSession {
  org_id: string;
  org_name: string;
  plan: 'starter' | 'growth' | 'enterprise';
  role: UserRole;
  email: string;
}

// ── Time Range ──
export type TimeRange = 'last_hour' | 'last_24h' | 'last_7d' | 'last_30d' | 'custom';
