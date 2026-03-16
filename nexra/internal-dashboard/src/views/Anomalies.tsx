import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime } from '../utils/formatters';
import type { TimeRange, Agent, AuditEntry } from '../types';

interface Props {
  timeRange: TimeRange;
}

export function Anomalies({ timeRange: _timeRange }: Props) {
  const { data: agents } = useQuery<Agent[]>({
    queryKey: ['agents-quarantined'],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry').then(r => r.agents.filter(a => a.status === 'quarantined')),
  });

  const { data: circuitBreakers } = useQuery<AuditEntry[]>({
    queryKey: ['circuit-breakers'],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', { event_type: 'circuit_breaker_tripped' }).then(r => r.entries),
  });

  const { data: anomalies } = useQuery<AuditEntry[]>({
    queryKey: ['anomaly-history'],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', { event_type: 'anomaly_detected' }).then(r => r.entries),
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Circuit Breakers & Anomalies</h1>
      </div>

      {/* Active Circuit Breakers */}
      <div style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="section-heading">Active Circuit Breakers</div>
        {agents && agents.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {agents.map(a => (
              <div key={a.agent_id} className="card" style={{
                borderColor: '#3A2020',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <Link to={`/agents/${a.agent_id}`} style={{ fontSize: '13px' }}>{a.name}</Link>
                  <div className="mono" style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{a.agent_id}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: '#9A4A4A', fontSize: '12px' }}>Quarantined</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>Trust: {a.trust_score.toFixed(3)}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon="✓" heading="No active circuit breakers" message="All agents are operating normally." />
        )}
      </div>

      {/* Circuit Breaker History */}
      <div style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="section-heading">Circuit Breaker History</div>
        {circuitBreakers && circuitBreakers.length > 0 ? (
          <div className="card" style={{ padding: 0 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Agent', 'Details'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {circuitBreakers.map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(e.created_at)}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <Link to={`/agents/${e.actor_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{e.actor_agent_id}</Link>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: '#9A4A4A' }}>Circuit breaker tripped</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card" style={{ padding: '16px', fontSize: '13px', color: 'var(--text-tertiary)' }}>No circuit breaker events.</div>
        )}
      </div>

      {/* Spend Anomalies */}
      <div>
        <div className="section-heading">Spend Anomaly History</div>
        {anomalies && anomalies.length > 0 ? (
          <div className="card" style={{ padding: 0 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Agent', 'Details'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {anomalies.map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(e.created_at)}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <Link to={`/agents/${e.actor_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{e.actor_agent_id}</Link>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--status-probationary)' }}>Spend anomaly detected</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card" style={{ padding: '16px', fontSize: '13px', color: 'var(--text-tertiary)' }}>No spend anomalies detected.</div>
        )}
      </div>

      {/* Threshold Info */}
      <div className="card" style={{ marginTop: 'var(--space-xl)', padding: '12px 16px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
        <strong style={{ color: 'var(--text-secondary)' }}>Thresholds:</strong> Circuit breaker trips at &gt;50% failure rate in 10-min window. Anomaly detection alerts on 3σ spend deviation (hourly check). Auto-quarantine at trust_score &lt; 0.20.
      </div>
    </div>
  );
}
