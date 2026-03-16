import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatUsd, formatPercent, formatRelativeTime, formatLatency } from '../utils/formatters';
import { getTimeRangeParams } from '../hooks/useTimeRange';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { TimeRange, Agent, Delegation, AuditEntry, UsageStats, UsageBucket } from '../types';
import { Link } from 'react-router-dom';

interface Props {
  timeRange: TimeRange;
}

export function Overview({ timeRange }: Props) {
  const params = getTimeRangeParams(timeRange);

  const { data: usage } = useQuery<UsageStats>({
    queryKey: ['usage', params.window],
    queryFn: () => apiGet('/analytics/usage', { window: params.window }),
    refetchInterval: 30_000,
  });

  const { data: chartData } = useQuery<UsageBucket[]>({
    queryKey: ['usage-chart', params.window],
    queryFn: () => apiGet('/analytics/usage', { window: params.window, bucket: 'hour' }),
    refetchInterval: 30_000,
    select: (data: unknown) => Array.isArray(data) ? data : [],
  });

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ['agents-overview'],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry').then(r => r.agents),
    refetchInterval: 30_000,
  });

  const { data: recentDelegations } = useQuery<Delegation[]>({
    queryKey: ['recent-delegations'],
    queryFn: () => apiGet<{ items: Delegation[] }>('/delegations', { limit: 10, sort: 'created_at:desc' }).then(r => r.items),
    refetchInterval: 30_000,
  });

  const { data: alerts } = useQuery<AuditEntry[]>({
    queryKey: ['alerts'],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', {
      event_type: 'anomaly_detected,circuit_breaker_tripped',
      limit: 20,
    }).then(r => r.entries),
    refetchInterval: 30_000,
  });

  const activeAgents = agents?.filter(a => a.status === 'active').length ?? 0;
  const probAgents = agents?.filter(a => a.status === 'probationary').length ?? 0;
  const quarAgents = agents?.filter(a => a.status === 'quarantined').length ?? 0;
  const pendingHitl = recentDelegations?.filter(d => d.status === 'pending_approval').length ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Overview</h1>
      </div>

      {/* Row 1 — Stat Cards */}
      <div className="stat-row stat-row-6">
        <StatCard label="Active Agents" value={activeAgents} />
        <StatCard label="Delegations" value={usage?.total_delegations ?? 0} />
        <StatCard label="Success Rate" value={formatPercent(usage?.success_rate ?? null)} />
        <StatCard label="Blocked" value={usage?.blocked ?? 0} />
        <StatCard label="Total Spend" value={formatUsd(usage?.total_cost_usd ?? null)} />
        <StatCard
          label="Pending HiTL"
          value={pendingHitl}
          alert={pendingHitl > 0}
        />
      </div>

      {/* Row 2 — Chart + Agent Status */}
      <div className="two-col two-col-60-40">
        <div className="card">
          <div className="section-heading">Delegation Volume</div>
          {chartData && chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData}>
                <XAxis
                  dataKey="timestamp"
                  tick={{ fill: '#5A5A56', fontSize: 11 }}
                  axisLine={{ stroke: '#2A2A26' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#5A5A56', fontSize: 11 }}
                  axisLine={{ stroke: '#2A2A26' }}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: '#161614',
                    border: '1px solid #2A2A26',
                    borderRadius: '4px',
                    fontSize: '12px',
                    color: '#E8E6DE',
                  }}
                />
                <Line type="monotone" dataKey="completed" stroke="#4A7C59" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="blocked" stroke="#7C3A3A" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
                <Line type="monotone" dataKey="failed" stroke="#7C5A2A" dot={false} strokeWidth={1.5} strokeDasharray="2 2" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon="📊" heading="No chart data" message="No delegation data available for this time range." />
          )}
        </div>

        <div className="card">
          <div className="section-heading">Agent Status</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {[
                { label: 'Active', count: activeAgents, status: 'active' as const },
                { label: 'Probationary', count: probAgents, status: 'probationary' as const },
                { label: 'Quarantined', count: quarAgents, status: 'quarantined' as const },
              ].map(row => (
                <tr key={row.status}>
                  <td style={{ padding: '8px 0' }}>
                    <Link to={`/agents?status=${row.status}`}
                      style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                      <StatusPill status={row.status} />
                    </Link>
                  </td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '16px' }}>
                    {row.count}
                  </td>
                  <td style={{ padding: '8px 0', textAlign: 'right', color: 'var(--text-tertiary)', fontSize: '12px' }}>
                    {agents && agents.length > 0
                      ? `${((row.count / agents.length) * 100).toFixed(0)}%`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row 3 — Recent Activity + Alerts */}
      <div className="two-col two-col-50-50">
        <div className="card">
          <div className="section-heading">Recent Delegation Activity</div>
          {recentDelegations && recentDelegations.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Caller', 'Callee', 'Status', 'Cost', 'Latency'].map(h => (
                    <th key={h} className="label" style={{ padding: '6px 8px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentDelegations.map(d => (
                  <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {formatRelativeTime(d.created_at)}
                    </td>
                    <td style={{ padding: '8px' }}>
                      <Link to={`/agents/${d.caller_agent_id}`} className="mono" style={{ fontSize: '12px' }}>
                        {d.caller_agent_id}
                      </Link>
                    </td>
                    <td style={{ padding: '8px' }}>
                      <Link to={`/agents/${d.callee_agent_id}`} className="mono" style={{ fontSize: '12px' }}>
                        {d.callee_agent_id}
                      </Link>
                    </td>
                    <td style={{ padding: '8px' }}><StatusPill status={d.status} /></td>
                    <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{formatUsd(d.actual_cost_usd)}</td>
                    <td style={{ padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{formatLatency(d.latency_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon="⇄"
              heading="No delegations yet"
              message="Register an agent and make your first delegation."
            />
          )}
        </div>

        <div className="card">
          <div className="section-heading">Active Alerts</div>
          {alerts && alerts.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {alerts.map(a => (
                <Link key={a.id} to="/anomalies" style={{
                  padding: '8px 12px',
                  background: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  display: 'flex',
                  gap: '8px',
                  alignItems: 'flex-start',
                  fontSize: '12px',
                }}>
                  <span style={{ color: a.event_type === 'circuit_breaker_tripped' ? '#9A4A4A' : '#9A8A3A' }}>
                    {a.event_type === 'circuit_breaker_tripped' ? '⚡' : '⚠'}
                  </span>
                  <div>
                    <div className="mono" style={{ color: 'var(--text-primary)', fontSize: '12px' }}>
                      {a.actor_agent_id ?? a.target_agent_id ?? 'system'}
                    </div>
                    <div style={{ color: 'var(--text-tertiary)', marginTop: '2px' }}>
                      {a.event_type.replace(/_/g, ' ')} · {formatRelativeTime(a.created_at)}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon="✓" heading="No active alerts" message="All systems operating normally." />
          )}
        </div>
      </div>
    </div>
  );
}
