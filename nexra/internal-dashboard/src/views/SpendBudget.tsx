import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { StatCard } from '../components/common/StatCard';
import { EmptyState } from '../components/common/EmptyState';
import { formatUsd, formatPercent } from '../utils/formatters';
import { getTimeRangeParams } from '../hooks/useTimeRange';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { TimeRange, SpendSummary, AgentSpend } from '../types';

interface Props {
  timeRange: TimeRange;
}

export function SpendBudget({ timeRange }: Props) {
  const params = getTimeRangeParams(timeRange);
  const { data: spendPayload } = useQuery<{
    summary?: Array<{
      agent_id: string;
      period: string;
      period_type: 'daily' | 'monthly';
      cap_usd: number;
      spent_usd: number;
      remaining_usd: number;
    }>;
    totals?: SpendSummary;
    agent_breakdown?: Array<{
      agent_id: string;
      delegation_count: number;
      total_spend_usd: number;
      avg_cost_usd: number;
    }>;
    timeseries?: Array<{ timestamp: string; spend_usd: number; delegation_count: number }>;
  }>({
    queryKey: ['spend-summary', params.window],
    queryFn: () => apiGet('/spend/summary', { window: params.window, breakdown: 'all' }),
    refetchInterval: 300_000,
  });

  const summary = spendPayload?.totals;
  const rows = spendPayload?.summary ?? [];
  const spendSeries = (spendPayload?.timeseries ?? []).map((row) => ({
    timestamp: row.timestamp,
    total: row.spend_usd,
  }));

  const { data: anomalyCounts } = useQuery<Record<string, number>>({
    queryKey: ['spend-anomaly-counts', params.window],
    queryFn: async () => {
      const events = await apiGet<{ entries: Array<{ actor_agent_id: string | null; target_agent_id: string | null }> }>(
        '/audit/log',
        { event_type: 'anomaly_detected', limit: 500 },
      );
      const counts: Record<string, number> = {};
      for (const entry of events.entries) {
        const key = entry.target_agent_id ?? entry.actor_agent_id ?? '';
        if (!key) continue;
        counts[key] = (counts[key] ?? 0) + 1;
      }
      return counts;
    },
    refetchInterval: 300_000,
  });

  const agentSpend: AgentSpend[] = (spendPayload?.agent_breakdown ?? []).map((item) => {
    const agentRows = rows.filter((row) => row.agent_id === item.agent_id);
    const dailyCap = agentRows.find((row) => row.period_type === 'daily')?.cap_usd ?? null;
    const monthlyCap = agentRows.find((row) => row.period_type === 'monthly')?.cap_usd ?? null;
    const capBase = monthlyCap ?? dailyCap ?? 0;
    return {
      agent_id: item.agent_id,
      delegation_count: item.delegation_count,
      total_spend_usd: item.total_spend_usd,
      avg_cost_usd: item.avg_cost_usd,
      daily_cap_usd: dailyCap,
      monthly_cap_usd: monthlyCap,
      utilization: capBase > 0 ? item.total_spend_usd / capBase : 0,
      anomaly_count: anomalyCounts?.[item.agent_id] ?? 0,
    };
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Spend & Budget</h1>
      </div>

      <div className="stat-row stat-row-4">
        <StatCard label="Total Spend" value={formatUsd(summary?.total_spend_usd ?? null)} />
        <StatCard label="Avg Cost / Delegation" value={formatUsd(summary?.avg_cost_per_delegation ?? null)} />
        <StatCard
          label="Highest Spend Agent"
          value={summary?.highest_spend_agent?.agent_id ?? '—'}
        />
        <StatCard label="Budget Utilization" value={formatPercent(summary?.budget_utilization ?? null)} />
      </div>

      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="section-heading">Spend Over Time</div>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={spendSeries ?? []}>
            <XAxis dataKey="timestamp" tick={{ fill: '#5A5A56', fontSize: 11 }} axisLine={{ stroke: '#2A2A26' }} tickLine={false} />
            <YAxis tick={{ fill: '#5A5A56', fontSize: 11 }} axisLine={{ stroke: '#2A2A26' }} tickLine={false} />
            <Tooltip contentStyle={{ background: '#161614', border: '1px solid #2A2A26', borderRadius: '4px', fontSize: '12px', color: '#E8E6DE' }} />
            <Line type="monotone" dataKey="total" stroke="#4A7C59" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <div className="section-heading" style={{ padding: '16px 12px 8px' }}>Per-Agent Spend</div>
        {agentSpend.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '900px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Agent', 'Delegations', 'Total Spend', 'Avg Cost', 'Daily Cap', 'Monthly Cap', 'Utilization', 'Anomalies'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agentSpend.map(a => (
                <tr key={a.agent_id} style={{ borderBottom: '1px solid var(--border)', height: '40px' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${a.agent_id}`} className="mono" style={{ fontSize: '12px' }}>{a.agent_id}</Link>
                  </td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{a.delegation_count}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(a.total_spend_usd)}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(a.avg_cost_usd)}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{a.daily_cap_usd != null ? formatUsd(a.daily_cap_usd) : '—'}</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{a.monthly_cap_usd != null ? formatUsd(a.monthly_cap_usd) : '—'}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ flex: 1, background: 'var(--bg-tertiary)', borderRadius: '2px', height: '4px' }}>
                        <div style={{
                          width: `${Math.min(a.utilization * 100, 100)}%`,
                          height: '100%',
                          background: a.utilization > 0.8 ? 'var(--status-quarantined)' : 'var(--status-active)',
                          borderRadius: '2px',
                        }} />
                      </div>
                      <span className="mono" style={{ fontSize: '11px', color: a.utilization > 0.8 ? '#9A4A4A' : 'var(--text-secondary)' }}>
                        {formatPercent(a.utilization)}
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    {a.anomaly_count > 0 ? (
                      <span className="badge-count">{a.anomaly_count}</span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState icon="$" heading="No spend data" message="Spend data will appear after delegations are processed." />
        )}
      </div>
    </div>
  );
}
