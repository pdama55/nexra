export interface RegisterParams {
  agent_id: string;
  name: string;
  description: string;
  capability_type: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  pricing: { per_call_usd: number };
  sla: { p99_latency_ms: number; availability: number };
  webhook_url: string;
  webhook_secret: string;
  is_public?: boolean;
}

export interface RegisterResult {
  agent_id: string;
  status: string;
  embedding_id: string | null;
  registered_at: string;
}

export interface AgentMatch {
  agent_id: string;
  name: string;
  match_score: number;
  trust_score: number;
  status: string;
  pricing: Record<string, unknown>;
  sla: Record<string, unknown>;
  is_cross_org: boolean;
  capability_type: string;
}

export interface DiscoverParams {
  query: string;
  capability_type?: string;
  budget_cap_usd?: number;
  max_latency_ms?: number;
  limit?: number;
}

export interface DelegateParams {
  callee_agent_id: string;
  task: Record<string, unknown>;
  context_scope?: string[];
  budget_cap_usd?: number;
  timeout_ms?: number;
  callback_url?: string;
}

export interface PolicyResult {
  policy_id: string | null;
  policy_version: number | null;
  decision: string;
}

export interface Usage {
  cost_usd: number;
  latency_ms: number;
  llm_tokens: number | null;
}

export interface DelegationResult {
  delegation_id: string;
  status: string;
  policy_result?: PolicyResult;
  result?: unknown;
  usage?: Usage;
  poll_url?: string;
}

export interface NexraClientOptions {
  apiKey: string;
  agentId: string;
  baseUrl?: string;
  timeout?: number;
}
