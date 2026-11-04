"""Integration tests for loading clinic documents into PostgreSQL."""

from pathlib import Path
from uuid import uuid4

import pytest

from clinic_assistant.kb import loader
from clinic_assistant.repository.db import DictPool


async def test_load_documents_into_database(
    pool: DictPool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load paragraphs and update existing chunks without duplicates."""

    source = f"test_{uuid4().hex}.md"
    document = tmp_path / source

    document.write_text(
        "# Test Policy\n\nFirst paragraph.\n\nSecond paragraph.",
        encoding="utf-8",
    )

    monkeypatch.setattr(loader, "DOCUMENTS_DIR", tmp_path)

    try:
        # First run: insert two paragraphs.
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
        assert rows[0]["content"] == "First paragraph."
        assert rows[1]["chunk_index"] == 1
        assert rows[1]["content"] == "Second paragraph."

        # Second run: should not create duplicate records.
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

        # Update the document and run the loader again.
        document.write_text(
            "# Test Policy\n\nUpdated first paragraph.\n\nSecond paragraph.",
            encoding="utf-8",
        )

        await loader.load_documents(pool)

        async with pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT content
                FROM doc_chunks
                WHERE source = %s AND chunk_index = 0
                """,
                (source,),
            )
            updated_row = await cursor.fetchone()

        assert updated_row is not None
        assert updated_row["content"] == "Updated first paragraph."
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

    # The directory is empty.
    assert list(tmp_path.glob("*.md")) == []

    # Loading should complete without errors.
    await loader.load_documents(pool)
