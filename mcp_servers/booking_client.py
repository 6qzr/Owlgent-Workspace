import asyncio

from fastmcp import Client


async def run_booking_demo() -> None:

    async with Client("http://127.0.0.1:8001/mcp") as client:
        # List the available tools
        tools = await client.list_tools()
        print("Booking tools:", [tool.name for tool in tools])

        # 1. Register a patient
        patient = await client.call_tool(
            "register_patient",
            {
                "name": "Baraah",
                "phone": "99112233",
            },
        )
        print(f"booking.register_patient -> {patient.data}")

        patient_id = patient.data["patient_id"]

        # 2. Book an appointment
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

        # 3. Error case: book the same slot
        duplicate = await client.call_tool(
            "book_appointment",
            booking_details,
        )
        print(f"booking.book_appointment -> {duplicate.data}")

        # 4. Error case: unknown patient
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
