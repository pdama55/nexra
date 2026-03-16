import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatUsd, formatLatency, formatAbsoluteTime, truncateId } from '../utils/formatters';
import type { Delegation, AuditEntry } from '../types';

export function DelegationDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: delegation } = useQuery<Delegation>({
    queryKey: ['delegation', id],
    queryFn: () => apiGet(`/delegations/${id}`),
    enabled: !!id,
  });

  const { data: timeline } = useQuery<AuditEntry[]>({
    queryKey: ['delegation-timeline', id],
    queryFn: () => apiGet<{ entries: AuditEntry[] }>('/audit/log', { delegation_id: id }).then(r => r.entries),
    enabled: !!id,
  });

  if (!delegation) {
    return <EmptyState icon="⇄" heading="Delegation not found" message={`No delegation found with ID: ${id}`} />;
  }

  return (
    <div>
      {delegation.status === 'blocked' && (
        <div style={{
          background: 'var(--status-blocked-bg)',
          border: '1px solid #3A2020',
          borderRadius: '4px',
          padding: '16px',
          marginBottom: '24px',
          color: '#9A4A4A',
          fontWeight: 500,
          fontSize: '14px',
        }}>
          POLICY BLOCKED — This delegation was blocked by policy {truncateId(delegation.policy_id)}.
        </div>
      )}

      <div className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          Delegation {truncateId(delegation.id)}
          <StatusPill status={delegation.status} />
        </h1>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
        {/* Left — Core Details */}
        <div className="card">
          <div className="section-heading">Details</div>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
            {[
              ['Delegation ID', delegation.id],
              ['Status', delegation.status],
              ['Created', formatAbsoluteTime(delegation.created_at)],
              ['Completed', formatAbsoluteTime(delegation.completed_at)],
              ['Latency', formatLatency(delegation.latency_ms)],
            ].map(([label, value]) => (
              <div key={label} style={{ display: 'contents' }}>
                <div style={{ color: 'var(--text-tertiary)' }}>{label}</div>
                <div className="mono">{value}</div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
              <div style={{ color: 'var(--text-tertiary)' }}>Caller</div>
              <Link to={`/agents/${delegation.caller_agent_id}`} className="mono">{delegation.caller_agent_id}</Link>
              <div style={{ color: 'var(--text-tertiary)' }}>Callee</div>
              <Link to={`/agents/${delegation.callee_agent_id}`} className="mono">{delegation.callee_agent_id}</Link>
              <div style={{ color: 'var(--text-tertiary)' }}>Budget cap</div>
              <div className="mono">{formatUsd(delegation.budget_cap_usd)}</div>
              <div style={{ color: 'var(--text-tertiary)' }}>Est. cost</div>
              <div className="mono">{formatUsd(delegation.estimated_cost_usd)}</div>
              <div style={{ color: 'var(--text-tertiary)' }}>Actual cost</div>
              <div className="mono">{formatUsd(delegation.actual_cost_usd)}</div>
              <div style={{ color: 'var(--text-tertiary)' }}>Context scope</div>
              <div className="mono">{delegation.context_scope.join(', ') || '—'}</div>
              <div style={{ color: 'var(--text-tertiary)' }}>Policy</div>
              <div>
                {delegation.policy_id ? (
                  <Link to={`/policies/${delegation.policy_id}`} className="mono" style={{ fontSize: '12px' }}>
                    {truncateId(delegation.policy_id)} v{delegation.policy_version}
                  </Link>
                ) : '—'}
              </div>
              <div style={{ color: 'var(--text-tertiary)' }}>Decision</div>
              <div>{delegation.policy_decision ? <StatusPill status={delegation.policy_decision} /> : '—'}</div>
            </div>
          </div>
        </div>

        {/* Right — Timeline */}
        <div className="card">
          <div className="section-heading">Timeline</div>
          {timeline && timeline.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
              {timeline.map((event, idx) => (
                <div key={event.id} style={{
                  display: 'flex',
                  gap: '12px',
                  padding: '8px 0',
                  borderLeft: idx < timeline.length - 1 ? '1px solid var(--border)' : '1px solid transparent',
                  marginLeft: '6px',
                  paddingLeft: '16px',
                  position: 'relative',
                }}>
                  <div style={{
                    position: 'absolute',
                    left: '-3px',
                    top: '12px',
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: event.event_type.includes('blocked') || event.event_type.includes('failed')
                      ? 'var(--status-quarantined)'
                      : event.event_type.includes('completed')
                        ? 'var(--status-active)'
                        : 'var(--text-tertiary)',
                  }} />
                  <div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className="mono" style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                        {new Date(event.created_at).toLocaleTimeString()}
                      </span>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {event.event_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {event.cost_usd != null && (
                      <div className="mono" style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                        {formatUsd(event.cost_usd)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon="⊞" heading="No timeline events" message="Timeline will populate as the delegation progresses." />
          )}
        </div>
      </div>

      {/* Result Payload */}
      {delegation.result && (
        <div className="card" style={{ marginTop: 'var(--space-xl)' }}>
          <div className="section-heading">Result Payload</div>
          <pre style={{
            background: 'var(--code-bg)',
            padding: '12px',
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            overflow: 'auto',
            maxHeight: '300px',
          }}>
            {JSON.stringify(delegation.result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
