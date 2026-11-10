"""Async MCP client demonstrating booking tools and error cases."""

import asyncio

from fastmcp import Client

BOOKING_URL = "http://127.0.0.1:8001/mcp"


async def run_booking_demo() -> None:
    """Call the booking tools and demonstrate success and failure cases."""
    async with Client(BOOKING_URL) as client:
        tools = await client.list_tools()

        for tool in tools:
            print(f"Booking tool: {tool.name} - {tool.description}")

        patient = await client.call_tool(
            "register_patient",
            {
                "name": "Baraah",
                "phone": "99112233",
            },
        )
        print(f"booking.register_patient -> {patient.data}")

        patient_id = patient.data["patient_id"]

        booking_details = {
            "patient_id": patient_id,
            "doctor": "Dr. Huda",
            "date": "2026-11-20",
            "time": "10:00",
        }

        booking = await client.call_tool(
            "book_appointment",
            booking_details,
        )
        print(f"booking.book_appointment -> {booking.data}")

        duplicate = await client.call_tool(
            "book_appointment",
            booking_details,
        )
        print(f"booking.book_appointment -> {duplicate.data}")

        invalid = await client.call_tool(
            "book_appointment",
            {
                "patient_id": 999,
                "doctor": "Dr. Huda",
                "date": "2026-11-21",
                "time": "11:00",
            },
        )
        print(f"booking.book_appointment -> {invalid.data}")


if __name__ == "__main__":
    asyncio.run(run_booking_demo())
