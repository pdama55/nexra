import { useState } from 'react';

const REPORT_TYPES = [
  { id: 'soc2', name: 'SOC 2 Type II', desc: 'Access controls, change management, monitoring evidence', icon: '🛡' },
  { id: 'gdpr', name: 'GDPR / DPA', desc: 'Data processing records, subject access log, retention', icon: '🇪🇺' },
  { id: 'hipaa', name: 'HIPAA', desc: 'PHI access audit trail, breach notification log', icon: '🏥' },
  { id: 'iso27001', name: 'ISO 27001', desc: 'Information security controls, risk metrics', icon: '📋' },
  { id: 'custom', name: 'Custom Export', desc: 'Full audit log with all fields, configurable filters', icon: '⬇' },
  { id: 'executive', name: 'Executive Summary', desc: 'High-level metrics, risk posture, compliance status', icon: '📊' },
];

export function ComplianceExport() {
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [generating, setGenerating] = useState(false);

  async function handleGenerate() {
    if (!selectedReport || !dateFrom || !dateTo) return;
    setGenerating(true);
    // Client-side CSV generation would go here — for now simulate delay
    await new Promise(r => setTimeout(r, 2000));
    setGenerating(false);
    setSelectedReport(null);
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Compliance Export</h1>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-lg)', marginBottom: 'var(--space-xl)' }}>
        {REPORT_TYPES.map(r => (
          <div
            key={r.id}
            className="card"
            style={{
              cursor: 'pointer',
              borderColor: selectedReport === r.id ? 'var(--border-strong)' : undefined,
            }}
            onClick={() => setSelectedReport(r.id)}
          >
            <div style={{ fontSize: '20px', marginBottom: '8px' }}>{r.icon}</div>
            <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '4px' }}>{r.name}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>{r.desc}</div>
          </div>
        ))}
      </div>

      {selectedReport && (
        <div className="card">
          <div className="section-heading">
            Generate {REPORT_TYPES.find(r => r.id === selectedReport)?.name} Report
          </div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', marginTop: '12px' }}>
            <div>
              <label className="label" style={{ display: 'block', marginBottom: '4px' }}>From</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label className="label" style={{ display: 'block', marginBottom: '4px' }}>To</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} />
            </div>
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={generating || !dateFrom || !dateTo}
            >
              {generating ? 'Generating…' : 'Generate Report'}
            </button>
          </div>
          {generating && (
            <div style={{ marginTop: '16px' }}>
              <div style={{ background: 'var(--bg-tertiary)', borderRadius: '2px', height: '4px', overflow: 'hidden' }}>
                <div style={{
                  width: '60%',
                  height: '100%',
                  background: 'var(--text-secondary)',
                  borderRadius: '2px',
                  animation: 'pulse 1.5s infinite',
                }} />
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '8px' }}>
                Generating report… this may take up to 30 seconds for large datasets.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
