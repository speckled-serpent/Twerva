"""Twerva API process entrypoint.

This module is a runnable shell only: health check, no domain models.
"""

from fastapi import FastAPI
from pydantic import BaseModel


APPLICATION_TITLE: str = "Twerva Server"
HEALTH_STATUS_OK: str = "ok"


class HealthStatusResponse(BaseModel):
    """JSON body returned by the process health endpoint."""

    status: str


application: FastAPI = FastAPI(
    title=APPLICATION_TITLE,
    description="Distribution control plane API shell.",
)


@application.get("/health", response_model=HealthStatusResponse)
async def get_health_status() -> HealthStatusResponse:
    """Return a liveness payload for local and load-balancer checks.

    Returns:
        A JSON object with status set to ok when the process is up.
    """

    health_status_response: HealthStatusResponse = HealthStatusResponse(
        status=HEALTH_STATUS_OK,
    )

    return health_status_response
