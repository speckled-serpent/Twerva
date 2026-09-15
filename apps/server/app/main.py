"""Twerva API process entrypoint.

`GET /health` is a liveness check and does **not** import settings, models,
or the engine (same 1.2a pattern). Domain routes live under `/api/v1` and
are attached only when `DATABASE_URL` can be resolved (env, `.env`, or a
test flag). A health-only process still starts without Postgres.
"""

from fastapi import FastAPI
from pydantic import BaseModel


APPLICATION_TITLE: str = "Twerva Server"
HEALTH_STATUS_OK: str = "ok"
MISSING_DATABASE_URL_ERROR_NAME: str = "MissingDatabaseUrlError"


class HealthStatusResponse(BaseModel):
    """JSON body returned by the process health endpoint."""

    status: str


application: FastAPI = FastAPI(
    title=APPLICATION_TITLE,
    description="Distribution control plane API.",
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


def attach_api_v1_routes(fastapi_application: FastAPI) -> None:
    """Mount Phase 1 persist-proof routes under `/api/v1`.

    Importing the router package loads settings and the engine. Callers
    that must stay health-only should not invoke this when `DATABASE_URL`
    cannot be resolved.

    Args:
        fastapi_application: Application that should expose `/api/v1`.
    """

    routes_already_attached: bool = bool(
        getattr(fastapi_application.state, "api_v1_attached", False),
    )

    if routes_already_attached:

        return

    from app.api.v1.router import api_v1_router

    fastapi_application.include_router(api_v1_router)
    fastapi_application.state.api_v1_attached = True


def _attach_api_v1_routes_when_database_url_is_available() -> None:
    """Attach `/api/v1` when settings can load; skip for health-only boots."""

    try:
        attach_api_v1_routes(application)
    except Exception as attach_error:
        error_type_name: str = type(attach_error).__name__

        if error_type_name == MISSING_DATABASE_URL_ERROR_NAME:

            return

        raise


_attach_api_v1_routes_when_database_url_is_available()
