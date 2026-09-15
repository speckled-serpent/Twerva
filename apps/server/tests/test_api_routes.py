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
