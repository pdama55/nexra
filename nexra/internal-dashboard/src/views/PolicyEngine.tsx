import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { RefreshAge } from '../components/Shell/RefreshAge';
import { formatRelativeTime } from '../utils/formatters';
import { useSession } from '../hooks/useSession';
import { hasPermission } from '../utils/rbac';
import type { Policy } from '../types';

export function PolicyEngine() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('Created from dashboard');
  const [priority, setPriority] = useState('100');
  const [formError, setFormError] = useState<string | null>(null);
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
      setFormOpen(false);
      setName('');
      setDescription('Created from dashboard');
      setPriority('100');
      setFormError(null);
    },
    onError: () => {
      setFormError('Unable to create policy. Check fields and retry.');
    },
  });

  function submitCreatePolicy(): void {
    const parsedPriority = Number(priority);
    if (!name.trim()) {
      setFormError('Policy name is required.');
      return;
    }
    if (!Number.isFinite(parsedPriority) || parsedPriority < 1) {
      setFormError('Priority must be a positive number.');
      return;
    }
    setFormError(null);
    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || 'Created from dashboard',
      priority: parsedPriority,
      on_violation: 'block_and_alert',
    });
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h1 className="page-title">Policy Engine</h1>
          <RefreshAge queryKeys={[['policies']]} />
        </div>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setFormOpen(true)} disabled={createMutation.isPending}>
            New Policy
          </button>
        )}
      </div>

      {formOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.55)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1200,
          }}
          onClick={() => setFormOpen(false)}
        >
          <div className="card" style={{ width: 'min(520px, 92vw)' }} onClick={(event) => event.stopPropagation()}>
            <div className="section-heading">Create Policy</div>
            <div style={{ display: 'grid', gap: '10px' }}>
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Policy name" />
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Policy description"
                rows={4}
              />
              <input
                value={priority}
                onChange={(event) => setPriority(event.target.value)}
                placeholder="Priority"
                inputMode="numeric"
              />
            </div>
            {formError && (
              <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--status-quarantined)' }}>{formError}</div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
              <button className="btn btn-secondary" onClick={() => setFormOpen(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitCreatePolicy} disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

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
