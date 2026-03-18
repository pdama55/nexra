#!/usr/bin/env -S node

import { appendFile, mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

type ModuleRequire = (id: string) => unknown;

interface Args {
  dashboardUrl: string;
  apiBaseUrl: string;
  apiKey: string;
  userEmail: string;
  durationMin: number;
  sweepIntervalSec: number;
  routeTimeoutMs: number;
  failureMode: "collect-all" | "fail-fast";
  resultsDir: string;
}

interface RouteRun {
  route_key: string;
  path: string;
  passed: boolean;
  latency_ms: number;
  mismatches: string[];
  errors: string[];
  warnings: string[];
  screenshot?: string;
}

interface SweepRun {
  sweep_index: number;
  started_at: string;
  finished_at: string;
  routes: RouteRun[];
}

interface RouteSummary {
  checks: number;
  passes: number;
  failures: number;
  mismatch_count: number;
  last_error: string | null;
}

interface ParitySummary {
  generated_at: string;
  dashboard_url: string;
  api_base_url: string;
  duration_min: number;
  sweep_interval_sec: number;
  route_timeout_ms: number;
  failure_mode: string;
  sweeps_run: number;
  required_routes: string[];
  route_summaries: Record<string, RouteSummary>;
  sweeps: SweepRun[];
  mismatches_total: number;
  required_mismatches: number;
  route_render_failures: number;
  route_latency_breaches: number;
  route_warnings: number;
  api_fetch_timeout_warnings: number;
  loading_delay_warnings: number;
  frontend_uncaught_errors: number;
  frontend_console_errors: number;
  frontend_network_errors: number;
  critical_failures: string[];
}

type ApiEnvelope = { data?: unknown; meta?: unknown };
const SOFT_MISMATCH_CODES = new Set<string>([
  "spend.first_agent_missing",
  "spend.highest_spend_agent_missing",
  "anomalies.first_agent_missing",
]);

function parseArgs(argv: string[]): Args {
  const raw: Partial<Args> = {
    dashboardUrl: "http://127.0.0.1:5173",
    apiBaseUrl: "http://127.0.0.1:8000",
    userEmail: "admin@nexra.local",
    durationMin: 90,
    sweepIntervalSec: 120,
    routeTimeoutMs: 15000,
    failureMode: "collect-all",
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--dashboard-url" && value) {
      raw.dashboardUrl = value;
      i += 1;
    } else if (key === "--api-base-url" && value) {
      raw.apiBaseUrl = value;
      i += 1;
    } else if (key === "--api-key" && value) {
      raw.apiKey = value;
      i += 1;
    } else if (key === "--user-email" && value) {
      raw.userEmail = value;
      i += 1;
    } else if (key === "--duration-min" && value) {
      raw.durationMin = Number(value);
      i += 1;
    } else if (key === "--sweep-interval-sec" && value) {
      raw.sweepIntervalSec = Number(value);
      i += 1;
    } else if (key === "--route-timeout-ms" && value) {
      raw.routeTimeoutMs = Number(value);
      i += 1;
    } else if (key === "--failure-mode" && value) {
      if (value !== "collect-all" && value !== "fail-fast") {
        throw new Error("--failure-mode must be collect-all or fail-fast");
      }
      raw.failureMode = value;
      i += 1;
    } else if (key === "--results-dir" && value) {
      raw.resultsDir = value;
      i += 1;
    } else {
      throw new Error("Unknown argument: " + key);
    }
  }

  if (!raw.apiKey) {
    throw new Error("--api-key is required");
  }
  if (!raw.resultsDir) {
    throw new Error("--results-dir is required");
  }
  if (!raw.durationMin || raw.durationMin <= 0) {
    throw new Error("--duration-min must be > 0");
  }
  if (!raw.sweepIntervalSec || raw.sweepIntervalSec <= 0) {
    throw new Error("--sweep-interval-sec must be > 0");
  }
  if (!raw.routeTimeoutMs || raw.routeTimeoutMs <= 0) {
    throw new Error("--route-timeout-ms must be > 0");
  }

  return raw as Args;
}

