# Post-Release Verification Runbook

Use this immediately after merging PR #1 and triggering `release-smoke`.

## Preconditions

1. `release-smoke` workflow completed successfully on `main`.
2. Deployment URL is known and reachable.
3. At least one valid org API key and agent id are available for smoke calls.

## API Health Checks

1. Verify service health:
   - `GET /health`
   - Expect `200` and healthy dependency status.
2. Verify authenticated critical endpoints:
   - `GET /v1/analytics/usage`
   - `GET /v1/delegations`
   - `GET /v1/policies`
   - `GET /v1/spend/summary`
   - `GET /v1/audit/log`
   - Expect `200` and JSON envelope shape `{ "data": ..., "meta": ... }`.

## Dashboard Route Smoke

1. Load each sidebar route once (no placeholders, no hard failures):
   - Overview
   - Delegations list/detail
   - Policies list/detail
   - Spend/Budget
   - Audit log
   - Agent registry/detail/trust
2. Validate empty/error states render cleanly where data is absent.

## Core Delegation Flow Checks

1. Execute one allowed delegation and confirm:
   - terminal status is `completed`
   - budget reservation/settlement updated
   - audit trail contains correlation id.
2. Execute one blocked or paused path and confirm:
   - expected policy decision fields are present
   - audit trail includes terminal outcome.

## Release Candidate Gate

Tag an RC only when all items above pass and `CONVERGENCE_CHECKLIST.md` has no open required items.
