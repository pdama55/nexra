import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class RouteErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Keep logging local; avoid breaking render path.
    console.error('Route render error', error, errorInfo.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="card">
          <div className="section-heading">View Error</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
            This view failed to render. Refresh the page or try a different route.
          </div>
          <pre style={{ marginTop: '12px', color: 'var(--text-tertiary)', fontSize: '12px' }}>
            {this.state.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
