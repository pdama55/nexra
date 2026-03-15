import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import type { Agent } from '../types';

export function TrustScores() {
  const { data: agents, isLoading } = useQuery<Agent[]>({
    queryKey: ['agents-trust'],
    queryFn: () => apiGet<{ items: Agent[] }>('/agents/registry').then(r => r.items),
    refetchInterval: 300_000,
  });

  const sorted = [...(agents ?? [])].sort((a, b) => a.trust_score - b.trust_score);
  const lowTrust = sorted.filter(a => a.trust_score < 0.4);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Trust Scores</h1>
      </div>

      {lowTrust.length > 0 && (
        <div style={{
          background: 'var(--status-quarantined-bg)',
          border: '1px solid #3A2020',
          borderRadius: '4px',
          padding: '12px 16px',
          marginBottom: '16px',
          color: '#9A4A4A',
          fontSize: '13px',
        }}>
          ⚠ {lowTrust.length} agent{lowTrust.length > 1 ? 's' : ''} below trust threshold (0.40)
        </div>
      )}

      <div className="card" style={{ marginBottom: '24px', padding: '12px 16px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
        <strong style={{ color: 'var(--text-secondary)' }}>Formula:</strong> trust = 0.4 × success_rate + 0.3 × sla_compliance + 0.2 × cost_accuracy + 0.1 × (1 − policy_violations)
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading trust scores…</div>
      ) : sorted.length === 0 ? (
        <EmptyState icon="★" heading="No agents" message="Trust scores will appear once agents are registered." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Agent', 'Status', 'Trust Score', 'Delegations', 'Trend'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(a => (
                <tr key={a.agent_id} style={{ borderBottom: '1px solid var(--border)', height: '40px' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${a.agent_id}`} style={{ fontSize: '13px' }}>{a.name}</Link>
                    <div className="mono" style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{a.agent_id}</div>
                  </td>
                  <td style={{ padding: '8px 12px' }}><StatusPill status={a.status} /></td>
                  <td style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="mono" style={{
                        fontSize: '14px',
                        color: a.trust_score >= 0.7 ? 'var(--text-primary)' :
                          a.trust_score >= 0.4 ? 'var(--status-probationary)' : '#9A4A4A',
                      }}>
                        {a.trust_score.toFixed(3)}
                      </span>
                      <div style={{ flex: 1, maxWidth: '80px', background: 'var(--bg-tertiary)', borderRadius: '2px', height: '4px' }}>
                        <div style={{
                          width: `${a.trust_score * 100}%`,
                          height: '100%',
                          background: a.trust_score >= 0.7 ? 'var(--status-active)' :
                            a.trust_score >= 0.4 ? 'var(--status-probationary)' : 'var(--status-quarantined)',
                          borderRadius: '2px',
                        }} />
                      </div>
                    </div>
                  </td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '13px' }}>{a.delegation_count}</td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-tertiary)', fontSize: '12px' }}>—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
