
"""Client for testing the Medical Reports MCP server."""

import asyncio

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8003/mcp"


async def main() -> None:
    """Connect to the server and test its medical reports tools."""

    async with Client(SERVER_URL) as client:

        # 1. List the available tools
        tools = await client.list_tools()

        print("Available tools:")
        for tool in tools:
            print(f"- {tool.name}")

        # 2. Get medical records for patient 1
        print("\nMedical records for patient 1:")
        result = await client.call_tool(
            "get_patient_medical_records",
            {"patient_id": 1}
        )
        print(result.data)

        # 3. Get OPD records for patient 1
        print("\nOPD records for patient 1:")
        result = await client.call_tool(
            "get_opd_records",
            {"patient_id": 1}
        )
        print(result.data)

        # 4. Test unknown patient
        print("\nMedical records for unknown patient 99:")
        result = await client.call_tool(
            "get_patient_medical_records",
            {"patient_id": 99}
        )
        print(result.data)

        # 5. Test unknown patient for OPD records
        print("\nOPD records for unknown patient 99:")
        result = await client.call_tool(
            "get_opd_records",
            {"patient_id": 99}
        )
        print(result.data)


if __name__ == "__main__":
    asyncio.run(main())
