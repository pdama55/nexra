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

type ModuleRequire = (id: string) => unknown;

function parseArgs(argv: string[]): Args {
  const args: Record<string, string | boolean> = {
    baseUrl: "http://127.0.0.1:5173",
    userEmail: "admin@nexra.local",
    outDir: "test-results/vc-demo/screenshots",
    timelinePath: "demo/vc_timeline.yaml",
    eventsPath: "test-results/vc-demo/integration_events.jsonl",
    headed: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--base-url" && value) {
      args.baseUrl = value;
      i += 1;
    } else if (key === "--api-key" && value) {
      args.apiKey = value;
      i += 1;
    } else if (key === "--user-email" && value) {
      args.userEmail = value;
      i += 1;
    } else if (key === "--out-dir" && value) {
      args.outDir = value;
      i += 1;
    } else if (key === "--timeline" && value) {
      args.timelinePath = value;
      i += 1;
    } else if (key === "--events-path" && value) {
      args.eventsPath = value;
      i += 1;
    } else if (key === "--headed") {
      args.headed = true;
    }
  }

  if (!args.apiKey || typeof args.apiKey !== "string") {
    throw new Error("--api-key is required");
  }

  return args as Args;
}

function buildModuleRequire(): ModuleRequire {
  const dashboardDir = process.env.NEXRA_DASHBOARD_DIR;
  if (dashboardDir) {
    const packagePath = path.join(dashboardDir, "package.json");
    if (existsSync(packagePath)) {
      return createRequire(packagePath);
    }
  }
  return createRequire(import.meta.url);
}

async function loadTimeline(timelinePath: string): Promise<TimelineAct[]> {
  const requireFromModuleRoot = buildModuleRequire();
  const yaml = requireFromModuleRoot("yaml") as { parse: (source: string) => unknown };
  const raw = await readFile(timelinePath, "utf-8");
  const doc = yaml.parse(raw);
  if (!doc || !Array.isArray(doc.acts)) {
    throw new Error("Invalid timeline file: " + timelinePath);
  }
  return doc.acts as TimelineAct[];
}

function routeForPanel(panel: string): string {
  const key = panel.toLowerCase();
  if (key.includes("agent")) return "/agents";
  if (key.includes("policy")) return "/policies";
  if (key.includes("trust")) return "/trust";
  if (key.includes("anomal")) return "/anomalies";
  if (key.includes("audit")) return "/audit";
  if (key.includes("compliance")) return "/compliance";
  if (key.includes("marketplace") || key.includes("settings")) return "/settings";
  if (key.includes("delegation")) return "/delegations";
  return "/";
}

async function eventSeen(eventsPath: string, expectedEvents: string[]): Promise<boolean> {
  try {
    const raw = await readFile(eventsPath, "utf-8");
    return expectedEvents.every((ev) => raw.includes('"event":"' + ev + '"') || raw.includes(ev));
  } catch {
    return false;
  }
}

async function waitForCheckpoint(
  eventsPath: string,
  expectedEvents: string[],
  timeoutMs = 15000
): Promise<boolean> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await eventSeen(eventsPath, expectedEvents)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
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

  const markers: Array<Record<string, unknown>> = [];
  await appendFile(
    path.join(args.outDir, "autoplay.log"),
    "[" + new Date().toISOString() + "] starting autoplay at " + initialUrl.toString() + "\n",
    "utf-8"
  );

  await page.goto(initialUrl.toString(), { waitUntil: "networkidle" });

  for (let idx = 0; idx < timeline.length; idx += 1) {
    const act = timeline[idx];
    const route = routeForPanel(act.panel);
    const routeUrl = args.baseUrl.replace(/\/$/, "") + route;
    await page.goto(routeUrl, { waitUntil: "networkidle" });

    const checkpointSeen = await waitForCheckpoint(args.eventsPath, act.expected_events, 12000);
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
      talking_point: act.talking_point,
    });
  }

  await writeFile(
    path.join(args.outDir, "timeline_markers.json"),
    JSON.stringify(markers, null, 2),
    "utf-8"
  );
  await appendFile(
    path.join(args.outDir, "autoplay.log"),
    "[" + new Date().toISOString() + "] completed autoplay (" + markers.length + " captures)\n",
    "utf-8"
  );

  await context.close();
  await browser.close();
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
