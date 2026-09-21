"""HTTP client for the locked Spotmu public ingest path (1.3a / 1.3b / 1.3d).

Locked origin: ``https://spotmu.com`` (``SPOTMU_API_BASE_URL``).
Interest JSON: ``GET {origin}/api/v1/interests/slug/{slug}``.
Discovery: ``GET {origin}/sitemap.xml``.

This module does not import settings or the database so fetch-only use
stays independent of ``DATABASE_URL``.
"""

from __future__ import annotations

import json
import os
from urllib.parse import ParseResult, urlencode, urlparse
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


DEFAULT_SPOTMU_API_BASE_URL: str = "https://spotmu.com"
DEFAULT_HTTP_TIMEOUT_SECONDS: float = 15.0
DEFAULT_SITEMAP_SLUG_LIMIT: int = 20
MAXIMUM_SITEMAP_SLUG_LIMIT: int = 200
INTEREST_BY_SLUG_PATH_PREFIX: str = "/api/v1/interests/slug/"
INTEREST_SEARCH_PATH: str = "/api/v1/interests/search"
SITEMAP_PATH: str = "/sitemap.xml"
PUBLIC_INTEREST_PATH_PREFIX: str = "/interest/"
JSON_CONTENT_TYPE_NEEDLE: str = "json"
SPOTMU_API_BASE_URL_ENVIRONMENT_NAME: str = "SPOTMU_API_BASE_URL"
DEFAULT_INTEREST_SEARCH_LIMIT: int = 10
MAXIMUM_INTEREST_SEARCH_LIMIT: int = 20


class SpotmuInterestNotFoundError(Exception):
    """Spotmu returned HTTP 404 for an interest slug."""


class SpotmuInterestNotJsonError(Exception):
    """Spotmu returned a non-JSON body where public JSON was required."""


class SpotmuInterestTimeoutError(Exception):
    """The Spotmu HTTP call exceeded the timeout."""


class SpotmuInterestRequestError(Exception):
    """Spotmu returned an unexpected status or the payload failed validation."""


class SpotmuPublicInterestPayload(BaseModel):
    """Live public interest page JSON (spike 2026-09-15).

    Extra fields are kept so ``raw_payload`` can round-trip forward-compat
    keys (teasers, categories, overview_text, …).
    """

    model_config = ConfigDict(extra="allow")

    interest_hash_id: str
    slug: str
    title: str
    interest_heading: str | None = None
    overview_summary: str | None = None
    overview_bullets: str | list[str] | None = None
    overview_text: str | None = None
    overview_created_at: str | None = None
    last_updated: str | None = None
    serve_story_count: int | None = None
    categories: list[str] = Field(default_factory=list)
    teasers: list[object] = Field(default_factory=list)


class SpotmuInterestFetch(BaseModel):
    """Mapped interest ready for ``source_items`` upsert."""

    slug: str
    title: str
    interest_heading: str | None
    overview_bullets: list[str]
    canonical_url: str
    brand_kit_refs: dict[str, object] | None
    raw_payload: dict[str, object]


class SpotmuInterestSearchHit(BaseModel):
    """One guest-search hit mapped for the ops campaign form."""

    slug: str
    title: str
    spotmu_interest_id: str | None = None
    interest_heading: str | None = None


def resolve_spotmu_api_base_url(api_base_url: str | None = None) -> str:
    """Return the Spotmu origin, without a trailing slash.

    Args:
        api_base_url: Explicit override. When blank, read
            ``SPOTMU_API_BASE_URL``, then the locked default.

    Returns:
        Origin used to build interest and sitemap URLs.
    """

    if api_base_url is not None:
        stripped_override: str = api_base_url.strip().rstrip("/")

        if stripped_override != "":

            return stripped_override

    environment_base_url: str = os.environ.get(
        SPOTMU_API_BASE_URL_ENVIRONMENT_NAME,
        "",
    ).strip().rstrip("/")

    if environment_base_url != "":

        return environment_base_url

    return DEFAULT_SPOTMU_API_BASE_URL


def build_spotmu_interest_json_url(slug: str, api_base_url: str) -> str:
    """Build the public JSON URL for one interest slug.

    Args:
        slug: Spotmu interest slug (no leading slash).
        api_base_url: Origin from ``resolve_spotmu_api_base_url``.

    Returns:
        Absolute URL ``{origin}/api/v1/interests/slug/{slug}``.
    """

    normalized_slug: str = slug.strip().strip("/")
    interest_json_url: str = (
        f"{api_base_url.rstrip('/')}{INTEREST_BY_SLUG_PATH_PREFIX}{normalized_slug}"
    )

    return interest_json_url


