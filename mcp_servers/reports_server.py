"""Medical Reports MCP server: patient medical records and OPD visits, on port 8003."""

from fastmcp import FastMCP

PORT = 8003

mcp = FastMCP("Medical Reports Server")

Record = dict[str, str]

medical_records: dict[int, list[Record]] = {
    1: [{"date": "2026-10-02", "diagnosis": "Flu", "notes": "Rest"}],
    2: [{"date": "2026-10-05", "diagnosis": "Headache", "notes": "Follow-up if symptoms continue"}],
}

opd_records: dict[int, list[Record]] = {
    1: [{"date": "2026-10-02", "department": "General"}],
    2: [{"date": "2026-10-05", "department": "Cardiology"}],
}


def patient_not_found(patient_id: int) -> Record:
    """Build the error returned for a patient ID with no records."""
    return {"error": f"Patient with ID {patient_id} was not found."}


@mcp.tool
def get_patient_medical_records(patient_id: int) -> list[Record] | Record:
    """Return a patient's medical records (date, diagnosis, notes), or an error if unknown."""
    if patient_id not in medical_records:
        return patient_not_found(patient_id)
    return medical_records[patient_id]


@mcp.tool
def get_opd_records(patient_id: int) -> list[Record] | Record:
    """Return a patient's outpatient visits (date, department), or an error if unknown."""
    if patient_id not in opd_records:
        return patient_not_found(patient_id)
    return opd_records[patient_id]


if __name__ == "__main__":
    mcp.run(transport="http", port=PORT)
