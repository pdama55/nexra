import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { StatusPill } from '../components/common/StatusPill';
import { EmptyState } from '../components/common/EmptyState';
import { formatRelativeTime } from '../utils/formatters';
import type { TimeRange, Agent } from '../types';
import { useState } from 'react';

interface Props {
  timeRange: TimeRange;
}

export function AgentRegistry({ timeRange: _timeRange }: Props) {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [capFilter, setCapFilter] = useState<string>('all');
  const [search, setSearch] = useState('');

  const { data: agents, isLoading } = useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry').then(r => r.agents),
    refetchInterval: 300_000,
  });

  const filtered = (agents ?? []).filter(a => {
    if (statusFilter !== 'all' && a.status !== statusFilter) return false;
    if (capFilter !== 'all' && a.capability_type !== capFilter) return false;
    if (search && !a.agent_id.includes(search) && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Agent Registry</h1>
      </div>

      <div className="filters-bar">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="probationary">Probationary</option>
          <option value="quarantined">Quarantined</option>
        </select>
        <select value={capFilter} onChange={e => setCapFilter(e.target.value)}>
          <option value="all">All Capabilities</option>
          {['research','analysis','generation','enrichment','validation','execution','other'].map(c =>
            <option key={c} value={c}>{c}</option>
          )}
        </select>
        <input
          placeholder="Search agent ID or name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ flex: 1, minWidth: '200px' }}
        />
      </div>

      {isLoading ? (
        <div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading agents…</div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="⬡"
          heading="No agents registered"
          message="Use the SDK to register your first agent."
        />
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '900px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Agent ID', 'Name', 'Capability', 'Status', 'Trust Score', 'Delegations', 'Last Active', 'Actions'].map(h => (
                  <th key={h} className="label" style={{ padding: '10px 12px', textAlign: 'left', position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(agent => (
                <tr key={agent.agent_id} style={{ borderBottom: '1px solid var(--border)', height: '40px' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${agent.agent_id}`} className="mono" style={{ fontSize: '13px' }}>
                      {agent.agent_id}
                    </Link>
                  </td>
                  <td style={{ padding: '8px 12px', fontSize: '13px', color: 'var(--text-secondary)' }}>{agent.name}</td>
                  <td style={{ padding: '8px 12px' }}><StatusPill status={agent.capability_type} /></td>
                  <td style={{ padding: '8px 12px' }}><StatusPill status={agent.status} /></td>
                  <td style={{ padding: '8px 12px' }}>
                    <span className="mono" style={{
                      fontSize: '13px',
                      color: agent.trust_score >= 0.7 ? 'var(--text-primary)' :
                        agent.trust_score >= 0.4 ? 'var(--status-probationary)' : '#9A4A4A',
                    }}>
                      {agent.trust_score.toFixed(3)}
                    </span>
                  </td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: '13px' }}>{agent.delegation_count}</td>
                  <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {formatRelativeTime(agent.updated_at)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <Link to={`/agents/${agent.agent_id}`} className="btn btn-sm btn-secondary">View</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
