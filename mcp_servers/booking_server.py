from fastmcp import FastMCP

mcp = FastMCP("Booking MCP Server")

# Inmemory storage
patients: dict[int, dict] = {}
appointments: dict[int, dict] = {}


@mcp.tool
def register_patient(name: str, phone: str) -> dict:
    # Register a patient and return their information
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
) -> dict:
    # book an appointment for a registered patient

    # Check that the patient exists
    if patient_id not in patients:
        return {"error": "Patient not found"}

    # Prevent double booking
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
    mcp.run(transport="http", port=8001)
