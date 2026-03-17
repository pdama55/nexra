type WaitlistSource = 'hero' | 'footer' | 'nav';

interface WaitlistRequestBody {
  email: string;
  source: WaitlistSource;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  website?: string;
  timestamp?: string;
}

interface SuccessResponse {
  ok: true;
  message: 'queued';
}

interface ErrorResponse {
  ok: false;
  code: 'invalid_email' | 'invalid_payload' | 'rate_limited' | 'upstream_failed' | 'method_not_allowed';
}

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

interface ApiRequest {
  method?: string;
  headers: Record<string, string | string[] | undefined>;
  body?: unknown;
  socket?: { remoteAddress?: string };
}

interface ApiResponse {
  status(code: number): ApiResponse;
  setHeader(name: string, value: string): void;
  json(payload: SuccessResponse | ErrorResponse): void;
}

declare const process: {
  env: Record<string, string | undefined>;
};

const MAX_REQUESTS_PER_WINDOW = 5;
const RATE_WINDOW_MS = 10 * 60 * 1000;
const REQUEST_TIMEOUT_MS = 5000;
const rateLimitStore = new Map<string, RateLimitEntry>();

function respond(res: ApiResponse, status: number, body: SuccessResponse | ErrorResponse): void {
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('cache-control', 'no-store');
  res.status(status).json(body);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isSource(value: unknown): value is WaitlistSource {
  return value === 'hero' || value === 'footer' || value === 'nav';
}

function normalizeOptionalString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function parseBody(rawBody: unknown): unknown {
  if (typeof rawBody === 'string') {
    try {
      return JSON.parse(rawBody);
    } catch {
      return null;
    }
  }
  return rawBody;
}

function parsePayload(value: unknown): WaitlistRequestBody | null {
  if (!isObject(value)) return null;
  if (typeof value.email !== 'string' || !isSource(value.source)) return null;

  return {
    email: value.email.trim(),
    source: value.source,
    utm_source: normalizeOptionalString(value.utm_source),
    utm_medium: normalizeOptionalString(value.utm_medium),
    utm_campaign: normalizeOptionalString(value.utm_campaign),
    website: typeof value.website === 'string' ? value.website : undefined,
    timestamp: normalizeOptionalString(value.timestamp)
  };
}

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function getHeaderValue(header: string | string[] | undefined): string | undefined {
  if (Array.isArray(header)) return header[0];
  return header;
}

function getClientIp(req: ApiRequest): string {
  const forwarded = getHeaderValue(req.headers['x-forwarded-for']);
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }

  const realIp = getHeaderValue(req.headers['x-real-ip']);
  if (realIp) return realIp.trim();

  if (req.socket?.remoteAddress) return req.socket.remoteAddress;
  return 'unknown';
}

function isRateLimited(ip: string, now: number): boolean {
  const existing = rateLimitStore.get(ip);

  if (!existing || existing.resetAt <= now) {
    rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return false;
  }

  if (existing.count >= MAX_REQUESTS_PER_WINDOW) {
    return true;
  }

  existing.count += 1;
  rateLimitStore.set(ip, existing);
  return false;
}

function pruneRateLimitStore(now: number): void {
  for (const [ip, entry] of rateLimitStore.entries()) {
    if (entry.resetAt <= now) {
      rateLimitStore.delete(ip);
    }
  }
}

async function forwardToWebhook(req: ApiRequest, payload: WaitlistRequestBody): Promise<ErrorResponse | SuccessResponse> {
  const webhookUrl = process.env.WAITLIST_WEBHOOK_URL;
  if (!webhookUrl) {
    return { ok: false, code: 'upstream_failed' };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'content-type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify({
        ...payload,
        source_section: payload.source,
        page_url: getHeaderValue(req.headers.referer),
        user_agent: getHeaderValue(req.headers['user-agent']),
        client_timestamp: payload.timestamp,
        received_at: new Date().toISOString()
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      return { ok: false, code: 'upstream_failed' };
    }

    return { ok: true, message: 'queued' };
  } catch {
    return { ok: false, code: 'upstream_failed' };
  } finally {
    clearTimeout(timeoutId);
  }
}

export default async function handler(req: ApiRequest, res: ApiResponse): Promise<void> {
  if (req.method !== 'POST') {
    respond(res, 405, { ok: false, code: 'method_not_allowed' });
    return;
  }

  const parsed = parseBody(req.body);
  const payload = parsePayload(parsed);
  if (!payload) {
    respond(res, 400, { ok: false, code: 'invalid_payload' });
    return;
  }

  if (payload.website && payload.website.trim().length > 0) {
    respond(res, 400, { ok: false, code: 'invalid_payload' });
    return;
  }

  if (!isValidEmail(payload.email)) {
    respond(res, 400, { ok: false, code: 'invalid_email' });
    return;
  }

  const now = Date.now();
  pruneRateLimitStore(now);
  const clientIp = getClientIp(req);
  if (isRateLimited(clientIp, now)) {
    respond(res, 429, { ok: false, code: 'rate_limited' });
    return;
  }

  const forwarded = await forwardToWebhook(req, payload);
  if (!forwarded.ok) {
    respond(res, 502, forwarded);
    return;
  }

  respond(res, 202, forwarded);
}
