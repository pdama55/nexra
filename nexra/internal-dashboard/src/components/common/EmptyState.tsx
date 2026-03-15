interface Props {
  icon?: string;
  heading: string;
  message: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, heading, message, action }: Props) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '64px 24px',
      textAlign: 'center',
    }}>
      {icon && (
        <div style={{
          fontSize: '32px',
          marginBottom: '16px',
          opacity: 0.4,
        }}>
          {icon}
        </div>
      )}
      <div style={{
        font: 'var(--text-section-heading)',
        color: 'var(--text-secondary)',
        marginBottom: '8px',
      }}>
        {heading}
      </div>
      <div style={{
        fontSize: '13px',
        color: 'var(--text-tertiary)',
        maxWidth: '400px',
      }}>
        {message}
      </div>
      {action && (
        <button
          className="btn btn-secondary"
          style={{ marginTop: '16px' }}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
