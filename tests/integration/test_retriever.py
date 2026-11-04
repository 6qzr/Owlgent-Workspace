"""Integration tests for PostgreSQL document retrieval."""

from uuid import uuid4

from clinic_assistant.kb.retriever import Retriever
from clinic_assistant.repository.db import DictPool


async def test_search_returns_matching_documents(pool: DictPool) -> None:
    """Return document chunks matching the patient's question."""
    source = f"test_{uuid4().hex}.md"

    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO doc_chunks (source, chunk_index, content)
            VALUES (%s, %s, %s)
            """,
            (
                source,
                0,
                "The clinic provides quasar appointments every morning.",
            ),
        )

    try:
        retriever = Retriever(pool, threshold=0.0, top_k=3)

        results = await retriever.search("quasar")

        assert len(results) == 1
        assert results[0]["source"] == source
        assert results[0]["content"] == ("The clinic provides quasar appointments every morning.")
        assert results[0]["chunk_index"] == 0
        assert isinstance(results[0]["score"], float)
        assert results[0]["score"] >= 0.0

    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM doc_chunks WHERE source = %s",
                (source,),
            )


async def test_search_returns_empty_for_no_matches(
    pool: DictPool,
) -> None:
    """Return an empty list when no documents match."""
    retriever = Retriever(pool, threshold=0.0, top_k=3)

    results = await retriever.search(f"nonexistent_{uuid4().hex}")

    assert results == []


async def test_search_returns_empty_for_blank_question(
    pool: DictPool,
) -> None:
    """Do not query the database for a blank question."""
    retriever = Retriever(pool, threshold=0.0, top_k=3)

    assert await retriever.search("") == []
    assert await retriever.search("   ") == []


async def test_search_respects_threshold(pool: DictPool) -> None:
    """Exclude results below the configured relevance threshold."""
    source = f"test_{uuid4().hex}.md"

    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO doc_chunks (source, chunk_index, content)
            VALUES (%s, %s, %s)
            """,
            (
                source,
                0,
                "The clinic provides quasar appointments.",
            ),
        )

    try:
        retriever = Retriever(pool, threshold=1.0, top_k=3)

        results = await retriever.search("quasar")

        assert results == []

    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM doc_chunks WHERE source = %s",
                (source,),
            )


async def test_search_respects_top_k(pool: DictPool) -> None:
    """Limit the number of retrieved document chunks."""
    source = f"test_{uuid4().hex}.md"

    try:
        async with pool.connection() as conn:
            for index in range(3):
                await conn.execute(
                    """
                    INSERT INTO doc_chunks (source, chunk_index, content)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        source,
                        index,
                        f"The clinic offers quasar appointments. Document number {index}.",
                    ),
                )

        retriever = Retriever(pool, threshold=0.0, top_k=2)
        results = await retriever.search("quasar")

        assert len(results) == 2
        assert all(result["source"] == source for result in results)

    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM doc_chunks WHERE source = %s",
                (source,),
            )
