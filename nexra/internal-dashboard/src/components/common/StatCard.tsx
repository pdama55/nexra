interface Props {
  label: string;
  value: string | number;
  delta?: { value: number; label: string } | null;
  alert?: boolean;
}

export function StatCard({ label, value, delta, alert }: Props) {
  const deltaColor = delta && delta.value > 0 ? 'var(--status-active)' :
    delta && delta.value < 0 ? 'var(--status-quarantined)' : 'var(--text-tertiary)';

  const deltaArrow = delta && delta.value > 0 ? '↑' : delta && delta.value < 0 ? '↓' : '';

  return (
    <div className="card" style={{
      borderColor: alert ? 'var(--status-quarantined)' : undefined,
    }}>
      <div className="label">{label}</div>
      <div style={{
        font: 'var(--text-data-lg)',
        color: 'var(--text-primary)',
        marginTop: '8px',
      }} className="mono">
        {value}
      </div>
      {delta && (
        <div style={{
          fontSize: '12px',
          color: deltaColor,
          marginTop: '4px',
        }}>
          {deltaArrow} {Math.abs(delta.value)} {delta.label}
        </div>
      )}
    </div>
  );
}
