"""Offline tests for the clinic PDF ingestion job."""

import shutil
import uuid
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from openai import OpenAI
from qdrant_client import QdrantClient, models

from ingestion import ingest


def test_split_into_chunks() -> None:
    """Overlapping windows advance by 400 characters."""
    text = "x" * 400 + "y" * 100 + "z" * 100
    chunks = ingest.split_into_chunks(text)

    assert len(chunks) == 2
    assert chunks[0] == text[:500]
    assert chunks[1] == text[400:]
    assert len(chunks[0]) == 500


def test_short_and_empty_text() -> None:
    """Short text stays in one chunk, and empty text has no chunks."""
    assert ingest.split_into_chunks("Hello clinic") == ["Hello clinic"]
    assert ingest.split_into_chunks("") == []


def test_bad_overlap() -> None:
    """Overlaps must be smaller than the window."""
    with pytest.raises(ValueError):
        ingest.split_into_chunks(
            "hello",
            chunk_size=100,
            overlap=100,
        )


def test_fake_embedder() -> None:
    """Embedding requests use the configured model and preserve order."""
    fake = MagicMock()

    fake.embeddings.create.return_value.data = [
        MagicMock(index=1, embedding=[2.0] * 1536),
        MagicMock(index=0, embedding=[1.0] * 1536),
    ]

    vectors = ingest.embed_texts(
        ["first", "second"],
        cast(OpenAI, fake),
        "text-embedding-3-small",
    )

    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0

    fake.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["first", "second"],
    )


def test_ensure_collection_creates_only_once() -> None:
    """An existing collection is never deleted or recreated."""
    fake = MagicMock()
    fake.collection_exists.side_effect = [False, True]

    client = cast(QdrantClient, fake)

    ingest.ensure_collection(client, "clinic_docs")
    ingest.ensure_collection(client, "clinic_docs")

    fake.create_collection.assert_called_once()
    fake.delete_collection.assert_not_called()

    config = fake.create_collection.call_args.kwargs["vectors_config"]

    assert isinstance(config, models.VectorParams)
    assert config.size == 1536
    assert config.distance == models.Distance.COSINE


def test_stable_ids_prevent_duplicate_points() -> None:
    """Two upserts of identical chunks have identical point IDs."""
    fake = MagicMock()
    client = cast(QdrantClient, fake)

    chunks = ["one", "two"]
    vectors = [
        [0.1] * 1536,
        [0.2] * 1536,
    ]

    ingest.store_chunks(
        client,
        "clinic_docs",
        "doctors.pdf",
        chunks,
        vectors,
    )

    ingest.store_chunks(
        client,
        "clinic_docs",
        "doctors.pdf",
        chunks,
        vectors,
    )

    first = fake.upsert.call_args_list[0].kwargs["points"]
    second = fake.upsert.call_args_list[1].kwargs["points"]

    assert [point.id for point in first] == [point.id for point in second]

    assert first[0].id == str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "doctors.pdf#0",
        )
    )

    assert first[0].payload == {
        "text": "one",
        "source": "doctors.pdf",
    }

    unique_ids = {
        point.id for call in fake.upsert.call_args_list for point in call.kwargs["points"]
    }

    assert len(unique_ids) == 2


def test_embedding_count_must_match() -> None:
    """An incomplete embedding response must not write points."""
    fake = MagicMock()

    with pytest.raises(ValueError):
        ingest.store_chunks(
            cast(QdrantClient, fake),
            "clinic_docs",
            "a.pdf",
            ["hi"],
            [],
        )

    fake.upsert.assert_not_called()


def test_pdf_text_and_pipeline(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fake embedder and Qdrant client can ingest the same PDF twice."""
    path = tmp_path / "doctors.pdf"

    shutil.copyfile(
        ingest.PDF_DIR / "doctors.pdf",
        path,
    )

    assert "dermatologist" in ingest.load_pdf_text(path).lower()

    points_by_id: dict[str, models.PointStruct] = {}

    fake = MagicMock()
    fake.collection_exists.return_value = True

    def fake_upsert(
        *,
        collection_name: str,
        points: list[models.PointStruct],
    ) -> None:
        """Simulate Qdrant's overwrite-on-duplicate-ID behavior."""
        assert collection_name == "clinic_docs"

        for point in points:
            points_by_id[str(point.id)] = point

    fake.upsert.side_effect = fake_upsert

    def fake_embeddings(
        chunks: list[str],
    ) -> list[list[float]]:
        """Return deterministic fake vectors without API requests."""
        return [[0.5] * 1536 for _ in chunks]

    client = cast(QdrantClient, fake)

    first = ingest.ingest_pdfs(
        client,
        tmp_path,
        "clinic_docs",
        fake_embeddings,
    )

    count_after_first = len(points_by_id)

    second = ingest.ingest_pdfs(
        client,
        tmp_path,
        "clinic_docs",
        fake_embeddings,
    )

    assert first == second
    assert len(points_by_id) == count_after_first

    output = capsys.readouterr().out

    assert f"doctors.pdf: {first['doctors.pdf']} chunks stored" in output
