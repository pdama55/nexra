import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime } from '../utils/formatters';
import type { Policy } from '../types';

export function PolicyEngine() {
  const { data: policies, isLoading } = useQuery<Policy[]>({
    queryKey: ['policies'],
    queryFn: () => apiGet<{ items: Policy[] }>('/policies').then(r => Array.isArray(r) ? r : r.items ?? []),
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Policy Engine</h1>
        <button className="btn btn-primary">New Policy</button>
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
