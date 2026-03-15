import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import type { Policy } from '../types';
import { useState } from 'react';

export function PolicyDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState(0);

  const { data: policy } = useQuery<Policy>({
    queryKey: ['policy', id],
    queryFn: () => apiGet(`/policies/${id}`),
    enabled: !!id,
  });

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
        <button className="btn btn-primary">Edit</button>
      </div>

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
            {policy.rule_yaml}
          </pre>
        </div>
      )}

      {activeTab === 1 && (
        <EmptyState icon="⊞" heading="Version History" message="Version history will show all previous versions with diffs." />
      )}

      {activeTab === 2 && (
        <EmptyState icon="⊞" heading="Evaluation History" message="Shows every policy evaluation in the selected time window." />
      )}
    </div>
  );
}
