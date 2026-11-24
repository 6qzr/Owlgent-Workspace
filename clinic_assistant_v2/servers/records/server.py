"""Medical Records MCP server with JWT authentication."""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from servers.records.tokens import (
    Unauthorized,
    get_jwt_secret,
    token_from_header,
    verify_token,
)

HOST = "0.0.0.0"  # noqa: S104 - Required for Docker networking.
PORT = 8003
READ_SCOPE = "records:read"

mcp = FastMCP("Medical Records MCP Server")

# Records are ordered from oldest to newest.
medical_records: dict[str, list[dict[str, str]]] = {
    "user-a": [
        {
            "date": "2026-09-15",
            "diagnosis": "Cold",
            "notes": "Drink water",
        },
        {
            "date": "2026-10-02",
            "diagnosis": "Flu",
            "notes": "Rest",
        },
    ],
    "user-b": [
        {
            "date": "2026-09-20",
            "diagnosis": "Headache",
            "notes": "Follow up",
        },
        {
            "date": "2026-10-20",
            "diagnosis": "Sprained ankle",
            "notes": "Ice and rest",
        },
    ],
}


def get_current_user() -> str:
    """Verify the JWT and return the signed-in patient's identity."""
    headers = get_http_headers(include={"authorization"})
    authorization = headers.get("authorization")
    token = token_from_header(authorization)

    claims = verify_token(token, READ_SCOPE)
    return str(claims["sub"])


@mcp.tool
def get_my_medical_records() -> list[dict[str, str]] | dict[str, str]:
    """Return all medical records for the signed-in patient."""
    try:
        user_id = get_current_user()
    except Unauthorized:
        return {"error": "unauthorized"}

    records = medical_records.get(user_id)

    if not records:
        return {"error": "no records"}

    return [record.copy() for record in records]


@mcp.tool
def get_my_last_medical_record() -> dict[str, str]:
    """Return the signed-in patient's most recent medical record."""
    try:
        user_id = get_current_user()
    except Unauthorized:
        return {"error": "unauthorized"}

    records = medical_records.get(user_id)

    if not records:
        return {"error": "no records"}

    return records[-1].copy()


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    """Return a health response for Docker Compose."""
    return PlainTextResponse("OK")


def main() -> None:
    """Start the Medical Records MCP server."""
    get_jwt_secret()
    mcp.run(transport="http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
