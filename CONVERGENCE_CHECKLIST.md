# Nexra PRD/TDD Convergence Checklist

This checklist is the release-gate tracker for PRD/TDD convergence.

## Phase 0 — Baseline Lock
- [x] OpenAPI snapshot generated: `docs/baseline/openapi.snapshot.json`
- [x] Dashboard route map generated: `docs/baseline/dashboard_route_map.md`
- [x] Validation snapshot generated: `docs/baseline/validation_snapshot.md`
- [x] Dedicated stabilization branch created: `stabilization/prd-tdd-convergence`

## Phase 1 — Core Delegation Correctness
- [x] Delegation depth derived from parent chain (`parent_delegation_id` + persisted `delegation_depth`)
- [x] Max depth enforcement uses derived depth
- [x] Caller-based budget settlement principal
- [x] Budget exceed path emits audit event
- [x] Policy evaluation audit now always has a delegation correlation id
- [x] Deterministic reserve/release ledger persisted and invariant-checked (`reserved >= settled`)

## Phase 2 — API Contract Stabilization
- [x] `GET /v1/analytics/usage`
- [x] `GET /v1/delegations`
- [x] `GET /v1/delegations/{id}` detail shape includes dashboard fields
- [x] Dashboard API client generic `{data,meta}` unwrap
- [x] All JSON endpoints standardized to explicit response envelope + response models
- [x] Contract tests enforce key payload shape for all dashboard-consumed endpoints

## Phase 3 — Dashboard Functional Completion
- [x] Policy Version History tab populated
- [x] Policy Evaluation History tab populated (audit-based)
- [x] Spend-over-time chart wired to `/analytics/usage` bucket data
- [x] Route-level error boundary added
- [x] Exponential retry delay configured
- [x] Remaining placeholder views removed or fully wired to backend (where required by PRD/TDD)

## Phase 4 — Testing Pyramid Completion
- [x] Unit tests runnable and green
- [x] Integration tests green in DB-enabled environment
- [x] E2E tests green in DB-enabled environment
- [x] Contract tests green locally and gated in CI workflow

## Phase 5 — CI/CD Hardening
- [x] CI workflow added for python + dashboard + sdk checks
- [x] Postgres/Redis services wired for integration/e2e in CI
- [ ] Branch protection configured in repository settings (blocked by GitHub plan limitation: private repo requires Pro/public for protection rules)
- [x] Release workflow with deploy smoke checks

## Phase 6 — P1/P2 Validation
- [x] Marketplace/compliance flows proven by automated tests
- [x] Worker flows proven by automated tests
- [x] Adapter/SDK compatibility proven against current API contract
