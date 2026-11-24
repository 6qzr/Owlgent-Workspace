"""Load clinic PDF text into Qdrant using stable point identifiers."""

import os
import uuid
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from qdrant_client import QdrantClient, models

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
VECTOR_SIZE = 1536

PDF_DIR = Path(__file__).parent / "pdfs"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_COLLECTION = "clinic_docs"
DEFAULT_QDRANT_URL = "http://qdrant:6333"


def load_pdf_text(path: Path) -> str:
    """Read selectable text from every page of one PDF."""
    reader = PdfReader(path)
    pages: list[str] = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def split_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping windows without empty chunks."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")

    chunks: list[str] = []
    step = chunk_size - overlap

    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(text):
            break

    return chunks


def embed_texts(
    chunks: list[str],
    client: OpenAI,
    model: str,
) -> list[list[float]]:
    """Request one embedding for each chunk, preserving input order."""
    if not chunks:
        return []

    response = client.embeddings.create(
        model=model,
        input=chunks,
    )

    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def ensure_collection(
    client: QdrantClient,
    collection: str,
) -> None:
    """Create the cosine vector collection only when it does not exist."""
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )


def store_chunks(
    client: QdrantClient,
    collection: str,
    source: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> int:
    """Upsert PDF chunks using stable source-and-index UUID5 point IDs."""
    if len(chunks) != len(vectors):
        raise ValueError("Every chunk must have exactly one embedding")

    points: list[models.PointStruct] = []

    for index, chunk in enumerate(chunks):
        points.append(
            models.PointStruct(
                id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{source}#{index}",
                    )
                ),
                vector=vectors[index],
                payload={
                    "text": chunk,
                    "source": source,
                },
            )
        )

    if points:
        client.upsert(
            collection_name=collection,
            points=points,
        )

    return len(points)


def ingest_pdfs(
    client: QdrantClient,
    pdf_dir: Path,
    collection: str,
    embedder: Callable[[list[str]], list[list[float]]],
) -> dict[str, int]:
    """Read, chunk, embed and upsert each PDF in the given directory."""
    if not pdf_dir.is_dir():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

    ensure_collection(client, collection)

    counts: dict[str, int] = {}

    for path in sorted(pdf_dir.glob("*.pdf")):
        chunks = split_into_chunks(load_pdf_text(path))
        vectors = embedder(chunks)

        count = store_chunks(
            client,
            collection,
            path.name,
            chunks,
            vectors,
        )

        counts[path.name] = count
        print(f"{path.name}: {count} chunks stored")

    return counts


def main() -> None:
    """Connect to OpenAI and Qdrant and ingest the clinic PDFs once."""
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key or api_key == "your-key-here":
        raise RuntimeError("Set a real OPENAI_API_KEY in your .env file")

    model = os.environ.get(
        "EMBEDDING_MODEL",
        DEFAULT_EMBEDDING_MODEL,
    )
    collection = os.environ.get(
        "QDRANT_COLLECTION",
        DEFAULT_COLLECTION,
    )
    qdrant_url = os.environ.get(
        "QDRANT_URL",
        DEFAULT_QDRANT_URL,
    )

    openai_client = OpenAI(api_key=api_key)
    qdrant_client = QdrantClient(url=qdrant_url)

    def make_embeddings(chunks: list[str]) -> list[list[float]]:
        """Create embeddings using the configured OpenAI embedding model."""
        return embed_texts(
            chunks,
            openai_client,
            model,
        )

    ingest_pdfs(
        qdrant_client,
        PDF_DIR,
        collection,
        make_embeddings,
    )


if __name__ == "__main__":
    main()
