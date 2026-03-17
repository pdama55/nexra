import { useState } from 'react';

import { NexraApiError, apiGet, getApiUrl } from '../api/client';
import { EmptyState } from '../components/common/EmptyState';

type ReportType = 'soc2' | 'gdpr' | 'hipaa';

const REPORT_TYPES: Array<{ id: ReportType; name: string; desc: string; icon: string }> = [
  { id: 'soc2', name: 'SOC 2 Type II', desc: 'Access controls, integrity, incident, change management', icon: 'S' },
  { id: 'gdpr', name: 'GDPR / DPA', desc: 'Data processing and access evidence by agent/context scope', icon: 'G' },
  { id: 'hipaa', name: 'HIPAA', desc: 'PHI-related access events and safeguard posture', icon: 'H' },
];

function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ComplianceExport() {
  const [selectedReport, setSelectedReport] = useState<ReportType | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastReport, setLastReport] = useState<Record<string, unknown> | null>(null);

  async function generateJsonReport(): Promise<void> {
    if (!selectedReport || !dateFrom || !dateTo) return;
    setLoading(true);
    setError(null);
    try {
      const report = await apiGet<Record<string, unknown>>(`/compliance/report/${selectedReport}`, {
        date_from: `${dateFrom}T00:00:00Z`,
        date_to: `${dateTo}T23:59:59Z`,
      });
      setLastReport(report);
      downloadBlob(
        `nexra-${selectedReport}-report.json`,
        new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }),
      );
    } catch (err) {
      if (err instanceof NexraApiError) {
        setError(`${err.code} (${err.status})`);
      } else {
        setError('Unexpected compliance export error');
      }
    } finally {
      setLoading(false);
    }
  }

  async function exportAuditCsv(): Promise<void> {
    if (!dateFrom || !dateTo) return;
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        date_from: `${dateFrom}T00:00:00Z`,
        date_to: `${dateTo}T23:59:59Z`,
      });
      const resp = await fetch(`${getApiUrl('/compliance/export/csv')}?${query.toString()}`, {
        headers: {
          'Content-Type': 'text/csv',
          Authorization: `Bearer ${localStorage.getItem('nexra_api_key') ?? ''}`,
        },
      });
      if (!resp.ok) {
        throw new Error(`CSV export failed with ${resp.status}`);
      }
      const csvBlob = await resp.blob();
      downloadBlob('nexra-compliance-audit.csv', csvBlob);
    } catch {
      setError('Audit CSV export failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Compliance Export</h1>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-lg)', marginBottom: 'var(--space-xl)' }}>
        {REPORT_TYPES.map((r) => (
          <button
            key={r.id}
            className="card"
            style={{
              cursor: 'pointer',
              borderColor: selectedReport === r.id ? 'var(--border-strong)' : undefined,
              textAlign: 'left',
            }}
            onClick={() => setSelectedReport(r.id)}
          >
            <div style={{ fontSize: '20px', marginBottom: '8px' }}>{r.icon}</div>
            <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '4px' }}>{r.name}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>{r.desc}</div>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="section-heading">Export Window</div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', marginTop: '12px', flexWrap: 'wrap' }}>
          <div>
            <label className="label" style={{ display: 'block', marginBottom: '4px' }}>From</label>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="label" style={{ display: 'block', marginBottom: '4px' }}>To</label>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <button
            className="btn btn-primary"
            onClick={() => void generateJsonReport()}
            disabled={loading || !selectedReport || !dateFrom || !dateTo}
          >
            {loading ? 'Exporting…' : 'Generate JSON Report'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => void exportAuditCsv()}
            disabled={loading || !dateFrom || !dateTo}
          >
            Export Audit CSV
          </button>
        </div>
        {error && (
          <div style={{ marginTop: '12px', color: 'var(--status-quarantined)', fontSize: '12px' }}>
            {error}
          </div>
        )}
      </div>

      {lastReport ? (
        <div className="card" style={{ marginTop: 'var(--space-xl)' }}>
          <div className="section-heading">Last Generated Report Preview</div>
          <pre style={{
            background: 'var(--code-bg)',
            padding: '12px',
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            overflow: 'auto',
            maxHeight: '320px',
          }}
          >
            {JSON.stringify(lastReport, null, 2)}
          </pre>
        </div>
      ) : (
        <div style={{ marginTop: 'var(--space-xl)' }}>
          <EmptyState icon="R" heading="No report generated yet" message="Select a report type and date range to export." />
        </div>
      )}
    </div>
  );
}
