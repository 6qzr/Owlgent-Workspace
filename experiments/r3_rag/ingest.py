
import re
from pathlib import Path

from database import get_connection

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def split_into_paragraphs(text: str) -> list[str]:
    """Split document text into non-empty paragraphs."""
    # Remove Markdown headings
    text = re.sub(r"(?m)^#{1,6}\s+.*$", "", text)

    # Split paragraphs using blank lines
    paragraphs = re.split(r"\n\s*\n", text)

    return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]


def ingest_documents() -> None:
    """Read clinic documents and store their paragraphs in PostgreSQL."""

    documents = list(DOCUMENTS_DIR.glob("*.md"))

    if not documents:
        print("No Markdown documents found.")
        return

    with get_connection() as conn:
        for document_path in sorted(documents):
            source = document_path.name

            content = document_path.read_text(encoding="utf-8")
            paragraphs = split_into_paragraphs(content)

            # Remove previous chunks from this document
            # so re-running ingestion does not create duplicates.
            conn.execute(
                "DELETE FROM r3_rag_chunks WHERE source = %s",
                (source,),
            )

            for index, paragraph in enumerate(paragraphs):
                conn.execute(
                    """
                    INSERT INTO r3_rag_chunks
                        (source, chunk_index, content)
                    VALUES (%s, %s, %s)
                    """,
                    (source, index, paragraph),
                )

            print(f"Processed {source}: {len(paragraphs)} paragraphs")

    print("Document ingestion completed successfully.")


if __name__ == "__main__":
    ingest_documents()

