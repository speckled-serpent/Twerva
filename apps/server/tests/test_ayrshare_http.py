"""Ayrshare post HTTP with a mock transport. No socket to api.ayrshare.com."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path

import httpx

from app.models import Account, Artifact, PostJob
from app.models.enums import AccountStatus, ArtifactStatus, Platform, PostJobStatus
from app.publish.adapter import PublishResult
from app.publish.ayrshare import (
    AYRSHARE_POST_ENDPOINT,
    AYRSHARE_PROFILE_KEY_HEADER,
    AYRSHARE_PUBLISH_LOGGER_NAME,
    AyrsharePublishAdapter,
)
from app.publish.errors import PublishError
from app.publish.mock import MockPublishAdapter


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
        account: Account = _account(Platform.INSTAGRAM, None)

        adapter.publish(
            _post_job(),
            _artifact(None),
            account,
            [],
            media_urls,
        )
        empty_body: dict[str, object] = _request_json(transport.requests[0])

        self.assertEqual(empty_body["post"], "")
        self.assertNotIn(AYRSHARE_PROFILE_KEY_HEADER.lower(), _header_names(transport.requests[0]))

        adapter.publish(
            _post_job(),
            _artifact("Slide name"),
            account,
            [Path("/tmp/local-frame.png")],
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
                _account(Platform.INSTAGRAM, None),
                [],
                "Harbor",
                [FIRST_MEDIA_URL],
            )

        message: str = str(raised.exception)

        self.assertIn("400", message)
        self.assertIn("response was not JSON", message)
        self.assertNotIn(AYRSHARE_TEST_API_KEY, message)
        self.assertNotIn("<html>", message)

    def test_filesystem_paths_without_urls_do_not_call_http(self) -> None:
        """Local frames raise the public-URL detail and send no request."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=_instagram_success_body()),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )
        media_paths: list[Path] = [Path("/tmp/frame-one.png"), Path("/tmp/frame-two.png")]

        with self.assertRaises(PublishError) as raised_media:
            adapter.publish_media(
                FIXED_POST_ID,
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                media_paths,
                "Harbor",
            )

        with self.assertRaises(PublishError) as raised_publish:
            adapter.publish(
                _post_job(),
                _artifact("Harbor"),
                _account(Platform.INSTAGRAM, AYRSHARE_TEST_PROFILE_KEY),
                media_paths,
            )

        self.assertEqual(transport.requests, [])
        self.assertEqual(
            str(raised_media.exception),
            "Publish media is not on a public URL yet.",
        )
        self.assertEqual(
            str(raised_publish.exception),
            "Publish media is not on a public URL yet.",
        )
        self.assertNotIn(AYRSHARE_TEST_API_KEY, str(raised_media.exception))

    def test_blank_profile_key_omits_the_header(self) -> None:
        """A whitespace profile key is not sent. Task 10.4 refuses it later."""

        transport: _RecordingTransport = _RecordingTransport(
            httpx.Response(200, json=_instagram_success_body()),
        )
        adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
            AYRSHARE_TEST_API_KEY,
            transport.client(),
        )

        adapter.publish_media(
            FIXED_POST_ID,
            _account(Platform.INSTAGRAM, "   "),
            [],
            "",
            [FIRST_MEDIA_URL],
        )
        header_names: set[str] = _header_names(transport.requests[0])
        request_body: dict[str, object] = _request_json(transport.requests[0])

        self.assertNotIn(AYRSHARE_PROFILE_KEY_HEADER.lower(), header_names)
        self.assertEqual(request_body["post"], "")
        self.assertEqual(request_body["platforms"], ["instagram"])

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


def _header_names(request: httpx.Request) -> set[str]:
    """Lower-case header names on one recorded request."""

    header_names: set[str] = {header_name.lower() for header_name in request.headers.keys()}

    return header_names


if __name__ == "__main__":
    unittest.main()
