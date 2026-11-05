"""Full-text search over doc_chunks (ADR 0003).

Owner: @NoorAlbusaidi (#13). Shell from #83 so the graph and app can wire it: add the methods.
"""

import asyncio

from clinic_assistant.repository.db import DictPool

DB_TIMEOUT_SECONDS = 5.0


class Retriever:
    """Find the clinic passages that best match a question."""

    def __init__(
        self,
        pool: DictPool,
        threshold: float,
        top_k: int,
    ) -> None:
        self.pool = pool
        self.threshold = threshold
        self.top_k = top_k

    async def search(self, question: str) -> list[dict[str, str | int | float]]:
        """Return the most relevant document chunks for a question."""

        if not question.strip():
            return []

        sql = """
            WITH search_query AS (
                SELECT websearch_to_tsquery(
                    'english',
                    replace(%s, ' ', ' OR ')
                ) AS query
            ),
            ranked_chunks AS (
                SELECT
                    chunks.content,
                    chunks.source,
                    chunks.chunk_index,
                    ts_rank(
                        chunks.search_vector,
                        search_query.query
                    ) AS score
                FROM doc_chunks AS chunks
                CROSS JOIN search_query
                WHERE chunks.search_vector @@ search_query.query
            )
            SELECT content, source, chunk_index, score
            FROM ranked_chunks
            WHERE score >= %s
            ORDER BY score DESC
            LIMIT %s;
        """

        async with asyncio.timeout(DB_TIMEOUT_SECONDS):
            async with self.pool.connection() as conn:
                cursor = await conn.execute(
                    sql,
                    (question, self.threshold, self.top_k),
                )
                rows = await cursor.fetchall()

        return [
            {
                "content": row["content"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "score": float(row["score"]),
            }
            for row in rows
        ]
