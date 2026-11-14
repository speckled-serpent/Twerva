"""Ayrshare post HTTP with a mock transport. No socket to api.ayrshare.com."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("TWERVA_ENV", "test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from app.api.v1.router import api_v1_router
from app.db import get_our_database_session
from app.models import Account, Artifact, PostJob
from app.models.enums import AccountStatus, ArtifactStatus, Platform, PostJobStatus
from app.publish.adapter import PublishResult
from app.publish.ayrshare import (
    AYRSHARE_MEDIA_UPLOAD_ENDPOINT,
    AYRSHARE_POST_ENDPOINT,
    AYRSHARE_PROFILE_KEY_HEADER,
    AYRSHARE_PUBLISH_LOGGER_NAME,
    AyrsharePublishAdapter,
)
from app.publish.errors import PublishError
from app.publish.mock import MockPublishAdapter
from app.settings import clear_settings_cache


AYRSHARE_TEST_API_KEY: str = "test-ayrshare-api-key"
AYRSHARE_TEST_PROFILE_KEY: str = "test-ayrshare-profile-key"
FIXED_ACCOUNT_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")
FIXED_ARTIFACT_ID: uuid.UUID = uuid.UUID("55555555-5555-5555-5555-555555555555")
FIXED_POST_ID: uuid.UUID = uuid.UUID("66666666-6666-6666-6666-666666666666")
FIXED_CLUSTER_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PLATFORM_POST_ID: str = "17878176260289172"
PLATFORM_POST_URL: str = "https://www.instagram.com/p/CP1dI9Hp_WO/"
AYRSHARE_OWN_POST_ID: str = "RhrbDtYh7hdSMc67zC8H"
FIRST_MEDIA_URL: str = "https://cdn.example/frames/one.png"
SECOND_MEDIA_URL: str = "https://cdn.example/frames/two.png"


class _RecordingTransport:
    """Mock transport that keeps each request the adapter sent."""

    def __init__(self, handler_response: httpx.Response | Exception) -> None:

        self.requests: list[httpx.Request] = []
        self._handler_response: httpx.Response | Exception = handler_response

    def client(self) -> httpx.Client:
        """Build a client whose transport cannot open a real socket."""

        recording_transport: _RecordingTransport = self

        def handler(request: httpx.Request) -> httpx.Response:

            recording_transport.requests.append(request)
            outcome: httpx.Response | Exception = recording_transport._handler_response

            if isinstance(outcome, Exception):
                raise outcome

            fresh_response: httpx.Response = httpx.Response(
                outcome.status_code,
                content=outcome.content,
                headers=outcome.headers,
            )

            return fresh_response

        mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
        http_client: httpx.Client = httpx.Client(transport=mock_transport)

        return http_client


def _instagram_success_body() -> dict[str, object]:
    """Documented post response. The platform id is not the top-level id."""

    return {
        "status": "success",
        "errors": [],
        "postIds": [
            {
                "status": "success",
                "platform": "instagram",
                "id": PLATFORM_POST_ID,
                "postUrl": PLATFORM_POST_URL,
            },
        ],
        "id": AYRSHARE_OWN_POST_ID,
    }


def _account(
    platform: Platform,
    external_account_id: str | None,
) -> Account:
    """Build an unbound account."""

    account: Account = Account(
        cluster_id=FIXED_CLUSTER_ID,
        platform=platform,
        handle="brendan",
        status=AccountStatus.ACTIVE,
        external_account_id=external_account_id,
    )
    account.id = FIXED_ACCOUNT_ID

    return account


def _post_job() -> PostJob:
    """Build an unbound scheduled post job."""

    post_job: PostJob = PostJob(
        artifact_id=FIXED_ARTIFACT_ID,
        account_id=FIXED_ACCOUNT_ID,
        status=PostJobStatus.SCHEDULED,
    )
    post_job.id = FIXED_POST_ID

    return post_job


def _artifact(caption: str | None) -> Artifact:
    """Build an unbound draft artifact."""

    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        status=ArtifactStatus.DRAFT,
        format="carousel",
        caption=caption,
    )
    artifact.id = FIXED_ARTIFACT_ID

    return artifact


def _request_json(request: httpx.Request) -> dict[str, object]:
    """Decode one recorded POST body."""

    decoded_body: object = json.loads(request.content.decode("utf-8"))

    if not isinstance(decoded_body, dict):
        raise AssertionError("Ayrshare post body was not a JSON object")

    return decoded_body


class AyrshareHttpTests(unittest.TestCase):
    """One mocked POST. The transport is the only HTTP path."""

    def test_publish_media_posts_caption_urls_and_profile_key(self) -> None:
        """Instagram body, bearer key, and Profile-Key match the docs."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=_instagram_success_body()),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )
        media_urls: list[str] = [FIRST_MEDIA_URL, SECOND_MEDIA_URL]
        caption: str = "Harbor lights"

        with self.assertLogs(AYRSHARE_PUBLISH_LOGGER_NAME, level="INFO") as log_context:
            publish_result: PublishResult = adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.INSTAGRAM, f"  {AYRSHARE_TEST_PROFILE_KEY}  "),
                [],
                caption,
                media_urls,
            )

        self.assertEqual(len(transport.requests), 1)
        request: httpx.Request = transport.requests[0]
        request_body: dict[str, object] = _request_json(request)
        joined_log: str = "\n".join(log_context.output)

        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), AYRSHARE_POST_ENDPOINT)
        self.assertEqual(request_body["post"], caption)
        self.assertEqual(request_body["platforms"], ["instagram"])
        self.assertEqual(request_body["mediaUrls"], media_urls)
        self.assertNotIn("scheduleDate", request_body)
        self.assertEqual(
            request.headers["Authorization"],
            f"Bearer {AYRSHARE_TEST_API_KEY}",
        )
        self.assertEqual(
            request.headers[AYRSHARE_PROFILE_KEY_HEADER],
            AYRSHARE_TEST_PROFILE_KEY,
        )
        self.assertEqual(publish_result.platform_post_id, PLATFORM_POST_ID)
        self.assertEqual(publish_result.platform_post_url, PLATFORM_POST_URL)
        self.assertNotEqual(publish_result.platform_post_id, AYRSHARE_OWN_POST_ID)
        self.assertIn(str(FIXED_POST_ID), joined_log)
        self.assertIn("platform=instagram", joined_log)
        self.assertIn("http_status=200", joined_log)
        self.assertIn("media_count=2", joined_log)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, joined_log)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, joined_log)

    def test_publish_sends_artifact_caption_and_null_caption_is_empty(self) -> None:
        """The post-job path sends artifact.caption, or an empty string."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=_instagram_success_body()),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )
        media_urls: list[str] = [FIRST_MEDIA_URL]
        account: Account = _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY)

        adapter.publish(
            _post_job(),
            _artifact(None),
            account,
            [],
            media_urls,
        )
        empty_body: dict[str, object] = _request_json(transport.requests[0])

        self.assertEqual(empty_body["post"], "")
        self.assertEqual(
            transport.requests[0].headers[AYRSHARE_PROFILE_KEY_HEADER],
            AYRSHARE_TEST_PROFILE_KEY,
        )

        adapter.publish(
            _post_job(),
            _artifact("Slide name"),
            account,
            [],
            media_urls,
        )
        named_body: dict[str, object] = _request_json(transport.requests[1])

        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(named_body["post"], "Slide name")
        self.assertEqual(named_body["mediaUrls"], media_urls)

    def test_profile_response_uses_nested_platform_id(self) -> None:
        """A user-profile body nests id and postUrl under posts[].postIds."""

        nested_body: dict[str, object] = {
            "status": "success",
            "posts": [
                {
                    "status": "success",
                    "errors": [],
                    "postIds": [
                        {
                            "status": "success",
                            "id": PLATFORM_POST_ID,
                            "postUrl": PLATFORM_POST_URL,
                            "platform": "instagram",
                        },
                    ],
                    "id": AYRSHARE_OWN_POST_ID,
                },
            ],
        }
        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=nested_body),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )
        publish_result: PublishResult = adapter.publish_media(
            FIXED_POST_ID,
            _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
            [],
            "Harbor",
            [FIRST_MEDIA_URL],
        )

        self.assertEqual(publish_result.platform_post_id, PLATFORM_POST_ID)
        self.assertEqual(publish_result.platform_post_url, PLATFORM_POST_URL)

    def test_status_400_raises_and_hides_both_secrets(self) -> None:
        """A 400 uses the documented errors[].message and drops both keys."""

        vendor_message: str = (
            f"Instagram rejected {AYRSHARE_TEST_API_KEY} "
            f"for profile {AYRSHARE_TEST_PROFILE_KEY}."
        )
        error_body: dict[str, object] = {
            "status": "error",
            "errors": [
                {
                    "action": "post",
                    "status": "error",
                    "code": 156,
                    "message": vendor_message,
                    "platform": "instagram",
                },
            ],
            "postIds": [],
        }
        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(400, json=error_body),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with self.assertLogs(AYRSHARE_PUBLISH_LOGGER_NAME, level="INFO") as log_context:
            with self.assertRaises(PublishError) as raised:
                adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                    [],
                    "Harbor",
                    [FIRST_MEDIA_URL],
                )

        message: str = str(raised.exception)
        joined_log: str = "\n".join(log_context.output)

        self.assertIn("400", message)
        self.assertIn("Instagram rejected", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, joined_log)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, joined_log)
        self.assertIn("http_status=400", joined_log)

    def test_transport_error_raises_without_the_key(self) -> None:
        """A connection failure is PublishError and does not echo the key."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.ConnectError("connection refused"),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with self.assertRaises(PublishError) as raised:
            adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.TIKTOK, AYRSHARE_TEST_PROFILE_KEY),
                [],
                "Harbor",
                [FIRST_MEDIA_URL],
            )

        message: str = str(raised.exception)

        self.assertIn("transport error", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, message)

    def test_timeout_raises_without_the_key(self) -> None:
        """A timeout is PublishError and does not echo the key."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.TimeoutException("timed out"),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with self.assertRaises(PublishError) as raised:
            adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                [],
                "Harbor",
                [FIRST_MEDIA_URL],
            )

        message: str = str(raised.exception)

        self.assertIn("timed out", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, message)

    def test_missing_platform_entry_raises_without_the_key(self) -> None:
        """A success body for another platform is not a success for this one."""

        other_platform_body: dict[str, object] = {
            "status": "success",
            "postIds": [
                {
                    "status": "success",
                    "platform": "facebook",
                    "id": "facebook-id",
                    "postUrl": "https://example.invalid/facebook/p/1",
                },
            ],
            "id": AYRSHARE_OWN_POST_ID,
        }
        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=other_platform_body),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with self.assertRaises(PublishError) as raised:
            adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                [],
                "Harbor",
                [FIRST_MEDIA_URL],
            )

        message: str = str(raised.exception)

        self.assertIn("200", message)
        self.assertIn("no success entry for instagram", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, message)
        self.assertNotIn("facebook-id", message)

    def test_non_json_error_does_not_include_the_body_or_the_key(self) -> None:
        """A non-JSON 400 reports the status and not the raw body."""

        raw_body: str = f"<html>{AYRSHARE_TEST_API_KEY}</html>"
        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(400, text=raw_body),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with self.assertRaises(PublishError) as raised:
            adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                [],
                "Harbor",
                [FIRST_MEDIA_URL],
            )

        message: str = str(raised.exception)

        self.assertIn("400", message)
        self.assertIn("response was not JSON", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn("<html>", message)

    def test_two_png_paths_upload_then_post_in_frame_order(self) -> None:
        """Two local frames become two uploads and one post, in that order."""

        upload_urls: list[str] = [
            "https://images.ayrshare.com/frames/zero.png",
            "https://images.ayrshare.com/frames/one.png",
        ]
        transport: _UploadThenPostTransport = _UploadThenPostTransport(upload_urls)
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))

            with self.assertLogs(AYRSHARE_PUBLISH_LOGGER_NAME, level="INFO") as log_context:
                publish_result: PublishResult = adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                    media_paths,
                    "Harbor",
                )

        joined_log: str = "\n".join(log_context.output)
        post_request: httpx.Request = transport.requests[2]
        post_body: dict[str, object] = _request_json(post_request)

        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(str(transport.requests[0].url), AYRSHARE_MEDIA_UPLOAD_ENDPOINT)
        self.assertEqual(str(transport.requests[1].url), AYRSHARE_MEDIA_UPLOAD_ENDPOINT)
        self.assertEqual(str(post_request.url), AYRSHARE_POST_ENDPOINT)
        self.assertIn(b"frame-zero-bytes", transport.requests[0].content)
        self.assertIn(b"frame-one-bytes", transport.requests[1].content)
        self.assertIn(b'name="file"', transport.requests[0].content)
        self.assertIn(b'name="fileName"', transport.requests[0].content)
        self.assertIn(b"frame-0.png", transport.requests[0].content)
        self.assertIn(b"frame-1.png", transport.requests[1].content)
        self.assertTrue(
            transport.requests[0].headers["content-type"].startswith("multipart/form-data"),
        )
        self.assertEqual(
            transport.requests[0].headers["Authorization"],
            f"Bearer {AYRSHARE_TEST_API_KEY}",
        )
        self.assertEqual(
            transport.requests[0].headers[AYRSHARE_PROFILE_KEY_HEADER],
            AYRSHARE_TEST_PROFILE_KEY,
        )
        self.assertEqual(post_body["mediaUrls"], upload_urls)
        self.assertEqual(post_body["post"], "Harbor")
        self.assertEqual(post_body["platforms"], ["instagram"])
        self.assertEqual(publish_result.platform_post_id, PLATFORM_POST_ID)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, joined_log)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, joined_log)

    def test_publish_uploads_slide_files_before_the_post(self) -> None:
        """The post-job path uploads the same way as a campaign post."""

        upload_urls: list[str] = [
            "https://images.ayrshare.com/slides/zero.png",
            "https://images.ayrshare.com/slides/one.png",
        ]
        transport: _UploadThenPostTransport = _UploadThenPostTransport(upload_urls)
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))
            adapter.publish(
                _post_job(),
                _artifact("Slide name"),
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                media_paths,
            )

        post_body: dict[str, object] = _request_json(transport.requests[2])

        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(post_body["post"], "Slide name")
        self.assertEqual(post_body["mediaUrls"], upload_urls)
        self.assertEqual(
            transport.requests[0].headers[AYRSHARE_PROFILE_KEY_HEADER],
            AYRSHARE_TEST_PROFILE_KEY,
        )

    def test_failed_upload_does_not_post(self) -> None:
        """A refused upload raises and the post endpoint is not called."""

        vendor_message: str = f"Upload refused for {AYRSHARE_TEST_API_KEY}."
        transport: _UploadThenPostTransport = _UploadThenPostTransport(
            ["https://images.ayrshare.com/frames/zero.png"],
            fail_at_index=0,
            failure=httpx.Response(
                400,
                json={
                    "action": "request",
                    "status": "error",
                    "code": 101,
                    "message": vendor_message,
                },
            ),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))

            with self.assertRaises(PublishError) as raised:
                adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                    media_paths,
                    "Harbor",
                )

        post_requests: list[httpx.Request] = [
            request
            for request in transport.requests
            if str(request.url) == AYRSHARE_POST_ENDPOINT
        ]
        message: str = str(raised.exception)

        self.assertEqual(post_requests, [])
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(str(transport.requests[0].url), AYRSHARE_MEDIA_UPLOAD_ENDPOINT)
        self.assertIn("400", message)
        self.assertIn("Upload refused", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn(AYRSHARE_TEST_PROFILE_KEY, message)

    def test_second_upload_failure_does_not_post(self) -> None:
        """A later frame failure still skips the post."""

        transport: _UploadThenPostTransport = _UploadThenPostTransport(
            [
                "https://images.ayrshare.com/frames/zero.png",
                "https://images.ayrshare.com/frames/one.png",
            ],
            fail_at_index=1,
            failure=httpx.ConnectError("connection refused"),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))

            with self.assertRaises(PublishError) as raised:
                adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                    media_paths,
                    "Harbor",
                )

        post_requests: list[httpx.Request] = [
            request
            for request in transport.requests
            if str(request.url) == AYRSHARE_POST_ENDPOINT
        ]

        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(post_requests, [])
        self.assertIn("transport error", str(raised.exception))
        self.assertNotIn(AYRSHARE_TEST_API_KEY, str(raised.exception))

    def test_upload_without_a_url_does_not_post(self) -> None:
        """A 200 upload body with no url field is a failure."""

        transport: _UploadThenPostTransport = _UploadThenPostTransport(
            ["https://images.ayrshare.com/frames/zero.png"],
            fail_at_index=0,
            failure=httpx.Response(200, json={"id": "upload-id-only"}),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))

            with self.assertRaises(PublishError) as raised:
                adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                    media_paths[:1],
                    "Harbor",
                )

        self.assertEqual(len(transport.requests), 1)
        self.assertIn("no url", str(raised.exception))
        self.assertNotIn(AYRSHARE_TEST_API_KEY, str(raised.exception))

    def test_file_over_the_documented_cap_does_not_upload(self) -> None:
        """30 MB is the documented cap. A larger file never opens HTTP."""

        transport: _UploadThenPostTransport = _UploadThenPostTransport(
            ["https://images.ayrshare.com/frames/zero.png"],
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_path: Path = Path(raw_directory) / "frame-0.png"
            media_path.write_bytes(b"12345")

            with patch("app.publish.ayrshare.AYRSHARE_MEDIA_UPLOAD_MAX_BYTES", 4):
                with self.assertRaises(PublishError) as raised:
                    adapter.publish_media(
                        FIXED_POST_ID,
                        _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                        [media_path],
                        "Harbor",
                    )

        message: str = str(raised.exception)

        self.assertEqual(transport.requests, [])
        self.assertIn("30 MB", message)
        self.assertIn("5 bytes", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)

    def test_frame_file_route_requires_a_session(self) -> None:
        """GET of a frame PNG without a session cookie is 401."""

        previous_environment: str | None = os.environ.get("TWERVA_ENV")
        previous_secret: str | None = os.environ.get("SESSION_SECRET")
        previous_secure: str | None = os.environ.get("SESSION_COOKIE_SECURE")
        os.environ["TWERVA_ENV"] = "test"
        os.environ["SESSION_SECRET"] = "test-session-secret-not-for-production"
        os.environ["SESSION_COOKIE_SECURE"] = "false"
        clear_settings_cache()
        application: FastAPI = FastAPI()
        application.include_router(api_v1_router)

        def override_session() -> Generator[None, None, None]:

            yield None

        application.dependency_overrides[get_our_database_session] = override_session
        client: TestClient = TestClient(application)
        frame_url: str = (
            "/api/v1/carousels/11111111-1111-1111-1111-111111111111"
            "/assembly/frames/22222222-2222-2222-2222-222222222222/file"
        )

        try:
            frame_response = client.get(frame_url)
        finally:
            client.close()
            application.dependency_overrides.clear()

            if previous_environment is None:
                os.environ.pop("TWERVA_ENV", None)
            else:
                os.environ["TWERVA_ENV"] = previous_environment

            if previous_secret is None:
                os.environ.pop("SESSION_SECRET", None)
            else:
                os.environ["SESSION_SECRET"] = previous_secret

            if previous_secure is None:
                os.environ.pop("SESSION_COOKIE_SECURE", None)
            else:
                os.environ["SESSION_COOKIE_SECURE"] = previous_secure

            clear_settings_cache()

        self.assertEqual(frame_response.status_code, 401)

    def test_blank_profile_key_refuses_before_any_request(self) -> None:
        """A blank profile key raises before upload and before the post."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=_instagram_success_body()),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )
        expected_detail: str = (
            "This account has no Ayrshare profile key. "
            "Set external_account_id before publishing."
        )

        with tempfile.TemporaryDirectory() as raw_directory:
            media_paths: list[Path] = _write_two_frames(Path(raw_directory))

            with self.assertRaises(PublishError) as raised_blank:
                adapter.publish_media(
                    FIXED_POST_ID,
                    _account(Platform.INSTAGRAM, "   "),
                    media_paths,
                    "Harbor",
                    [FIRST_MEDIA_URL],
                )

            with self.assertRaises(PublishError) as raised_missing:
                adapter.publish(
                    _post_job(),
                    _artifact("Harbor"),
                    _account(Platform.INSTAGRAM, None),
                    media_paths,
                )

        self.assertEqual(transport.requests, [])
        self.assertEqual(str(raised_blank.exception), expected_detail)
        self.assertEqual(str(raised_missing.exception), expected_detail)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, str(raised_blank.exception))

    def test_mock_publish_media_ignores_caption_and_opens_no_client(self) -> None:
        """Mock still returns the fake id and does not take an HTTP client."""

        mock_adapter: MockPublishAdapter = MockPublishAdapter()
        publish_result: PublishResult = mock_adapter.publish_media(
            FIXED_POST_ID,
            _account(Platform.INSTAGRAM, None),
            [Path("/tmp/frame.png")],
            AYRSHARE_TEST_API_KEY,
            [FIRST_MEDIA_URL],
        )

        self.assertEqual(
            publish_result.platform_post_id,
            f"mock-instagram-{FIXED_POST_ID}",
        )
        self.assertEqual(
            publish_result.platform_post_url,
            f"https://example.invalid/instagram/p/{FIXED_POST_ID}",
        )


