import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatUsd, formatRelativeTime } from '../utils/formatters';
import type { TimeRange, Agent, AuditEntry, Delegation, TrustBreakdown } from '../types';
import { useState } from 'react';

interface Props {
  timeRange: TimeRange;
}

export function AgentDetail({ timeRange }: Props) {
  const { agentId } = useParams<{ agentId: string }>();
  const [activeTab, setActiveTab] = useState(0);

  const { data: agent } = useQuery<Agent>({
    queryKey: ['agent', agentId, timeRange],
    queryFn: () => apiGet(`/agents/${agentId}`),
    enabled: !!agentId,
  });

  const { data: trustData } = useQuery<TrustBreakdown>({
    queryKey: ['agent-trust', agentId, timeRange],
    queryFn: () => apiGet<{
      trust_score: number;
      delegation_count: number;
      recent_events: Array<{ components: Record<string, number>; created_at: string }>;
    }>(`/agents/${agentId}/trust`).then((r) => {
      const latest = r.recent_events?.[0]?.components ?? {};
      return {
        trust_score: r.trust_score,
        success_rate: Number(latest.success_rate ?? 0),
        sla_compliance: Number(latest.latency_score ?? 0),
        cost_accuracy: Number(latest.budget_adherence ?? 0),
        policy_violations_inverse: Number(latest.recency ?? 0),
        delegation_count: r.delegation_count,
        last_active: r.recent_events?.[0]?.created_at ?? null,
      };
    }),
    enabled: !!agentId && activeTab === 1,
  });
  const { data: agentDelegations } = useQuery<Delegation[]>({
    queryKey: ['agent-delegations', agentId, timeRange],
    queryFn: () => apiGet<{ items: Delegation[] }>('/delegations', { limit: 100 }).then((r) =>
      r.items.filter((item) => item.caller_agent_id === agentId || item.callee_agent_id === agentId),
    ),
    enabled: !!agentId && activeTab === 2,
  });
  const { data: agentAudit } = useQuery<AuditEntry[]>({
    queryKey: ['agent-audit', agentId, timeRange],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', { agent_id: agentId, limit: 100 }).then((r) => r.entries),
    enabled: !!agentId && activeTab === 3,
  });

  if (!agent) {
    return <EmptyState icon="⬡" heading="Agent not found" message={`No agent found with ID: ${agentId}`} />;
  }

  const tabs = ['Overview', 'Trust Score', 'Delegation History', 'Audit History'];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {agent.name}
            <StatusPill status={agent.status} />
          </h1>
          <div className="mono" style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {agent.agent_id}
          </div>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((tab, i) => (
          <button
            key={tab}
            className={`tab${activeTab === i ? ' active' : ''}`}
            onClick={() => setActiveTab(i)}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
          <div className="card">
            <div className="section-heading">Registration</div>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
              {[
                ['Agent ID', agent.agent_id],
                ['Capability', agent.capability_type],
                ['Webhook', agent.webhook_url.replace(/\/[^/]*$/, '/***')],
                ['Public', agent.is_public ? 'Yes' : 'No'],
                ['Registered', formatRelativeTime(agent.created_at)],
                ['Updated', formatRelativeTime(agent.updated_at)],
              ].map(([label, value]) => (
                <div key={label} style={{ display: 'contents' }}>
                  <div style={{ color: 'var(--text-tertiary)' }}>{label}</div>
                  <div className="mono" style={{ color: 'var(--text-primary)' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="section-heading">Pricing & SLA</div>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
              {[
                ['Per-call price', formatUsd(agent.pricing.per_call_usd)],
                ['P99 latency', `${agent.sla.p99_latency_ms}ms`],
                ['Availability', `${(agent.sla.availability * 100).toFixed(1)}%`],
                ['Trust Score', agent.trust_score.toFixed(3)],
                ['Delegations', String(agent.delegation_count)],
              ].map(([label, value]) => (
                <div key={label} style={{ display: 'contents' }}>
                  <div style={{ color: 'var(--text-tertiary)' }}>{label}</div>
                  <div className="mono" style={{ color: 'var(--text-primary)' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="section-heading">Input Schema</div>
            <pre style={{
              background: 'var(--code-bg)',
              padding: '12px',
              borderRadius: '4px',
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              overflow: 'auto',
              maxHeight: '200px',
            }}>
              {JSON.stringify(agent.input_schema, null, 2)}
            </pre>
          </div>

          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="section-heading">Output Schema</div>
            <pre style={{
              background: 'var(--code-bg)',
              padding: '12px',
              borderRadius: '4px',
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              overflow: 'auto',
              maxHeight: '200px',
            }}>
              {JSON.stringify(agent.output_schema, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === 1 && (
        <div className="card">
          <div className="section-heading">Trust Score Breakdown</div>
          {trustData ? (
            <div style={{ display: 'grid', gap: '16px' }}>
              <div style={{ font: 'var(--text-data-lg)', color: 'var(--text-primary)' }} className="mono">
                {trustData.trust_score.toFixed(3)}
              </div>
              {[
                { label: 'Success Rate', value: trustData.success_rate, weight: 0.4 },
                { label: 'SLA Compliance', value: trustData.sla_compliance, weight: 0.3 },
                { label: 'Cost Accuracy', value: trustData.cost_accuracy, weight: 0.2 },
                { label: 'Policy Violations', value: trustData.policy_violations_inverse, weight: 0.1 },
              ].map(comp => (
                <div key={comp.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{comp.label} (×{comp.weight})</span>
                    <span className="mono" style={{ fontSize: '12px' }}>{comp.value.toFixed(3)}</span>
                  </div>
                  <div style={{ background: 'var(--bg-tertiary)', borderRadius: '2px', height: '4px' }}>
                    <div style={{
                      width: `${comp.value * 100}%`,
                      height: '100%',
                      background: comp.value >= 0.7 ? 'var(--status-active)' : comp.value >= 0.4 ? 'var(--status-probationary)' : 'var(--status-quarantined)',
                      borderRadius: '2px',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon="★" heading="No trust data" message="Trust data will appear after the agent completes delegations." />
          )}
        </div>
      )}

      {activeTab === 2 && (
        agentDelegations && agentDelegations.length > 0 ? (
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Created', 'Role', 'Counterparty', 'Status', 'Est. Cost', 'Actual Cost'].map((h) => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {agentDelegations.map((d) => {
                  const isCaller = d.caller_agent_id === agentId;
                  const counterparty = isCaller ? d.callee_agent_id : d.caller_agent_id;
                  return (
                    <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(d.created_at)}</td>
                      <td style={{ padding: '8px 12px' }}>{isCaller ? 'caller' : 'callee'}</td>
                      <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{counterparty}</td>
                      <td style={{ padding: '8px 12px' }}><StatusPill status={d.status} /></td>
                      <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(d.estimated_cost_usd)}</td>
                      <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(d.actual_cost_usd)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="⇄" heading="No delegation history" message={`No delegations found for ${agentId}.`} />
        )
      )}

      {activeTab === 3 && (
        agentAudit && agentAudit.length > 0 ? (
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Event', 'Target', 'Cost'].map((h) => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {agentAudit.map((entry) => (
                  <tr key={entry.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>{formatRelativeTime(entry.created_at)}</td>
                    <td style={{ padding: '8px 12px' }}>{entry.event_type.replace(/_/g, ' ')}</td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{entry.target_agent_id ?? '—'}</td>
                    <td className="mono" style={{ padding: '8px 12px', fontSize: '12px' }}>{formatUsd(entry.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="⊞" heading="No audit history" message={`No audit entries found for ${agentId}.`} />
        )
      )}
    </div>
  );
}
