import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface Props {
  queryKeys?: Array<readonly unknown[]>;
}

function formatAge(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function RefreshAge({ queryKeys }: Props) {
  const queryClient = useQueryClient();
  const [tick, setTick] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const updatedAt = useMemo(() => {
    const keys = queryKeys && queryKeys.length > 0
      ? queryKeys
      : queryClient
          .getQueryCache()
          .getAll()
          .map((q) => q.queryKey as readonly unknown[]);

    let latest = 0;
    for (const key of keys) {
      const state = queryClient.getQueryState(key);
      if (state?.dataUpdatedAt && state.dataUpdatedAt > latest) {
        latest = state.dataUpdatedAt;
      }
    }
    return latest;
  }, [queryClient, queryKeys]);

  if (!updatedAt) {
    return <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>No data yet</span>;
  }

  return (
    <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>
      Updated {formatAge(tick - updatedAt)}
    </span>
  );
}
