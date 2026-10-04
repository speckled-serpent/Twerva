"""`/api/v1` route surface without opening Postgres."""

import os
import unittest

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import APIRouter, FastAPI

from app.api.v1.router import api_v1_router
from app.main import application, attach_api_v1_routes


EXPECTED_API_V1_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/brands",
        "/api/v1/brands/{brand_id}",
        "/api/v1/source-items",
        "/api/v1/source-items/{source_item_id}",
        "/api/v1/campaigns",
        "/api/v1/campaigns/{campaign_id}",
        "/api/v1/campaigns/{campaign_id}/start",
        "/api/v1/campaigns/{campaign_id}/pause",
        "/api/v1/campaigns/{campaign_id}/resume",
        "/api/v1/campaigns/{campaign_id}/finish",
        "/api/v1/themes",
        "/api/v1/themes/{theme_id}",
        "/api/v1/themes/{theme_id}/elements",
        "/api/v1/themes/{theme_id}/elements/{element_id}",
        "/api/v1/spotmu/interests/search",
        "/api/v1/clusters",
        "/api/v1/clusters/{cluster_id}",
        "/api/v1/accounts",
        "/api/v1/accounts/{account_id}",
        "/api/v1/artifacts",
        "/api/v1/artifacts/{artifact_id}",
        "/api/v1/post-jobs",
        "/api/v1/post-jobs/{post_job_id}",
        "/api/v1/ingest/spotmu/interests/{slug}",
        "/api/v1/ingest/spotmu/sync",
        "/api/v1/clusters/{cluster_id}/source-items/{source_item_id}",
        "/api/v1/generate/carousel",
        "/api/v1/generate/templates",
        "/api/v1/artifacts/{artifact_id}/slides/{slide_index}/image",
        "/api/v1/artifacts/{artifact_id}/regenerate",
        "/api/v1/artifacts/{artifact_id}/approve",
        "/api/v1/artifacts/{artifact_id}/reject",
        "/api/v1/schedule",
        "/api/v1/publish/run/{post_job_id}",
        "/api/v1/post-jobs/{post_job_id}/metrics",
        "/api/v1/post-jobs/{post_job_id}/metrics/stub",
        "/api/v1/clusters/{cluster_id}/metrics/summary",
        "/api/v1/clusters/{cluster_id}/steer",
        "/api/v1/clusters/{cluster_id}/agent-summary",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/users",
        "/api/v1/auth/users/{ops_user_id}",
        "/api/v1/auth/users/{ops_user_id}/reset-password",
    },
)
COLLECTION_HTTP_METHODS: frozenset[str] = frozenset({"post", "get"})
ITEM_HTTP_METHODS: frozenset[str] = frozenset({"get"})


