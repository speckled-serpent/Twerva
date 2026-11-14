"""Ayrshare publish adapter.

``publish`` and ``publish_media`` POST to ``AYRSHARE_POST_ENDPOINT`` when
the caller supplies public media URLs. Local filesystem paths raise
``PublishError`` until an upload supplies those URLs. The API key and
the profile key are request headers and are not written to the log.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.models import Account, Artifact, PostJob
from app.publish.adapter import PublishAdapter, PublishResult
from app.publish.errors import PublishError


AYRSHARE_POST_ENDPOINT: str = "https://api.ayrshare.com/api/post"
AYRSHARE_PROFILE_KEY_HEADER: str = "Profile-Key"
AYRSHARE_HTTP_TIMEOUT_SECONDS: float = 30.0
AYRSHARE_SUCCESS_STATUS: str = "success"
AYRSHARE_PUBLISH_LOGGER_NAME: str = "app.publish.ayrshare"
AYRSHARE_VENDOR_MESSAGE_LIMIT: int = 200
PUBLISH_MEDIA_NOT_PUBLIC_DETAIL: str = "Publish media is not on a public URL yet."
AYRSHARE_TIMEOUT_DETAIL: str = "Ayrshare post failed: timed out."
AYRSHARE_TRANSPORT_ERROR_DETAIL: str = "Ayrshare post failed: transport error."


@dataclass(frozen=True)
class AyrsharePostRequest:
    """JSON body and headers for one Ayrshare post.

    ``body`` is ``post``, ``platforms``, and ``mediaUrls``. ``headers``
    carries the bearer API key and, when the account has one, the
    profile key. Neither secret belongs in a log line.
    """

    body: dict[str, object]
    headers: dict[str, str]


def build_ayrshare_post_request(
    api_key: str,
    caption: str,
    platform_name: str,
    media_urls: list[str],
    external_account_id: str | None,
) -> AyrsharePostRequest:
    """Build the post body and headers. This function does not send HTTP.

    Args:
        api_key: ``AYRSHARE_API_KEY``. Sent as a bearer token.
        caption: The ``post`` field. An empty string is allowed.
        platform_name: One platform, ``instagram`` or ``tiktok``.
        media_urls: Public media URLs, in caller order.
        external_account_id: Ayrshare profile key. Blank omits the header.

    Returns:
        The JSON body and the headers for one POST.
    """

    copied_media_urls: list[str] = list(media_urls)
    request_body: dict[str, object] = {
        "post": caption,
        "platforms": [platform_name],
        "mediaUrls": copied_media_urls,
    }
    request_headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
    }
    profile_key: str = _stripped_profile_key(external_account_id)

    if profile_key != "":
        request_headers[AYRSHARE_PROFILE_KEY_HEADER] = profile_key

    post_request: AyrsharePostRequest = AyrsharePostRequest(
        body=request_body,
        headers=request_headers,
    )

    return post_request


class AyrsharePublishAdapter(PublishAdapter):
    """Post one account's media through Ayrshare.

    The factory passes no client, so a normal ``httpx.Client`` is built
    on the first request. Tests pass ``httpx.Client(transport=MockTransport)``.
    The methods that talk HTTP use that stored client and no other.
    """

    def __init__(
        self,
        api_key: str,
        http_client: httpx.Client | None = None,
    ) -> None:

        self._api_key: str = api_key
        self._http_client: httpx.Client | None = http_client
        self._logger: logging.Logger = logging.getLogger(AYRSHARE_PUBLISH_LOGGER_NAME)

    def publish(
        self,
        post_job: PostJob,
        artifact: Artifact,
        account: Account,
        media_paths: list[Path],
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Post one post job. The caption is the artifact caption.

        A null caption is sent as an empty string. Filesystem paths are
        not turned into URLs.

        Args:
            post_job: Job being published.
            artifact: Supplies the caption.
            account: Target platform and optional profile key.
            media_paths: Local slide files. Unused when URLs are passed.
            media_urls: Public URLs in slide order, when the caller has them.

        Returns:
            The platform post id and permalink.

        Raises:
            PublishError: The media is still local, or Ayrshare refused.
        """

        caption_text: str = _caption_or_empty(artifact.caption)
        publish_result: PublishResult = self._publish_with_public_urls(
            post_job.id,
            account,
            media_paths,
            caption_text,
            media_urls,
        )

        return publish_result

    def publish_media(
        self,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        caption: str,
        media_urls: list[str] | None = None,
    ) -> PublishResult:
        """Post one campaign post. The caption is the argument.

        Filesystem paths are not turned into URLs.

        Args:
            post_id: Campaign post being published.
            account: Target platform and optional profile key.
            media_paths: Local frame files, in position order.
            caption: Caption sent as Ayrshare's ``post`` field.
            media_urls: Public URLs in frame order, when the caller has them.

        Returns:
            The platform post id and permalink.

        Raises:
            PublishError: The media is still local, or Ayrshare refused.
        """

        publish_result: PublishResult = self._publish_with_public_urls(
            post_id,
            account,
            media_paths,
            caption,
            media_urls,
        )

        return publish_result

    def _publish_with_public_urls(
        self,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        caption: str,
        media_urls: list[str] | None,
    ) -> PublishResult:
        """POST once when URLs were supplied. Paths alone never open HTTP."""

        resolved_media_urls: list[str] = _media_urls_or_refuse(media_paths, media_urls)
        platform_name: str = account.platform.value
        post_request: AyrsharePostRequest = build_ayrshare_post_request(
            self._api_key,
            caption,
            platform_name,
            resolved_media_urls,
            account.external_account_id,
        )
        http_client: httpx.Client
        close_after_request: bool
        http_client, close_after_request = self._http_client_for_request()
        post_identifier: str = str(post_id)
        media_count: int = len(resolved_media_urls)
        response: httpx.Response

        try:
            response = http_client.post(
                AYRSHARE_POST_ENDPOINT,
                json=post_request.body,
                headers=post_request.headers,
                timeout=AYRSHARE_HTTP_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as timeout_error:
            self._log_attempt(post_identifier, platform_name, "none", media_count)

            raise PublishError(AYRSHARE_TIMEOUT_DETAIL) from timeout_error
        except httpx.HTTPError as transport_error:
            self._log_attempt(post_identifier, platform_name, "none", media_count)

            raise PublishError(AYRSHARE_TRANSPORT_ERROR_DETAIL) from transport_error
        finally:

            if close_after_request:
                http_client.close()

        http_status: str = str(response.status_code)
        self._log_attempt(post_identifier, platform_name, http_status, media_count)
        profile_key: str = _stripped_profile_key(account.external_account_id)
        publish_result: PublishResult = _publish_result_from_response(
            response,
            platform_name,
            self._api_key,
            profile_key,
        )

        return publish_result

    def _http_client_for_request(self) -> tuple[httpx.Client, bool]:
        """Return the stored client, or a new one this call will close."""

        if self._http_client is not None:

            return self._http_client, False

        owned_client: httpx.Client = httpx.Client(timeout=AYRSHARE_HTTP_TIMEOUT_SECONDS)

        return owned_client, True

    def _log_attempt(
        self,
        post_identifier: str,
        platform_name: str,
        http_status: str,
        media_count: int,
    ) -> None:
        """Log the post id, platform, status, and media count. No secrets."""

        self._logger.info(
            "AyrsharePublishAdapter post=%s platform=%s http_status=%s media_count=%s",
            post_identifier,
            platform_name,
            http_status,
            media_count,
        )


def _caption_or_empty(caption: str | None) -> str:
    """Return the artifact caption, or an empty string when it is null."""

    if caption is None:

        return ""

    return caption


def _stripped_profile_key(external_account_id: str | None) -> str:
    """Return the profile key, or an empty string when it is blank."""

    if external_account_id is None:

        return ""

    return external_account_id.strip()


def _media_urls_or_refuse(
    media_paths: list[Path],
    media_urls: list[str] | None,
) -> list[str]:
    """Return the caller URLs. Local paths with no URLs refuse before HTTP."""

    has_filesystem_paths: bool = len(media_paths) > 0
    has_media_urls: bool = media_urls is not None and len(media_urls) > 0

    if has_filesystem_paths and not has_media_urls:
        raise PublishError(PUBLISH_MEDIA_NOT_PUBLIC_DETAIL)

    if media_urls is None:

        return []

    copied_media_urls: list[str] = list(media_urls)

    return copied_media_urls


def _publish_result_from_response(
    response: httpx.Response,
    platform_name: str,
    api_key: str,
    profile_key: str,
) -> PublishResult:
    """Read the platform id and postUrl, or raise PublishError."""

    parsed_body: object | None = _parsed_json_body(response)
    vendor_message: str | None = None

    if parsed_body is not None:
        vendor_message = _first_vendor_message(parsed_body)
    elif response.status_code >= 400:
        vendor_message = "response was not JSON"

    if response.status_code >= 400:
        raise PublishError(
            _http_failure_message(
                response.status_code,
                vendor_message,
                api_key,
                profile_key,
            ),
        )

    if parsed_body is None:
        raise PublishError(
            _http_failure_message(
                response.status_code,
                "response was not JSON",
                api_key,
                profile_key,
            ),
        )

    success_entry: dict[str, object] | None = _platform_success_entry(
        parsed_body,
        platform_name,
    )

    if success_entry is None:
        missing_detail: str = f"no success entry for {platform_name}"

        if vendor_message is not None:
            missing_detail = f"{missing_detail}. {vendor_message}"

        raise PublishError(
            _http_failure_message(
                response.status_code,
                missing_detail,
                api_key,
                profile_key,
            ),
        )

    platform_post_id: str | None = _entry_identifier(success_entry)
    platform_post_url: str | None = _entry_post_url(success_entry)

    if platform_post_id is None or platform_post_url is None:
        incomplete_detail: str = (
            f"{platform_name} success entry is missing id or postUrl"
        )

        raise PublishError(
            _http_failure_message(
                response.status_code,
                incomplete_detail,
                api_key,
                profile_key,
            ),
        )

    publish_result: PublishResult = PublishResult(
        platform_post_id=platform_post_id,
        platform_post_url=platform_post_url,
    )

    return publish_result


def _parsed_json_body(response: httpx.Response) -> object | None:
    """Return the JSON body, or None when the body is not JSON."""

    try:
        parsed_body: object = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):

        return None

    return parsed_body