def build_spotmu_interest_canonical_url(slug: str, api_base_url: str) -> str:
    """Build the public page URL stored on ``source_items.canonical_url``.

    Args:
        slug: Spotmu interest slug.
        api_base_url: Same origin as the JSON API.

    Returns:
        Absolute URL ``{origin}/interest/{slug}``.
    """

    normalized_slug: str = slug.strip().strip("/")
    canonical_url: str = (
        f"{api_base_url.rstrip('/')}{PUBLIC_INTEREST_PATH_PREFIX}{normalized_slug}"
    )

    return canonical_url


def build_spotmu_sitemap_url(api_base_url: str) -> str:
    """Build the public sitemap URL.

    Args:
        api_base_url: Origin from ``resolve_spotmu_api_base_url``.

    Returns:
        Absolute URL ``{origin}/sitemap.xml``.
    """

    sitemap_url: str = f"{api_base_url.rstrip('/')}{SITEMAP_PATH}"

    return sitemap_url


def parse_overview_bullets(raw_overview_bullets: str | list[str] | None) -> list[str]:
    """Normalize Spotmu overview bullets to a list of non-empty strings.

    Live public JSON sends a single newline-separated string. A list is
    accepted if the payload shape changes.

    Args:
        raw_overview_bullets: Public ``overview_bullets`` value.

    Returns:
        Stripped bullet lines, empty list when missing.
    """

    if raw_overview_bullets is None:

        return []

    if isinstance(raw_overview_bullets, list):
        list_bullets: list[str] = [
            str(bullet_item).strip()
            for bullet_item in raw_overview_bullets
            if str(bullet_item).strip() != ""
        ]

        return list_bullets

    string_bullets: list[str] = [
        bullet_line.strip()
        for bullet_line in raw_overview_bullets.splitlines()
        if bullet_line.strip() != ""
    ]

    return string_bullets


def extract_interest_slug_from_location(location_url: str) -> str | None:
    """Return the interest slug from a sitemap ``<loc>``, if present.

    Args:
        location_url: Absolute URL from the sitemap.

    Returns:
        Slug after ``/interest/``, or ``None`` for the homepage and
        non-interest paths.
    """

    parsed_location: ParseResult = urlparse(location_url.strip())
    location_path: str = parsed_location.path.rstrip("/")

    if not location_path.startswith(PUBLIC_INTEREST_PATH_PREFIX):

        return None

    slug_remainder: str = location_path[len(PUBLIC_INTEREST_PATH_PREFIX):]

    if slug_remainder == "" or "/" in slug_remainder:

        return None

    return slug_remainder


def extract_interest_slugs_from_sitemap_xml(sitemap_xml_text: str) -> list[str]:
    """Parse sitemap XML and return unique interest slugs in document order.

    Args:
        sitemap_xml_text: Raw sitemap body.

    Returns:
        Interest slugs (homepage and duplicates omitted).

    Raises:
        SpotmuInterestNotJsonError: If the XML cannot be parsed.
    """

    try:
        sitemap_root: ElementTree.Element = ElementTree.fromstring(sitemap_xml_text)
    except ElementTree.ParseError as parse_error:
        raise SpotmuInterestNotJsonError(
            "Spotmu sitemap body is not valid XML.",
        ) from parse_error

    interest_slugs: list[str] = []
    seen_slugs: set[str] = set()

    for loc_element in sitemap_root.iter():
        loc_tag_name: str = loc_element.tag

        if not loc_tag_name.endswith("loc"):
            continue

        location_text: str = (loc_element.text or "").strip()
        extracted_slug: str | None = extract_interest_slug_from_location(
            location_text,
        )

        if extracted_slug is None:
            continue

        if extracted_slug in seen_slugs:
            continue

        seen_slugs.add(extracted_slug)
        interest_slugs.append(extracted_slug)

    return interest_slugs


