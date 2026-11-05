"""Integration tests for loading clinic documents into PostgreSQL."""

from pathlib import Path
from uuid import uuid4

import pytest

from clinic_assistant.kb import loader
from clinic_assistant.repository.db import DictPool

pytestmark = pytest.mark.integration


async def test_load_documents_into_database(
    pool: DictPool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load documents, preserve headings, and remove stale chunks."""

    source = f"test_{uuid4().hex}.md"
    document = tmp_path / source

    document.write_text(
        "# Test Policy\n\nFirst paragraph.\n\nSecond paragraph.",
        encoding="utf-8",
    )

    monkeypatch.setattr(loader, "DOCUMENTS_DIR", tmp_path)

    try:
        # First run: insert two paragraphs with their heading.
        await loader.load_documents(pool)

        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT source, chunk_index, content
                FROM doc_chunks
                WHERE source = %s
                ORDER BY chunk_index
                """,
                (source,),
            )
            rows = await cursor.fetchall()

        assert len(rows) == 2
        assert rows[0]["chunk_index"] == 0
        assert rows[0]["content"] == "Test Policy:\nFirst paragraph."
        assert rows[1]["chunk_index"] == 1
        assert rows[1]["content"] == "Test Policy:\nSecond paragraph."

        # Second run: loading again must not create duplicates.
        await loader.load_documents(pool)

        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM doc_chunks
                WHERE source = %s
                """,
                (source,),
            )
            result = await cursor.fetchone()

        assert result is not None
        assert result["total"] == 2

        # Third run: shorten the document to one paragraph.
        document.write_text(
            "# Test Policy\n\nUpdated first paragraph.",
            encoding="utf-8",
        )

        await loader.load_documents(pool)

        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT chunk_index, content
                FROM doc_chunks
                WHERE source = %s
                ORDER BY chunk_index
                """,
                (source,),
            )
            updated_rows = await cursor.fetchall()

        # The old second chunk must no longer exist.
        assert len(updated_rows) == 1
        assert updated_rows[0]["chunk_index"] == 0
        assert updated_rows[0]["content"] == ("Test Policy:\nUpdated first paragraph.")

    finally:
        # Remove test records from PostgreSQL.
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM doc_chunks WHERE source = %s",
                (source,),
            )


async def test_load_documents_empty_directory(
    pool: DictPool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complete successfully when there are no Markdown documents."""

    monkeypatch.setattr(loader, "DOCUMENTS_DIR", tmp_path)

    assert list(tmp_path.glob("*.md")) == []

    await loader.load_documents(pool)
