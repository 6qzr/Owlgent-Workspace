"""Warm-up MCP server with one tool, add, on port 8004 (8000 is the clinic API)."""

from fastmcp import FastMCP

PORT = 8004

mcp = FastMCP("Hello Server")


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two whole numbers and return the sum."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="http", port=PORT)