def fetch_spotmu_interest_by_slug(
    slug: str,
    api_base_url: str | None = None,
    http_client: httpx.Client | None = None,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> SpotmuInterestFetch:
    """GET one public Spotmu interest and map it to an ingest record.

    Args:
        slug: Interest slug (for example ``ai-agents``).
        api_base_url: Optional origin override.
        http_client: Optional injected client (tests). Owned clients close.
        timeout_seconds: HTTP timeout.

    Returns:
        Typed fetch with split bullets, constructed canonical URL, and
        the full JSON in ``raw_payload``.

    Raises:
        SpotmuInterestNotFoundError: HTTP 404.
        SpotmuInterestNotJsonError: HTML or non-object JSON.
        SpotmuInterestTimeoutError: Timeout.
        SpotmuInterestRequestError: Other HTTP or validation failures.
    """

    resolved_api_base_url: str = resolve_spotmu_api_base_url(api_base_url)
    interest_json_url: str = build_spotmu_interest_json_url(
        slug,
        resolved_api_base_url,
    )
    http_response: httpx.Response = _get_spotmu_url(
        interest_json_url,
        http_client,
        timeout_seconds,
        slug,
    )
    raw_payload: dict[str, object] = _parse_interest_json_object(
        http_response,
        interest_json_url,
        slug,
    )

    try:
        public_interest_payload: SpotmuPublicInterestPayload = (
            SpotmuPublicInterestPayload.model_validate(raw_payload)
        )
    except ValidationError as validation_error:
        raise SpotmuInterestRequestError(
            f"Spotmu interest JSON failed validation for slug {slug!r} "
            f"at {interest_json_url}: {validation_error}",
        ) from validation_error

    overview_bullets: list[str] = parse_overview_bullets(
        public_interest_payload.overview_bullets,
    )
    canonical_url: str = build_spotmu_interest_canonical_url(
        public_interest_payload.slug,
        resolved_api_base_url,
    )
    spotmu_interest_fetch: SpotmuInterestFetch = SpotmuInterestFetch(
        slug=public_interest_payload.slug,
        title=public_interest_payload.title,
        interest_heading=public_interest_payload.interest_heading,
        overview_bullets=overview_bullets,
        canonical_url=canonical_url,
        brand_kit_refs=None,
        raw_payload=raw_payload,
    )

    return spotmu_interest_fetch


def list_spotmu_interest_slugs_from_sitemap(
    api_base_url: str | None = None,
    limit: int = DEFAULT_SITEMAP_SLUG_LIMIT,
    http_client: httpx.Client | None = None,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> list[str]:
    """GET the public sitemap and return a capped list of interest slugs.

    Args:
        api_base_url: Optional origin override.
        limit: Maximum slugs to return (clamped to 1..200).
        http_client: Optional injected client (tests).
        timeout_seconds: HTTP timeout.

    Returns:
        Interest slugs in sitemap order, truncated to ``limit``.

    Raises:
        SpotmuInterestNotJsonError: Non-XML or unparseable body.
        SpotmuInterestTimeoutError: Timeout.
        SpotmuInterestRequestError: Unexpected HTTP status.
    """

    resolved_limit: int = _clamp_sitemap_slug_limit(limit)
    resolved_api_base_url: str = resolve_spotmu_api_base_url(api_base_url)
    sitemap_url: str = build_spotmu_sitemap_url(resolved_api_base_url)
    http_response: httpx.Response = _get_spotmu_url(
        sitemap_url,
        http_client,
        timeout_seconds,
        "sitemap",
    )
    _raise_for_sitemap_status(http_response, sitemap_url)
    sitemap_text: str = http_response.text
    interest_slugs: list[str] = extract_interest_slugs_from_sitemap_xml(
        sitemap_text,
    )
    limited_interest_slugs: list[str] = interest_slugs[:resolved_limit]

    return limited_interest_slugs


def build_spotmu_interest_search_url(
    query: str,
    api_base_url: str,
    limit: int,
) -> str:
    """Build the public guest search URL.

    Live probe (2026-09-21): unauthenticated
    ``GET {origin}/api/v1/interests/search?q=`` returns a JSON array.
    ``limit`` is honored. ``/interests/autocomplete`` is 401.

    Args:
        query: Operator search string.
        api_base_url: Origin from ``resolve_spotmu_api_base_url``.
        limit: Maximum hits (already clamped).

    Returns:
        Absolute URL with ``q`` and ``limit`` query params.
    """

    query_string: str = urlencode({"q": query, "limit": limit})
    search_url: str = (
        f"{api_base_url.rstrip('/')}{INTEREST_SEARCH_PATH}?{query_string}"
    )

    return search_url


def search_spotmu_interests(
    query: str,
    api_base_url: str | None = None,
    limit: int = DEFAULT_INTEREST_SEARCH_LIMIT,
    http_client: httpx.Client | None = None,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> list[SpotmuInterestSearchHit]:
    """GET public Spotmu interest search and map hits for ops.

    Args:
        query: Search string. Blank returns an empty list without HTTP.
        api_base_url: Optional origin override.
        limit: Maximum hits (clamped to 1..20).
        http_client: Optional injected client (tests).
        timeout_seconds: HTTP timeout.

    Returns:
        Mapped hits with ``slug``, ``title``, optional ids.

    Raises:
        SpotmuInterestNotJsonError: Non-JSON or non-array body.
        SpotmuInterestTimeoutError: Timeout.
        SpotmuInterestRequestError: Unexpected HTTP status.
    """

    stripped_query: str = query.strip()

    if stripped_query == "":

        return []

    resolved_limit: int = _clamp_interest_search_limit(limit)
    resolved_api_base_url: str = resolve_spotmu_api_base_url(api_base_url)
    search_url: str = build_spotmu_interest_search_url(
        stripped_query,
        resolved_api_base_url,
        resolved_limit,
    )
    http_response: httpx.Response = _get_spotmu_url(
        search_url,
        http_client,
        timeout_seconds,
        stripped_query,
    )
    raw_hits: list[object] = _parse_interest_search_json_array(
        http_response,
        search_url,
        stripped_query,
    )
    mapped_hits: list[SpotmuInterestSearchHit] = []

    for raw_hit in raw_hits:
        mapped_hit: SpotmuInterestSearchHit | None = _map_interest_search_hit(
            raw_hit,
        )

        if mapped_hit is None:
            continue

        mapped_hits.append(mapped_hit)

    return mapped_hits


def _clamp_interest_search_limit(limit: int) -> int:
    """Clamp a caller search limit into the proxy window."""

    if limit < 1:

        return 1

    if limit > MAXIMUM_INTEREST_SEARCH_LIMIT:

        return MAXIMUM_INTEREST_SEARCH_LIMIT

    return limit


def _parse_interest_search_json_array(
    http_response: httpx.Response,
    search_url: str,
    query: str,
) -> list[object]:
    """Validate status + JSON array for interest search.

    Args:
        http_response: Raw HTTP response.
        search_url: URL used in error messages.
        query: Requested query.

    Returns:
        Parsed JSON array.

    Raises:
        SpotmuInterestNotJsonError: Non-JSON or non-array body.
        SpotmuInterestRequestError: Non-200 status.
    """

    response_status_code: int = http_response.status_code

    if response_status_code != 200:
        raise SpotmuInterestRequestError(
            f"Spotmu interest search returned HTTP {response_status_code} "
            f"for query {query!r} at {search_url}",
        )

    content_type_header: str = http_response.headers.get("content-type", "")

    if JSON_CONTENT_TYPE_NEEDLE not in content_type_header.lower():
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest search was not JSON for query {query!r} at "
            f"{search_url} (content-type={content_type_header!r})",
        )

    response_text: str = http_response.text

    try:
        parsed_payload: object = json.loads(response_text)
    except json.JSONDecodeError as json_error:
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest search body was not valid JSON for query "
            f"{query!r} at {search_url}",
        ) from json_error

    if not isinstance(parsed_payload, list):
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest search JSON was not an array for query "
            f"{query!r} at {search_url}",
        )

    raw_hits: list[object] = parsed_payload

    return raw_hits


