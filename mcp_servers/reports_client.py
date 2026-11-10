"""Client for the Medical Reports MCP server: known patient records and unknown-patient errors."""

import asyncio

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8003/mcp"
KNOWN_PATIENT_ID = 1
UNKNOWN_PATIENT_ID = 99


async def call_and_print(client: Client, tool: str, patient_id: int) -> None:
    """Call one reports tool for a patient and print its result on a single line."""
    result = await client.call_tool(tool, {"patient_id": patient_id})
    print(f"reports.{tool} -> {result.data}")


async def run_reports_demo() -> None:
    """List the tools, read both record types for a known patient, then show the errors."""
    async with Client(SERVER_URL) as client:
        tools = await client.list_tools()
        print(f"reports tools -> {[tool.name for tool in tools]}")
        for patient_id in (KNOWN_PATIENT_ID, UNKNOWN_PATIENT_ID):
            await call_and_print(client, "get_patient_medical_records", patient_id)
            await call_and_print(client, "get_opd_records", patient_id)


if __name__ == "__main__":
    asyncio.run(run_reports_demo())
