import type {
  AgentMatch,
  DelegateParams,
  DelegationResult,
  DiscoverParams,
  NexraClientOptions,
  RegisterParams,
  RegisterResult,
} from "./types.js";

export class NexraClient {
  private baseUrl: string;
  private headers: Record<string, string>;
  private timeout: number;

  constructor(options: NexraClientOptions) {
    this.baseUrl = options.baseUrl ?? "https://api.usenexra.com/v1";
    this.timeout = options.timeout ?? 60000;
    this.headers = {
      Authorization: `Bearer ${options.apiKey}`,
      "X-Agent-ID": options.agentId,
      "Content-Type": "application/json",
    };
  }

  async register(params: RegisterParams): Promise<RegisterResult> {
    const resp = await this.post("/agents/register", params);
    return resp.data as RegisterResult;
  }

  async discover(params: DiscoverParams): Promise<AgentMatch[]> {
    const resp = await this.post("/capabilities/discover", params);
    return (resp.data as { matches: AgentMatch[] }).matches;
  }

  async delegate(params: DelegateParams): Promise<DelegationResult> {
    const resp = await this.post("/delegate", params);
    return resp.data as DelegationResult;
  }

  async hire(
    capability: string,
    task: Record<string, unknown>,
    budgetCap = 1.0,
    contextScope?: string[]
  ): Promise<DelegationResult> {
    const matches = await this.discover({ query: capability, limit: 1 });
    if (matches.length === 0) {
      throw new Error(`No agents found for capability: ${capability}`);
    }
    return this.delegate({
      callee_agent_id: matches[0].agent_id,
      task,
      budget_cap_usd: budgetCap,
      context_scope: contextScope,
    });
  }

  async getDelegation(delegationId: string): Promise<DelegationResult> {
    const resp = await this.get(`/delegations/${delegationId}`);
    return resp.data as DelegationResult;
  }

  private async post(path: string, body: unknown): Promise<{ data: unknown }> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    try {
      const resp = await fetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const errorBody = await resp.json().catch(() => ({}));
        throw new NexraAPIError(
          resp.status,
          (errorBody as { error?: { code?: string } }).error?.code ?? "UNKNOWN",
          (errorBody as { error?: { message?: string } }).error?.message ?? resp.statusText
        );
      }

      return (await resp.json()) as { data: unknown };
    } finally {
      clearTimeout(id);
    }
  }

  private async get(path: string): Promise<{ data: unknown }> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), this.timeout);

    try {
      const resp = await fetch(`${this.baseUrl}${path}`, {
        method: "GET",
        headers: this.headers,
        signal: controller.signal,
      });

      if (!resp.ok) {
        const errorBody = await resp.json().catch(() => ({}));
        throw new NexraAPIError(
          resp.status,
          (errorBody as { error?: { code?: string } }).error?.code ?? "UNKNOWN",
          (errorBody as { error?: { message?: string } }).error?.message ?? resp.statusText
        );
      }

      return (await resp.json()) as { data: unknown };
    } finally {
      clearTimeout(id);
    }
  }
}

export class NexraAPIError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly code: string,
    message: string
  ) {
    super(`[${statusCode}] ${code}: ${message}`);
    this.name = "NexraAPIError";
  }
}