def _map_interest_search_hit(raw_hit: object) -> SpotmuInterestSearchHit | None:
    """Map one Spotmu search object to a slug/title hit.

    Args:
        raw_hit: One array element from the public search JSON.

    Returns:
        A hit when ``slug`` and ``title`` are present; otherwise ``None``.
    """

    if not isinstance(raw_hit, dict):

        return None

    raw_slug: object = raw_hit.get("slug")
    raw_title: object = raw_hit.get("title")

    if not isinstance(raw_slug, str) or raw_slug.strip() == "":

        return None

    if not isinstance(raw_title, str) or raw_title.strip() == "":

        return None

    raw_interest_hash_id: object = raw_hit.get("interest_hash_id")
    raw_interest_heading: object = raw_hit.get("interest_heading")
    spotmu_interest_id: str | None = None
    interest_heading: str | None = None

    if isinstance(raw_interest_hash_id, str) and raw_interest_hash_id.strip() != "":
        spotmu_interest_id = raw_interest_hash_id.strip()

    if isinstance(raw_interest_heading, str) and raw_interest_heading.strip() != "":
        interest_heading = raw_interest_heading.strip()

    mapped_hit: SpotmuInterestSearchHit = SpotmuInterestSearchHit(
        slug=raw_slug.strip(),
        title=raw_title.strip(),
        spotmu_interest_id=spotmu_interest_id,
        interest_heading=interest_heading,
    )

    return mapped_hit