class ApiRouteSurfaceTests(unittest.TestCase):
    """1.2l-ii / 1.2l-iii: POST + GET list + GET by id are registered."""

    def test_api_v1_router_exposes_create_list_and_get_paths(self) -> None:
        """Every persist-proof resource has collection and item paths."""

        openapi_paths: set[str] = set(_openapi_paths_for_router(api_v1_router))

        self.assertTrue(EXPECTED_API_V1_PATHS.issubset(openapi_paths))

    def test_collection_routes_accept_post_and_get(self) -> None:
        """Collection paths support POST (create) and GET (list)."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        collection_paths: tuple[str, ...] = (
            "/api/v1/brands",
            "/api/v1/source-items",
            "/api/v1/clusters",
            "/api/v1/accounts",
            "/api/v1/artifacts",
            "/api/v1/post-jobs",
            "/api/v1/campaigns",
            "/api/v1/themes",
        )

        for collection_path in collection_paths:
            collection_methods: set[str] = methods_by_path[collection_path]

            self.assertTrue(
                COLLECTION_HTTP_METHODS.issubset(collection_methods),
                msg=f"{collection_path} missing POST/GET: {collection_methods}",
            )

    def test_ingest_and_cluster_link_routes_exist(self) -> None:
        """1.3c–1.3e: ingest + attach/detach paths are registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        ingest_interest_methods: set[str] = methods_by_path[
            "/api/v1/ingest/spotmu/interests/{slug}"
        ]
        ingest_sync_methods: set[str] = methods_by_path["/api/v1/ingest/spotmu/sync"]
        cluster_link_methods: set[str] = methods_by_path[
            "/api/v1/clusters/{cluster_id}/source-items/{source_item_id}"
        ]

        self.assertIn("post", ingest_interest_methods)
        self.assertIn("post", ingest_sync_methods)
        self.assertIn("post", cluster_link_methods)
        self.assertIn("delete", cluster_link_methods)

    def test_generate_carousel_route_accepts_post(self) -> None:
        """1.4e-i: POST /api/v1/generate/carousel is registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        generate_carousel_methods: set[str] = methods_by_path["/api/v1/generate/carousel"]

        self.assertIn("post", generate_carousel_methods)

    def test_carousel_template_and_preview_routes_exist(self) -> None:
        """Template list, slide image GET, and regenerate POST are registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        template_list_methods: set[str] = methods_by_path["/api/v1/generate/templates"]
        slide_image_methods: set[str] = methods_by_path[
            "/api/v1/artifacts/{artifact_id}/slides/{slide_index}/image"
        ]
        regenerate_methods: set[str] = methods_by_path[
            "/api/v1/artifacts/{artifact_id}/regenerate"
        ]

        self.assertIn("get", template_list_methods)
        self.assertIn("get", slide_image_methods)
        self.assertIn("post", regenerate_methods)

    def test_review_queue_and_schedule_routes_exist(self) -> None:
        """1.5a / 1.5c: approve, reject, PATCH caption, POST schedule."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        approve_methods: set[str] = methods_by_path[
            "/api/v1/artifacts/{artifact_id}/approve"
        ]
        reject_methods: set[str] = methods_by_path[
            "/api/v1/artifacts/{artifact_id}/reject"
        ]
        artifact_item_methods: set[str] = methods_by_path["/api/v1/artifacts/{artifact_id}"]
        schedule_methods: set[str] = methods_by_path["/api/v1/schedule"]

        self.assertIn("post", approve_methods)
        self.assertIn("post", reject_methods)
        self.assertIn("patch", artifact_item_methods)
        self.assertIn("get", artifact_item_methods)
        self.assertIn("post", schedule_methods)

    def test_campaign_lifecycle_routes_accept_post(self) -> None:
        """Start / pause / resume / finish are POST actions on a campaign."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        start_methods: set[str] = methods_by_path["/api/v1/campaigns/{campaign_id}/start"]
        pause_methods: set[str] = methods_by_path["/api/v1/campaigns/{campaign_id}/pause"]
        resume_methods: set[str] = methods_by_path["/api/v1/campaigns/{campaign_id}/resume"]
        finish_methods: set[str] = methods_by_path["/api/v1/campaigns/{campaign_id}/finish"]

        self.assertIn("post", start_methods)
        self.assertIn("post", pause_methods)
        self.assertIn("post", resume_methods)
        self.assertIn("post", finish_methods)

    def test_theme_item_route_accepts_patch(self) -> None:
        """1.10a-i: PATCH /api/v1/themes/{theme_id} is registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        theme_item_methods: set[str] = methods_by_path["/api/v1/themes/{theme_id}"]

        self.assertIn("patch", theme_item_methods)
        self.assertIn("get", theme_item_methods)

    def test_theme_element_routes_accept_post_patch_and_delete(self) -> None:
        """1.10b-ii: element create, patch, and delete are registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        element_collection_methods: set[str] = methods_by_path[
            "/api/v1/themes/{theme_id}/elements"
        ]
        element_item_methods: set[str] = methods_by_path[
            "/api/v1/themes/{theme_id}/elements/{element_id}"
        ]

        self.assertIn("post", element_collection_methods)
        self.assertIn("patch", element_item_methods)
        self.assertIn("delete", element_item_methods)

    def test_publish_run_route_accepts_post(self) -> None:
        """1.6c-i: POST /api/v1/publish/run/{post_job_id} is registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        publish_run_methods: set[str] = methods_by_path[
            "/api/v1/publish/run/{post_job_id}"
        ]

        self.assertIn("post", publish_run_methods)

    def test_measure_and_steer_routes_exist(self) -> None:
        """1.7: metrics append, stub, cluster median, steer, agent-summary."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        metrics_methods: set[str] = methods_by_path[
            "/api/v1/post-jobs/{post_job_id}/metrics"
        ]
        stub_methods: set[str] = methods_by_path[
            "/api/v1/post-jobs/{post_job_id}/metrics/stub"
        ]
        summary_methods: set[str] = methods_by_path[
            "/api/v1/clusters/{cluster_id}/metrics/summary"
        ]
        steer_methods: set[str] = methods_by_path["/api/v1/clusters/{cluster_id}/steer"]
        agent_summary_methods: set[str] = methods_by_path[
            "/api/v1/clusters/{cluster_id}/agent-summary"
        ]

        self.assertIn("post", metrics_methods)
        self.assertIn("post", stub_methods)
        self.assertIn("get", summary_methods)
        self.assertIn("post", steer_methods)
        self.assertIn("get", agent_summary_methods)

    def test_auth_routes_exist(self) -> None:
        """Login / logout / me plus password and user-admin routes."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        login_methods: set[str] = methods_by_path["/api/v1/auth/login"]
        logout_methods: set[str] = methods_by_path["/api/v1/auth/logout"]
        me_methods: set[str] = methods_by_path["/api/v1/auth/me"]
        change_password_methods: set[str] = methods_by_path[
            "/api/v1/auth/change-password"
        ]
        users_methods: set[str] = methods_by_path["/api/v1/auth/users"]
        user_item_methods: set[str] = methods_by_path["/api/v1/auth/users/{ops_user_id}"]
        reset_password_methods: set[str] = methods_by_path[
            "/api/v1/auth/users/{ops_user_id}/reset-password"
        ]

        self.assertIn("post", login_methods)
        self.assertIn("post", logout_methods)
        self.assertIn("get", me_methods)
        self.assertIn("post", change_password_methods)
        self.assertIn("get", users_methods)
        self.assertIn("post", users_methods)
        self.assertIn("patch", user_item_methods)
        self.assertIn("post", reset_password_methods)

    def test_spotmu_interest_search_route_accepts_get(self) -> None:
        """Ops proxy GET /api/v1/spotmu/interests/search is registered."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        search_methods: set[str] = methods_by_path["/api/v1/spotmu/interests/search"]

        self.assertIn("get", search_methods)

    def test_item_routes_accept_get(self) -> None:
        """By-id paths support GET."""

        methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_v1_router)
        item_paths: tuple[str, ...] = (
            "/api/v1/brands/{brand_id}",
            "/api/v1/source-items/{source_item_id}",
            "/api/v1/clusters/{cluster_id}",
            "/api/v1/accounts/{account_id}",
            "/api/v1/artifacts/{artifact_id}",
            "/api/v1/post-jobs/{post_job_id}",
            "/api/v1/campaigns/{campaign_id}",
            "/api/v1/themes/{theme_id}",
        )

        for item_path in item_paths:
            item_methods: set[str] = methods_by_path[item_path]

            self.assertTrue(
                ITEM_HTTP_METHODS.issubset(item_methods),
                msg=f"{item_path} missing GET: {item_methods}",
            )

    def test_attach_api_v1_routes_is_idempotent_on_the_process_app(self) -> None:
        """Mounting twice does not duplicate `/api/v1/brands` in OpenAPI."""

        attach_api_v1_routes(application)
        attach_api_v1_routes(application)
        openapi_document: dict[str, object] = application.openapi()
        openapi_paths_object: object = openapi_document["paths"]

        if not isinstance(openapi_paths_object, dict):
            self.fail("OpenAPI paths must be an object")

        self.assertIn("/api/v1/brands", openapi_paths_object)
        self.assertIn("/health", openapi_paths_object)


def _openapi_paths_for_router(api_router: APIRouter) -> set[str]:
    """Return OpenAPI paths after mounting `api_router` on a throwaway app."""

    methods_by_path: dict[str, set[str]] = _openapi_methods_by_path(api_router)

    return set(methods_by_path.keys())


def _openapi_methods_by_path(api_router: APIRouter) -> dict[str, set[str]]:
    """Map each OpenAPI path to lowercase HTTP methods."""

    throwaway_application: FastAPI = FastAPI()
    throwaway_application.include_router(api_router)
    openapi_document: dict[str, object] = throwaway_application.openapi()
    openapi_paths_object: object = openapi_document["paths"]

    if not isinstance(openapi_paths_object, dict):
        raise TypeError("OpenAPI paths must be an object")

    methods_by_path: dict[str, set[str]] = {}

    for path_key, path_item in openapi_paths_object.items():

        if not isinstance(path_key, str) or not isinstance(path_item, dict):
            continue

        methods_by_path[path_key] = {
            method_name
            for method_name in path_item.keys()
            if method_name in {"get", "post", "put", "patch", "delete"}
        }

    return methods_by_path


if __name__ == "__main__":
    unittest.main()
