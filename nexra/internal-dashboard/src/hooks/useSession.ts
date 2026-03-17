import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { UserSession } from '../types';

export function useSession() {
  return useQuery<UserSession>({
    queryKey: ['session'],
    queryFn: () => apiGet('/orgs/session'),
    staleTime: 300_000,
    refetchInterval: 300_000,
  });
}

