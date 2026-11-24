"""In-process FastMCP stubs that follow docs/contract.md, so /chat can be tested before the real
servers land. Each tool checks the Bearer JWT and its scope exactly like a real server would."""

from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from auth_reference.tokens import Unauthorized, token_from_header, verify_token

UNAUTHORIZED = {"error": "unauthorized"}

LAST_RECORDS = {
    "user-a": {"date": "2026-10-02", "diagnosis": "Flu", "notes": "Rest"},
    "user-b": {"date": "2026-10-20", "diagnosis": "Sprained ankle", "notes": "Ice and rest"},
}


class StubLog:
    """What the stubs saw: every Authorization header, so tests can check the JWT was sent."""

    def __init__(self) -> None:
        """Start with an empty log."""
        self.authorization_headers: list[str] = []


def signed_in_user(log: StubLog, scope: str) -> str:
    """Return the caller's sub from the Bearer JWT, or raise Unauthorized."""
    authorization = get_http_headers(include={"authorization"}).get("authorization", "")
    log.authorization_headers.append(authorization)
    claims = verify_token(token_from_header(authorization), scope)
    return str(claims["sub"])


def build_stub_servers(log: StubLog) -> dict[str, FastMCP]:
    """Return the four stub servers, keyed by the names in config.MCP_URL_ENV_VARS."""
    appointments = FastMCP("stub-appointments")
    pharmacy = FastMCP("stub-pharmacy")
    records = FastMCP("stub-records")
    knowledge = FastMCP("stub-knowledge")
    booked: list[dict[str, Any]] = []

    @appointments.tool
    def book_appointment(doctor: str, date: str, time: str) -> dict[str, Any]:
        """Book an appointment for the signed-in user."""
        try:
            user = signed_in_user(log, "appointments:write")
        except Unauthorized:
            return UNAUTHORIZED
        appointment = {"appointment_id": len(booked) + 1, "doctor": doctor, "date": date}
        booked.append({**appointment, "time": time, "user": user})
        return {**appointment, "time": time}

    @appointments.tool
    def list_my_appointments() -> list[dict[str, Any]] | dict[str, str]:
        """List the signed-in user's appointments."""
        try:
            user = signed_in_user(log, "appointments:read")
        except Unauthorized:
            return UNAUTHORIZED
        return [item for item in booked if item["user"] == user]

    @appointments.tool
    def cancel_appointment(appointment_id: int) -> dict[str, Any]:
        """Cancel one of the signed-in user's appointments."""
        try:
            user = signed_in_user(log, "appointments:write")
        except Unauthorized:
            return UNAUTHORIZED
        for item in booked:
            if item["appointment_id"] == appointment_id and item["user"] == user:
                return {**item, "status": "cancelled"}
        return {"error": "not found"}

    @pharmacy.tool
    def view_inventory() -> list[dict[str, Any]] | dict[str, str]:
        """Show the pharmacy stock."""
        try:
            signed_in_user(log, "pharmacy:read")
        except Unauthorized:
            return UNAUTHORIZED
        return [{"medicine": "Paracetamol", "stock": 120}]

    @pharmacy.tool
    def add_inventory(medicine: str, quantity: int) -> dict[str, Any]:
        """Add stock for one medicine."""
        try:
            signed_in_user(log, "pharmacy:write")
        except Unauthorized:
            return UNAUTHORIZED
        return {"medicine": medicine, "stock": quantity}

    @records.tool
    def get_my_medical_records() -> list[dict[str, str]] | dict[str, str]:
        """Return the signed-in user's records."""
        try:
            user = signed_in_user(log, "records:read")
        except Unauthorized:
            return UNAUTHORIZED
        return [LAST_RECORDS[user]] if user in LAST_RECORDS else {"error": "no records"}

    @records.tool
    def get_my_last_medical_record() -> dict[str, str]:
        """Return the signed-in user's newest record."""
        try:
            user = signed_in_user(log, "records:read")
        except Unauthorized:
            return UNAUTHORIZED
        return LAST_RECORDS.get(user, {"error": "no records"})

    @knowledge.tool
    def search_clinic_docs(query: str, top_k: int = 3) -> list[dict[str, Any]] | dict[str, str]:
        """Search the clinic documents."""
        try:
            signed_in_user(log, "docs:read")
        except Unauthorized:
            return UNAUTHORIZED
        chunk = {"text": "Dr. Sara is the dermatologist.", "source": "doctors.pdf", "score": 0.9}
        return [chunk][:top_k]

    return {
        "appointments": appointments,
        "pharmacy": pharmacy,
        "records": records,
        "knowledge": knowledge,
    }
