import type { DelegationStatus, AgentStatus } from '../../types';

type StatusValue = DelegationStatus | AgentStatus | string;

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  active:            { bg: 'var(--status-active-bg)',        color: 'var(--status-active)' },
  probationary:      { bg: 'var(--status-probationary-bg)',  color: 'var(--status-probationary)' },
  quarantined:       { bg: 'var(--status-quarantined-bg)',   color: '#9A4A4A' },
  completed:         { bg: 'var(--status-completed-bg)',     color: 'var(--status-completed)' },
  in_flight:         { bg: 'var(--status-in-flight-bg)',     color: '#3A6A9A' },
  blocked:           { bg: 'var(--status-blocked-bg)',       color: '#9A4A4A' },
  failed:            { bg: 'var(--status-failed-bg)',        color: 'var(--status-failed)' },
  timeout:           { bg: 'var(--status-failed-bg)',        color: 'var(--status-failed)' },
  pending:           { bg: 'var(--status-pending-bg)',       color: 'var(--status-pending)' },
  pending_approval:  { bg: 'var(--status-pending-bg)',       color: 'var(--status-pending)' },
  allow:             { bg: 'var(--status-completed-bg)',     color: 'var(--status-completed)' },
  block:             { bg: 'var(--status-blocked-bg)',       color: '#9A4A4A' },
  pause:             { bg: 'var(--status-pending-bg)',       color: 'var(--status-pending)' },
};

interface Props {
  status: StatusValue;
}

export function StatusPill({ status }: Props) {
  const style = STATUS_STYLES[status] ?? {
    bg: 'var(--bg-tertiary)',
    color: 'var(--text-secondary)',
  };

  return (
    <span
      className="badge"
      style={{
        background: style.bg,
        color: style.color,
      }}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}