def _platform_success_entry(
    response_body: object,
    platform_name: str,
) -> dict[str, object] | None:
    """Find the postIds entry whose platform succeeded.

    Ayrshare puts ``id`` and ``postUrl`` on each ``postIds`` object.
    A user-profile response nests that same array under ``posts``.
    The top-level ``id`` is Ayrshare's own post id and is not used.
    """

    entries: list[dict[str, object]] = []
    _collect_post_id_entries(response_body, entries)

    for entry in entries:
        entry_platform: object = entry.get("platform")
        entry_status: object = entry.get("status")

        if entry_platform != platform_name:
            continue

        if entry_status != AYRSHARE_SUCCESS_STATUS:
            continue

        return entry

    return None


def _collect_post_id_entries(body: object, found: list[dict[str, object]]) -> None:
    """Append postIds objects from this body and from nested posts."""

    if not isinstance(body, dict):

        return

    post_ids: object = body.get("postIds")

    if isinstance(post_ids, list):

        for entry in post_ids:

            if isinstance(entry, dict):
                found.append(entry)

    nested_posts: object = body.get("posts")

    if isinstance(nested_posts, list):

        for nested_post in nested_posts:
            _collect_post_id_entries(nested_post, found)


def _entry_identifier(entry: dict[str, object]) -> str | None:
    """Return the platform post id. A boolean is not an id."""

    raw_identifier: object = entry.get("id")

    if isinstance(raw_identifier, str):
        stripped_identifier: str = raw_identifier.strip()

        if stripped_identifier == "":

            return None

        return raw_identifier

    if isinstance(raw_identifier, bool):

        return None

    if isinstance(raw_identifier, int):

        return str(raw_identifier)

    return None


