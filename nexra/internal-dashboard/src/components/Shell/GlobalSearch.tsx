import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { apiGet } from '../../api/client';
import type { Agent, Delegation, Policy } from '../../types';

interface SearchResult {
  id: string;
  label: string;
  subtitle: string;
  path: string;
}

export function GlobalSearch() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === 'Escape') {
        setOpen(false);
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const shouldSearch = open && query.trim().length >= 1;

  const agentsQuery = useQuery<Agent[]>({
    queryKey: ['global-search', 'agents'],
    queryFn: () => apiGet<{ agents: Agent[] }>('/agents/registry', { limit: 100 }).then((r) => r.agents),
    enabled: shouldSearch,
    staleTime: 60_000,
  });

  const policiesQuery = useQuery<Policy[]>({
    queryKey: ['global-search', 'policies'],
    queryFn: () => apiGet<{ policies: Policy[] }>('/policies').then((r) => r.policies),
    enabled: shouldSearch,
    staleTime: 60_000,
  });

  const delegationsQuery = useQuery<Delegation[]>({
    queryKey: ['global-search', 'delegations'],
    queryFn: () => apiGet<{ items: Delegation[] }>('/delegations', { limit: 100 }).then((r) => r.items),
    enabled: shouldSearch,
    staleTime: 60_000,
  });

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [] as SearchResult[];

    const agentResults: SearchResult[] = (agentsQuery.data ?? [])
      .filter((agent) =>
        agent.agent_id.toLowerCase().includes(needle)
        || agent.name.toLowerCase().includes(needle)
        || agent.team.toLowerCase().includes(needle),
      )
      .slice(0, 8)
      .map((agent) => ({
        id: `agent-${agent.agent_id}`,
        label: agent.name,
        subtitle: `Agent · ${agent.agent_id} · Team ${agent.team}`,
        path: `/agents/${agent.agent_id}`,
      }));

    const policyResults: SearchResult[] = (policiesQuery.data ?? [])
      .filter((policy) =>
        policy.name.toLowerCase().includes(needle)
        || (policy.description ?? '').toLowerCase().includes(needle),
      )
      .slice(0, 6)
      .map((policy) => ({
        id: `policy-${policy.id}`,
        label: policy.name,
        subtitle: `Policy · priority ${policy.priority} · v${policy.version}`,
        path: `/policies/${policy.id}`,
      }));

    const delegationResults: SearchResult[] = (delegationsQuery.data ?? [])
      .filter((delegation) =>
        delegation.id.toLowerCase().includes(needle)
        || delegation.caller_agent_id.toLowerCase().includes(needle)
        || delegation.callee_agent_id.toLowerCase().includes(needle)
        || (delegation.workflow ?? '').toLowerCase().includes(needle),
      )
      .slice(0, 8)
      .map((delegation) => ({
        id: `delegation-${delegation.id}`,
        label: delegation.id.slice(0, 12),
        subtitle: `Delegation · ${delegation.caller_agent_id} -> ${delegation.callee_agent_id} · ${delegation.workflow ?? 'unclassified'}`,
        path: `/delegations/${delegation.id}`,
      }));

    return [...agentResults, ...policyResults, ...delegationResults].slice(0, 16);
  }, [query, agentsQuery.data, policiesQuery.data, delegationsQuery.data]);

  function openResult(path: string) {
    setOpen(false);
    setQuery('');
    navigate(path);
  }

  return (
    <>
      <button className="btn btn-secondary" onClick={() => setOpen(true)}>
        Search
      </button>
      {open && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(6, 6, 6, 0.65)',
            zIndex: 2000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            paddingTop: '15vh',
          }}
          onClick={() => setOpen(false)}
        >
          <div
            className="card"
            style={{ width: 'min(680px, 92vw)', maxHeight: '70vh', overflow: 'auto', padding: '12px' }}
            onClick={(event) => event.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search agents, delegations, policies"
              style={{ width: '100%', marginBottom: '12px' }}
            />
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '8px' }}>
              Keyboard: Cmd/Ctrl + K
            </div>
            {results.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', padding: '8px 0' }}>
                {query ? 'No matching results.' : 'Start typing to search.'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {results.map((result) => (
                  <button
                    key={result.id}
                    className="btn btn-secondary"
                    style={{ textAlign: 'left', justifyContent: 'flex-start', flexDirection: 'column', alignItems: 'flex-start' }}
                    onClick={() => openResult(result.path)}
                  >
                    <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{result.label}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{result.subtitle}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
