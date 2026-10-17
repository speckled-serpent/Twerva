"""Aggregate `/api/v1` persist-proof routers.

`/api/v1/auth/login`, `/logout`, and `/me` stay public as before (`/me`
still 401 without a cookie). Other `/api/v1` routes require a session
cookie. Readers may GET; mutations return 403 except self
`change-password` and `logout`. User-admin routes are admin-only.
"""

from fastapi import APIRouter, Depends

from app.api.v1.accounts import accounts_router
from app.api.v1.albums import albums_router
from app.api.v1.artifacts import artifacts_router
from app.api.v1.authentication import authentication_router
from app.api.v1.brands import brands_router
from app.api.v1.campaigns import campaigns_router
from app.api.v1.clusters import clusters_router
from app.api.v1.generate import generate_router
from app.api.v1.ingest import ingest_router
from app.api.v1.metrics import metrics_router
from app.api.v1.post_jobs import post_jobs_router
from app.api.v1.publish import publish_router
from app.api.v1.schedule import schedule_router
from app.api.v1.source_items import source_items_router
from app.api.v1.carousels import carousels_router
from app.api.v1.spotmu import spotmu_router
from app.api.v1.steer import steer_router
from app.api.v1.skeletons import skeletons_router
from app.auth.dependencies import require_ops_operator_allowed_for_request


api_v1_router: APIRouter = APIRouter(prefix="/api/v1")
api_v1_router.include_router(authentication_router)

protected_api_v1_router: APIRouter = APIRouter(
    dependencies=[Depends(require_ops_operator_allowed_for_request)],
)
protected_api_v1_router.include_router(brands_router)
protected_api_v1_router.include_router(source_items_router)
protected_api_v1_router.include_router(carousels_router)
protected_api_v1_router.include_router(albums_router)
protected_api_v1_router.include_router(campaigns_router)
protected_api_v1_router.include_router(skeletons_router)
protected_api_v1_router.include_router(spotmu_router)
protected_api_v1_router.include_router(clusters_router)
protected_api_v1_router.include_router(steer_router)
protected_api_v1_router.include_router(accounts_router)
protected_api_v1_router.include_router(artifacts_router)
protected_api_v1_router.include_router(post_jobs_router)
protected_api_v1_router.include_router(metrics_router)
protected_api_v1_router.include_router(ingest_router)
protected_api_v1_router.include_router(generate_router)
protected_api_v1_router.include_router(schedule_router)
protected_api_v1_router.include_router(publish_router)
api_v1_router.include_router(protected_api_v1_router)
