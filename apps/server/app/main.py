"""Twerva API process entrypoint.

`GET /health` is a liveness check and does **not** import settings, models,
or the engine (same 1.2a pattern). Domain routes live under `/api/v1` and
are attached only when `DATABASE_URL` can be resolved (env, `.env`, or a
test flag). A health-only process still starts without Postgres.

When `/api/v1` mounts, CORS (ops origins + credentials) is attached and
the first ops admin may be bootstrapped from env. Those imports stay
inside `attach_api_v1_routes` so health stays import-light.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


APPLICATION_TITLE: str = "Twerva Server"
HEALTH_STATUS_OK: str = "ok"
MISSING_DATABASE_URL_ERROR_NAME: str = "MissingDatabaseUrlError"
LOGGER: logging.Logger = logging.getLogger("twerva.main")


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
    _attach_ops_cors_middleware(fastapi_application)
    _bootstrap_ops_admin_after_attach()


def _attach_api_v1_routes_when_database_url_is_available() -> None:
    """Attach `/api/v1` when settings can load; skip for health-only boots."""

    try:
        attach_api_v1_routes(application)
    except Exception as attach_error:
        error_type_name: str = type(attach_error).__name__

        if error_type_name == MISSING_DATABASE_URL_ERROR_NAME:

            return

        raise


def _attach_ops_cors_middleware(fastapi_application: FastAPI) -> None:
    """Allow credentialed browser calls from configured ops origins.

    Same-origin nginx (`https://twerva.com`) does not need CORS. Local Vite
    on :5173 does when it talks to uvicorn without the proxy.
    """

    cors_already_attached: bool = bool(
        getattr(fastapi_application.state, "ops_cors_attached", False),
    )

    if cors_already_attached:

        return

    from app.settings import Settings, get_settings, parse_ops_cors_origins

    settings: Settings = get_settings()
    allowed_origins: list[str] = parse_ops_cors_origins(settings.ops_cors_origins)

    if not allowed_origins:
        fastapi_application.state.ops_cors_attached = True

        return

    fastapi_application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_application.state.ops_cors_attached = True


def _bootstrap_ops_admin_after_attach() -> None:
    """Create the first ops admin when env is set. Skipped under tests."""

    from app.settings import _running_in_test_environment

    if _running_in_test_environment():

        return

    from app.auth.bootstrap import bootstrap_admin_operator_from_environment

    try:
        bootstrap_admin_operator_from_environment()
    except Exception as bootstrap_error:
        error_type_name: str = type(bootstrap_error).__name__
        LOGGER.warning(
            "Ops admin bootstrap skipped (%s).",
            error_type_name,
        )


_attach_api_v1_routes_when_database_url_is_available()