class _UploadThenPostTransport:
    """Mock transport: upload responses in order, then one post response."""

    def __init__(
        self,
        upload_urls: list[str],
        fail_at_index: int | None = None,
        failure: httpx.Response | Exception | None = None,
    ) -> None:

        self.requests: list[httpx.Request] = []
        self._upload_urls: list[str] = upload_urls
        self._fail_at_index: int | None = fail_at_index
        self._failure: httpx.Response | Exception | None = failure
        self._upload_index: int = 0

    def client(self) -> httpx.Client:
        """Build a client that cannot open a real socket."""

        recording_transport: _UploadThenPostTransport = self

        def handler(request: httpx.Request) -> httpx.Response:

            recording_transport.requests.append(request)
            request_url: str = str(request.url)

            if request_url == AYRSHARE_MEDIA_UPLOAD_ENDPOINT:
                upload_index: int = recording_transport._upload_index
                recording_transport._upload_index += 1

                if (
                    recording_transport._fail_at_index is not None
                    and upload_index == recording_transport._fail_at_index
                ):
                    return _fresh_or_raise(recording_transport._failure)

                upload_body: dict[str, object] = {
                    "id": f"upload-{upload_index}",
                    "url": recording_transport._upload_urls[upload_index],
                    "fileName": "frame.png",
                    "description": "",
                }

                return httpx.Response(200, json=upload_body)

            if request_url == AYRSHARE_POST_ENDPOINT:

                return httpx.Response(200, json=_instagram_success_body())

            raise AssertionError(f"unexpected Ayrshare URL {request_url}")

        mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
        http_client: httpx.Client = httpx.Client(transport=mock_transport)

        return http_client


def _fresh_or_raise(failure: httpx.Response | Exception | None) -> httpx.Response:
    """Return a copy of an error response, or raise the stored transport error."""

    if isinstance(failure, Exception):
        raise failure

    if isinstance(failure, httpx.Response):
        fresh_response: httpx.Response = httpx.Response(
            failure.status_code,
            content=failure.content,
            headers=failure.headers,
        )

        return fresh_response

    raise AssertionError("upload failure was not set")


def _write_two_frames(directory: Path) -> list[Path]:
    """Write two distinct PNG payloads in frame order."""

    first_path: Path = directory / "frame-0.png"
    second_path: Path = directory / "frame-1.png"
    first_path.write_bytes(b"frame-zero-bytes")
    second_path.write_bytes(b"frame-one-bytes")
    media_paths: list[Path] = [first_path, second_path]

    return media_paths


def _header_names(request: httpx.Request) -> set[str]:
    """Lower-case header names on one recorded request."""

    header_names: set[str] = {header_name.lower() for header_name in request.headers.keys()}

    return header_names


if __name__ == "__main__":
    unittest.main()
