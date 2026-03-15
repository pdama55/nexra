"""CrewAI adapter for Nexra SDK.

Provides tool classes compatible with CrewAI's BaseTool interface.
"""
from typing import Any


class NexraTool:
    """CrewAI-compatible tool for delegating tasks via Nexra.

    Usage:
        from nexra_sdk.adapters.crewai import NexraTool
        tool = NexraTool(client=nexra_client)
    """

    name: str = "nexra_delegate"
    description: str = "Delegate a task to an AI agent via Nexra governance layer"

    def __init__(self, client: Any) -> None:
        self.client = client

    async def _arun(
        self,
        agent_id: str,
        task: dict,
        budget_cap: float = 1.0,
        context_scope: list[str] | None = None,
    ) -> dict:
        result = await self.client.delegate(
            agent_id=agent_id,
            task=task,
            context_scope=context_scope,
            budget_cap=budget_cap,
        )
        return {
            "delegation_id": result.delegation_id,
            "status": result.status,
            "result": result.result,
        }


class NexraDiscoverTool:
    """CrewAI-compatible tool for discovering agents via Nexra."""

    name: str = "nexra_discover"
    description: str = "Discover AI agent capabilities via Nexra semantic search"

    def __init__(self, client: Any) -> None:
        self.client = client

    async def _arun(self, query: str, limit: int = 5) -> list[dict]:
        matches = await self.client.discover(query=query, limit=limit)
        return [
            {
                "agent_id": m.agent_id,
                "name": m.name,
                "match_score": m.match_score,
                "trust_score": m.trust_score,
            }
            for m in matches
        ]
