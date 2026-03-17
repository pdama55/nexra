import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { EmptyState } from '../components/common/EmptyState';
import { RefreshAge } from '../components/Shell/RefreshAge';
import { getTimeRangeParams } from '../hooks/useTimeRange';
import { formatRelativeTime } from '../utils/formatters';
import type { TimeRange, Agent, AuditEntry } from '../types';

interface Props {
  timeRange: TimeRange;
}

export function Anomalies({ timeRange }: Props) {
  const params = getTimeRangeParams(timeRange);
  const nowIso = new Date().toISOString();
  const dateFromIso = (() => {
    const now = new Date();
    if (params.window === 'last_hour') return new Date(now.getTime() - 60 * 60 * 1000).toISOString();
    if (params.window === 'last_24h') return new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
    if (params.window === 'last_7d') return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
    return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
  })();
  const { data: agents } = useQuery<Agent[]>({
    queryKey: ['agents-quarantined', timeRange],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry').then(r => r.agents.filter(a => a.status === 'quarantined')),
  });

  const { data: circuitBreakers } = useQuery<AuditEntry[]>({
    queryKey: ['circuit-breakers', timeRange],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', {
      event_type: 'circuit_breaker_tripped',
      date_from: dateFromIso,
      date_to: nowIso,
    }).then(r => r.entries),
  });

  const { data: anomalies } = useQuery<AuditEntry[]>({
    queryKey: ['anomaly-history', timeRange],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', {
      event_type: 'anomaly_detected',
      date_from: dateFromIso,
      date_to: nowIso,
    }).then(r => r.entries),
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Circuit Breakers & Anomalies</h1>
        <RefreshAge queryKeys={[['circuit-breakers', timeRange], ['anomaly-history', timeRange]]} />
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
                  {['Time', 'Agent', 'Severity', 'Reason'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {circuitBreakers.map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(e.created_at)}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <Link to={`/agents/${e.target_agent_id ?? e.actor_agent_id}`} className="mono" style={{ fontSize: '12px' }}>
                        {e.target_agent_id ?? e.actor_agent_id}
                      </Link>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: '#9A4A4A' }}>high</td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: '#9A4A4A' }}>
                      threshold {String(e.details?.threshold ?? '0.5')}, window {String(e.details?.window_seconds ?? 600)}s
                    </td>
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
                  {['Time', 'Agent', 'Severity', 'Reason', 'Spend Delta'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {anomalies.map(e => {
                  const sigma = Number(e.details?.sigma_deviation ?? 0);
                  const severity = sigma >= 5 ? 'high' : sigma >= 3.5 ? 'medium' : 'low';
                  const current = Number(e.details?.current_hour_spend ?? 0);
                  const threshold = Number(e.details?.threshold ?? 0);
                  const delta = current - threshold;
                  const reason = `sigma ${sigma.toFixed(2)} above threshold`;
                  return (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(e.created_at)}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <Link to={`/agents/${e.target_agent_id ?? e.actor_agent_id}`} className="mono" style={{ fontSize: '12px' }}>
                        {e.target_agent_id ?? e.actor_agent_id}
                      </Link>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: severity === 'high' ? '#9A4A4A' : 'var(--status-probationary)' }}>
                      {severity}
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px' }}>{reason}</td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {delta.toFixed(4)}
                    </td>
                  </tr>
                )})}
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
