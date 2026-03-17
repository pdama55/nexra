import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPut } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import type { Policy } from '../types';
import { useState } from 'react';
import { formatAbsoluteTime } from '../utils/formatters';
import { useSession } from '../hooks/useSession';
import { hasPermission } from '../utils/rbac';

interface PolicyDetailPayload {
  current: Policy & {
    allow?: Record<string, unknown>;
    conditions?: Array<Record<string, unknown>>;
    hil_threshold_usd?: number | null;
    on_violation?: string;
  };
}

interface PolicyEvalEvent {
  id: string;
  created_at: string;
  actor_agent_id: string | null;
  target_agent_id: string | null;
  details: Record<string, unknown>;
}

export function PolicyDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [editDescription, setEditDescription] = useState('');
  const [editPriority, setEditPriority] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const session = useSession();
  const canEdit = hasPermission(session.data?.role ?? 'viewer', 'createPolicy');

  const { data: payload } = useQuery<PolicyDetailPayload>({
    queryKey: ['policy', id],
    queryFn: () => apiGet(`/policies/${id}`),
    enabled: !!id,
  });
  const { data: versions } = useQuery<Policy[]>({
    queryKey: ['policy-versions', id],
    queryFn: () =>
      apiGet<{ versions: Policy[] }>(`/policies/${id}/versions`).then((r) => r.versions),
    enabled: !!id && activeTab === 1,
  });
  const { data: evaluations } = useQuery<PolicyEvalEvent[]>({
    queryKey: ['policy-evaluations', id],
    queryFn: () =>
      apiGet<{ entries: PolicyEvalEvent[] }>('/audit/log', {
        event_type: 'policy_evaluated',
        limit: 100,
      }).then((r) =>
        r.entries.filter(
          (e) => String(e.details?.policy_id ?? '') === String(id ?? ''),
        ),
      ),
    enabled: !!id && activeTab === 2,
  });
  const updateMutation = useMutation({
    mutationFn: (payload: { description: string; priority: number }) => apiPut(`/policies/${id}`, payload),
    onSuccess: () => {
      setEditOpen(false);
      setEditError(null);
      queryClient.invalidateQueries({ queryKey: ['policy', id] });
      queryClient.invalidateQueries({ queryKey: ['policy-versions', id] });
      queryClient.invalidateQueries({ queryKey: ['policies'] });
    },
    onError: () => {
      setEditError('Update failed. Check values and retry.');
    },
  });

  function openEditPolicy(): void {
    if (!policy) return;
    setEditDescription(policy.description ?? '');
    setEditPriority(String(policy.priority));
    setEditError(null);
    setEditOpen(true);
  }

  function submitPolicyEdit(): void {
    const parsedPriority = Number(editPriority);
    if (!Number.isFinite(parsedPriority) || parsedPriority < 1) {
      setEditError('Priority must be a positive number.');
      return;
    }
    updateMutation.mutate({
      description: editDescription.trim(),
      priority: parsedPriority,
    });
  }

  const policy = payload?.current;
  if (!policy) {
    return <EmptyState icon="⛊" heading="Policy not found" message={`No policy found with ID: ${id}`} />;
  }

  const tabs = ['Current Policy', 'Version History', 'Evaluation History'];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {policy.name}
            <StatusPill status={policy.enabled ? 'active' : 'quarantined'} />
            <span className="mono" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>v{policy.version}</span>
          </h1>
          {policy.description && (
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>{policy.description}</div>
          )}
        </div>
        {canEdit && (
          <button className="btn btn-primary" onClick={openEditPolicy} disabled={updateMutation.isPending}>
            Edit
          </button>
        )}
      </div>

      {editOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.55)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1200,
          }}
          onClick={() => setEditOpen(false)}
        >
          <div className="card" style={{ width: 'min(520px, 92vw)' }} onClick={(event) => event.stopPropagation()}>
            <div className="section-heading">Edit Policy</div>
            <div style={{ display: 'grid', gap: '10px' }}>
              <textarea
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
                rows={4}
                placeholder="Description"
              />
              <input
                value={editPriority}
                onChange={(event) => setEditPriority(event.target.value)}
                inputMode="numeric"
                placeholder="Priority"
              />
            </div>
            {editError && (
              <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--status-quarantined)' }}>{editError}</div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
              <button className="btn btn-secondary" onClick={() => setEditOpen(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitPolicyEdit} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="tabs">
        {tabs.map((tab, i) => (
          <button key={tab} className={`tab${activeTab === i ? ' active' : ''}`} onClick={() => setActiveTab(i)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 0 && (
        <div className="card">
          <pre style={{
            background: 'var(--code-bg)',
            padding: '16px',
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            overflow: 'auto',
            lineHeight: 1.6,
            color: 'var(--text-primary)',
          }}>
            {JSON.stringify(
              {
                allow: policy.allow ?? {},
                conditions: policy.conditions ?? [],
                hil_threshold_usd: policy.hil_threshold_usd ?? null,
                on_violation: policy.on_violation ?? 'block_and_alert',
              },
              null,
              2,
            )}
          </pre>
        </div>
      )}

      {activeTab === 1 && (
        versions && versions.length > 0 ? (
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Version', 'Priority', 'Enabled', 'Created'].map((h) => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => (
                  <tr key={v.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="mono" style={{ padding: '8px 12px' }}>v{v.version}</td>
                    <td className="mono" style={{ padding: '8px 12px' }}>{v.priority}</td>
                    <td style={{ padding: '8px 12px' }}>
                      <StatusPill status={v.enabled ? 'active' : 'quarantined'} />
                    </td>
                    <td style={{ padding: '8px 12px' }}>{formatAbsoluteTime(v.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="⊞" heading="No version history" message="No prior versions found for this policy." />
        )
      )}

      {activeTab === 2 && (
        evaluations && evaluations.length > 0 ? (
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Time', 'Actor', 'Target', 'Decision', 'Reason'].map((h) => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {evaluations.map((e) => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px' }}>{formatAbsoluteTime(e.created_at)}</td>
                    <td className="mono" style={{ padding: '8px 12px' }}>{e.actor_agent_id ?? 'system'}</td>
                    <td className="mono" style={{ padding: '8px 12px' }}>{e.target_agent_id ?? '—'}</td>
                    <td style={{ padding: '8px 12px' }}>{String(e.details?.decision ?? '—')}</td>
                    <td style={{ padding: '8px 12px' }}>{String(e.details?.reason ?? '—')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="⊞" heading="No evaluation history" message="No policy evaluation events found for this policy." />
        )
      )}
    </div>
  );
}
