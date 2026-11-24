"""Appointments MCP server for Clinic Assistant v2."""

import threading
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from servers.appointments.tokens import (
    Unauthorized,
    get_jwt_secret,
    token_from_header,
    verify_token,
)

HOST = "0.0.0.0"  # noqa: S104 - Required for Docker networking.
PORT = 8001

READ_SCOPE = "appointments:read"
WRITE_SCOPE = "appointments:write"

mcp = FastMCP("Appointments MCP Server")

Appointment = dict[str, Any]

# Protect shared appointment data from concurrent requests.
appointments_lock = threading.Lock()

# Sample appointments stored in memory.
appointments: dict[int, Appointment] = {
    1: {
        "appointment_id": 1,
        "user_id": "user-a",
        "doctor": "Dr. Huda",
        "date": "2026-12-01",
        "time": "09:00",
        "status": "booked",
    },
    2: {
        "appointment_id": 2,
        "user_id": "user-b",
        "doctor": "Dr. Ahmed",
        "date": "2026-12-01",
        "time": "10:00",
        "status": "booked",
    },
}


def get_current_user(required_scope: str) -> str:
    """Verify the Bearer token and return the signed-in user."""
    headers = get_http_headers(include={"authorization"})
    authorization = headers.get("authorization")
    token = token_from_header(authorization)

    claims = verify_token(token, required_scope)
    return str(claims["sub"])


@mcp.tool
def book_appointment(
    doctor: str,
    date: str,
    time: str,
) -> Appointment:
    """Book a free appointment for the signed-in patient."""
    try:
        user_id = get_current_user(WRITE_SCOPE)
    except Unauthorized:
        return {"error": "unauthorized"}

    # Only one thread can check and book a slot at a time.
    with appointments_lock:
        for existing in appointments.values():
            if (
                existing["doctor"] == doctor
                and existing["date"] == date
                and existing["time"] == time
                and existing["status"] == "booked"
            ):
                return {"error": "slot already booked"}

        appointment_id = max(appointments, default=0) + 1

        new_appointment: Appointment = {
            "appointment_id": appointment_id,
            "user_id": user_id,
            "doctor": doctor,
            "date": date,
            "time": time,
            "status": "booked",
        }

        appointments[appointment_id] = new_appointment
        return new_appointment.copy()


@mcp.tool
def list_my_appointments() -> list[Appointment] | Appointment:
    """List only the signed-in patient's appointments."""
    try:
        user_id = get_current_user(READ_SCOPE)
    except Unauthorized:
        return {"error": "unauthorized"}

    with appointments_lock:
        my_appointments: list[Appointment] = []

        for appointment in appointments.values():
            if appointment["user_id"] == user_id:
                my_appointments.append(appointment.copy())

        return my_appointments


@mcp.tool
def cancel_appointment(appointment_id: int) -> Appointment:
    """Cancel an appointment owned by the signed-in patient."""
    try:
        user_id = get_current_user(WRITE_SCOPE)
    except Unauthorized:
        return {"error": "unauthorized"}

    with appointments_lock:
        appointment = appointments.get(appointment_id)

        if appointment is None:
            return {"error": "not found"}

        if appointment["user_id"] != user_id:
            return {"error": "not found"}

        if appointment["status"] == "cancelled":
            return {"error": "already cancelled"}

        appointment["status"] = "cancelled"
        return appointment.copy()


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    """Return a health response for Docker Compose."""
    return PlainTextResponse("OK")


def main() -> None:
    """Start the appointments MCP server."""
    get_jwt_secret()
    mcp.run(transport="http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
