import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime, formatUsd, truncateId } from '../utils/formatters';
import type { Delegation } from '../types';
import { useState } from 'react';

export function HitlQueue() {
  const queryClient = useQueryClient();
  const [confirmAction, setConfirmAction] = useState<{ id: string; action: 'approve' | 'reject' } | null>(null);

  const { data: pendingDelegations, isLoading } = useQuery<Delegation[]>({
    queryKey: ['hitl-queue'],
    queryFn: () => apiGet<{ items: Delegation[] }>('/delegations', {
      status: 'pending_approval',
      sort: 'created_at:asc',
      limit: 50,
    }).then(r => r.items),
    refetchInterval: 30_000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/delegations/${id}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hitl-queue'] });
      setConfirmAction(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/delegations/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hitl-queue'] });
      setConfirmAction(null);
    },
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Human-in-the-Loop Queue</h1>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          {pendingDelegations?.length ?? 0} pending
        </span>
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading queue…</div>
      ) : !pendingDelegations || pendingDelegations.length === 0 ? (
        <EmptyState
          icon="✓"
          heading="No delegations pending approval"
          message="All clear. HiTL approvals will appear here when a delegation triggers a policy gate."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {pendingDelegations.map(d => (
            <div key={d.id} className="card" style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
                  <Link to={`/delegations/${d.id}`} className="mono" style={{ fontSize: '13px' }}>{truncateId(d.id)}</Link>
                  <StatusPill status="pending approval" />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '4px', fontSize: '12px' }}>
                  <div style={{ color: 'var(--text-tertiary)' }}>Caller</div>
                  <Link to={`/agents/${d.caller_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{d.caller_agent_id}</Link>
                  <div style={{ color: 'var(--text-tertiary)' }}>Callee</div>
                  <Link to={`/agents/${d.callee_agent_id}`} className="mono" style={{ fontSize: '12px' }}>{d.callee_agent_id}</Link>
                  <div style={{ color: 'var(--text-tertiary)' }}>Est. Cost</div>
                  <div className="mono">{formatUsd(d.estimated_cost_usd)}</div>
                  <div style={{ color: 'var(--text-tertiary)' }}>Requested</div>
                  <div>{formatRelativeTime(d.created_at)}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                <button
                  className="btn btn-sm"
                  style={{ background: 'var(--status-active-bg)', color: 'var(--status-active)', border: '1px solid #2A3E2E' }}
                  onClick={() => setConfirmAction({ id: d.id, action: 'approve' })}
                  disabled={approveMutation.isPending}
                >
                  Approve
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => setConfirmAction({ id: d.id, action: 'reject' })}
                  disabled={rejectMutation.isPending}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confirmation modal */}
      {confirmAction && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }} onClick={() => setConfirmAction(null)}>
          <div className="card" style={{ padding: '24px', maxWidth: '400px', width: '100%' }} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: '16px', fontWeight: 500, marginBottom: '12px' }}>
              {confirmAction.action === 'approve' ? 'Approve delegation?' : 'Reject delegation?'}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
              {confirmAction.action === 'approve'
                ? 'This will resume the paused delegation and execute it.'
                : 'This will permanently reject the delegation. It cannot be undone.'}
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setConfirmAction(null)}>Cancel</button>
              <button
                className={`btn ${confirmAction.action === 'approve' ? 'btn-primary' : 'btn-danger'}`}
                onClick={() => {
                  if (confirmAction.action === 'approve') {
                    approveMutation.mutate(confirmAction.id);
                  } else {
                    rejectMutation.mutate(confirmAction.id);
                  }
                }}
              >
                {confirmAction.action === 'approve' ? 'Approve' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
