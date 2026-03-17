// ─── API Client ───
// Thin fetch wrapper with auth header injection and error handling.

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') || '/v1';
const HEALTH_URL = (import.meta.env.VITE_HEALTH_URL as string | undefined) || '/health';

interface ApiErrorBody {
  status: number;
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}

interface ApiEnvelope<T> {
  data: T;
  meta?: {
    request_id?: string | null;
    latency_ms?: number | null;
  };
}

export class NexraApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown> | null;

  constructor(status: number, code: string, details: Record<string, unknown> | null) {
    super(`API Error ${status}: ${code}`);
    this.name = 'NexraApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('nexra_api_key');
  if (!token) return { 'Content-Type': 'application/json' };
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const base = API_BASE.startsWith('http') ? API_BASE : `${window.location.origin}${API_BASE}`;
  const url = new URL(`${base}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const res = await fetch(url.toString(), { headers: getAuthHeaders() });

  if (!res.ok) {
    let error: ApiErrorBody | null = null;
    try {
      const body = await res.json();
      error = body.error;
    } catch {
      // Non-JSON error response
    }
    throw new NexraApiError(
      res.status,
      error?.code ?? `HTTP_${res.status}`,
      error?.details ?? null,
    );
  }

  const body = (await res.json()) as ApiEnvelope<T>;
  if (!body || typeof body !== 'object' || !('data' in body)) {
    throw new NexraApiError(res.status, 'INVALID_ENVELOPE', { path });
  }
  return body.data;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const url = API_BASE.startsWith('http') ? `${API_BASE}${path}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let error: ApiErrorBody | null = null;
    try {
      const errBody = await res.json();
      error = errBody.error;
    } catch {
      // Non-JSON error response
    }
    throw new NexraApiError(
      res.status,
      error?.code ?? `HTTP_${res.status}`,
      error?.details ?? null,
    );
  }

  const resBody = (await res.json()) as ApiEnvelope<T>;
  if (!resBody || typeof resBody !== 'object' || !('data' in resBody)) {
    throw new NexraApiError(res.status, 'INVALID_ENVELOPE', { path });
  }
  return resBody.data;
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const url = API_BASE.startsWith('http') ? `${API_BASE}${path}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let error: ApiErrorBody | null = null;
    try {
      const errBody = await res.json();
      error = errBody.error;
    } catch {
      // Non-JSON error response
    }
    throw new NexraApiError(
      res.status,
      error?.code ?? `HTTP_${res.status}`,
      error?.details ?? null,
    );
  }

  const resBody = (await res.json()) as ApiEnvelope<T>;
  if (!resBody || typeof resBody !== 'object' || !('data' in resBody)) {
    throw new NexraApiError(res.status, 'INVALID_ENVELOPE', { path });
  }
  return resBody.data;
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const url = API_BASE.startsWith('http') ? `${API_BASE}${path}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let error: ApiErrorBody | null = null;
    try {
      const errBody = await res.json();
      error = errBody.error;
    } catch {
      // Non-JSON error response
    }
    throw new NexraApiError(
      res.status,
      error?.code ?? `HTTP_${res.status}`,
      error?.details ?? null,
    );
  }

  const resBody = (await res.json()) as ApiEnvelope<T>;
  if (!resBody || typeof resBody !== 'object' || !('data' in resBody)) {
    throw new NexraApiError(res.status, 'INVALID_ENVELOPE', { path });
  }
  return resBody.data;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const url = API_BASE.startsWith('http') ? `${API_BASE}${path}` : `${API_BASE}${path}`;
  const res = await fetch(url, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    let error: ApiErrorBody | null = null;
    try {
      const errBody = await res.json();
      error = errBody.error;
    } catch {
      // Non-JSON error response
    }
    throw new NexraApiError(
      res.status,
      error?.code ?? `HTTP_${res.status}`,
      error?.details ?? null,
    );
  }

  const resBody = (await res.json()) as ApiEnvelope<T>;
  if (!resBody || typeof resBody !== 'object' || !('data' in resBody)) {
    throw new NexraApiError(res.status, 'INVALID_ENVELOPE', { path });
  }
  return resBody.data;
}

/**
 * Health check — hits /health (not /v1/health).
 */
export async function fetchHealth(): Promise<{ status: string; latency_ms: number }> {
  const start = Date.now();
  const res = await fetch(HEALTH_URL);
  const latency = Date.now() - start;

  if (!res.ok) {
    return { status: 'unhealthy', latency_ms: latency };
  }

  const body = await res.json();
  return { ...body, latency_ms: latency };
}

export function getApiUrl(path: string): string {
  if (API_BASE.startsWith('http')) {
    return `${API_BASE}${path}`;
  }
  return `${API_BASE}${path}`;
}

export function getHealthUrl(): string {
  return HEALTH_URL;
}
