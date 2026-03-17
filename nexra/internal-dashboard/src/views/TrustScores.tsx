import { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { apiGet } from '../api/client';
import { RefreshAge } from '../components/Shell/RefreshAge';
import { EmptyState } from '../components/common/EmptyState';
import { StatusPill } from '../components/common/StatusPill';
import type { Agent } from '../types';
import { formatRelativeTime } from '../utils/formatters';

interface TrustDetail {
  trust_score: number;
  last_active: string | null;
  breakdown: {
    success_rate: number;
    sla_compliance: number;
    cost_accuracy: number;
    policy_violations_inverse: number;
  };
  timeseries: Array<{ score_after: number; created_at: string }>;
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) {
    return <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>—</span>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = Math.max(max - min, 0.0001);
  const width = 90;
  const height = 28;
  const path = points
    .map((value, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path d={path} fill="none" stroke="#4A7C59" strokeWidth="1.5" />
    </svg>
  );
}

export function TrustScores() {
  const { data: agents, isLoading } = useQuery<Agent[]>({
    queryKey: ['agents-trust'],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry').then((r) => r.agents),
    refetchInterval: 300_000,
  });

  const trustQueries = useQueries({
    queries: (agents ?? []).map((agent) => ({
      queryKey: ['agent-trust', agent.agent_id],
      queryFn: () => apiGet<TrustDetail>(`/agents/${agent.agent_id}/trust`),
      enabled: Boolean(agent.agent_id),
      staleTime: 60_000,
    })),
  });

  const trustByAgent = useMemo(() => {
    const map: Record<string, TrustDetail> = {};
    trustQueries.forEach((query, index) => {
      const agent = agents?.[index];
      if (!agent || !query.data) return;
      map[agent.agent_id] = query.data;
    });
    return map;
  }, [agents, trustQueries]);

  const sorted = [...(agents ?? [])].sort((a, b) => a.trust_score - b.trust_score);
  const lowTrust = sorted.filter((agent) => agent.trust_score < 0.4);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Trust Scores</h1>
        <RefreshAge queryKeys={[['agents-trust']]} />
      </div>

      {lowTrust.length > 0 && (
        <div
          style={{
            background: 'var(--status-quarantined-bg)',
            border: '1px solid #3A2020',
            borderRadius: '4px',
            padding: '12px 16px',
            marginBottom: '16px',
            color: '#9A4A4A',
            fontSize: '13px',
          }}
        >
          {lowTrust.length} agent{lowTrust.length > 1 ? 's' : ''} below trust threshold (0.40)
        </div>
      )}

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading trust scores…</div>
      ) : sorted.length === 0 ? (
        <EmptyState icon="★" heading="No agents" message="Trust scores will appear once agents are registered." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Agent', 'Status', 'Trust', 'Success', 'SLA', 'Cost', 'Policy', 'Last Active', 'Trend'].map((header) => (
                  <th
                    key={header}
                    className="label"
                    style={{
                      padding: '10px 12px',
                      textAlign: 'left',
                      position: 'sticky',
                      top: 0,
                      background: 'var(--bg-secondary)',
                    }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((agent) => {
                const trust = trustByAgent[agent.agent_id];
                const points = (trust?.timeseries ?? []).map((item) => item.score_after);
                return (
                  <tr
                    key={agent.agent_id}
                    style={{ borderBottom: '1px solid var(--border)', height: '44px' }}
                    onMouseEnter={(event) => {
                      event.currentTarget.style.background = 'var(--bg-tertiary)';
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.background = '';
                    }}
                  >
                    <td style={{ padding: '8px 12px' }}>
                      <Link to={`/agents/${agent.agent_id}`} style={{ fontSize: '13px' }}>
                        {agent.name}
                      </Link>
                      <div className="mono" style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                        {agent.agent_id}
                      </div>
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <StatusPill status={agent.status} />
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {agent.trust_score.toFixed(3)}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {(trust?.breakdown.success_rate ?? 0).toFixed(3)}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {(trust?.breakdown.sla_compliance ?? 0).toFixed(3)}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {(trust?.breakdown.cost_accuracy ?? 0).toFixed(3)}
                    </td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>
                      {(trust?.breakdown.policy_violations_inverse ?? 0).toFixed(3)}
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {trust?.last_active ? formatRelativeTime(trust.last_active) : '—'}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <Sparkline points={points} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
