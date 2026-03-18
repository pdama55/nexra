#!/usr/bin/env python3
"""Validate PRD 90s policy flip (ALLOW -> BLOCK) and persist proof artifact."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


@dataclass
class OrgContext:
    api_key: str
    owner_email: str
    caller_agent_id: str
    callee_agent_id: str


def _load_org_context(profile_path: Path) -> OrgContext:
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    buyer = ((payload.get("orgs") or {}).get("buyer") or {})

    api_key = str(buyer.get("api_key") or "").strip()
    owner_email = str(buyer.get("owner_email") or "admin@nexra.local").strip()
    agents = [str(a).strip() for a in list(buyer.get("agents") or []) if str(a).strip()]

    if not api_key:
        raise ValueError("org profile missing buyer api_key")
    if not agents:
        raise ValueError("org profile missing buyer agents")

    if len(agents) >= 3:
        caller_agent_id = agents[1]
        callee_agent_id = agents[2]
    elif len(agents) == 2:
        caller_agent_id = agents[1]
        callee_agent_id = agents[0]
    else:
        caller_agent_id = agents[0]
        callee_agent_id = agents[0]
    return OrgContext(
        api_key=api_key,
        owner_email=owner_email,
        caller_agent_id=caller_agent_id,
        callee_agent_id=callee_agent_id,
    )


def _headers(ctx: OrgContext, *, include_user_email: bool = False, include_agent_id: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {ctx.api_key}",
        "Content-Type": "application/json",
    }
    if include_user_email:
        headers["X-User-Email"] = ctx.owner_email
    if include_agent_id:
        headers["X-Agent-ID"] = ctx.caller_agent_id
    return headers


def _decode_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001
        return None, resp.text[:400]

    envelope = payload if isinstance(payload, dict) else {}
    error = envelope.get("error")
    if not isinstance(error, dict):
        detail = envelope.get("detail")
        if isinstance(detail, dict):
            nested = detail.get("error")
            if isinstance(nested, dict):
                error = nested
    if not isinstance(error, dict):
        return None, resp.text[:400]
    code = error.get("code")
    msg = error.get("message")
    return (str(code) if code is not None else None, str(msg) if msg is not None else None)


def _create_allow_policy(client: httpx.Client, ctx: OrgContext, run_id: int) -> tuple[str, int]:
    resp = client.post(
        "/v1/policies",
        headers=_headers(ctx, include_user_email=True),
        json={
            "name": f"vc-prd-policy-flip-{run_id}",
            "description": "PRD acceptance check: ALLOW -> BLOCK flip",
            "priority": 1,
            "allow": {},
            "conditions": [],
            "on_violation": "block_and_alert",
        },
    )
    if resp.status_code != 200:
        code, msg = _decode_error(resp)
        raise RuntimeError(f"create policy failed: {resp.status_code} {code or ''} {msg or resp.text[:250]}")

    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("create policy response missing data")

    policy_id = str(data.get("id") or "").strip()
    version = int(data.get("version") or 0)
    if not policy_id:
        raise RuntimeError("create policy response missing policy id")
    return policy_id, version


def _delegate(client: httpx.Client, ctx: OrgContext, *, run_id: int, stage: str) -> tuple[int, dict[str, Any] | None, str | None, str | None]:
    resp = client.post(
        "/v1/delegate",
        headers=_headers(ctx, include_agent_id=True),
        json={
            "callee_agent_id": ctx.callee_agent_id,
            "task": {
                "input": {
                    "query": f"prd-policy-flip-{stage}-{run_id}",
                }
            },
            "context_scope": ["deal_metadata"],
            "budget_cap_usd": 1.0,
            "timeout_ms": 4000,
            "callback_url": "https://example.com/vc/policy-flip-callback",
        },
    )

    body: dict[str, Any] | None = None
    try:
        parsed = resp.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:  # noqa: BLE001
        body = None

    if resp.is_success:
        return resp.status_code, body, None, None

    error_code, error_message = _decode_error(resp)
    return resp.status_code, body, error_code, error_message


def _update_policy_to_block(client: httpx.Client, ctx: OrgContext, policy_id: str) -> int:
    resp = client.put(
        f"/v1/policies/{policy_id}",
        headers=_headers(ctx, include_user_email=True),
        json={
            "conditions": [
                {
                    "field": "callee_agent_id",
                    "operator": "==",
                    "value": "__non_matching_target_for_flip_check__",
                }
            ],
            "on_violation": "block_and_alert",
        },
    )
    if resp.status_code != 200:
        code, msg = _decode_error(resp)
        raise RuntimeError(f"update policy failed: {resp.status_code} {code or ''} {msg or resp.text[:250]}")

    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("update policy response missing data")
    return int(data.get("version") or 0)


def _disable_policy(client: httpx.Client, ctx: OrgContext, policy_id: str) -> None:
    try:
        client.delete(
            f"/v1/policies/{policy_id}",
            headers=_headers(ctx, include_user_email=True),
        )
    except Exception:  # noqa: BLE001
        return


def _write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PRD 90s ALLOW -> BLOCK policy flip")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--org-profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    run_started = time.perf_counter()
    generated_at = datetime.now(UTC).isoformat()

    artifact: dict[str, Any] = {
        "generated_at": generated_at,
        "base_url": args.base_url,
        "passed": False,
    }

    policy_id: str | None = None

    try:
        ctx = _load_org_context(args.org_profile)
        artifact["caller_agent_id"] = ctx.caller_agent_id
        artifact["callee_agent_id"] = ctx.callee_agent_id

        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=25.0) as client:
            run_id = int(time.time())
            policy_id, allow_policy_version = _create_allow_policy(client, ctx, run_id)
            artifact["policy_id"] = policy_id
            artifact["allow_policy_version"] = allow_policy_version

            allow_status, allow_body, allow_error_code, allow_error_message = _delegate(
                client, ctx, run_id=run_id, stage="allow"
            )
            allow_policy_decision = None
            if isinstance(allow_body, dict):
                allow_policy_decision = (((allow_body.get("data") or {}).get("policy_result") or {}).get("decision"))

            artifact["allow_status_code"] = allow_status
            artifact["allow_policy_decision"] = allow_policy_decision
            artifact["allow_error_code"] = allow_error_code
            artifact["allow_error_message"] = allow_error_message

            flip_started = time.perf_counter()
            block_policy_version = _update_policy_to_block(client, ctx, policy_id)
            artifact["block_policy_version"] = block_policy_version

            block_status, _block_body, block_error_code, block_error_message = _delegate(
                client, ctx, run_id=run_id, stage="block"
            )
            artifact["block_status_code"] = block_status
            artifact["block_error_code"] = block_error_code
            artifact["block_error_message"] = block_error_message
            artifact["flip_duration_seconds"] = round(time.perf_counter() - flip_started, 4)

            allow_phase_ok = allow_status in {200, 202} and allow_policy_decision == "allow"
            block_phase_ok = block_status == 403 and block_error_code == "POLICY_BLOCKED"
            artifact["passed"] = bool(allow_phase_ok and block_phase_ok)

            if not artifact["passed"]:
                reasons: list[str] = []
                if not allow_phase_ok:
                    reasons.append(
                        f"allow phase unexpected: status={allow_status}, decision={allow_policy_decision}, error={allow_error_code}"
                    )
                if not block_phase_ok:
                    reasons.append(
                        f"block phase unexpected: status={block_status}, error_code={block_error_code}"
                    )
                artifact["failure_reasons"] = reasons

            _disable_policy(client, ctx, policy_id)

    except Exception as exc:  # noqa: BLE001
        artifact["passed"] = False
        artifact["exception"] = str(exc)

    artifact["total_duration_seconds"] = round(time.perf_counter() - run_started, 4)
    _write_artifact(args.out, artifact)

    print(json.dumps({
        "out": str(args.out),
        "passed": bool(artifact.get("passed")),
        "allow_status_code": artifact.get("allow_status_code"),
        "block_status_code": artifact.get("block_status_code"),
        "block_error_code": artifact.get("block_error_code"),
    }, indent=2, sort_keys=True))

    return 0 if artifact.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
