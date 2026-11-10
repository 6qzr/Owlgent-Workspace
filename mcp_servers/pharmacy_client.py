"""Pharmacy client: view the inventory, add stock and add a new medicine on the pharmacy server."""

import asyncio

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8002/mcp"


async def call_and_print(client: Client, tool: str, arguments: dict[str, object]) -> None:
    """Call one pharmacy tool and print its result on a single line."""
    result = await client.call_tool(tool, arguments)
    print(f"pharmacy.{tool} -> {result.data}")


async def run_pharmacy_demo() -> None:
    """List the tools, view the stock, top up Ibuprofen, then show the quantity-0 error."""
    async with Client(SERVER_URL) as client:
        tools = await client.list_tools()
        print(f"pharmacy tools -> {[tool.name for tool in tools]}")
        await call_and_print(client, "view_inventory", {})
        await call_and_print(client, "add_inventory", {"medicine": "Ibuprofen", "quantity": 10})
        await call_and_print(client, "add_inventory", {"medicine": "Ibuprofen", "quantity": 0})


async def run_new_medicine_flow() -> None:
    """Add a medicine that is not in stock yet, then view the inventory to show it is there."""
    async with Client(SERVER_URL) as client:
        await call_and_print(client, "add_inventory", {"medicine": "Amoxicillin", "quantity": 30})
        await call_and_print(client, "view_inventory", {})


async def main() -> None:
    """Run the demo, then the new-medicine flow."""
    await run_pharmacy_demo()
    await run_new_medicine_flow()


if __name__ == "__main__":
    asyncio.run(main())
