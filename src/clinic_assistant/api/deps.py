"""Dependencies shared by the routers."""

from fastapi import HTTPException, Request, status

from clinic_assistant.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    """The runtime the lifespan opened on app.state; 503 until it exists."""
    runtime: Runtime | None = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service is starting up")
    return runtime
