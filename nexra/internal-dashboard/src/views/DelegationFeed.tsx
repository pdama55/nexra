import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime, formatUsd, formatLatency, truncateId } from '../utils/formatters';
import type { TimeRange, Delegation, PaginatedResponse } from '../types';
import { useState } from 'react';

interface Props {
  timeRange: TimeRange;
}

export function DelegationFeed({ timeRange }: Props) {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [decisionFilter, setDecisionFilter] = useState<string>('all');
  const [callerFilter, setCallerFilter] = useState('');
  const [calleeFilter, setCalleeFilter] = useState('');
  const [liveMode, setLiveMode] = useState(false);

  const { data, isLoading } = useQuery<PaginatedResponse<Delegation>>({
    queryKey: ['delegations', statusFilter, decisionFilter, callerFilter, calleeFilter, timeRange],
    queryFn: () => apiGet('/delegations', {
      limit: 25,
      sort: 'created_at:desc',
      ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
      ...(decisionFilter !== 'all' ? { policy_decision: decisionFilter } : {}),
      ...(callerFilter ? { caller_agent_id: callerFilter } : {}),
      ...(calleeFilter ? { callee_agent_id: calleeFilter } : {}),
    }),
    refetchInterval: liveMode ? 10_000 : false,
  });

  const delegations = data?.items ?? [];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Delegation Feed</h1>
        <button
          className={`btn btn-sm ${liveMode ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setLiveMode(!liveMode)}
        >
          {liveMode ? '● Live' : '○ Live mode'}
        </button>
      </div>

      <div className="filters-bar">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Status</option>
          {['completed','in_flight','pending_approval','blocked','failed','timeout'].map(s =>
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          )}
        </select>
        <select value={decisionFilter} onChange={e => setDecisionFilter(e.target.value)}>
          <option value="all">All Decisions</option>
          <option value="allow">Allow</option>
          <option value="block">Block</option>
          <option value="pause">Pause</option>
        </select>
        <input
          placeholder="Caller agent ID"
          value={callerFilter}
          onChange={(e) => setCallerFilter(e.target.value)}
          style={{ minWidth: '180px' }}
        />
        <input
          placeholder="Callee agent ID"
          value={calleeFilter}
          onChange={(e) => setCalleeFilter(e.target.value)}
          style={{ minWidth: '180px' }}
        />
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading delegations…</div>
      ) : delegations.length === 0 ? (
        <EmptyState
          icon="⇄"
          heading="No delegations match your filters"
          message="Try widening the time range or removing filters."
        />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1100px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Delegation ID', 'Time', 'Caller', 'Callee', 'Status', 'Policy', 'Decision', 'Cost', 'Latency', 'Depth'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {delegations.map(d => (
                <tr key={d.id} style={{ borderBottom: '1px solid var(--border)', height: '40px' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/delegations/${d.id}`} className="mono" style={{ fontSize: '12px' }}>
                      {truncateId(d.id)}
                    </Link>
                  </td>
                  <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {formatRelativeTime(d.created_at)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${d.caller_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{d.caller_agent_id}</Link>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${d.callee_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{d.callee_agent_id}</Link>
                  </td>
                  <td style={{ padding: '8px 12px' }}><StatusPill status={d.status} /></td>
                  <td style={{ padding: '8px 12px' }}>
                    {d.policy_id ? (
                      <Link to={`/policies/${d.policy_id}`} className="mono" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {truncateId(d.policy_id)}
                      </Link>
                    ) : '—'}
                  </td>
                  <td style={{ padding: '8px 12px' }}>{d.policy_decision ? <StatusPill status={d.policy_decision} /> : '—'}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(d.actual_cost_usd)}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatLatency(d.latency_ms)}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px', color: (d.delegation_depth ?? 0) > 3 ? '#9A4A4A' : undefined }}>
                    {d.delegation_depth ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
