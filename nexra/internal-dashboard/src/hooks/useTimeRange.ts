import { useState, useCallback } from 'react';
import type { TimeRange } from '../types';

const STORAGE_KEY = 'nexra_time_range';

function loadTimeRange(): TimeRange {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && isValidTimeRange(stored)) {
    return stored;
  }
  return 'last_24h';
}

function isValidTimeRange(value: string): value is TimeRange {
  return ['last_hour', 'last_24h', 'last_7d', 'last_30d', 'custom'].includes(value);
}

export function getTimeRangeParams(range: TimeRange): { window: string } {
  switch (range) {
    case 'last_hour': return { window: 'last_hour' };
    case 'last_24h': return { window: 'last_24h' };
    case 'last_7d': return { window: 'last_7d' };
    case 'last_30d': return { window: 'last_30d' };
    case 'custom': return { window: 'last_24h' };
  }
}

export function getTimeRangeLabel(range: TimeRange): string {
  switch (range) {
    case 'last_hour': return 'Last hour';
    case 'last_24h': return 'Last 24h';
    case 'last_7d': return 'Last 7 days';
    case 'last_30d': return 'Last 30 days';
    case 'custom': return 'Custom';
  }
}

export function useTimeRange() {
  const [timeRange, setTimeRangeState] = useState<TimeRange>(loadTimeRange);

  const setTimeRange = useCallback((range: TimeRange) => {
    setTimeRangeState(range);
    localStorage.setItem(STORAGE_KEY, range);
  }, []);

  return { timeRange, setTimeRange } as const;
}
