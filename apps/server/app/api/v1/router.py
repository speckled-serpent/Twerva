"""Aggregate `/api/v1` persist-proof routers."""

from fastapi import APIRouter

from app.api.v1.accounts import accounts_router
from app.api.v1.artifacts import artifacts_router
from app.api.v1.brands import brands_router
from app.api.v1.clusters import clusters_router
from app.api.v1.generate import generate_router
from app.api.v1.ingest import ingest_router
from app.api.v1.metrics import metrics_router
from app.api.v1.post_jobs import post_jobs_router
from app.api.v1.publish import publish_router
from app.api.v1.schedule import schedule_router
from app.api.v1.source_items import source_items_router
from app.api.v1.steer import steer_router


api_v1_router: APIRouter = APIRouter(prefix="/api/v1")
api_v1_router.include_router(brands_router)
api_v1_router.include_router(source_items_router)
api_v1_router.include_router(clusters_router)
api_v1_router.include_router(steer_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(artifacts_router)
api_v1_router.include_router(post_jobs_router)
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(ingest_router)
api_v1_router.include_router(generate_router)
api_v1_router.include_router(schedule_router)
api_v1_router.include_router(publish_router)
