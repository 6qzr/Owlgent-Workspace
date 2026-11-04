"""Load clinic Markdown documents into PostgreSQL."""

import re
from pathlib import Path

from clinic_assistant.repository.db import DictPool

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def split_into_paragraphs(text: str) -> list[str]:
    """Split Markdown text into non-empty paragraphs."""

    # Remove Markdown headings.
    text = re.sub(r"(?m)^#{1,6}\s+.*$", "", text)

    # Split paragraphs using blank lines.
    paragraphs = re.split(r"\n\s*\n", text)

    return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]


async def load_documents(pool: DictPool) -> None:
    """Read Markdown documents and store their paragraphs in PostgreSQL."""

    documents = sorted(DOCUMENTS_DIR.glob("*.md"))

    async with pool.connection() as conn:
        for document_path in documents:
            source = document_path.name

            content = document_path.read_text(encoding="utf-8")
            paragraphs = split_into_paragraphs(content)

            for index, paragraph in enumerate(paragraphs):
                await conn.execute(
                    """
                    INSERT INTO doc_chunks (source, chunk_index, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source, chunk_index)
                    DO UPDATE SET content = EXCLUDED.content;
                    """,
                    (source, index, paragraph),
                )
