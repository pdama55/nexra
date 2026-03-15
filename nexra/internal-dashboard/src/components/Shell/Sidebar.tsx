import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import './Sidebar.css';

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const NAV_SECTIONS: { items: NavItem[] }[] = [
  {
    items: [
      { path: '/', label: 'Overview', icon: '◈' },
    ],
  },
  {
    items: [
      { path: '/agents', label: 'Agents', icon: '⬡' },
      { path: '/delegations', label: 'Delegations', icon: '⇄' },
      { path: '/policies', label: 'Policies', icon: '⛊' },
    ],
  },
  {
    items: [
      { path: '/spend', label: 'Spend', icon: '$' },
      { path: '/audit', label: 'Audit Log', icon: '⊞' },
      { path: '/hitl', label: 'HiTL Queue', icon: '⏸' },
    ],
  },
  {
    items: [
      { path: '/trust', label: 'Trust Scores', icon: '★' },
      { path: '/anomalies', label: 'Anomalies', icon: '⚡' },
    ],
  },
  {
    items: [
      { path: '/compliance', label: 'Compliance', icon: '⬇' },
      { path: '/settings', label: 'Settings', icon: '⚙' },
    ],
  },
];

type HealthState = 'healthy' | 'degraded' | 'unhealthy';

export function Sidebar() {
  const [healthState, setHealthState] = useState<HealthState>('healthy');
  const [hitlCount, setHitlCount] = useState(0);

  // Health check polling — every 60s per specs §4
  useEffect(() => {
    let mounted = true;

    async function checkHealth() {
      try {
        const start = Date.now();
        const res = await fetch('/health');
        const elapsed = Date.now() - start;

        if (!mounted) return;

        if (res.ok) {
          setHealthState(elapsed > 500 ? 'degraded' : 'healthy');
        } else {
          setHealthState('unhealthy');
        }
      } catch {
        if (mounted) setHealthState('unhealthy');
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 60_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // HiTL count polling — every 30s per specs §11
  useEffect(() => {
    let mounted = true;

    async function fetchHitlCount() {
      try {
        const res = await fetch('/v1/delegations?status=pending_approval&limit=0');
        if (!res.ok || !mounted) return;
        const data = await res.json();
        if (mounted) setHitlCount(data.total_count ?? data.items?.length ?? 0);
      } catch {
        // Silently fail — badge just won't update
      }
    }

    fetchHitlCount();
    const interval = setInterval(fetchHitlCount, 30_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const healthLabel = healthState === 'healthy' ? 'API healthy' :
    healthState === 'degraded' ? 'API degraded' : 'API unreachable';

  return (
    <aside className="sidebar">
      <div className="sidebar-wordmark">
        <div className="sidebar-wordmark-icon"><span>N</span></div>
        <span className="sidebar-wordmark-text">NEXRA</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_SECTIONS.map((section, sIdx) => (
          <div key={sIdx}>
            {sIdx > 0 && <div className="sidebar-divider" />}
            {section.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `nav-item${isActive ? ' active' : ''}`
                }
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
                {item.path === '/hitl' && hitlCount > 0 && (
                  <span className="nav-badge">{hitlCount}</span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-text">
          <div className="sidebar-footer-org">Nexra Org</div>
          <div className="sidebar-footer-plan">Growth</div>
        </div>
        <div className="sidebar-footer-health">
          <span className={`health-dot ${healthState}`} />
          <span>{healthLabel}</span>
        </div>
      </div>
    </aside>
  );
}
