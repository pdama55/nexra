/**
 * Format a number as USD currency.
 */
export function formatUsd(value: number | null | undefined): string {
  if (value == null) return '—';
  return `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

/**
 * Format a number with commas.
 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString('en-US');
}

/**
 * Format milliseconds as human-readable latency.
 */
export function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format a percentage (0-1 or 0-100 scale).
 */
export function formatPercent(value: number | null | undefined, fromDecimal = true): string {
  if (value == null) return '—';
  const pct = fromDecimal ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

/**
 * Format an ISO timestamp as a relative time string.
 */
export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  if (diffMs < 0) return 'just now';

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Format an ISO timestamp as absolute UTC.
 */
export function formatAbsoluteTime(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC');
}

/**
 * Truncate a string to a given length with ellipsis.
 */
export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + '…';
}

/**
 * Truncate a UUID to its first 12 characters for display.
 */
export function truncateId(id: string | null | undefined): string {
  if (!id) return '—';
  return id.slice(0, 12);
}

/**
 * Format a trust score as a colored class name.
 */
export function trustScoreClass(score: number): string {
  if (score >= 0.7) return '';
  if (score >= 0.4) return 'trust-warn';
  return 'trust-danger';
}
