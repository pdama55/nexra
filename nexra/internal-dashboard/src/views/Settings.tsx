import { useState } from 'react';

export function Settings() {
  const [activeTab, setActiveTab] = useState(0);
  const tabs = ['API Keys', 'Team', 'Webhooks', 'Billing', 'Organization'];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div className="tabs">
        {tabs.map((tab, i) => (
          <button key={tab} className={`tab${activeTab === i ? ' active' : ''}`} onClick={() => setActiveTab(i)}>
            {tab}
          </button>
        ))}
      </div>

      {/* API Keys */}
      {activeTab === 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div className="section-heading" style={{ margin: 0 }}>API Keys</div>
            <button className="btn btn-primary">Create API Key</button>
          </div>
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Name', 'Key Prefix', 'Created', 'Last Used', 'Actions'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '13px' }}>
                    No API keys created yet.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Team */}
      {activeTab === 1 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div className="section-heading" style={{ margin: 0 }}>Team Members</div>
            <button className="btn btn-primary">Invite Member</button>
          </div>
          <div className="card">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Email', 'Role', 'Joined', 'Actions'].map(h => (
                    <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={4} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '13px' }}>
                    No team members added yet.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Webhooks */}
      {activeTab === 2 && (
        <div>
          <div className="section-heading">Webhook Configuration</div>
          <div className="card">
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px', fontSize: '13px' }}>
              <div style={{ color: 'var(--text-tertiary)' }}>Endpoint URL</div>
              <input placeholder="https://your-endpoint.com/webhook" style={{ width: '100%' }} />
              <div style={{ color: 'var(--text-tertiary)' }}>Secret</div>
              <input placeholder="whsec_..." type="password" style={{ width: '100%' }} />
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              <button className="btn btn-primary">Save</button>
              <button className="btn btn-secondary">Test Webhook</button>
            </div>
          </div>
        </div>
      )}

      {/* Billing */}
      {activeTab === 3 && (
        <div>
          <div className="section-heading">Billing</div>
          <div className="card">
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Manage your subscription and billing through Stripe.
            </div>
            <button className="btn btn-primary">Open Stripe Portal</button>
          </div>
        </div>
      )}

      {/* Organization */}
      {activeTab === 4 && (
        <div>
          <div className="section-heading">Organization</div>
          <div className="card" style={{ marginBottom: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px', fontSize: '13px' }}>
              <div style={{ color: 'var(--text-tertiary)' }}>Org Name</div>
              <input defaultValue="Nexra Org" style={{ width: '100%' }} />
              <div style={{ color: 'var(--text-tertiary)' }}>Plan</div>
              <div className="mono" style={{ padding: '8px 0' }}>Growth</div>
            </div>
            <button className="btn btn-primary" style={{ marginTop: '16px' }}>Save</button>
          </div>

          <div className="card" style={{ borderColor: '#3A2020' }}>
            <div className="section-heading" style={{ color: '#9A4A4A' }}>Danger Zone</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Permanently delete this organization and all associated data. This action cannot be undone.
            </div>
            <button className="btn btn-danger">Delete Organization</button>
          </div>
        </div>
      )}
    </div>
  );
}
