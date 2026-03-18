#!/usr/bin/env -S node

import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

interface Args {
  baseUrl: string;
  apiKey: string;
  userEmail: string;
  outDir: string;
  timelinePath: string;
  eventsPath: string;
  summaryPath: string;
  minCheckpointCoverage: number;
  strictCheckpoints: boolean;
  headed: boolean;
}

interface TimelineAct {
  minute: string;
  act_id: string;
  panel: string;
  checkpoint: string;
  talking_point: string;
  expected_events: string[];
}

interface TimelineMarker {
  act_id: string;
  minute: string;
  panel: string;
  route: string;
  screenshot: string;
  checkpoint: string;
  checkpoint_seen: boolean;
  expected_events: string[];
  missing_events: string[];
  talking_point: string;
}

interface CheckpointSummary {
  generated_at: string;
  checkpoints_total: number;
  checkpoints_seen: number;
  checkpoints_missing: number;
  coverage_ratio: number;
  min_required_coverage: number;
  strict_mode: boolean;
  strict_gate_passed: boolean;
  missing_by_act: Array<{
    act_id: string;
    checkpoint: string;
    missing_events: string[];
  }>;
}

type ModuleRequire = (id: string) => unknown;

function parseArgs(argv: string[]): Args {
  const raw: {
    baseUrl: string;
    apiKey?: string;
    userEmail: string;
    outDir: string;
    timelinePath: string;
    eventsPath: string;
    summaryPath: string;
    minCheckpointCoverage: number;
    strictCheckpoints: boolean;
    headed: boolean;
  } = {
    baseUrl: "http://127.0.0.1:5173",
    userEmail: "admin@nexra.local",
    outDir: "test-results/vc-demo/screenshots",
    timelinePath: "demo/vc_timeline.yaml",
    eventsPath: "test-results/vc-demo/integration_events.jsonl",
    summaryPath: "",
    minCheckpointCoverage: 1.0,
    strictCheckpoints: false,
    headed: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--base-url" && value) {
      raw.baseUrl = value;
      i += 1;
    } else if (key === "--api-key" && value) {
      raw.apiKey = value;
      i += 1;
    } else if (key === "--user-email" && value) {
      raw.userEmail = value;
      i += 1;
    } else if (key === "--out-dir" && value) {
      raw.outDir = value;
      i += 1;
    } else if (key === "--timeline" && value) {
      raw.timelinePath = value;
      i += 1;
    } else if (key === "--events-path" && value) {
      raw.eventsPath = value;
      i += 1;
    } else if (key === "--summary-path" && value) {
      raw.summaryPath = value;
      i += 1;
    } else if (key === "--min-checkpoint-coverage" && value) {
      const parsed = Number(value);
      if (Number.isNaN(parsed) || parsed < 0 || parsed > 1) {
        throw new Error("--min-checkpoint-coverage must be a number between 0 and 1");
      }
      raw.minCheckpointCoverage = parsed;
      i += 1;
    } else if (key === "--strict-checkpoints") {
      raw.strictCheckpoints = true;
    } else if (key === "--headed") {
      raw.headed = true;
    } else {
      throw new Error("Unknown argument: " + key);
    }
  }

  if (!raw.apiKey || typeof raw.apiKey !== "string") {
    throw new Error("--api-key is required");
  }

  const summaryPath =
    raw.summaryPath && typeof raw.summaryPath === "string"
      ? raw.summaryPath
      : path.join(raw.outDir, "checkpoint_summary.json");

  return {
    baseUrl: raw.baseUrl,
    apiKey: raw.apiKey,
    userEmail: raw.userEmail,
    outDir: raw.outDir,
    timelinePath: raw.timelinePath,
    eventsPath: raw.eventsPath,
    summaryPath,
    minCheckpointCoverage: raw.minCheckpointCoverage,
    strictCheckpoints: raw.strictCheckpoints,
    headed: raw.headed,
  }
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

async function loadTimeline(timelinePath: string): Promise<TimelineAct[]> {
  const requireFromModuleRoot = buildModuleRequire();
  const yaml = requireFromModuleRoot("yaml") as { parse: (source: string) => unknown };
  const raw = await readFile(timelinePath, "utf-8");
  const doc = yaml.parse(raw) as { acts?: TimelineAct[] };
  if (!doc || !Array.isArray(doc.acts)) {
    throw new Error("Invalid timeline file: " + timelinePath);
  }
  return doc.acts.map((act) => ({ ...act, expected_events: act.expected_events ?? [] }));
}

function routeForPanel(panel: string): string {
  const key = panel.toLowerCase();
  if (key.includes("agent")) return "/agents";
  if (key.includes("delegation") || key.includes("api trace")) return "/delegations";
  if (key.includes("polic")) return "/policies";
  if (key.includes("trust")) return "/trust";
  if (key.includes("anomal")) return "/anomalies";
  if (key.includes("audit")) return "/audit";
  if (key.includes("compliance")) return "/compliance";
  if (key.includes("marketplace") || key.includes("settings")) return "/settings";
  return "/";
}

function collectEventNames(raw: string): Set<string> {
  const names = new Set<string>();
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      const parsed = JSON.parse(trimmed) as { event?: unknown };
      if (typeof parsed.event === "string" && parsed.event) {
        names.add(parsed.event);
      }
    } catch {
      // Ignore malformed lines.
    }
  }
  return names;
}

async function findMissingEvents(eventsPath: string, expectedEvents: string[]): Promise<string[]> {
  if (expectedEvents.length === 0) {
    return [];
  }

  try {
    const raw = await readFile(eventsPath, "utf-8");
    const names = collectEventNames(raw);
    return expectedEvents.filter((ev) => !names.has(ev));
  } catch {
    return expectedEvents;
  }
}

