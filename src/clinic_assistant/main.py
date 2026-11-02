"""Application factory: creates the FastAPI app and wires dependencies at start-up."""

from fastapi import FastAPI

from clinic_assistant import __version__

APP_TITLE = "Clinic Front-Desk Assistant"


def create_app() -> FastAPI:
    """Create the FastAPI app; each slice registers its router here."""
    return FastAPI(title=APP_TITLE, version=__version__)


app = create_app()