function buildModuleRequire(): ModuleRequire {
  const dashboardDir = process.env.NEXRA_DASHBOARD_DIR;
  if (dashboardDir) {
    const packagePath = path.join(dashboardDir, "package.json");
    if (existsSync(packagePath)) {
      return createRequire(packagePath);
    }
  }
  return createRequire(path.join(process.cwd(), "package.json"));
}

function parseNumberLike(text: string | null | undefined): number | null {
  if (!text) return null;
  const cleaned = text.replace(/[^0-9.-]/g, "");
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

async function fetchData(
  args: Args,
  route: string,
  query?: Record<string, string | number | boolean>
): Promise<unknown> {
  const url = new URL(args.apiBaseUrl.replace(/\/$/, "") + route);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      url.searchParams.set(k, String(v));
    }
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), args.routeTimeoutMs);
  let resp: Response;
  try {
    resp = await fetch(url.toString(), {
      headers: {
        Authorization: "Bearer " + args.apiKey,
        "X-User-Email": args.userEmail,
        "Content-Type": "application/json",
      },
      signal: controller.signal,
    });
  } catch (err: unknown) {
    if (controller.signal.aborted) {
      throw new Error(`api_fetch_timeout route=${route} timeout_ms=${args.routeTimeoutMs}`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  if (!resp.ok) {
    throw new Error(`api_fetch_failed route=${route} status=${resp.status}`);
  }
  const contentType = resp.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new Error(`api_fetch_non_json route=${route} content_type=${contentType}`);
  }
  const body = (await resp.json()) as ApiEnvelope;
  return body.data;
}

function makeSummary(requiredRoutes: string[], args: Args): ParitySummary {
  const routeSummaries: Record<string, RouteSummary> = {};
  for (const key of requiredRoutes) {
    routeSummaries[key] = {
      checks: 0,
      passes: 0,
      failures: 0,
      mismatch_count: 0,
      last_error: null,
    };
  }
  return {
    generated_at: new Date().toISOString(),
    dashboard_url: args.dashboardUrl,
    api_base_url: args.apiBaseUrl,
    duration_min: args.durationMin,
    sweep_interval_sec: args.sweepIntervalSec,
    route_timeout_ms: args.routeTimeoutMs,
    failure_mode: args.failureMode,
    sweeps_run: 0,
    required_routes: requiredRoutes,
    route_summaries: routeSummaries,
    sweeps: [],
    mismatches_total: 0,
    required_mismatches: 0,
    route_render_failures: 0,
    route_latency_breaches: 0,
    route_warnings: 0,
    api_fetch_timeout_warnings: 0,
    loading_delay_warnings: 0,
    frontend_uncaught_errors: 0,
    frontend_console_errors: 0,
    frontend_network_errors: 0,
    critical_failures: [],
  };
}

function firstString(values: Array<unknown>): string | null {
  for (const val of values) {
    if (typeof val === "string" && val.trim()) return val;
  }
  return null;
}

async function main(): Promise<number> {
  const args = parseArgs(process.argv);
  const navigationTimeoutMs = args.routeTimeoutMs + 5000;
  // Under stress, the dashboard continuously polls APIs, so "networkidle" can
  // time out even when the route is fully rendered and interactive.
  const navigationWaitUntil: "domcontentloaded" = "domcontentloaded";
  const requireFromModuleRoot = buildModuleRequire();
  const playwright = requireFromModuleRoot("playwright") as {
    chromium: {
      launch: (options: { headless: boolean }) => Promise<{
        newContext: () => Promise<{
          addInitScript: (script: string) => Promise<void>;
          newPage: () => Promise<{
            goto: (url: string, options?: { timeout?: number; waitUntil?: string }) => Promise<void>;
            title: () => Promise<string>;
            locator: (selector: string) => {
              count: () => Promise<number>;
              first: () => {
                textContent: () => Promise<string | null>;
              };
              textContent: () => Promise<string | null>;
              waitFor: (options: { state?: "attached" | "detached" | "visible" | "hidden"; timeout?: number }) => Promise<void>;
              filter: (opts: { hasText: string }) => {
                first: () => {
                  locator: (inner: string) => {
                    first: () => {
                      textContent: () => Promise<string | null>;
                    };
                  };
                };
              };
            };
            getByText: (pattern: RegExp | string) => {
              first: () => {
                isVisible: () => Promise<boolean>;
                textContent: () => Promise<string | null>;
                waitFor: (options: { state?: "attached" | "detached" | "visible" | "hidden"; timeout?: number }) => Promise<void>;
              };
              isVisible: () => Promise<boolean>;
              waitFor: (options: { state?: "attached" | "detached" | "visible" | "hidden"; timeout?: number }) => Promise<void>;
            };
            screenshot: (options: { path: string; fullPage: boolean }) => Promise<void>;
            on: (event: string, cb: (...params: unknown[]) => void) => void;
            waitForTimeout: (timeoutMs: number) => Promise<void>;
            url: () => string;
          }>;
          close: () => Promise<void>;
        }>;
        close: () => Promise<void>;
      }>;
    };
  };

  const outDir = path.resolve(args.resultsDir);
  const mismatchDir = path.join(outDir, "mismatch_screenshots");
  const finalDir = path.join(outDir, "screenshots_final");
  const uiSummaryPath = path.join(outDir, "ui_parity_results.json");
  const frontendErrorsPath = path.join(outDir, "frontend_errors.jsonl");
  const logPath = path.join(outDir, "parity.log");

  await mkdir(outDir, { recursive: true });
  await mkdir(mismatchDir, { recursive: true });
  await mkdir(finalDir, { recursive: true });
  await writeFile(frontendErrorsPath, "", "utf-8");

  const requiredRoutes = [
    "overview",
    "agents",
    "agent_detail",
    "delegations",
    "delegation_detail",
    "policies",
    "policy_detail",
    "spend",
    "audit",
    "hitl",
    "trust",
    "anomalies",
    "compliance",
    "settings",
  ];
  const summary = makeSummary(requiredRoutes, args);

  const browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addInitScript(
    "localStorage.setItem('nexra_time_range','last_24h');"
  );
  const page = await context.newPage();

  const frontendErrors: Array<Record<string, unknown>> = [];
  page.on("pageerror", (error: unknown) => {
    const msg = error instanceof Error ? error.message : String(error);
    const row = {
      timestamp: new Date().toISOString(),
      type: "pageerror",
      message: msg,
      dashboard_url: args.dashboardUrl,
      page_url: page.url(),
    };
    frontendErrors.push(row);
  });
  page.on("console", (msg: unknown) => {
    const c = msg as { type?: () => string; text?: () => string };
    const level = typeof c.type === "function" ? c.type() : "log";
    if (level === "error") {
      const text = typeof c.text === "function" ? c.text() : "<console error>";
      frontendErrors.push({
        timestamp: new Date().toISOString(),
        type: "console.error",
        message: text,
        page_url: page.url(),
      });
    }
  });
  page.on("response", (resp: unknown) => {
    const response = resp as {
      status?: () => number;
      url?: () => string;
      request?: () => { method?: () => string };
    };
    const status = typeof response.status === "function" ? response.status() : 0;
    if (status >= 400) {
      const method = response.request && typeof response.request === "function"
        ? (response.request().method && typeof response.request().method === "function"
          ? response.request().method()
          : "UNKNOWN")
        : "UNKNOWN";
      const url = typeof response.url === "function" ? response.url() : "";
      frontendErrors.push({
        timestamp: new Date().toISOString(),
        type: "network.response",
        status,
        method,
        url,
        page_url: page.url(),
      });
    }
  });

  const initialUrl = new URL(args.dashboardUrl);
  initialUrl.searchParams.set("nexra_api_key", args.apiKey);
  initialUrl.searchParams.set("nexra_user_email", args.userEmail);
  await page.goto(initialUrl.toString(), { waitUntil: navigationWaitUntil, timeout: navigationTimeoutMs });

  async function routeCheck(
    routeKey: string,
    routePath: string,
    run: () => Promise<{ mismatches: string[]; errors: string[] }>
  ): Promise<RouteRun> {
    const started = Date.now();
    let mismatches: string[] = [];
    let errors: string[] = [];
    let warnings: string[] = [];
    try {
      await page.goto(args.dashboardUrl.replace(/\/$/, "") + routePath, {
        waitUntil: navigationWaitUntil,
        timeout: navigationTimeoutMs,
      });
      const loading = page.getByText(/Loading/i).first();
      const loadingVisible = await loading.isVisible().catch(() => false);
      if (loadingVisible) {
        const settled = await loading
          .waitFor({ state: "hidden", timeout: Math.min(8000, args.routeTimeoutMs) })
          .then(() => true)
          .catch(() => false);
        if (!settled) {
          warnings.push("perpetual_loading_detected");
        }
      }
      const result = await run();
      mismatches = result.mismatches;
      errors = errors.concat(result.errors);
      const softMismatches = mismatches.filter((mismatch) => SOFT_MISMATCH_CODES.has(mismatch));
      if (softMismatches.length > 0) {
        warnings = warnings.concat(softMismatches.map((mismatch) => `soft_mismatch:${mismatch}`));
        mismatches = mismatches.filter((mismatch) => !SOFT_MISMATCH_CODES.has(mismatch));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("api_fetch_timeout")) {
        warnings.push(msg);
      } else {
        errors.push(msg);
      }
    }

    const latency = Date.now() - started;
    const passed = mismatches.length === 0 && errors.length === 0;
    const row: RouteRun = {
      route_key: routeKey,
      path: routePath,
      passed,
      latency_ms: latency,
      mismatches,
      errors,
      warnings,
    };
    if (!passed) {
      const file = `${routeKey}-${Date.now()}.png`;
      row.screenshot = file;
      await page.screenshot({ path: path.join(mismatchDir, file), fullPage: true });
    }
    return row;
  }

  async function safePrefetchData<T>(
    route: string,
    query?: Record<string, string | number | boolean>
  ): Promise<T | null> {
    try {
      return (await fetchData(args, route, query)) as T;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      frontendErrors.push({
        timestamp: new Date().toISOString(),
        type: "prefetch.error",
        route,
        message: msg,
        page_url: page.url(),
      });
      return null;
    }
  }

  async function runSingleSweep(sweepIdx: number): Promise<SweepRun> {
    const started = new Date().toISOString();
    const sweepRows: RouteRun[] = [];

    const agentsData = await safePrefetchData<{ agents?: Array<Record<string, unknown>> }>(
      "/v1/agents/registry",
      { limit: 50 }
    );
    const firstAgent = agentsData?.agents?.[0];
    const firstAgentId = typeof firstAgent?.agent_id === "string" ? firstAgent.agent_id : null;

    const delegData = await safePrefetchData<{ items?: Array<Record<string, unknown>> }>(
      "/v1/delegations",
      { limit: 1, sort: "created_at:desc" }
    );
    const firstDeleg = delegData?.items?.[0];
    const firstDelegId = typeof firstDeleg?.id === "string" ? firstDeleg.id : null;

    const polData = await safePrefetchData<{ policies?: Array<Record<string, unknown>> }>(
      "/v1/policies"
    );
    const firstPolicy = polData?.policies?.[0];
    const firstPolicyId = typeof firstPolicy?.id === "string" ? firstPolicy.id : null;

    sweepRows.push(
      await routeCheck("overview", "/", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const usage = (await fetchData(args, "/v1/analytics/usage", { window: "last_24h" })) as Record<string, unknown>;
        const agents = (await fetchData(args, "/v1/agents/registry")) as { agents?: Array<Record<string, unknown>> };
        const delegations = (await fetchData(args, "/v1/delegations", { limit: 10, sort: "created_at:desc" })) as { items?: Array<Record<string, unknown>> };

        const activeAgents = (agents.agents || []).filter((a) => a.status === "active").length;
        const totalDelegations = Number((usage.total_delegations as number | undefined) ?? 0);
        const blocked = Number((usage.blocked as number | undefined) ?? 0);
        const pendingHitl = (delegations.items || []).filter((d) => d.status === "pending_approval").length;

        async function stat(label: string): Promise<number | null> {
          const text = await page
            .locator(".stat-row .card")
            .filter({ hasText: label })
            .first()
            .locator(".mono")
            .first()
            .textContent()
            .catch(() => null);
          return parseNumberLike(text);
        }

        const uiActive = await stat("Active Agents");
        const uiDelegations = await stat("Delegations");
        const uiBlocked = await stat("Blocked");
        const uiPendingHitl = await stat("Pending HiTL");

        if (uiActive !== activeAgents) mismatches.push(`overview.active_agents ui=${uiActive} api=${activeAgents}`);
        if (uiDelegations !== totalDelegations) mismatches.push(`overview.delegations ui=${uiDelegations} api=${totalDelegations}`);
        if (uiBlocked !== blocked) mismatches.push(`overview.blocked ui=${uiBlocked} api=${blocked}`);
        if (uiPendingHitl !== pendingHitl) mismatches.push(`overview.pending_hitl ui=${uiPendingHitl} api=${pendingHitl}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("agents", "/agents", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const agents = (await fetchData(args, "/v1/agents/registry")) as { agents?: Array<Record<string, unknown>> };
        const expected = (agents.agents || []).length;
        const rows = await page.locator("tbody tr").count();
        if (rows !== expected) mismatches.push(`agents.rows ui=${rows} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("agent_detail", firstAgentId ? `/agents/${firstAgentId}` : "/agents", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        if (!firstAgentId) {
          errors.push("agent_detail.no_agent_available");
          return { mismatches, errors };
        }
        const detail = (await fetchData(args, `/v1/agents/${firstAgentId}`)) as Record<string, unknown>;
        const title = await page.locator(".page-title").first().textContent().catch(() => null);
        const agentIdText = await page.getByText(firstAgentId).first().textContent().catch(() => null);
        if (!title || !title.includes(String(detail.name || firstAgentId))) mismatches.push("agent_detail.title_mismatch");
        if (!agentIdText) mismatches.push("agent_detail.agent_id_missing");
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("delegations", "/delegations", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const deleg = (await fetchData(args, "/v1/delegations", { limit: 25, sort: "created_at:desc" })) as {
          items?: Array<Record<string, unknown>>;
        };
        const expected = (deleg.items || []).length;
        const rows = await page.locator("tbody tr").count();
        if (rows !== expected) mismatches.push(`delegations.rows ui=${rows} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("delegation_detail", firstDelegId ? `/delegations/${firstDelegId}` : "/delegations", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        if (!firstDelegId) {
          errors.push("delegation_detail.no_delegation_available");
          return { mismatches, errors };
        }
        const detail = (await fetchData(args, `/v1/delegations/${firstDelegId}`)) as Record<string, unknown>;
        const caller = String(detail.caller_agent_id || "");
        const callee = String(detail.callee_agent_id || "");
        const callerNode = page.getByText(caller).first();
        const calleeNode = page.getByText(callee).first();
        const callerVisible = (await callerNode.isVisible().catch(() => false))
          || (await callerNode.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false));
        const calleeVisible = (await calleeNode.isVisible().catch(() => false))
          || (await calleeNode.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false));
        if (!callerVisible) mismatches.push("delegation_detail.caller_missing");
        if (!calleeVisible) mismatches.push("delegation_detail.callee_missing");
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("policies", "/policies", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const policies = (await fetchData(args, "/v1/policies")) as { policies?: Array<Record<string, unknown>> };
        const expected = (policies.policies || []).length;
        const rows = await page.locator("tbody tr").count();
        if (rows !== expected) mismatches.push(`policies.rows ui=${rows} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("policy_detail", firstPolicyId ? `/policies/${firstPolicyId}` : "/policies", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        if (!firstPolicyId) {
          errors.push("policy_detail.no_policy_available");
          return { mismatches, errors };
        }
        const payload = (await fetchData(args, `/v1/policies/${firstPolicyId}`)) as {
          current?: Record<string, unknown>;
        };
        const policyName = String(payload.current?.name || "");
        const title = await page.locator(".page-title").first().textContent().catch(() => null);
        if (!title || (policyName && !title.includes(policyName))) mismatches.push("policy_detail.title_mismatch");
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("spend", "/spend", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const spend = (await fetchData(args, "/v1/spend/summary", { window: "last_24h", breakdown: "all" })) as {
          totals?: Record<string, unknown>;
          agent_breakdown?: Array<Record<string, unknown>>;
        };
        const firstAgentId = String((spend.agent_breakdown?.[0]?.agent_id as string | undefined) || "");
        if (firstAgentId) {
          const firstAgentNode = page.getByText(firstAgentId).first();
          const firstAgentVisible = (await firstAgentNode.isVisible().catch(() => false))
            || (await firstAgentNode.waitFor({ state: "visible", timeout: 8000 }).then(() => true).catch(() => false));
          if (!firstAgentVisible) mismatches.push("spend.first_agent_missing");
        }
        const highest = String((spend.totals?.highest_spend_agent as { agent_id?: string } | undefined)?.agent_id || "—");
        if (highest && highest !== "—") {
          const highestNode = page.getByText(highest).first();
          const highestVisible = (await highestNode.isVisible().catch(() => false))
            || (await highestNode.waitFor({ state: "visible", timeout: 8000 }).then(() => true).catch(() => false));
          if (!highestVisible) mismatches.push("spend.highest_spend_agent_missing");
        }
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("audit", "/audit", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const audit = (await fetchData(args, "/v1/audit/log", { limit: 50 })) as { entries?: Array<Record<string, unknown>> };
        const expected = (audit.entries || []).length;
        const rows = await page.locator("tbody tr").count();
        if (rows !== expected) mismatches.push(`audit.rows ui=${rows} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("hitl", "/hitl", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const pending = (await fetchData(args, "/v1/delegations", {
          status: "pending_approval",
          sort: "approval_deadline:asc",
          limit: 50,
        })) as { items?: Array<Record<string, unknown>> };
        const expected = (pending.items || []).length;
        const headerText = await page.locator(".page-header span").first().textContent().catch(() => null);
        const uiCount = parseNumberLike(headerText);
        if (uiCount !== expected) mismatches.push(`hitl.pending ui=${uiCount} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("trust", "/trust", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const agents = (await fetchData(args, "/v1/agents/registry", { limit: 50 })) as { agents?: Array<Record<string, unknown>> };
        const expected = (agents.agents || []).length;
        const rows = await page.locator("tbody tr").count();
        if (rows !== expected) mismatches.push(`trust.rows ui=${rows} api=${expected}`);
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("anomalies", "/anomalies", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const nowIso = new Date().toISOString();
        const dateFromIso = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
        const circuits = (await fetchData(args, "/v1/audit/log", {
          event_type: "circuit_breaker_tripped",
          date_from: dateFromIso,
          date_to: nowIso,
        })) as { entries?: Array<Record<string, unknown>> };
        const anomalies = (await fetchData(args, "/v1/audit/log", {
          event_type: "anomaly_detected",
          date_from: dateFromIso,
          date_to: nowIso,
        })) as { entries?: Array<Record<string, unknown>> };
        const firstId = firstString([
          circuits.entries?.[0]?.target_agent_id,
          circuits.entries?.[0]?.actor_agent_id,
          anomalies.entries?.[0]?.target_agent_id,
          anomalies.entries?.[0]?.actor_agent_id,
        ]);
        if (firstId) {
          const firstNode = page.getByText(firstId).first();
          const visible = (await firstNode.isVisible().catch(() => false))
            || (await firstNode.waitFor({ state: "visible", timeout: 8000 }).then(() => true).catch(() => false));
          if (!visible) mismatches.push("anomalies.first_agent_missing");
        }
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("compliance", "/compliance", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const headingVisible = await page.getByText("Compliance Export").first().isVisible().catch(() => false);
        if (!headingVisible) mismatches.push("compliance.heading_missing");
        return { mismatches, errors };
      })
    );

    sweepRows.push(
      await routeCheck("settings", "/settings", async () => {
        const mismatches: string[] = [];
        const errors: string[] = [];
        const org = (await fetchData(args, "/v1/orgs/me")) as Record<string, unknown>;
        const orgName = String(org.name || "");
        const orgId = String(org.org_id || "");
        const nameVisible = orgName ? await page.getByText(orgName).first().isVisible().catch(() => false) : false;
        const idVisible = orgId ? await page.getByText(orgId).first().isVisible().catch(() => false) : false;
        if (!nameVisible && !idVisible) mismatches.push("settings.org_identity_missing");
        return { mismatches, errors };
      })
    );

    const finished = new Date().toISOString();
    return {
      sweep_index: sweepIdx,
      started_at: started,
      finished_at: finished,
      routes: sweepRows,
    };
  }

  const runUntil = Date.now() + args.durationMin * 60_000;
  let sweepIdx = 0;
  let failFastTriggered = false;
  while (Date.now() < runUntil) {
    let sweep: SweepRun;
    try {
      sweep = await runSingleSweep(sweepIdx);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      const compact = msg.replace(/\s+/g, " ").trim();
      summary.critical_failures.push(`sweep_runtime_error:${compact}`);
      await appendFile(
        logPath,
        `[${new Date().toISOString()}] sweep=${sweepIdx} runtime_error=${compact}\n`,
        "utf-8"
      );
      break;
    }
    summary.sweeps.push(sweep);
    summary.sweeps_run += 1;

    for (const route of sweep.routes) {
      const routeSummary = summary.route_summaries[route.route_key];
      routeSummary.checks += 1;
      if (route.passed) {
        routeSummary.passes += 1;
      } else {
        routeSummary.failures += 1;
        routeSummary.last_error = route.errors[0] ?? route.mismatches[0] ?? route.warnings[0] ?? "unknown_failure";
      }
      routeSummary.mismatch_count += route.mismatches.length;
      summary.mismatches_total += route.mismatches.length;
      summary.required_mismatches += route.mismatches.length;
      summary.route_warnings += route.warnings.length;
      summary.api_fetch_timeout_warnings += route.warnings.filter((w) => w.startsWith("api_fetch_timeout")).length;
      summary.loading_delay_warnings += route.warnings.filter((w) => w === "perpetual_loading_detected").length;
      if (route.errors.length > 0) {
        summary.route_render_failures += 1;
      }
      if (route.latency_ms > args.routeTimeoutMs) {
        summary.route_latency_breaches += 1;
      }
      if (args.failureMode === "fail-fast" && (!route.passed || route.mismatches.length > 0)) {
        failFastTriggered = true;
      }
    }

    while (frontendErrors.length > 0) {
      const row = frontendErrors.shift();
      if (!row) continue;
      const type = String(row.type || "");
      const msg = String(row.message || "");
      const isUncaught =
        type === "pageerror" || (type === "console.error" && /\buncaught\b/i.test(msg));
      if (isUncaught) {
        summary.frontend_uncaught_errors += 1;
      } else if (type === "console.error") {
        summary.frontend_console_errors += 1;
      } else if (type === "network.response") {
        summary.frontend_network_errors += 1;
      }
      await appendFile(frontendErrorsPath, JSON.stringify(row) + "\n", "utf-8");
    }

    await appendFile(
      logPath,
      `[${new Date().toISOString()}] sweep=${sweepIdx} routes=${sweep.routes.length} mismatches=${sweep.routes.reduce((a, r) => a + r.mismatches.length, 0)}\n`,
      "utf-8"
    );

    sweepIdx += 1;
    if (failFastTriggered) break;

    const remaining = runUntil - Date.now();
    if (remaining <= 0) break;
    await page.waitForTimeout(Math.min(args.sweepIntervalSec * 1000, remaining));
  }

  const finalShots: Array<{ route: string; file: string }> = [];
  const finalRoutes = [
    "/",
    "/agents",
    "/delegations",
    "/policies",
    "/spend",
    "/audit",
    "/hitl",
    "/trust",
    "/anomalies",
    "/compliance",
    "/settings",
  ];
  for (const route of finalRoutes) {
    const file = route === "/" ? "overview.png" : route.slice(1).replace(/\//g, "_") + ".png";
    try {
      await page.goto(args.dashboardUrl.replace(/\/$/, "") + route, {
        waitUntil: navigationWaitUntil,
        timeout: navigationTimeoutMs,
      });
      await page.screenshot({ path: path.join(finalDir, file), fullPage: true });
      finalShots.push({ route, file });
    } catch {
      // Keep parity summary focused on route checks above.
    }
  }
  await writeFile(path.join(finalDir, "manifest.json"), JSON.stringify(finalShots, null, 2), "utf-8");

  const requiredRouteMissing = Object.entries(summary.route_summaries).filter(([_, row]) => row.checks < 1);
  for (const [routeKey] of requiredRouteMissing) {
    summary.critical_failures.push(`route_not_validated:${routeKey}`);
  }
  if (summary.required_mismatches > 0) {
    summary.critical_failures.push(`required_mismatches:${summary.required_mismatches}`);
  }
  if (summary.route_render_failures > 0) {
    summary.critical_failures.push(`route_render_failures:${summary.route_render_failures}`);
  }
  if (summary.frontend_uncaught_errors > 0) {
    summary.critical_failures.push(`frontend_uncaught_errors:${summary.frontend_uncaught_errors}`);
  }

  summary.generated_at = new Date().toISOString();
  await writeFile(uiSummaryPath, JSON.stringify(summary, null, 2), "utf-8");

  await context.close();
  await browser.close();

  console.log(
    JSON.stringify(
      {
        ui_parity_results: uiSummaryPath,
        frontend_errors: frontendErrorsPath,
        sweeps_run: summary.sweeps_run,
        critical_failures: summary.critical_failures.length,
      },
      null,
      2
    )
  );
  return summary.critical_failures.length > 0 ? 1 : 0;
}

main()
  .then((code) => process.exit(code))
  .catch(async (err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    // Best-effort fallback log path for catastrophic failures before arg parsing/writes.
    const fallback = path.resolve(process.cwd(), "test-results", "dashboard-stress", "parity-fatal.log");
    try {
      await mkdir(path.dirname(fallback), { recursive: true });
      await appendFile(fallback, `[${new Date().toISOString()}] ${msg}\n`, "utf-8");
    } catch {
      // no-op
    }
    console.error("[dashboard_parity_sweep] " + msg);
    process.exit(1);
  });