def _entry_post_url(entry: dict[str, object]) -> str | None:
    """Return postUrl when it is a non-empty string."""

    raw_post_url: object = entry.get("postUrl")

    if not isinstance(raw_post_url, str):

        return None

    if raw_post_url.strip() == "":

        return None

    return raw_post_url


def _first_vendor_message(body: object) -> str | None:
    """Return the first documented ``errors[].message``, if one exists."""

    messages: list[str] = []
    _collect_vendor_messages(body, messages)

    if len(messages) == 0:

        return None

    return messages[0]


def _collect_vendor_messages(body: object, found: list[str]) -> None:
    """Collect ``errors[].message`` and a top-level ``message`` string."""

    if not isinstance(body, dict):

        return

    errors: object = body.get("errors")

    if isinstance(errors, list):

        for error_entry in errors:

            if not isinstance(error_entry, dict):
                continue

            error_message: object = error_entry.get("message")

            if isinstance(error_message, str) and error_message.strip() != "":
                found.append(error_message.strip())

    nested_posts: object = body.get("posts")

    if isinstance(nested_posts, list):

        for nested_post in nested_posts:
            _collect_vendor_messages(nested_post, found)

    if len(found) > 0:

        return

    top_level_message: object = body.get("message")

    if isinstance(top_level_message, str) and top_level_message.strip() != "":
        found.append(top_level_message.strip())


def _http_failure_message(
    http_status: int,
    detail: str | None,
    api_key: str,
    profile_key: str,
) -> str:
    """HTTP status plus a short detail. Secrets are removed."""

    if detail is None or detail.strip() == "":
        message: str = f"Ayrshare post failed with HTTP {http_status}."
    else:
        redacted_detail: str = _redact_secrets(detail, api_key, profile_key)
        short_detail: str = _short_detail(redacted_detail)
        message = f"Ayrshare post failed with HTTP {http_status}: {short_detail}"

    redacted_message: str = _redact_secrets(message, api_key, profile_key)

    return redacted_message


def _short_detail(detail: str) -> str:
    """Collapse whitespace and keep the vendor sentence short."""

    words: list[str] = detail.split()
    collapsed: str = " ".join(words)

    if len(collapsed) <= AYRSHARE_VENDOR_MESSAGE_LIMIT:

        return collapsed

    return collapsed[:AYRSHARE_VENDOR_MESSAGE_LIMIT]


def _redact_secrets(message: str, api_key: str, profile_key: str) -> str:
    """Remove the API key and the profile key from an error sentence."""

    redacted: str = message

    if api_key != "":
        redacted = redacted.replace(api_key, "[redacted]")

    if profile_key != "" and profile_key != api_key:
        redacted = redacted.replace(profile_key, "[redacted]")

    return redacted
