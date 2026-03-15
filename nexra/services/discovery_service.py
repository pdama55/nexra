import asyncio
import logging

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.capabilities import DiscoverMatchItem, DiscoverRequest
from core.errors import EMBEDDING_SERVICE_UNAVAILABLE, NexraError

logger = logging.getLogger("nexra.services.discovery")


class DiscoveryService:
    """Semantic discovery with composite scoring.

    Composite score: schema fit 50% + trust 25% + cost 15% + latency 10%.
    All scoring computed in a single PostgreSQL CTE query.
    """

    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI) -> None:
        self.db = db
        self.openai = openai_client

    async def discover(
        self,
        caller_org_id: str,
        request: DiscoverRequest,
    ) -> tuple[list[DiscoverMatchItem], int, int]:
        """Execute semantic discovery with composite scoring.

        Returns:
            Tuple of (matches, total_candidates, filtered_count).
        """
        query_embedding = await self._embed(request.query)

        await self.db.execute(text("SET LOCAL ivfflat.probes = 10"))

        sql = text("""
            WITH candidates AS (
                SELECT
                    a.id,
                    a.agent_id,
                    a.name,
                    a.capability_type,
                    a.trust_score,
                    a.pricing,
                    a.sla,
                    a.is_public,
                    a.status,
                    a.org_id,
                    1 - (a.embedding <=> CAST(:query_embedding AS vector)) AS semantic_score,
                    (a.pricing->>'per_call_usd')::float AS price_usd,
                    (a.sla->>'p99_latency_ms')::float AS latency_ms
                FROM agents a
                WHERE
                    a.status != 'quarantined'
                    AND a.embedding IS NOT NULL
                    AND (:capability_type IS NULL OR a.capability_type = :capability_type)
                    AND (:budget_cap IS NULL OR (a.pricing->>'per_call_usd')::float <= :budget_cap)
                    AND (:max_latency IS NULL OR (a.sla->>'p99_latency_ms')::int <= :max_latency)
                    AND (a.org_id = CAST(:caller_org_id AS uuid) OR (a.is_public = TRUE AND :include_cross_org = TRUE))
                    AND a.agent_id != ALL(CAST(:exclude_agents AS text[]))
            ),
            price_stats AS (
                SELECT
                    COALESCE(MAX(price_usd), 1) AS max_price,
                    COALESCE(MAX(latency_ms), 1) AS max_latency,
                    COUNT(*) AS filtered_count
                FROM candidates
            )
            SELECT
                c.agent_id,
                c.name,
                c.capability_type,
                c.trust_score::float,
                c.status,
                c.pricing,
                c.sla,
                c.is_public,
                c.org_id,
                c.semantic_score,
                (
                    (c.semantic_score * 0.50)
                    + (c.trust_score::float * 0.25)
                    + ((1 - (c.price_usd / NULLIF(ps.max_price, 0))) * 0.15)
                    + ((1 - (c.latency_ms / NULLIF(ps.max_latency, 0))) * 0.10)
                ) AS composite_score,
                ps.filtered_count
            FROM candidates c, price_stats ps
            ORDER BY composite_score DESC
            LIMIT :result_limit;
        """)

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "capability_type": request.capability_type,
                "budget_cap": request.budget_cap_usd,
                "max_latency": request.max_latency_ms,
                "caller_org_id": caller_org_id,
                "include_cross_org": request.include_cross_org,
                "exclude_agents": request.exclude_agents or [],
                "result_limit": request.limit,
            },
        )

        rows = result.fetchall()

        total_q = text(
            "SELECT COUNT(*) FROM agents WHERE embedding IS NOT NULL AND status != 'quarantined'"
        )
        total_result = await self.db.execute(total_q)
        total_candidates = total_result.scalar() or 0

        filtered_count = rows[0].filtered_count if rows else 0

        matches = [
            DiscoverMatchItem(
                agent_id=row.agent_id,
                name=row.name,
                match_score=round(float(row.composite_score), 4),
                trust_score=round(float(row.trust_score), 3),
                status=row.status,
                pricing=row.pricing,
                sla=row.sla,
                is_cross_org=(str(row.org_id) != caller_org_id),
                capability_type=row.capability_type,
            )
            for row in rows
        ]

        return matches, total_candidates, int(filtered_count)

    async def _embed(self, text_input: str) -> list[float]:
        for attempt in range(3):
            try:
                resp = await self.openai.embeddings.create(
                    input=text_input,
                    model=self.EMBEDDING_MODEL,
                )
                return resp.data[0].embedding
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Query embedding attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2**attempt)
                else:
                    raise NexraError(
                        503,
                        EMBEDDING_SERVICE_UNAVAILABLE,
                        f"Failed to generate query embedding: {str(e)[:200]}",
                    )
        raise NexraError(503, EMBEDDING_SERVICE_UNAVAILABLE, "Embedding generation failed")
