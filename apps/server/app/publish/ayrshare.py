"""Ayrshare publish adapter.

``publish`` and ``publish_media`` upload each local file, then POST the
returned URLs to ``AYRSHARE_POST_ENDPOINT``. The API key and the profile
key are request headers and are not written to the log.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.models import Account, Artifact, PostJob
from app.publish.adapter import ConnectionCheck, PublishAdapter, PublishResult
from app.publish.errors import PublishError


AYRSHARE_POST_ENDPOINT: str = "https://api.ayrshare.com/api/post"
AYRSHARE_USER_ENDPOINT: str = "https://api.ayrshare.com/api/user"
AYRSHARE_MEDIA_UPLOAD_ENDPOINT: str = "https://api.ayrshare.com/api/media/upload"
AYRSHARE_MEDIA_UPLOAD_FILE_FIELD: str = "file"
AYRSHARE_MEDIA_UPLOAD_FILE_NAME_FIELD: str = "fileName"
AYRSHARE_MEDIA_UPLOAD_URL_FIELD: str = "url"
AYRSHARE_PROFILE_KEY_HEADER: str = "Profile-Key"
AYRSHARE_HTTP_TIMEOUT_SECONDS: float = 30.0
# The upload page does not name an HTTP timeout.
AYRSHARE_MEDIA_UPLOAD_TIMEOUT_SECONDS: float = 60.0
# Docs say "Maximum file size: 30 MB" and do not give a byte count.
AYRSHARE_MEDIA_UPLOAD_MAX_BYTES: int = 30 * 1024 * 1024
AYRSHARE_MEDIA_UPLOAD_MAX_LABEL: str = "30 MB"
AYRSHARE_SUCCESS_STATUS: str = "success"
AYRSHARE_PUBLISH_LOGGER_NAME: str = "app.publish.ayrshare"
AYRSHARE_VENDOR_MESSAGE_LIMIT: int = 200
AYRSHARE_TIMEOUT_DETAIL: str = "Ayrshare post failed: timed out."
AYRSHARE_TRANSPORT_ERROR_DETAIL: str = "Ayrshare post failed: transport error."
AYRSHARE_UPLOAD_TIMEOUT_DETAIL: str = "Ayrshare media upload failed: timed out."
AYRSHARE_UPLOAD_TRANSPORT_ERROR_DETAIL: str = "Ayrshare media upload failed: transport error."
AYRSHARE_PROFILE_KEY_REQUIRED_DETAIL: str = (
    "This account has no Ayrshare profile key. "
    "Set external_account_id before publishing."
)
# Instagram carousel: up to 10 images or videos.
# https://www.ayrshare.com/docs/apis/post/social-networks/instagram
AYRSHARE_INSTAGRAM_MEDIA_CAP: int = 10
# TikTok photo post: up to 35 images. No extra cap is invented beyond that.
# https://www.ayrshare.com/docs/apis/post/social-networks/tiktok
AYRSHARE_TIKTOK_MEDIA_CAP: int = 35
# Post docs name this body field. The value is the Twerva post id.
AYRSHARE_IDEMPOTENCY_KEY_FIELD: str = "idempotencyKey"
# TikTok's async id. The field is postIds[].id. postUrl is often absent.
AYRSHARE_TIKTOK_PENDING_ID: str = "pending"


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
    idempotency_key: str,
) -> AyrsharePostRequest:
    """Build the post body and headers. This function does not send HTTP.

    Args:
        api_key: ``AYRSHARE_API_KEY``. Sent as a bearer token.
        caption: The ``post`` field. An empty string is allowed.
        platform_name: One platform, ``instagram`` or ``tiktok``.
        media_urls: Public media URLs, in caller order.
        external_account_id: Ayrshare profile key. Blank omits the header.
        idempotency_key: Stable id for this post. Ayrshare names the field
            ``idempotencyKey``.

    Returns:
        The JSON body and the headers for one POST.
    """

    copied_media_urls: list[str] = list(media_urls)
    request_body: dict[str, object] = {
        "post": caption,
        "platforms": [platform_name],
        "mediaUrls": copied_media_urls,
        AYRSHARE_IDEMPOTENCY_KEY_FIELD: idempotency_key,
    }
    request_headers: dict[str, str] = build_ayrshare_auth_headers(
        api_key,
        external_account_id,
    )
    post_request: AyrsharePostRequest = AyrsharePostRequest(
        body=request_body,
        headers=request_headers,
    )

    return post_request


def build_ayrshare_auth_headers(
    api_key: str,
    external_account_id: str | None,
) -> dict[str, str]:
    """Bearer key, plus Profile-Key when the account has one.

    The post page documents ``Profile-Key``. The media upload page
    documents ``Authorization`` only and does not name ``Profile-Key``.
    A user-profile call still sends it, the same header as the post, so
    the upload and the post name the same profile.

    Args:
        api_key: ``AYRSHARE_API_KEY``.
        external_account_id: Profile key. Blank omits the header.

    Returns:
        Headers for one Ayrshare request. No ``Content-Type``; the
        caller sets JSON or lets httpx set the multipart boundary.
    """

    request_headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
    }
    profile_key: str = _stripped_profile_key(external_account_id)

    if profile_key != "":
        request_headers[AYRSHARE_PROFILE_KEY_HEADER] = profile_key

    return request_headers


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

        A null caption is sent as an empty string. Each local file is
        uploaded first. ``media_urls`` is used only when there are no paths.

        Args:
            post_job: Job being published.
            artifact: Supplies the caption.
            account: Target platform and optional profile key.
            media_paths: Local slide files, uploaded in order.
            media_urls: Public URLs when the caller already has them.

        Returns:
            The platform post id and permalink.

        Raises:
            PublishError: An upload or the post was refused.
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

        Each local frame is uploaded first, in position order.

        Args:
            post_id: Campaign post being published.
            account: Target platform and optional profile key.
            media_paths: Local frame files, uploaded in position order.
            caption: Caption sent as Ayrshare's ``post`` field.
            media_urls: Public URLs when the caller already has them.

        Returns:
            The platform post id and permalink.

        Raises:
            PublishError: An upload or the post was refused.
        """

        publish_result: PublishResult = self._publish_with_public_urls(
            post_id,
            account,
            media_paths,
            caption,
            media_urls,
        )

        return publish_result

    def check_connection(self, account: Account) -> ConnectionCheck:
        """GET the Ayrshare user profile. Do not post.

        The path is ``GET /api/user``. ``activeSocialAccounts`` lists the
        connected platforms. ``Profile-Key`` is sent when the account has one.

        Args:
            account: Supplies the optional profile key.

        Returns:
            ``ok`` true and a sentence naming the connected platforms.

        Raises:
            PublishError: The call failed. The message has no API key or profile key.
        """

        request_headers: dict[str, str] = build_ayrshare_auth_headers(
            self._api_key,
            account.external_account_id,
        )
        http_client: httpx.Client
        close_after_request: bool
        http_client, close_after_request = self._http_client_for_request()
        response: httpx.Response
        profile_key: str = _stripped_profile_key(account.external_account_id)

        try:
            try:
                response = http_client.get(
                    AYRSHARE_USER_ENDPOINT,
                    headers=request_headers,
                    timeout=AYRSHARE_HTTP_TIMEOUT_SECONDS,
                )
            except httpx.TimeoutException as timeout_error:
                raise PublishError(AYRSHARE_TIMEOUT_DETAIL) from timeout_error
            except httpx.HTTPError as transport_error:
                raise PublishError(AYRSHARE_TRANSPORT_ERROR_DETAIL) from transport_error
        finally:

            if close_after_request:
                http_client.close()

        self._logger.info(
            "AyrsharePublishAdapter connection account=%s http_status=%s",
            str(account.id),
            response.status_code,
        )
        connection_check: ConnectionCheck = _connection_check_from_response(
            response,
            self._api_key,
            profile_key,
        )

        return connection_check

    def _publish_with_public_urls(
        self,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        caption: str,
        media_urls: list[str] | None,
    ) -> PublishResult:
        """Upload local files, then POST once. One upload failure skips the post."""

        profile_key: str = _stripped_profile_key(account.external_account_id)

        if profile_key == "":
            raise PublishError(AYRSHARE_PROFILE_KEY_REQUIRED_DETAIL)

        media_count_for_cap: int = len(media_paths)

        if media_count_for_cap == 0 and media_urls is not None:
            media_count_for_cap = len(media_urls)

        _raise_if_media_count_exceeds_platform_cap(
            account.platform.value,
            media_count_for_cap,
        )

        http_client: httpx.Client
        close_after_request: bool
        http_client, close_after_request = self._http_client_for_request()

        try:
            resolved_media_urls: list[str] = self._media_urls_for_publish(
                http_client,
                post_id,
                account,
                media_paths,
                media_urls,
            )
            publish_result: PublishResult = self._post_to_ayrshare(
                http_client,
                post_id,
                account,
                caption,
                resolved_media_urls,
            )
        finally:

            if close_after_request:
                http_client.close()

        return publish_result

    def _media_urls_for_publish(
        self,
        http_client: httpx.Client,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
        media_urls: list[str] | None,
    ) -> list[str]:
        """Upload path bytes, or use URLs the caller already supplied."""

        if len(media_paths) > 0:
            uploaded_urls: list[str] = self._upload_frame_files(
                http_client,
                post_id,
                account,
                media_paths,
            )

            return uploaded_urls

        if media_urls is None:

            return []

        copied_media_urls: list[str] = list(media_urls)

        return copied_media_urls

    def _upload_frame_files(
        self,
        http_client: httpx.Client,
        post_id: uuid.UUID,
        account: Account,
        media_paths: list[Path],
    ) -> list[str]:
        """Upload each file in order. Stop before the post on the first failure."""

        uploaded_urls: list[str] = []

        for media_index, media_path in enumerate(media_paths):
            uploaded_url: str = self._upload_one_file(
                http_client,
                post_id,
                account,
                media_path,
                media_index,
            )
            uploaded_urls.append(uploaded_url)

        return uploaded_urls

    def _upload_one_file(
        self,
        http_client: httpx.Client,
        post_id: uuid.UUID,
        account: Account,
        media_path: Path,
        media_index: int,
    ) -> str:
        """POST one file as multipart field ``file`` and return its URL."""

        _require_uploadable_file(media_path)
        file_name: str = media_path.name
        file_bytes: bytes = media_path.read_bytes()
        content_type: str = _media_content_type(media_path)
        file_payload: tuple[str, bytes, str] = (file_name, file_bytes, content_type)
        request_headers: dict[str, str] = build_ayrshare_auth_headers(
            self._api_key,
            account.external_account_id,
        )
        form_fields: dict[str, str] = {
            AYRSHARE_MEDIA_UPLOAD_FILE_NAME_FIELD: file_name,
        }
        files: dict[str, tuple[str, bytes, str]] = {
            AYRSHARE_MEDIA_UPLOAD_FILE_FIELD: file_payload,
        }
        post_identifier: str = str(post_id)
        response: httpx.Response

        try:
            response = http_client.post(
                AYRSHARE_MEDIA_UPLOAD_ENDPOINT,
                headers=request_headers,
                data=form_fields,
                files=files,
                timeout=AYRSHARE_MEDIA_UPLOAD_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as timeout_error:
            self._log_upload(post_identifier, media_index, "none")

            raise PublishError(AYRSHARE_UPLOAD_TIMEOUT_DETAIL) from timeout_error
        except httpx.HTTPError as transport_error:
            self._log_upload(post_identifier, media_index, "none")

            raise PublishError(AYRSHARE_UPLOAD_TRANSPORT_ERROR_DETAIL) from transport_error

        http_status: str = str(response.status_code)
        self._log_upload(post_identifier, media_index, http_status)
        profile_key: str = _stripped_profile_key(account.external_account_id)
        uploaded_url: str = _upload_url_from_response(
            response,
            self._api_key,
            profile_key,
        )

        return uploaded_url

    def _post_to_ayrshare(
        self,
        http_client: httpx.Client,
        post_id: uuid.UUID,
        account: Account,
        caption: str,
        media_urls: list[str],
    ) -> PublishResult:
        """POST the caption and the uploaded URLs. Does not close the client."""

        platform_name: str = account.platform.value
        post_request: AyrsharePostRequest = build_ayrshare_post_request(
            self._api_key,
            caption,
            platform_name,
            media_urls,
            account.external_account_id,
            str(post_id),
        )
        post_identifier: str = str(post_id)
        media_count: int = len(media_urls)
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

        owned_client: httpx.Client = httpx.Client(
            timeout=AYRSHARE_MEDIA_UPLOAD_TIMEOUT_SECONDS,
        )

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

    def _log_upload(self, post_identifier: str, media_index: int, http_status: str) -> None:
        """Log one upload. The line has no API key, profile key, or file bytes."""

        self._logger.info(
            "AyrsharePublishAdapter upload post=%s index=%s http_status=%s",
            post_identifier,
            media_index,
            http_status,
        )


def _connection_check_from_response(
    response: httpx.Response,
    api_key: str,
    profile_key: str,
) -> ConnectionCheck:
    """Read connected platforms, or raise PublishError."""

    parsed_body: object | None = _parsed_json_body(response)
    vendor_message: str | None = None

    if parsed_body is not None:
        vendor_message = _first_vendor_message(parsed_body)
    elif response.status_code >= 400:
        vendor_message = "response was not JSON"

    if response.status_code >= 400 or not isinstance(parsed_body, dict):
        failure_detail: str | None = vendor_message

        if failure_detail is None:
            failure_detail = "response was not JSON"

        raise PublishError(
            _http_failure_message(
                response.status_code,
                failure_detail,
                api_key,
                profile_key,
                "connection check",
            ),
        )

    connected_platforms: list[str] = _connected_platform_names(parsed_body)
    detail: str = _connected_platforms_sentence(connected_platforms)
    redacted_detail: str = _redact_secrets(detail, api_key, profile_key)
    connection_check: ConnectionCheck = ConnectionCheck(
        adapter="ayrshare",
        ok=True,
        detail=redacted_detail,
    )

    return connection_check


def _connected_platform_names(body: dict[str, object]) -> list[str]:
    """Return platform names from ``activeSocialAccounts`` or ``displayNames``."""

    active_accounts: object = body.get("activeSocialAccounts")
    platform_names: list[str] = []

    if isinstance(active_accounts, list):

        for platform_name in active_accounts:

            if isinstance(platform_name, str) and platform_name.strip() != "":
                platform_names.append(platform_name.strip())

        if len(platform_names) > 0:

            return platform_names

    display_names: object = body.get("displayNames")

    if isinstance(display_names, list):

        for display_entry in display_names:

            if not isinstance(display_entry, dict):
                continue

            platform_value: object = display_entry.get("platform")

            if isinstance(platform_value, str) and platform_value.strip() != "":
                platform_names.append(platform_value.strip())

    return platform_names


def _connected_platforms_sentence(platform_names: list[str]) -> str:
    """Name the connected platforms, without handles or secrets."""

    if len(platform_names) == 0:

        return "No social accounts are linked."

    joined_platforms: str = ", ".join(platform_names)

    return f"Connected platforms: {joined_platforms}."


def _raise_if_media_count_exceeds_platform_cap(
    platform_name: str,
    media_count: int,
) -> None:
    """Refuse before HTTP when the documented image cap is exceeded.

    Frames are not dropped to fit the cap. TikTok's documented photo
    cap is 35. A count at or under the cap continues.
    """

    media_cap: int | None = None

    if platform_name == "instagram":
        media_cap = AYRSHARE_INSTAGRAM_MEDIA_CAP
    elif platform_name == "tiktok":
        media_cap = AYRSHARE_TIKTOK_MEDIA_CAP

    if media_cap is None or media_count <= media_cap:

        return

    raise PublishError(
        (
            f"Ayrshare accepts at most {media_cap} {platform_name} files. "
            f"This post has {media_count}."
        ),
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


def _require_uploadable_file(media_path: Path) -> None:
    """Refuse a missing file or one over the documented 30 MB cap.

    Uploaded files stay fetchable for 90 days. That retention is not
    checked here. This phase posts immediately and does not schedule.
    """

    if not media_path.is_file():
        raise PublishError(f"Ayrshare media upload cannot read {media_path.name}.")

    file_size: int = media_path.stat().st_size

    if file_size > AYRSHARE_MEDIA_UPLOAD_MAX_BYTES:
        raise PublishError(
            (
                "Ayrshare media upload accepts at most "
                f"{AYRSHARE_MEDIA_UPLOAD_MAX_LABEL} "
                f"({AYRSHARE_MEDIA_UPLOAD_MAX_BYTES} bytes). "
                f"{media_path.name} is {file_size} bytes."
            ),
        )


def _media_content_type(media_path: Path) -> str:
    """Return a part type for the multipart file. Frames are PNG."""

    suffix: str = media_path.suffix.lower()

    if suffix == ".png":

        return "image/png"

    if suffix == ".jpg" or suffix == ".jpeg":

        return "image/jpeg"

    return "application/octet-stream"


def _upload_url_from_response(
    response: httpx.Response,
    api_key: str,
    profile_key: str,
) -> str:
    """Read the documented ``url`` field, or raise PublishError."""

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
                "media upload",
            ),
        )

    if not isinstance(parsed_body, dict):
        raise PublishError(
            _http_failure_message(
                response.status_code,
                "response has no url",
                api_key,
                profile_key,
                "media upload",
            ),
        )

    raw_url: object = parsed_body.get(AYRSHARE_MEDIA_UPLOAD_URL_FIELD)

    if not isinstance(raw_url, str) or raw_url.strip() == "":
        raise PublishError(
            _http_failure_message(
                response.status_code,
                "response has no url",
                api_key,
                profile_key,
                "media upload",
            ),
        )

    return raw_url


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

    if isinstance(parsed_body, dict) and parsed_body.get("status") == "error":
        raise PublishError(
            _http_failure_message(
                response.status_code,
                vendor_message,
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

    if platform_post_id is None:
        incomplete_detail: str = f"{platform_name} success entry is missing id"

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
    action: str = "post",
) -> str:
    """HTTP status plus a short detail. Secrets are removed."""

    if detail is None or detail.strip() == "":
        message: str = f"Ayrshare {action} failed with HTTP {http_status}."
    else:
        redacted_detail: str = _redact_secrets(detail, api_key, profile_key)
        short_detail: str = _short_detail(redacted_detail)
        message = f"Ayrshare {action} failed with HTTP {http_status}: {short_detail}"

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
