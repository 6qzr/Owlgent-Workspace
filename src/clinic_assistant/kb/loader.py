"""Load clinic Markdown documents into PostgreSQL."""

import re
from pathlib import Path

from clinic_assistant.repository.db import DictPool

DOCUMENTS_DIR = Path(__file__).parent / "documents"


def split_into_paragraphs(text: str) -> list[str]:
    """Split Markdown into paragraphs while preserving heading context."""
    headings: dict[int, str] = {}
    paragraphs: list[str] = []
    current_lines: list[str] = []

    def save_paragraph() -> None:
        """Save the current paragraph with its heading context."""
        if not current_lines:
            return

        content = "\n".join(current_lines).strip()
        heading = "\n".join(headings[level] for level in sorted(headings))

        if heading:
            paragraphs.append(f"{heading}:\n{content}")
        else:
            paragraphs.append(content)

        current_lines.clear()

    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)

        if match:
            save_paragraph()

            level = len(match.group(1))
            headings = {key: value for key, value in headings.items() if key < level}
            headings[level] = match.group(2).strip()

        elif not stripped:
            save_paragraph()

        else:
            current_lines.append(line)

    save_paragraph()

    return paragraphs


async def load_documents(pool: DictPool) -> None:
    """Read Markdown documents and replace their stored chunks."""
    documents = sorted(DOCUMENTS_DIR.glob("*.md"))

    async with pool.connection() as conn:
        for document_path in documents:
            source = document_path.name
            content = document_path.read_text(encoding="utf-8")
            paragraphs = split_into_paragraphs(content)

            # Replace each document's chunks atomically.
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM doc_chunks WHERE source = %s",
                    (source,),
                )

                for index, paragraph in enumerate(paragraphs):
                    await conn.execute(
                        """
                        INSERT INTO doc_chunks (source, chunk_index, content)
                        VALUES (%s, %s, %s);
                        """,
                        (source, index, paragraph),
                    )
