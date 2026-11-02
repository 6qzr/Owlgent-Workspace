"""The app factory builds a working FastAPI app with OpenAPI docs."""

from fastapi.testclient import TestClient

from clinic_assistant.main import APP_TITLE, create_app


def test_openapi_schema_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == APP_TITLE
