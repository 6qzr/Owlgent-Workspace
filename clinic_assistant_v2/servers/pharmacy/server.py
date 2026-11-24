"""Pharmacy Inventory MCP Server with JWT authentication."""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from servers.pharmacy.tokens import (
    Unauthorized,
    get_jwt_secret,
    token_from_header,
    verify_token,
)

HOST = "0.0.0.0"  # noqa: S104 - Required for Docker networking.
PORT = 8002

READ_SCOPE = "pharmacy:read"
WRITE_SCOPE = "pharmacy:write"

mcp = FastMCP("Pharmacy MCP Server")

# In-memory medicine inventory.
inventory: dict[str, int] = {
    "Paracetamol": 120,
    "Ibuprofen": 40,
}


def verify_access(required_scope: str) -> bool:
    """Verify the Bearer token and its required scope."""
    headers = get_http_headers(include={"authorization"})
    authorization = headers.get("authorization")
    token = token_from_header(authorization)

    try:
        verify_token(token, required_scope)
    except Unauthorized:
        return False

    return True


@mcp.tool
def view_inventory() -> list[dict[str, str | int]] | dict[str, str]:
    """Return the complete pharmacy inventory."""
    if not verify_access(READ_SCOPE):
        return {"error": "unauthorized"}

    items: list[dict[str, str | int]] = []

    for medicine, stock in inventory.items():
        items.append(
            {
                "medicine": medicine,
                "stock": stock,
            }
        )

    return items


@mcp.tool
def add_inventory(
    medicine: str,
    quantity: int,
) -> dict[str, str | int]:
    """Add a new medicine or increase existing stock."""
    if not verify_access(WRITE_SCOPE):
        return {"error": "unauthorized"}

    if quantity <= 0:
        return {"error": "Quantity must be greater than zero"}

    current_stock = inventory.get(medicine, 0)
    new_stock = current_stock + quantity

    inventory[medicine] = new_stock

    return {
        "medicine": medicine,
        "stock": new_stock,
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    """Report whether the server is running."""
    return PlainTextResponse("OK")


def main() -> None:
    """Start the Pharmacy MCP Server."""
    get_jwt_secret()
    mcp.run(transport="http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
