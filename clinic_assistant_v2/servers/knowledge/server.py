"""Knowledge retrieval MCP server for clinic documents."""

import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from openai import OpenAI
from qdrant_client import QdrantClient
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from servers.knowledge.tokens import (
    Unauthorized,
    get_jwt_secret,
    token_from_header,
    verify_token,
)

HOST = "0.0.0.0"  # noqa: S104 - Required for Docker networking.
PORT = 8004

READ_SCOPE = "docs:read"
DEFAULT_TOP_K = 3
SCORE_THRESHOLD = 0.3
REQUEST_TIMEOUT_SECONDS = 10

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_COLLECTION = "clinic_docs"
DEFAULT_QDRANT_URL = "http://qdrant:6333"

mcp = FastMCP("Clinic Knowledge MCP Server")


def get_openai_client() -> OpenAI:
    """Create an OpenAI client with a request timeout."""
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key or api_key == "your-key-here":
        raise RuntimeError("OPENAI_API_KEY is not configured")

    return OpenAI(
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def get_qdrant_client() -> QdrantClient:
    """Create a Qdrant client with a request timeout."""
    url = os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL)

    return QdrantClient(
        url=url,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def verify_access() -> bool:
    """Verify the Bearer JWT has permission to search documents."""
    headers = get_http_headers(include={"authorization"})
    token = token_from_header(headers.get("authorization"))

    try:
        verify_token(token, READ_SCOPE)
    except Unauthorized:
        return False

    return True


@mcp.tool
def search_clinic_docs(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, str | float]] | dict[str, str]:
    """Find relevant clinic document chunks and their sources."""
    if not verify_access():
        return {"error": "unauthorized"}

    if not query.strip():
        return []

    if top_k <= 0:
        return {"error": "top_k must be greater than zero"}

    model = os.environ.get(
        "EMBEDDING_MODEL",
        DEFAULT_EMBEDDING_MODEL,
    )
    collection = os.environ.get(
        "QDRANT_COLLECTION",
        DEFAULT_COLLECTION,
    )

    try:
        openai_client = get_openai_client()
        qdrant_client = get_qdrant_client()

        embedding_response = openai_client.embeddings.create(
            model=model,
            input=query,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        question_vector = embedding_response.data[0].embedding

        search_response = qdrant_client.query_points(
            collection_name=collection,
            query=question_vector,
            limit=top_k,
            score_threshold=SCORE_THRESHOLD,
            with_payload=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        results: list[dict[str, str | float]] = []

        for hit in search_response.points:
            payload = hit.payload

            if payload is None:
                continue

            text = payload.get("text")
            source = payload.get("source")

            if not isinstance(text, str):
                continue

            if not isinstance(source, str):
                continue

            results.append(
                {
                    "text": text,
                    "source": source,
                    "score": float(hit.score),
                }
            )

        return results

    except Exception as error:
        # External provider failures must not crash the MCP tool
        # or expose sensitive request details.
        return {"error": f"retrieval failed: {type(error).__name__}"}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    """Report whether the knowledge server is running."""
    return PlainTextResponse("OK")


def main() -> None:
    """Start the Knowledge MCP server."""
    load_dotenv()
    get_jwt_secret()

    mcp.run(
        transport="http",
        host=HOST,
        port=PORT,
    )


if __name__ == "__main__":
    main()
