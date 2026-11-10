"""MCP server for patient registration and appointment booking."""

from fastmcp import FastMCP

BOOKING_PORT = 8001

mcp = FastMCP("Booking MCP Server")

# In-memory storage
patients: dict[int, dict[str, int | str]] = {}
appointments: dict[int, dict[str, int | str]] = {}


@mcp.tool
def register_patient(name: str, phone: str) -> dict[str, int | str]:
    """Register a new patient and return their generated ID and details."""
    patient_id = len(patients) + 1

    patient = {
        "patient_id": patient_id,
        "name": name,
        "phone": phone,
    }

    patients[patient_id] = patient
    return patient


@mcp.tool
def book_appointment(
    patient_id: int,
    doctor: str,
    date: str,
    time: str,
) -> dict[str, int | str]:
    """Book a patient appointment if the doctor is available at that time."""
    if patient_id not in patients:
        return {"error": "Patient not found"}

    # Prevent double booking for the same doctor, date, and time.
    for appointment in appointments.values():
        if (
            appointment["doctor"] == doctor
            and appointment["date"] == date
            and appointment["time"] == time
        ):
            return {"error": "Doctor is already booked"}

    appointment_id = len(appointments) + 1

    appointment = {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "doctor": doctor,
        "date": date,
        "time": time,
    }

    appointments[appointment_id] = appointment
    return appointment


if __name__ == "__main__":
    mcp.run(transport="http", port=BOOKING_PORT)
