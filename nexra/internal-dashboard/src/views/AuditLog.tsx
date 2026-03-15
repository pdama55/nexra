import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';

import { EmptyState } from '../components/common/EmptyState';
import { formatAbsoluteTime, formatUsd, truncateId } from '../utils/formatters';
import { getTimeRangeParams } from '../hooks/useTimeRange';
import type { TimeRange, AuditEntry, PaginatedResponse, AuditEventType } from '../types';
import { useState } from 'react';

const EVENT_TYPES: AuditEventType[] = [
  'policy_evaluated', 'delegation_initiated', 'delegation_completed', 'delegation_failed',
  'delegation_blocked', 'delegation_timeout', 'agent_quarantined', 'agent_activated',
  'budget_exceeded', 'hil_triggered', 'hil_approved', 'hil_expired',
  'anomaly_detected', 'circuit_breaker_tripped',
];

interface Props {
  timeRange: TimeRange;
}

export function AuditLog({ timeRange }: Props) {
  const params = getTimeRangeParams(timeRange);
  const [eventFilter, setEventFilter] = useState<string>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery<PaginatedResponse<AuditEntry>>({
    queryKey: ['audit', params.window, eventFilter],
    queryFn: () => apiGet('/audit/log', {
      ...(eventFilter !== 'all' ? { event_type: eventFilter } : {}),
      limit: 50,
    }),
  });

  const entries = data?.items ?? [];

  function getEventColor(type: string): string {
    if (type.includes('blocked') || type.includes('failed') || type.includes('timeout')) return '#9A4A4A';
    if (type.includes('quarantined') || type.includes('anomaly') || type.includes('circuit')) return 'var(--status-probationary)';
    if (type.includes('completed') || type.includes('approved') || type.includes('activated')) return 'var(--status-active)';
    return 'var(--text-secondary)';
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Audit Log</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm">Export CSV</button>
          <button className="btn btn-secondary btn-sm">Export JSON</button>
        </div>
      </div>

      <div className="filters-bar">
        <select value={eventFilter} onChange={e => setEventFilter(e.target.value)}>
          <option value="all">All Event Types</option>
          {EVENT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </select>
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading audit log…</div>
      ) : entries.length === 0 ? (
        <EmptyState icon="⊞" heading="No audit events" message="No audit events in this time window." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '900px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Time', 'Event Type', 'Actor', 'Target', 'Delegation ID', 'Cost', 'Details'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <>
                  <tr key={e.id} style={{ borderBottom: expanded === e.id ? 'none' : '1px solid var(--border)', height: '40px', cursor: 'pointer' }}
                    onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                    onMouseEnter={ev => (ev.currentTarget.style.background = 'var(--bg-tertiary)')}
                    onMouseLeave={ev => (ev.currentTarget.style.background = '')}>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {formatAbsoluteTime(e.created_at)}
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: getEventColor(e.event_type) }}>
                      {e.event_type.replace(/_/g, ' ')}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      {e.actor_agent_id ? (
                        <Link to={`/agents/${e.actor_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{e.actor_agent_id}</Link>
                      ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>system</span>}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      {e.target_agent_id ? (
                        <Link to={`/agents/${e.target_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{e.target_agent_id}</Link>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      {e.delegation_id ? (
                        <Link to={`/delegations/${e.delegation_id}`} className="mono" style={{ fontSize: '11px' }}>{truncateId(e.delegation_id)}</Link>
                      ) : '—'}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(e.cost_usd)}</td>
                    <td style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--text-tertiary)' }}>
                      {expanded === e.id ? '▼' : '▶'} Click to expand
                    </td>
                  </tr>
                  {expanded === e.id && (
                    <tr key={`${e.id}-detail`} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td colSpan={7} style={{ padding: '0 12px 12px' }}>
                        <pre style={{
                          background: 'var(--code-bg)',
                          padding: '12px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontFamily: 'var(--font-mono)',
                          overflow: 'auto',
                          maxHeight: '200px',
                        }}>
                          {JSON.stringify(e.details, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
