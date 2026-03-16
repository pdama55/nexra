import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPatch, apiPost } from '../api/client';
import { EmptyState } from '../components/common/EmptyState';

type SettingsTab = 'organization' | 'siem' | 'billing';

interface OrgSettings {
  org_id: string;
  name: string;
  plan: string;
  approval_url: string | null;
  stripe_connect_account_id: string | null;
  created_at: string;
}

interface SIEMSettings {
  target?: string;
  endpoint?: string;
  enabled?: boolean;
  event_types?: string[];
  api_key_set?: boolean;
  cursor?: string | null;
}

export function Settings() {
  const [tab, setTab] = useState<SettingsTab>('organization');
  const queryClient = useQueryClient();

  const orgQuery = useQuery<OrgSettings>({
    queryKey: ['org-settings'],
    queryFn: () => apiGet('/orgs/me'),
  });
  const siemQuery = useQuery<SIEMSettings>({
    queryKey: ['siem-config'],
    queryFn: () => apiGet('/siem/config'),
  });
  const connectStatusQuery = useQuery<{ onboarded: boolean; stripe_connect_account_id: string | null }>({
    queryKey: ['connect-status'],
    queryFn: () => apiGet('/marketplace/connect-status'),
  });

  const [orgName, setOrgName] = useState('');
  const [approvalUrl, setApprovalUrl] = useState('');
  const [siemTarget, setSiemTarget] = useState('generic');
  const [siemEndpoint, setSiemEndpoint] = useState('');
  const [siemApiKey, setSiemApiKey] = useState('');
  const [siemEnabled, setSiemEnabled] = useState(true);
  const [siemEventTypes, setSiemEventTypes] = useState('');

  useEffect(() => {
    if (!orgQuery.data) return;
    setOrgName(orgQuery.data.name);
    setApprovalUrl(orgQuery.data.approval_url ?? '');
  }, [orgQuery.data]);

  useEffect(() => {
    if (!siemQuery.data) return;
    setSiemTarget(siemQuery.data.target ?? 'generic');
    setSiemEndpoint(siemQuery.data.endpoint ?? '');
    setSiemEnabled(Boolean(siemQuery.data.enabled));
    setSiemEventTypes((siemQuery.data.event_types ?? []).join(','));
    setSiemApiKey('');
  }, [siemQuery.data]);

  const updateOrgMutation = useMutation({
    mutationFn: () => apiPatch('/orgs/me', { name: orgName, approval_url: approvalUrl || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-settings'] });
    },
  });

  const updateSIEMMutation = useMutation({
    mutationFn: () => apiPost('/siem/config', {
      target: siemTarget,
      endpoint: siemEndpoint,
      api_key: siemApiKey || null,
      enabled: siemEnabled,
      event_types: siemEventTypes
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siem-config'] });
      setSiemApiKey('');
    },
  });

  const connectMutation = useMutation({
    mutationFn: () => apiPost<{ onboarding_url: string }>('/marketplace/connect-onboard'),
    onSuccess: (data) => {
      if (data.onboarding_url) {
        window.open(data.onboarding_url, '_blank', 'noopener,noreferrer');
      }
      queryClient.invalidateQueries({ queryKey: ['connect-status'] });
      queryClient.invalidateQueries({ queryKey: ['org-settings'] });
    },
  });

  const tabs = useMemo<Array<{ key: SettingsTab; label: string }>>(
    () => [
      { key: 'organization', label: 'Organization' },
      { key: 'siem', label: 'SIEM' },
      { key: 'billing', label: 'Billing' },
    ],
    [],
  );

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div className="tabs">
        {tabs.map((t) => (
          <button key={t.key} className={`tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'organization' && (
        <div className="card">
          {orgQuery.data ? (
            <>
              <div className="section-heading">Organization Profile</div>
              <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
                <div style={{ color: 'var(--text-tertiary)' }}>Org Name</div>
                <input value={orgName} onChange={(e) => setOrgName(e.target.value)} />
                <div style={{ color: 'var(--text-tertiary)' }}>Approval URL</div>
                <input value={approvalUrl} onChange={(e) => setApprovalUrl(e.target.value)} placeholder="https://example.com/approval-webhook" />
                <div style={{ color: 'var(--text-tertiary)' }}>Plan</div>
                <div className="mono" style={{ padding: '8px 0' }}>{orgQuery.data.plan}</div>
                <div style={{ color: 'var(--text-tertiary)' }}>Org ID</div>
                <div className="mono" style={{ padding: '8px 0' }}>{orgQuery.data.org_id}</div>
              </div>
              <button
                className="btn btn-primary"
                style={{ marginTop: '16px' }}
                disabled={updateOrgMutation.isPending}
                onClick={() => updateOrgMutation.mutate()}
              >
                {updateOrgMutation.isPending ? 'Saving…' : 'Save Organization'}
              </button>
            </>
          ) : (
            <EmptyState icon="O" heading="Organization unavailable" message="Unable to load organization settings." />
          )}
        </div>
      )}

      {tab === 'siem' && (
        <div className="card">
          <div className="section-heading">SIEM Export Configuration</div>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', fontSize: '13px' }}>
            <div style={{ color: 'var(--text-tertiary)' }}>Target</div>
            <select value={siemTarget} onChange={(e) => setSiemTarget(e.target.value)}>
              <option value="generic">generic</option>
              <option value="splunk">splunk</option>
              <option value="datadog">datadog</option>
              <option value="elastic">elastic</option>
            </select>
            <div style={{ color: 'var(--text-tertiary)' }}>Endpoint</div>
            <input value={siemEndpoint} onChange={(e) => setSiemEndpoint(e.target.value)} placeholder="https://siem.example.com/ingest" />
            <div style={{ color: 'var(--text-tertiary)' }}>API Key</div>
            <input value={siemApiKey} onChange={(e) => setSiemApiKey(e.target.value)} type="password" placeholder={siemQuery.data?.api_key_set ? 'Key already set (enter new to rotate)' : 'Optional'} />
            <div style={{ color: 'var(--text-tertiary)' }}>Event Types</div>
            <input value={siemEventTypes} onChange={(e) => setSiemEventTypes(e.target.value)} placeholder="policy_evaluated,delegation_completed" />
          </div>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '12px', fontSize: '13px' }}>
            <input type="checkbox" checked={siemEnabled} onChange={(e) => setSiemEnabled(e.target.checked)} />
            Enabled
          </label>
          <div style={{ marginTop: '16px' }}>
            <button
              className="btn btn-primary"
              disabled={updateSIEMMutation.isPending || !siemEndpoint}
              onClick={() => updateSIEMMutation.mutate()}
            >
              {updateSIEMMutation.isPending ? 'Saving…' : 'Save SIEM Config'}
            </button>
          </div>
          {siemQuery.data?.cursor && (
            <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Last export cursor: <span className="mono">{siemQuery.data.cursor}</span>
            </div>
          )}
        </div>
      )}

      {tab === 'billing' && (
        <div className="card">
          <div className="section-heading">Stripe Connect</div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            Cross-org marketplace payouts require a connected Stripe account.
          </div>
          <div style={{ fontSize: '13px', marginBottom: '12px' }}>
            Status:{' '}
            <strong>
              {connectStatusQuery.data?.onboarded ? 'Onboarded' : 'Not onboarded'}
            </strong>
          </div>
          <button
            className="btn btn-primary"
            disabled={connectMutation.isPending}
            onClick={() => connectMutation.mutate()}
          >
            {connectMutation.isPending ? 'Opening…' : 'Start Connect Onboarding'}
          </button>
          {connectStatusQuery.data?.stripe_connect_account_id && (
            <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Connect Account: <span className="mono">{connectStatusQuery.data.stripe_connect_account_id}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
