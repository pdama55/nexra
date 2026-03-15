import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from './components/Shell/Sidebar';
import { TimeRangeSelector } from './components/Shell/TimeRangeSelector';
import { useTimeRange } from './hooks/useTimeRange';
import { Overview } from './views/Overview';
import { AgentRegistry } from './views/AgentRegistry';
import { AgentDetail } from './views/AgentDetail';
import { DelegationFeed } from './views/DelegationFeed';
import { DelegationDetail } from './views/DelegationDetail';
import { PolicyEngine } from './views/PolicyEngine';
import { PolicyDetail } from './views/PolicyDetail';
import { SpendBudget } from './views/SpendBudget';
import { AuditLog } from './views/AuditLog';
import { HitlQueue } from './views/HitlQueue';
import { TrustScores } from './views/TrustScores';
import { Anomalies } from './views/Anomalies';
import { ComplianceExport } from './views/ComplianceExport';
import { Settings } from './views/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
      refetchOnWindowFocus: true,
    },
  },
});

function AppContent() {
  const { timeRange, setTimeRange } = useTimeRange();

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginBottom: 'var(--space-lg)',
        }}>
          <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
        </div>
        <Routes>
          <Route path="/" element={<Overview timeRange={timeRange} />} />
          <Route path="/agents" element={<AgentRegistry timeRange={timeRange} />} />
          <Route path="/agents/:agentId" element={<AgentDetail timeRange={timeRange} />} />
          <Route path="/delegations" element={<DelegationFeed timeRange={timeRange} />} />
          <Route path="/delegations/:id" element={<DelegationDetail />} />
          <Route path="/policies" element={<PolicyEngine />} />
          <Route path="/policies/:id" element={<PolicyDetail />} />
          <Route path="/spend" element={<SpendBudget timeRange={timeRange} />} />
          <Route path="/audit" element={<AuditLog timeRange={timeRange} />} />
          <Route path="/hitl" element={<HitlQueue />} />
          <Route path="/trust" element={<TrustScores />} />
          <Route path="/anomalies" element={<Anomalies timeRange={timeRange} />} />
          <Route path="/compliance" element={<ComplianceExport />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
