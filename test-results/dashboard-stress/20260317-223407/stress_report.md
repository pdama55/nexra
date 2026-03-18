# Dashboard Stress Validation Report
- Generated: 2026-03-18T05:38:02.693503+00:00
- Status: **FAILED**
- Results Directory: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407`

## Critical Failures
- dashboard_parity_sweep exit=1
- ui required mismatches=7
- route render failures=14

## Warnings
- endpoint_metrics.json missing (api load terminated after parity fail-fast)
- dashboard_api_load exit=143 (terminated after parity fail-fast)
- route latency breaches=1 (threshold_ms=15000)

## Key Artifacts
- stress_summary: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/stress_summary.json`
- endpoint_metrics: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/endpoint_metrics.json`
- ui_parity_results: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/ui_parity_results.json`
- frontend_errors: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/frontend_errors.jsonl`
- api_failures: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/api_failures.jsonl`
- vc_capability_matrix: `/Users/parthdama/Documents/Nexra/test-results/dashboard-stress/20260317-223407/vc_suite/capability_matrix_result.json`
