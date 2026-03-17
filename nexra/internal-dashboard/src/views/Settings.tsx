import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPatch, apiPost } from '../api/client';
import { EmptyState } from '../components/common/EmptyState';
import { RefreshAge } from '../components/Shell/RefreshAge';
import { useSession } from '../hooks/useSession';
import { hasPermission } from '../utils/rbac';

type SettingsTab = 'organization' | 'siem' | 'billing';
type ExtendedSettingsTab = SettingsTab | 'apiKeys' | 'team' | 'webhooks';

interface OrgSettings {
  org_id: string;
  name: string;
  plan: string;
  max_delegation_depth: number | null;
  owner_email: string | null;
  approval_url: string | null;
  notification_url: string | null;
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

interface OrgWebhookSettings {
  approval_url: string | null;
  notification_url: string | null;
}

export function Settings() {
  const [tab, setTab] = useState<ExtendedSettingsTab>('organization');
  const queryClient = useQueryClient();
  const session = useSession();
  const role = session.data?.role ?? 'viewer';
  const canManageKeys = hasPermission(role, 'manageApiKeys');
  const canManageTeam = hasPermission(role, 'manageTeam');
  const canConfigureWebhooks = hasPermission(role, 'configureWebhooks');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');

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
  const apiKeysQuery = useQuery<{ items: Array<{
    id: string;
    name: string;
    key_prefix: string;
    created_at: string;
    last_used_at: string | null;
    revoked_at: string | null;
  }> }>({
    queryKey: ['org-api-keys'],
    queryFn: () => apiGet('/orgs/api-keys'),
  });
  const membersQuery = useQuery<{ items: Array<{
    id: string;
    email: string;
    role: 'admin' | 'engineer' | 'compliance' | 'viewer';
    created_at: string;
    last_active_at: string | null;
  }> }>({
    queryKey: ['org-members'],
    queryFn: () => apiGet('/orgs/members'),
  });
  const webhookSettingsQuery = useQuery<OrgWebhookSettings>({
    queryKey: ['org-webhooks'],
    queryFn: () => apiGet('/orgs/webhooks'),
  });

  const [orgNameDraft, setOrgNameDraft] = useState<string | null>(null);
  const [approvalUrlDraft, setApprovalUrlDraft] = useState<string | null>(null);
  const [siemTargetDraft, setSiemTargetDraft] = useState<string | null>(null);
  const [siemEndpointDraft, setSiemEndpointDraft] = useState<string | null>(null);
  const [siemApiKey, setSiemApiKey] = useState('');
  const [siemEnabledDraft, setSiemEnabledDraft] = useState<boolean | null>(null);
  const [siemEventTypesDraft, setSiemEventTypesDraft] = useState<string | null>(null);
  const [approvalWebhookDraft, setApprovalWebhookDraft] = useState<string | null>(null);
  const [notificationWebhookDraft, setNotificationWebhookDraft] = useState<string | null>(null);
  const [maxDepthDraft, setMaxDepthDraft] = useState<string | null>(null);
  const [webhookTestResult, setWebhookTestResult] = useState<string | null>(null);

  const orgName = orgNameDraft ?? orgQuery.data?.name ?? '';
  const approvalUrl = approvalUrlDraft ?? orgQuery.data?.approval_url ?? '';
  const siemTarget = siemTargetDraft ?? siemQuery.data?.target ?? 'generic';
  const siemEndpoint = siemEndpointDraft ?? siemQuery.data?.endpoint ?? '';
  const siemEnabled = siemEnabledDraft ?? Boolean(siemQuery.data?.enabled ?? true);
  const siemEventTypes = siemEventTypesDraft ?? (siemQuery.data?.event_types ?? []).join(',');
  const approvalWebhook = approvalWebhookDraft ?? webhookSettingsQuery.data?.approval_url ?? '';
  const notificationWebhook = notificationWebhookDraft ?? webhookSettingsQuery.data?.notification_url ?? '';
  const maxDelegationDepth = maxDepthDraft ?? String(orgQuery.data?.max_delegation_depth ?? 5);

  const updateOrgMutation = useMutation({
    mutationFn: () => apiPatch('/orgs/me', {
      name: orgName,
      approval_url: approvalUrl || null,
      max_delegation_depth: Number(maxDelegationDepth),
    }),
    onSuccess: () => {
      setOrgNameDraft(null);
      setApprovalUrlDraft(null);
      setMaxDepthDraft(null);
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
      setSiemTargetDraft(null);
      setSiemEndpointDraft(null);
      setSiemEnabledDraft(null);
      setSiemEventTypesDraft(null);
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
  const createApiKeyMutation = useMutation({
    mutationFn: (name: string) => apiPost<{ api_key: string; key_prefix: string; name: string }>('/orgs/api-keys', { name }),
    onSuccess: (data) => {
      window.alert(`New API key (copy now):\n${data.api_key}`);
      queryClient.invalidateQueries({ queryKey: ['org-api-keys'] });
    },
  });
  const revokeApiKeyMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/orgs/api-keys/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-api-keys'] });
    },
  });
  const inviteMemberMutation = useMutation({
    mutationFn: () => apiPost('/orgs/members', { email: inviteEmail, role: inviteRole }),
    onSuccess: () => {
      setInviteEmail('');
      setInviteRole('viewer');
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
    },
  });
  const updateMemberMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => apiPatch(`/orgs/members/${id}`, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
    },
  });
  const deleteMemberMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/orgs/members/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
    },
  });
  const updateWebhookMutation = useMutation({
    mutationFn: () => apiPatch('/orgs/webhooks', {
      approval_url: approvalWebhook || null,
      notification_url: notificationWebhook || null,
    }),
    onSuccess: () => {
      setApprovalWebhookDraft(null);
      setNotificationWebhookDraft(null);
      queryClient.invalidateQueries({ queryKey: ['org-webhooks'] });
    },
  });
  const testWebhookMutation = useMutation({
    mutationFn: (target: 'approval' | 'notification') => apiPost<{ ok: boolean; status_code: number | null; error: string | null }>('/orgs/webhooks/test', { target }),
    onSuccess: (data, target) => {
      setWebhookTestResult(`${target}: ${data.ok ? 'ok' : 'failed'}${data.status_code ? ` (status ${data.status_code})` : ''}${data.error ? ` - ${data.error}` : ''}`);
    },
    onError: () => {
      setWebhookTestResult('Webhook test failed');
    },
  });

  const tabs = useMemo<Array<{ key: ExtendedSettingsTab; label: string }>>(
    () => [
      { key: 'organization', label: 'Organization' },
      { key: 'apiKeys', label: 'API Keys' },
      { key: 'team', label: 'Team' },
      { key: 'webhooks', label: 'Webhooks' },
      { key: 'siem', label: 'SIEM' },
      { key: 'billing', label: 'Billing' },
    ],
    [],
  );

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <RefreshAge queryKeys={[['org-settings'], ['org-api-keys'], ['org-members'], ['org-webhooks']]} />
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
                <input value={orgName} onChange={(e) => setOrgNameDraft(e.target.value)} />
                <div style={{ color: 'var(--text-tertiary)' }}>Approval URL</div>
                <input value={approvalUrl} onChange={(e) => setApprovalUrlDraft(e.target.value)} placeholder="https://example.com/approval-webhook" />
                <div style={{ color: 'var(--text-tertiary)' }}>Max Delegation Depth</div>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={maxDelegationDepth}
                  onChange={(e) => setMaxDepthDraft(e.target.value)}
                />
                <div style={{ color: 'var(--text-tertiary)' }}>Owner Email</div>
                <div className="mono" style={{ padding: '8px 0' }}>{orgQuery.data.owner_email ?? 'N/A'}</div>
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
            <select value={siemTarget} onChange={(e) => setSiemTargetDraft(e.target.value)}>
              <option value="generic">generic</option>
              <option value="splunk">splunk</option>
              <option value="datadog">datadog</option>
              <option value="elastic">elastic</option>
            </select>
            <div style={{ color: 'var(--text-tertiary)' }}>Endpoint</div>
            <input value={siemEndpoint} onChange={(e) => setSiemEndpointDraft(e.target.value)} placeholder="https://siem.example.com/ingest" />
            <div style={{ color: 'var(--text-tertiary)' }}>API Key</div>
            <input value={siemApiKey} onChange={(e) => setSiemApiKey(e.target.value)} type="password" placeholder={siemQuery.data?.api_key_set ? 'Key already set (enter new to rotate)' : 'Optional'} />
            <div style={{ color: 'var(--text-tertiary)' }}>Event Types</div>
            <input value={siemEventTypes} onChange={(e) => setSiemEventTypesDraft(e.target.value)} placeholder="policy_evaluated,delegation_completed" />
          </div>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '12px', fontSize: '13px' }}>
            <input type="checkbox" checked={siemEnabled} onChange={(e) => setSiemEnabledDraft(e.target.checked)} />
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

      {tab === 'apiKeys' && (
        <div className="card">
          <div className="section-heading">API Keys</div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <button
              className="btn btn-primary"
              onClick={() => {
                const name = window.prompt('Key label', 'dashboard');
                if (!name) return;
                createApiKeyMutation.mutate(name);
              }}
              disabled={createApiKeyMutation.isPending || !canManageKeys}
            >
              {createApiKeyMutation.isPending ? 'Creating…' : 'Create API Key'}
            </button>
          </div>
          {!apiKeysQuery.data || apiKeysQuery.data.items.length === 0 ? (
            <EmptyState icon="K" heading="No API keys" message="Create an API key to access the API." />
          ) : (
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Label', 'Prefix', 'Created', 'Last Used', 'Status', 'Actions'].map((h) => (
                      <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {apiKeysQuery.data.items.map((item) => (
                    <tr key={item.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px' }}>{item.name}</td>
                      <td style={{ padding: '8px 12px' }} className="mono">{item.key_prefix}</td>
                      <td style={{ padding: '8px 12px' }} className="mono">{item.created_at}</td>
                      <td style={{ padding: '8px 12px' }} className="mono">{item.last_used_at ?? '—'}</td>
                      <td style={{ padding: '8px 12px' }}>{item.revoked_at ? 'revoked' : 'active'}</td>
                      <td style={{ padding: '8px 12px' }}>
                        {!item.revoked_at && (
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => revokeApiKeyMutation.mutate(item.id)}
                            disabled={revokeApiKeyMutation.isPending || !canManageKeys}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'team' && (
        <div className="card">
          <div className="section-heading">Team Members</div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
            <input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="member@example.com"
              style={{ minWidth: '220px' }}
            />
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
              <option value="viewer">viewer</option>
              <option value="compliance">compliance</option>
              <option value="engineer">engineer</option>
              <option value="admin">admin</option>
            </select>
            <button
              className="btn btn-primary"
              onClick={() => inviteMemberMutation.mutate()}
              disabled={inviteMemberMutation.isPending || !inviteEmail || !canManageTeam}
            >
              {inviteMemberMutation.isPending ? 'Inviting…' : 'Invite'}
            </button>
          </div>
          {!membersQuery.data || membersQuery.data.items.length === 0 ? (
            <EmptyState icon="M" heading="No members" message="Invite members to collaborate in the dashboard." />
          ) : (
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Email', 'Role', 'Joined', 'Last Active', 'Actions'].map((h) => (
                      <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {membersQuery.data.items.map((member) => (
                    <tr key={member.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px' }}>{member.email}</td>
                      <td style={{ padding: '8px 12px' }}>
                        <select
                          value={member.role}
                          onChange={(e) => updateMemberMutation.mutate({ id: member.id, role: e.target.value })}
                          disabled={!canManageTeam}
                        >
                          <option value="viewer">viewer</option>
                          <option value="compliance">compliance</option>
                          <option value="engineer">engineer</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td style={{ padding: '8px 12px' }} className="mono">{member.created_at}</td>
                      <td style={{ padding: '8px 12px' }} className="mono">{member.last_active_at ?? '—'}</td>
                      <td style={{ padding: '8px 12px' }}>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => deleteMemberMutation.mutate(member.id)}
                          disabled={deleteMemberMutation.isPending || !canManageTeam}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'webhooks' && (
        <div className="card">
          <div className="section-heading">Webhook Governance</div>
          <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '8px', fontSize: '13px' }}>
            <div style={{ color: 'var(--text-tertiary)' }}>Approval Endpoint</div>
            <input
              value={approvalWebhook}
              onChange={(e) => setApprovalWebhookDraft(e.target.value)}
              placeholder="https://example.com/hitl-approval"
              disabled={!canConfigureWebhooks}
            />
            <div style={{ color: 'var(--text-tertiary)' }}>Notification Endpoint</div>
            <input
              value={notificationWebhook}
              onChange={(e) => setNotificationWebhookDraft(e.target.value)}
              placeholder="https://example.com/ops-notify"
              disabled={!canConfigureWebhooks}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '16px', flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary"
              onClick={() => updateWebhookMutation.mutate()}
              disabled={updateWebhookMutation.isPending || !canConfigureWebhooks}
            >
              {updateWebhookMutation.isPending ? 'Saving…' : 'Save Webhooks'}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => testWebhookMutation.mutate('approval')}
              disabled={testWebhookMutation.isPending || !canConfigureWebhooks}
            >
              Test Approval Ping
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => testWebhookMutation.mutate('notification')}
              disabled={testWebhookMutation.isPending || !canConfigureWebhooks}
            >
              Test Notification Ping
            </button>
          </div>
          {webhookTestResult && (
            <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              {webhookTestResult}
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
