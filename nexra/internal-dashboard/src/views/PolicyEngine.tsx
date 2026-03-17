import { useQuery } from '@tanstack/react-query';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime } from '../utils/formatters';
import { useSession } from '../hooks/useSession';
import { hasPermission } from '../utils/rbac';
import type { Policy } from '../types';

export function PolicyEngine() {
  const queryClient = useQueryClient();
  const session = useSession();
  const canCreate = hasPermission(session.data?.role ?? 'viewer', 'createPolicy');
  const { data: policies, isLoading } = useQuery<Policy[]>({
    queryKey: ['policies'],
    queryFn: () => apiGet<{ policies: Policy[] }>('/policies').then(r => r.policies),
  });
  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      description: string;
      priority: number;
      on_violation: string;
    }) =>
      apiPost('/policies', {
        ...payload,
        allow: {},
        conditions: [],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policies'] });
    },
  });

  function createPolicy(): void {
    const name = window.prompt('Policy name');
    if (!name) return;
    const description = window.prompt('Policy description', 'Created from dashboard') ?? 'Created from dashboard';
    const priorityInput = window.prompt('Priority (lower runs first)', '100') ?? '100';
    const priority = Number(priorityInput);
    if (!Number.isFinite(priority) || priority < 1) return;
    createMutation.mutate({
      name,
      description,
      priority,
      on_violation: 'block_and_alert',
    });
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Policy Engine</h1>
        {canCreate && (
          <button className="btn btn-primary" onClick={createPolicy} disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Creating…' : 'New Policy'}
          </button>
        )}
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading policies…</div>
      ) : !policies || policies.length === 0 ? (
        <EmptyState
          icon="⛊"
          heading="No policies configured"
          message="A default allow-all policy is active. Create a policy to enforce governance."
        />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Name', 'Status', 'Priority', 'Version', 'Created'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {policies.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border)', height: '40px' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/policies/${p.id}`} style={{ fontSize: '13px' }}>{p.name}</Link>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <StatusPill status={p.enabled ? 'active' : 'quarantined'} />
                  </td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '13px' }}>{p.priority}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '13px' }}>v{p.version}</td>
                  <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
