"""The MCP tools one signed-in user may call, with that user's JWT on every request."""

import asyncio
import json
import logging

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import TextContent

from api.config import MAX_TOOL_RESULT_CHARS, MCP_TIMEOUT_SECONDS
from api.llm import ToolSpec

logger = logging.getLogger(__name__)

UNAVAILABLE_RESULT = json.dumps({"error": "this service is unavailable right now"})


class McpToolbox:
    """Finds the tools on each MCP server and calls them as the signed-in user."""

    def __init__(
        self, server_urls: dict[str, str], jwt: str, timeout: float = MCP_TIMEOUT_SECONDS
    ) -> None:
        """Remember the servers and the user's JWT; nothing is called yet."""
        self._server_urls = server_urls
        self._jwt = jwt
        self._timeout = timeout
        self._tool_servers: dict[str, str] = {}

    def _client(self, url: str) -> Client[StreamableHttpTransport]:
        """Return an MCP client for one server that sends the user's JWT."""
        transport = StreamableHttpTransport(url, headers={"Authorization": f"Bearer {self._jwt}"})
        return Client(transport, timeout=self._timeout, init_timeout=self._timeout)

    async def discover(self) -> list[ToolSpec]:
        """List the tools of every reachable server; a down server is logged and skipped."""
        per_server = await asyncio.gather(
            *(self._list_server_tools(name, url) for name, url in self._server_urls.items())
        )
        return [tool for tools in per_server for tool in tools]

    async def _list_server_tools(self, name: str, url: str) -> list[ToolSpec]:
        """List one server's tools and remember which server owns each one."""
        try:
            async with self._client(url) as client:
                tools = await client.list_tools()
        # Any failure (refused, timeout, bad reply) means the same thing: skip this server.
        except Exception as error:
            logger.warning("MCP server %s (%s) is unavailable: %r", name, url, error)
            return []

        specs: list[ToolSpec] = []
        for tool in tools:
            self._tool_servers[tool.name] = url
            specs.append(ToolSpec(tool.name, tool.description or "", tool.input_schema))
        return specs

    async def call(self, name: str, arguments: dict[str, object]) -> str:
        """Call one tool and return its result as text for the model; never raise."""
        url = self._tool_servers.get(name)
        if url is None:
            return json.dumps({"error": f"unknown tool {name}"})
        try:
            async with self._client(url) as client:
                result = await client.call_tool(name, arguments, raise_on_error=False)
        # The model only needs to know the call failed; the details go to the log.
        except Exception as error:
            logger.warning("MCP tool %s at %s failed: %r", name, url, error)
            return UNAVAILABLE_RESULT

        text = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
        return text[:MAX_TOOL_RESULT_CHARS]
