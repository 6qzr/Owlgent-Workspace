"""Pharmacy MCP server: view the inventory and add stock, on port 8002."""

from fastmcp import FastMCP

PORT = 8002

mcp = FastMCP("Pharmacy Server")

inventory: dict[str, int] = {"Paracetamol": 120, "Ibuprofen": 40}


@mcp.tool
def view_inventory() -> dict[str, int]:
    """Return the full pharmacy inventory as a dict of medicine name to stock."""
    return inventory


@mcp.tool
def add_inventory(medicine: str, quantity: int) -> dict:
    """Add stock for a medicine (a new medicine is added); reject quantity <= 0."""
    if quantity <= 0:
        return {"error": "quantity must be greater than 0"}
    inventory[medicine] = inventory.get(medicine, 0) + quantity
    return {"medicine": medicine, "stock": inventory[medicine]}


if __name__ == "__main__":
    mcp.run(transport="http", port=PORT)
