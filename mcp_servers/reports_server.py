
from fastmcp import FastMCP

PORT = 8003

mcp = FastMCP("Medical Reports Server")

medical_records = {
    1: [
        {
            "date": "2026-10-02",
            "diagnosis": "Flu",
            "notes": "Rest"
        }
    ],
    2: [
        {
            "date": "2026-10-05",
            "diagnosis": "Headache",
            "notes": "Follow-up if symptoms continue"
        }
    ]
}

opd_records = {
    1: [
        {
            "date": "2026-10-02",
            "department": "General"
        }
    ],
    2: [
        {
            "date": "2026-10-05",
            "department": "Cardiology"
        }
    ]
}


@mcp.tool
def get_patient_medical_records(patient_id: int) -> list[dict] | dict:
    """Retrieve medical records for a patient by their ID."""

    if patient_id not in medical_records:
        return {"error": f"Patient with ID {patient_id} was not found."}

    return medical_records[patient_id]


@mcp.tool
def get_opd_records(patient_id: int) -> list[dict] | dict:
    """Retrieve OPD records for a patient by their ID."""

    if patient_id not in opd_records:
        return {"error": f"Patient with ID {patient_id} was not found."}

    return opd_records[patient_id]


if __name__ == "__main__":
    mcp.run(transport="http", port=PORT)
