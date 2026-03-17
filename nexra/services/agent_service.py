import asyncio
import logging
from datetime import datetime, timezone

import jsonschema
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from core.errors import (
    EMBEDDING_SERVICE_UNAVAILABLE,
    INVALID_SCHEMA,
    INVALID_WEBHOOK_URL,
    NexraError,
)
from models.agent import Agent

logger = logging.getLogger("nexra.services.agent")


class AgentService:
    """Handles agent registration, embedding generation, and listing."""

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    EMBEDDING_MAX_RETRIES = 3

    def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI) -> None:
        self.db = db
        self.openai = openai_client

    @staticmethod
    def _normalize_team(team: str | None) -> str:
        value = (team or "").strip()
        return value if value else "unassigned"

    async def register(self, org_id: str, data: AgentRegisterRequest) -> Agent:
        """Register or re-register an agent capability.

        Idempotent on (org_id, agent_id). Re-registration updates all fields
        except trust_score and delegation_count.
        """
        existing = await self._get_by_agent_id(org_id, data.agent_id)

        if not data.webhook_url.startswith("https://"):
            raise NexraError(400, INVALID_WEBHOOK_URL, "webhook_url must use HTTPS")

        self._validate_json_schema(data.input_schema, "input_schema")
        self._validate_json_schema(data.output_schema, "output_schema")

        embed_text = f"{data.name}. {data.description}"
        embedding = await self._embed(embed_text)

        if existing:
            existing.name = data.name
            existing.description = data.description
            existing.capability_type = data.capability_type
            existing.input_schema = data.input_schema
            existing.output_schema = data.output_schema
            existing.webhook_url = data.webhook_url
            existing.webhook_secret = data.webhook_secret
            existing.team = self._normalize_team(data.team)
            existing.pricing = data.pricing.model_dump()
            existing.sla = data.sla.model_dump()
            existing.embedding = embedding
            existing.is_public = data.is_public
            existing.updated_at = datetime.now(timezone.utc)
            agent = existing
        else:
            agent = Agent(
                org_id=org_id,
                agent_id=data.agent_id,
                name=data.name,
                description=data.description,
                capability_type=data.capability_type,
                input_schema=data.input_schema,
                output_schema=data.output_schema,
                webhook_url=data.webhook_url,
                webhook_secret=data.webhook_secret,
                team=self._normalize_team(data.team),
                pricing=data.pricing.model_dump(),
                sla=data.sla.model_dump(),
                embedding=embedding,
                is_public=data.is_public,
                status="probationary",
            )
            self.db.add(agent)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_by_agent_id(self, org_id: str, agent_id: str) -> Agent | None:
        return await self._get_by_agent_id(org_id, agent_id)

    async def get_by_uuid(self, org_id: str, uuid_str: str) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(Agent.id == uuid_str, Agent.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: str,
        capability_type: str | None = None,
        status: str | None = None,
        is_public: bool | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Agent], str | None, int]:
        """List agents for an org with optional filters and cursor pagination."""
        q = select(Agent).where(Agent.org_id == org_id)

        if capability_type:
            q = q.where(Agent.capability_type == capability_type)
        if status:
            q = q.where(Agent.status == status)
        if is_public is not None:
            q = q.where(Agent.is_public == is_public)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        if cursor:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(Agent.created_at < cursor_dt)

        q = q.order_by(Agent.created_at.desc()).limit(limit + 1)
        result = await self.db.execute(q)
        agents = list(result.scalars().all())

        next_cursor = None
        if len(agents) > limit:
            next_cursor = agents[limit - 1].created_at.isoformat()
            agents = agents[:limit]

        return agents, next_cursor, total

    async def update_status(self, org_id: str, agent_id: str, new_status: str) -> Agent:
        agent = await self._get_by_agent_id(org_id, agent_id)
        if not agent:
            raise NexraError(404, "AGENT_NOT_FOUND", f"Agent '{agent_id}' not found")
        agent.status = new_status
        agent.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def _get_by_agent_id(self, org_id: str, agent_id: str) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    def _validate_json_schema(self, schema: dict, field_name: str) -> None:
        try:
            jsonschema.Draft7Validator.check_schema(schema)
        except jsonschema.SchemaError as e:
            raise NexraError(400, INVALID_SCHEMA, f"{field_name} is not a valid JSON Schema: {e.message}")

    async def _embed(self, text: str) -> list[float]:
        """Generate 1536-dim embedding with retry on transient errors."""
        for attempt in range(self.EMBEDDING_MAX_RETRIES):
            try:
                resp = await self.openai.embeddings.create(
                    input=text,
                    model=self.EMBEDDING_MODEL,
                )
                return resp.data[0].embedding
            except Exception as e:
                if attempt < self.EMBEDDING_MAX_RETRIES - 1:
                    logger.warning(f"Embedding attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2**attempt)
                else:
                    raise NexraError(
                        503,
                        EMBEDDING_SERVICE_UNAVAILABLE,
                        f"Failed to generate embedding after {self.EMBEDDING_MAX_RETRIES} attempts: {str(e)[:200]}",
                    )
        raise NexraError(503, EMBEDDING_SERVICE_UNAVAILABLE, "Embedding generation failed")
