import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from './components/Shell/Sidebar';
import { TimeRangeSelector } from './components/Shell/TimeRangeSelector';
import { GlobalSearch } from './components/Shell/GlobalSearch';
import { RefreshAge } from './components/Shell/RefreshAge';
import { RouteErrorBoundary } from './components/common/RouteErrorBoundary';
import { useTimeRange } from './hooks/useTimeRange';

const Overview = lazy(() => import('./views/Overview').then((m) => ({ default: m.Overview })));
const AgentRegistry = lazy(() => import('./views/AgentRegistry').then((m) => ({ default: m.AgentRegistry })));
const AgentDetail = lazy(() => import('./views/AgentDetail').then((m) => ({ default: m.AgentDetail })));
const DelegationFeed = lazy(() => import('./views/DelegationFeed').then((m) => ({ default: m.DelegationFeed })));
const DelegationDetail = lazy(() => import('./views/DelegationDetail').then((m) => ({ default: m.DelegationDetail })));
const PolicyEngine = lazy(() => import('./views/PolicyEngine').then((m) => ({ default: m.PolicyEngine })));
const PolicyDetail = lazy(() => import('./views/PolicyDetail').then((m) => ({ default: m.PolicyDetail })));
const SpendBudget = lazy(() => import('./views/SpendBudget').then((m) => ({ default: m.SpendBudget })));
const AuditLog = lazy(() => import('./views/AuditLog').then((m) => ({ default: m.AuditLog })));
const HitlQueue = lazy(() => import('./views/HitlQueue').then((m) => ({ default: m.HitlQueue })));
const TrustScores = lazy(() => import('./views/TrustScores').then((m) => ({ default: m.TrustScores })));
const Anomalies = lazy(() => import('./views/Anomalies').then((m) => ({ default: m.Anomalies })));
const ComplianceExport = lazy(() => import('./views/ComplianceExport').then((m) => ({ default: m.ComplianceExport })));
const Settings = lazy(() => import('./views/Settings').then((m) => ({ default: m.Settings })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10_000),
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
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--space-lg)',
        }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <GlobalSearch />
            <RefreshAge />
          </div>
          <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
        </div>
        <RouteErrorBoundary>
          <Suspense fallback={<div style={{ color: 'var(--text-tertiary)', padding: '24px' }}>Loading view…</div>}>
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
          </Suspense>
        </RouteErrorBoundary>
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
