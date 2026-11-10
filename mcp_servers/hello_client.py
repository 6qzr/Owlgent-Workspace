"""Warm-up client: call the hello server's add tool and print the result."""

import asyncio

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8004/mcp"


async def main() -> None:
    """Connect to the hello server, call add(2, 3) and print the sum."""
    async with Client(SERVER_URL) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(result.data)


if __name__ == "__main__":
    asyncio.run(main())
