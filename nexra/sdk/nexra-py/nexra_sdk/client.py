from typing import Any

import httpx

from nexra_sdk.types import AgentMatch, DelegationResult, PolicyResult, RegisterResult, Usage


class NexraClient:
    """Nexra Python SDK client.

    Usage:
        async with NexraClient(api_key='nx_live_...', agent_id='my-agent') as client:
            result = await client.hire(capability='research', task={'company_name': 'Acme'})
    """

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://api.usenexra.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Agent-ID": agent_id,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(headers=self._headers, timeout=timeout)

    async def register(self, **kwargs: Any) -> RegisterResult:
        resp = await self._client.post(f"{self.base_url}/agents/register", json=kwargs)
        self._check_response(resp)
        data = resp.json()["data"]
        return RegisterResult(**data)

    async def discover(
        self,
        query: str,
        capability_type: str | None = None,
        budget_cap: float | None = None,
        max_latency_ms: int | None = None,
        limit: int = 5,
    ) -> list[AgentMatch]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if capability_type:
            payload["capability_type"] = capability_type
        if budget_cap:
            payload["budget_cap_usd"] = budget_cap
        if max_latency_ms:
            payload["max_latency_ms"] = max_latency_ms

        resp = await self._client.post(
            f"{self.base_url}/capabilities/discover", json=payload
        )
        self._check_response(resp)
        return [AgentMatch(**m) for m in resp.json()["data"]["matches"]]

    async def delegate(
        self,
        agent_id: str,
        task: dict,
        context_scope: list[str] | None = None,
        budget_cap: float = 1.0,
        timeout_ms: int = 30000,
        callback_url: str | None = None,
    ) -> DelegationResult:
        resp = await self._client.post(
            f"{self.base_url}/delegate",
            json={
                "callee_agent_id": agent_id,
                "task": task,
                "context_scope": context_scope or [],
                "budget_cap_usd": budget_cap,
                "timeout_ms": timeout_ms,
                "callback_url": callback_url,
            },
        )
        self._check_response(resp)
        return self._parse_delegation_result(resp.json()["data"])

    async def hire(
        self,
        capability: str,
        task: dict,
        context_scope: list[str] | None = None,
        budget_cap: float = 1.0,
    ) -> DelegationResult:
        """Convenience: discover + delegate in one call."""
        matches = await self.discover(capability, budget_cap=budget_cap, limit=1)
        if not matches:
            raise ValueError(f"No agents found for capability: {capability}")
        return await self.delegate(
            agent_id=matches[0].agent_id,
            task=task,
            context_scope=context_scope,
            budget_cap=budget_cap,
        )

    async def get_delegation(self, delegation_id: str) -> DelegationResult:
        resp = await self._client.get(
            f"{self.base_url}/delegations/{delegation_id}"
        )
        self._check_response(resp)
        return self._parse_delegation_result(resp.json()["data"])

    def _parse_delegation_result(self, data: dict) -> DelegationResult:
        policy = None
        if data.get("policy_result"):
            policy = PolicyResult(**data["policy_result"])
        usage = None
        if data.get("usage"):
            usage = Usage(**data["usage"])
        return DelegationResult(
            delegation_id=data["delegation_id"],
            status=data["status"],
            policy_result=policy,
            result=data.get("result"),
            usage=usage,
            poll_url=data.get("poll_url"),
        )

    def _check_response(self, resp: httpx.Response) -> None:
        if resp.is_success:
            return
        try:
            body = resp.json()
            error = body.get("error", {})
            raise NexraAPIError(
                status_code=resp.status_code,
                code=error.get("code", "UNKNOWN"),
                message=error.get("message", resp.text[:200]),
                details=error.get("details", {}),
            )
        except (ValueError, KeyError):
            resp.raise_for_status()

    async def __aenter__(self) -> "NexraClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()


class NexraAPIError(Exception):
    """Raised when the Nexra API returns an error response."""

    def __init__(
        self, status_code: int, code: str, message: str, details: dict | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status_code}] {code}: {message}")
