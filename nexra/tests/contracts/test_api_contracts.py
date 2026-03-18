"""Contract tests for dashboard-consumed API surface."""

import json
import os
from pathlib import Path
from typing import Any


def _required_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/nexra",
        "REDIS_URL": "redis://localhost:6379/0",
        "OPENAI_API_KEY": "test-openai-key",
        "STRIPE_SECRET_KEY": "test-stripe-key",
        "STRIPE_WEBHOOK_SECRET": "test-stripe-whsec",
        "STRIPE_DELEGATION_METER_ID": "meter_test",
        "SECRET_KEY_ENCRYPTION_KEY": "a" * 64,
    }


def _openapi() -> dict[str, Any]:
    env = _required_env()
    for key, value in env.items():
        os.environ.setdefault(key, value)

    from api.main import app

    return app.openapi()


def _resolve_schema(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in schema:
        return schema
    ref = schema["$ref"]
    assert ref.startswith("#/components/schemas/")
    name = ref.replace("#/components/schemas/", "")
    return spec["components"]["schemas"][name]


def _json_response_schema(spec: dict[str, Any], path: str, method: str = "get") -> dict[str, Any]:
    method_obj = spec["paths"][path][method]
    response = method_obj["responses"]["200"]
    content = response["content"]["application/json"]
    return _resolve_schema(content["schema"], spec)


def _parameter_names(spec: dict[str, Any], path: str, method: str = "get") -> set[str]:
    method_obj = spec["paths"][path][method]
    return {p["name"] for p in method_obj.get("parameters", [])}


def test_required_dashboard_paths_and_methods_present() -> None:
    spec = _openapi()
    paths = spec.get("paths", {})
    required = {
        "/v1/analytics/usage": "get",
        "/v1/delegations": "get",
        "/v1/delegations/{delegation_id}": "get",
        "/v1/agents/registry": "get",
        "/v1/audit/log": "get",
        "/v1/policies": "get",
        "/v1/policies/{policy_id}": "get",
        "/v1/policies/{policy_id}/versions": "get",
        "/v1/spend/summary": "get",
        "/v1/spend/summary/export": "get",
        "/v1/agents/{agent_ref}/trust": "get",
        "/v1/orgs/session": "get",
        "/v1/orgs/api-keys": "get",
        "/v1/orgs/members": "get",
        "/v1/compliance/export/package": "get",
        "/v1/mcp/tools": "get",
        "/v1/mcp/tools/discover": "post",
        "/v1/mcp/tools/delegate": "post",
        "/v1/mcp/tools/governance/read": "get",
    }
    for path, method in required.items():
        assert path in paths, f"Missing required API path in OpenAPI: {path}"
        assert method in paths[path], f"Missing required method {method} for path: {path}"


def test_org_admin_path_method_matrix_present() -> None:
    spec = _openapi()
    paths = spec.get("paths", {})
    required_methods = {
        "/v1/orgs/api-keys": {"get", "post"},
        "/v1/orgs/api-keys/{key_id}": {"delete"},
        "/v1/orgs/members": {"get", "post"},
        "/v1/orgs/members/{member_id}": {"patch", "delete"},
    }
    for path, methods in required_methods.items():
        assert path in paths, f"Missing required org-admin path: {path}"
        present = set(paths[path].keys())
        missing = methods - present
        assert not missing, f"{path} missing required methods: {sorted(missing)}"


def test_required_json_endpoints_use_data_meta_envelope() -> None:
    spec = _openapi()
    envelope_paths = [
        "/v1/analytics/usage",
        "/v1/delegations",
        "/v1/delegations/{delegation_id}",
        "/v1/agents/registry",
        "/v1/audit/log",
        "/v1/policies",
        "/v1/policies/{policy_id}",
        "/v1/policies/{policy_id}/versions",
        "/v1/spend/summary",
        "/v1/agents/{agent_ref}/trust",
    ]
    for path in envelope_paths:
        schema = _json_response_schema(spec, path)
        properties = schema.get("properties", {})
        assert "data" in properties, f"{path} must expose envelope.data"
        assert "meta" in properties, f"{path} must expose envelope.meta"
        required = schema.get("required", [])
        assert "data" in required, f"{path} must require data"


def test_enums_and_required_fields_for_dashboard_contracts() -> None:
    spec = _openapi()
    components = spec.get("components", {}).get("schemas", {})

    delegations_schema = _json_response_schema(spec, "/v1/delegations/{delegation_id}")
    assert "data" in delegations_schema.get("properties", {})
    assert "meta" in delegations_schema.get("properties", {})

    policy_result = components.get("PolicyResultResponse")
    if policy_result is not None:
        assert "decision" in policy_result.get("properties", {})

    delegate_request = components.get("DelegateRequest")
    assert delegate_request is not None
    request_required = set(delegate_request.get("required", []))
    assert {"callee_agent_id", "task", "budget_cap_usd"}.issubset(request_required)


def test_openapi_snapshot_contains_required_paths() -> None:
    snapshot_path = Path(__file__).resolve().parents[3] / "docs" / "baseline" / "openapi.snapshot.json"
    assert snapshot_path.exists(), f"Missing OpenAPI snapshot: {snapshot_path}"
    snapshot = json.loads(snapshot_path.read_text())
    paths = snapshot.get("paths", {})
    assert "/v1/analytics/usage" in paths
    assert "/v1/delegations" in paths
    assert "/v1/delegations/{delegation_id}" in paths
    assert "/v1/mcp/tools" in paths
    assert "/v1/mcp/tools/discover" in paths
    assert "/v1/mcp/tools/delegate" in paths
    assert "/v1/mcp/tools/governance/read" in paths


def test_delegations_list_query_contract_includes_dashboard_filters() -> None:
    spec = _openapi()
    names = _parameter_names(spec, "/v1/delegations", "get")
    required = {
        "status",
        "caller_agent_id",
        "callee_agent_id",
        "policy_decision",
        "workflow",
        "date_from",
        "date_to",
        "cost_min",
        "cost_max",
        "cursor",
        "limit",
        "sort",
    }
    missing = required - names
    assert not missing, f"/v1/delegations missing query params: {sorted(missing)}"


def test_audit_log_query_contract_includes_dashboard_filters() -> None:
    spec = _openapi()
    names = _parameter_names(spec, "/v1/audit/log", "get")
    required = {
        "agent_id",
        "actor_agent_id",
        "target_agent_id",
        "policy_id",
        "policy_decision",
        "event_type",
        "date_from",
        "date_to",
        "cost_min",
        "cost_max",
        "delegation_id",
        "cursor",
        "limit",
        "format",
    }
    missing = required - names
    assert not missing, f"/v1/audit/log missing query params: {sorted(missing)}"


def test_spend_summary_query_contract_includes_window_and_breakdown() -> None:
    spec = _openapi()
    names = _parameter_names(spec, "/v1/spend/summary", "get")
    required = {"agent_id", "window", "breakdown"}
    missing = required - names
    assert not missing, f"/v1/spend/summary missing query params: {sorted(missing)}"


def test_spend_summary_export_query_contract_includes_window_and_breakdown() -> None:
    spec = _openapi()
    names = _parameter_names(spec, "/v1/spend/summary/export", "get")
    required = {"agent_id", "window", "breakdown"}
    missing = required - names
    assert not missing, f"/v1/spend/summary/export missing query params: {sorted(missing)}"


def test_compliance_package_query_contract_present() -> None:
    spec = _openapi()
    names = _parameter_names(spec, "/v1/compliance/export/package", "get")
    required = {"set", "date_from", "date_to"}
    missing = required - names
    assert not missing, f"/v1/compliance/export/package missing query params: {sorted(missing)}"


def test_mcp_path_contracts_present() -> None:
    spec = _openapi()
    paths = spec.get("paths", {})

    required_methods = {
        "/v1/mcp/tools": {"get"},
        "/v1/mcp/tools/discover": {"post"},
        "/v1/mcp/tools/delegate": {"post"},
        "/v1/mcp/tools/governance/read": {"get"},
    }
    for path, methods in required_methods.items():
        assert path in paths, f"Missing required MCP path: {path}"
        present = set(paths[path].keys())
        missing = methods - present
        assert not missing, f"{path} missing required methods: {sorted(missing)}"

    discover_params = _parameter_names(spec, "/v1/mcp/tools/discover", "post")
    delegate_params = _parameter_names(spec, "/v1/mcp/tools/delegate", "post")
    governance_params = _parameter_names(spec, "/v1/mcp/tools/governance/read", "get")

    assert {"authorization", "X-Agent-ID"}.issubset(discover_params)
    assert {"authorization", "X-Agent-ID"}.issubset(delegate_params)
    assert {"authorization"}.issubset(governance_params)

    discover_body_ref = spec["paths"]["/v1/mcp/tools/discover"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ].get("$ref")
    delegate_body_ref = spec["paths"]["/v1/mcp/tools/delegate"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ].get("$ref")
    assert discover_body_ref == "#/components/schemas/DiscoverRequest"
    assert delegate_body_ref == "#/components/schemas/DelegateRequest"