async function waitForCheckpoint(
  eventsPath: string,
  expectedEvents: string[],
  timeoutMs = 15000
): Promise<string[]> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const missing = await findMissingEvents(eventsPath, expectedEvents);
    if (missing.length === 0) {
      return [];
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return findMissingEvents(eventsPath, expectedEvents);
}

function buildCheckpointSummary(
  markers: TimelineMarker[],
  minRequiredCoverage: number,
  strictMode: boolean
): CheckpointSummary {
  const checkpointsTotal = markers.length;
  const checkpointsSeen = markers.filter((m) => m.checkpoint_seen).length;
  const coverageRatio = checkpointsTotal === 0 ? 1 : Number((checkpointsSeen / checkpointsTotal).toFixed(4));
  const strictGatePassed = coverageRatio >= minRequiredCoverage;

  return {
    generated_at: new Date().toISOString(),
    checkpoints_total: checkpointsTotal,
    checkpoints_seen: checkpointsSeen,
    checkpoints_missing: checkpointsTotal - checkpointsSeen,
    coverage_ratio: coverageRatio,
    min_required_coverage: minRequiredCoverage,
    strict_mode: strictMode,
    strict_gate_passed: strictGatePassed,
    missing_by_act: markers
      .filter((m) => !m.checkpoint_seen)
      .map((m) => ({
        act_id: m.act_id,
        checkpoint: m.checkpoint,
        missing_events: m.missing_events,
      })),
  };
}

async function main(): Promise<number> {
  const args = parseArgs(process.argv);
  const requireFromModuleRoot = buildModuleRequire();
  await mkdir(args.outDir, { recursive: true });

  const timeline = await loadTimeline(args.timelinePath);
  const playwright = requireFromModuleRoot("playwright") as {
    chromium: {
      launch: (options: { headless: boolean }) => Promise<{
        newContext: (options: { viewport: { width: number; height: number } }) => Promise<{
          newPage: () => Promise<{
            goto: (url: string, options?: { waitUntil?: string }) => Promise<void>;
            waitForTimeout: (timeoutMs: number) => Promise<void>;
            screenshot: (options: { path: string; fullPage: boolean }) => Promise<void>;
          }>;
          close: () => Promise<void>;
        }>;
        close: () => Promise<void>;
      }>;
    };
  };
  const browser = await playwright.chromium.launch({ headless: !args.headed });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const initialUrl = new URL(args.baseUrl);
  initialUrl.searchParams.set("nexra_api_key", args.apiKey);
  initialUrl.searchParams.set("nexra_user_email", args.userEmail);

  const markers: TimelineMarker[] = [];
  const logPath = path.join(args.outDir, "autoplay.log");
  await appendFile(
    logPath,
    "[" + new Date().toISOString() + "] starting autoplay at " + initialUrl.toString() + "\n",
    "utf-8"
  );

  await page.goto(initialUrl.toString(), { waitUntil: "networkidle" });

  for (let idx = 0; idx < timeline.length; idx += 1) {
    const act = timeline[idx];
    const route = routeForPanel(act.panel);
    const routeUrl = args.baseUrl.replace(/\/$/, "") + route;
    await page.goto(routeUrl, { waitUntil: "networkidle" });

    const missingEvents = await waitForCheckpoint(args.eventsPath, act.expected_events, 12000);
    const checkpointSeen = missingEvents.length === 0;
    await page.waitForTimeout(1200);

    const fileName = String(idx + 1).padStart(2, "0") + "-" + act.act_id + ".png";
    const filePath = path.join(args.outDir, fileName);
    await page.screenshot({ path: filePath, fullPage: true });

    markers.push({
      act_id: act.act_id,
      minute: act.minute,
      panel: act.panel,
      route,
      screenshot: fileName,
      checkpoint: act.checkpoint,
      checkpoint_seen: checkpointSeen,
      expected_events: act.expected_events,
      missing_events: missingEvents,
      talking_point: act.talking_point,
    });

    if (!checkpointSeen) {
      await appendFile(
        logPath,
        "[" +
          new Date().toISOString() +
          "] checkpoint not fully resolved for " +
          act.act_id +
          "; missing events=" +
          missingEvents.join(",") +
          "\n",
        "utf-8"
      );
    }
  }

  const summary = buildCheckpointSummary(markers, args.minCheckpointCoverage, args.strictCheckpoints);

  await writeFile(
    path.join(args.outDir, "timeline_markers.json"),
    JSON.stringify(markers, null, 2),
    "utf-8"
  );
  await writeFile(args.summaryPath, JSON.stringify(summary, null, 2), "utf-8");
  await appendFile(
    logPath,
    "[" +
      new Date().toISOString() +
      "] completed autoplay (" +
      markers.length +
      " captures); coverage=" +
      summary.coverage_ratio +
      "\n",
    "utf-8"
  );

  if (!summary.strict_gate_passed) {
    const gateMessage =
      "checkpoint coverage " + summary.coverage_ratio + " below threshold " + summary.min_required_coverage;
    if (args.strictCheckpoints) {
      await appendFile(logPath, "[" + new Date().toISOString() + "] strict checkpoint gate failed: " + gateMessage + "\n", "utf-8");
    } else {
      await appendFile(logPath, "[" + new Date().toISOString() + "] warning: " + gateMessage + "\n", "utf-8");
      console.warn("[vc_dashboard_autoplay] " + gateMessage);
    }
  }

  await context.close();
  await browser.close();

  if (args.strictCheckpoints && !summary.strict_gate_passed) {
    return 2;
  }
  return 0;
}

main()
  .then((code) => {
    process.exit(code);
  })
  .catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[vc_dashboard_autoplay] " + message);
    process.exit(1);
  });
