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
  const chartBucket = params.window === 'last_30d' || params.window === 'last_7d' ? 'day' : 'hour';

  const { data: rows } = useQuery<Array<{
    agent_id: string;
    period: string;
    period_type: 'daily' | 'monthly';
    cap_usd: number;
    spent_usd: number;
    remaining_usd: number;
  }>>({
    queryKey: ['spend-rows', params.window],
    queryFn: () => apiGet<{ summary: Array<{
      agent_id: string;
      period: string;
      period_type: 'daily' | 'monthly';
      cap_usd: number;
      spent_usd: number;
      remaining_usd: number;
    }> }>('/spend/summary').then(r => r.summary),
    refetchInterval: 300_000,
  });

  const { data: summary } = useQuery<SpendSummary>({
    queryKey: ['spend-summary', params.window],
    queryFn: async () => {
      const spendRows = rows ?? [];
      const totalSpend = spendRows.reduce((acc, row) => acc + row.spent_usd, 0);
      const agentTotals = new Map<string, number>();
      const capTotals = new Map<string, number>();

      for (const row of spendRows) {
        agentTotals.set(row.agent_id, (agentTotals.get(row.agent_id) ?? 0) + row.spent_usd);
        capTotals.set(row.agent_id, (capTotals.get(row.agent_id) ?? 0) + row.cap_usd);
      }

      const delegationCount = spendRows.length;
      const highest = [...agentTotals.entries()].sort((a, b) => b[1] - a[1])[0];
      const totalCap = [...capTotals.values()].reduce((acc, cap) => acc + cap, 0);
      return {
        total_spend_usd: totalSpend,
        delegation_count: delegationCount,
        avg_cost_per_delegation: delegationCount > 0 ? totalSpend / delegationCount : 0,
        highest_spend_agent: highest ? { agent_id: highest[0], spend_usd: highest[1] } : null,
        budget_utilization: totalCap > 0 ? totalSpend / totalCap : 0,
      };
    },
    enabled: !!rows,
    refetchInterval: 300_000,
  });

  const { data: agentSpend } = useQuery<AgentSpend[]>({
    queryKey: ['spend-agents', params.window],
    queryFn: async () => {
      const spendRows = rows ?? [];
      const byAgent = new Map<string, {
        total_spend_usd: number;
        delegation_count: number;
        daily_cap_usd: number | null;
        monthly_cap_usd: number | null;
      }>();

      for (const row of spendRows) {
        const current = byAgent.get(row.agent_id) ?? {
          total_spend_usd: 0,
          delegation_count: 0,
          daily_cap_usd: null,
          monthly_cap_usd: null,
        };
        current.total_spend_usd += row.spent_usd;
        current.delegation_count += 1;
        if (row.period_type === 'daily') current.daily_cap_usd = row.cap_usd;
        if (row.period_type === 'monthly') current.monthly_cap_usd = row.cap_usd;
        byAgent.set(row.agent_id, current);
      }

      return [...byAgent.entries()].map(([agent_id, item]) => {
        const capBase = (item.monthly_cap_usd ?? item.daily_cap_usd ?? 0);
        return {
          agent_id,
          delegation_count: item.delegation_count,
          total_spend_usd: item.total_spend_usd,
          avg_cost_usd: item.delegation_count > 0 ? item.total_spend_usd / item.delegation_count : 0,
          daily_cap_usd: item.daily_cap_usd,
          monthly_cap_usd: item.monthly_cap_usd,
          utilization: capBase > 0 ? item.total_spend_usd / capBase : 0,
          anomaly_count: 0,
        };
      });
    },
    enabled: !!rows,
    refetchInterval: 300_000,
  });

  const { data: spendSeries } = useQuery<Array<{ timestamp: string; total: number }>>({
    queryKey: ['spend-series', params.window, chartBucket],
    queryFn: async () => {
      const buckets = await apiGet<Array<{
        timestamp: string;
        completed: number;
        blocked: number;
        failed: number;
        total: number;
      }>>('/analytics/usage', { window: params.window, bucket: chartBucket });
      return buckets.map((b) => ({
        timestamp: b.timestamp,
        total: b.total,
      }));
    },
    refetchInterval: 300_000,
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
        {agentSpend && agentSpend.length > 0 ? (
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