def _clamp_sitemap_slug_limit(limit: int) -> int:
    """Clamp a caller limit into the MVP sitemap window."""

    if limit < 1:

        return 1

    if limit > MAXIMUM_SITEMAP_SLUG_LIMIT:

        return MAXIMUM_SITEMAP_SLUG_LIMIT

    return limit


def _get_spotmu_url(
    request_url: str,
    http_client: httpx.Client | None,
    timeout_seconds: float,
    slug_for_errors: str,
) -> httpx.Response:
    """GET a Spotmu URL, mapping timeout and transport errors.

    Args:
        request_url: Absolute URL.
        http_client: Optional injected client.
        timeout_seconds: HTTP timeout.
        slug_for_errors: Slug or label included in error messages.

    Returns:
        The HTTP response (caller interprets status).

    Raises:
        SpotmuInterestTimeoutError: Timeout.
        SpotmuInterestRequestError: Other transport failures.
    """

    owned_http_client: bool = http_client is None
    active_http_client: httpx.Client

    if http_client is None:
        active_http_client = httpx.Client(timeout=timeout_seconds)
    else:
        active_http_client = http_client

    try:
        http_response: httpx.Response = active_http_client.get(
            request_url,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException as timeout_error:
        raise SpotmuInterestTimeoutError(
            f"Spotmu request timed out for {slug_for_errors!r} at {request_url}",
        ) from timeout_error
    except httpx.RequestError as request_error:
        raise SpotmuInterestRequestError(
            f"Spotmu request failed for {slug_for_errors!r} at {request_url}: "
            f"{request_error}",
        ) from request_error
    finally:

        if owned_http_client:
            active_http_client.close()

    return http_response


def _parse_interest_json_object(
    http_response: httpx.Response,
    interest_json_url: str,
    slug: str,
) -> dict[str, object]:
    """Validate status + JSON object for an interest GET.

    Args:
        http_response: Raw HTTP response.
        interest_json_url: URL used in error messages.
        slug: Requested slug.

    Returns:
        Parsed JSON object.

    Raises:
        SpotmuInterestNotFoundError: HTTP 404.
        SpotmuInterestNotJsonError: Non-JSON or non-object body.
        SpotmuInterestRequestError: Other non-200 status.
    """

    response_status_code: int = http_response.status_code

    if response_status_code == 404:
        raise SpotmuInterestNotFoundError(
            f"Spotmu interest not found for slug {slug!r} at {interest_json_url}",
        )

    if response_status_code != 200:
        raise SpotmuInterestRequestError(
            f"Spotmu interest request returned HTTP {response_status_code} "
            f"for slug {slug!r} at {interest_json_url}",
        )

    content_type_header: str = http_response.headers.get("content-type", "")

    if JSON_CONTENT_TYPE_NEEDLE not in content_type_header.lower():
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest response was not JSON for slug {slug!r} at "
            f"{interest_json_url} (content-type={content_type_header!r})",
        )

    response_text: str = http_response.text

    try:
        parsed_payload: object = json.loads(response_text)
    except json.JSONDecodeError as json_error:
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest body was not valid JSON for slug {slug!r} at "
            f"{interest_json_url}",
        ) from json_error

    if not isinstance(parsed_payload, dict):
        raise SpotmuInterestNotJsonError(
            f"Spotmu interest JSON was not an object for slug {slug!r} at "
            f"{interest_json_url}",
        )

    raw_payload: dict[str, object] = parsed_payload

    return raw_payload


def _raise_for_sitemap_status(
    http_response: httpx.Response,
    sitemap_url: str,
) -> None:
    """Raise when the sitemap GET is not HTTP 200.

    Args:
        http_response: Raw HTTP response.
        sitemap_url: URL used in error messages.

    Raises:
        SpotmuInterestRequestError: Non-200 status.
    """

    response_status_code: int = http_response.status_code

    if response_status_code != 200:
        raise SpotmuInterestRequestError(
            f"Spotmu sitemap request returned HTTP {response_status_code} "
            f"at {sitemap_url}",
        )
