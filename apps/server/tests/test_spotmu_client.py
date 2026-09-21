"""Mocked HTTP tests for the locked Spotmu public client (1.3b / 1.3d)."""

import unittest

import httpx

from app.ingest.spotmu import (
    DEFAULT_SPOTMU_API_BASE_URL,
    SpotmuInterestNotFoundError,
    SpotmuInterestNotJsonError,
    SpotmuInterestRequestError,
    SpotmuInterestTimeoutError,
    extract_interest_slugs_from_sitemap_xml,
    fetch_spotmu_interest_by_slug,
    list_spotmu_interest_slugs_from_sitemap,
    parse_overview_bullets,
    resolve_spotmu_api_base_url,
    search_spotmu_interests,
)


LIVE_SHAPED_INTEREST_PAYLOAD: dict[str, object] = {
    "interest_hash_id": "s4ce16604dd1accb",
    "slug": "ai-agents",
    "title": "AI Agents",
    "interest_heading": "Google Grants All Engineers Access to Anthropic's Claude for Coding",
    "overview_summary": "Google has reversed its policy and granted all engineers access.",
    "overview_bullets": (
        "Google grants all engineers access to Claude for coding\n"
        "Anthropic CEO calls for global AI slowdown, rivals agree\n"
        "Apple's Siri to deeply integrate with ChatGPT and Claude"
    ),
    "overview_text": "The AI agent landscape is defined by a tension.",
    "overview_created_at": "2026-09-15T00:42:37.772958",
    "last_updated": "2026-09-14T04:56:57.538996",
    "serve_story_count": 1580,
    "categories": ["tech"],
    "teasers": [
        {
            "story_hash_id": "teaser-1",
            "title": "Fortune 500 Agent Adoption Hits 80%",
            "summary": "Agentic AI has crossed into mainstream enterprise adoption.",
            "created_at": "2026-09-03T12:17:58.501294",
            "source_published_at": None,
        },
    ],
}
SAMPLE_SITEMAP_XML: str = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://spotmu.com/</loc></url>
  <url><loc>https://spotmu.com/interest/ai-agents</loc></url>
  <url><loc>https://spotmu.com/interest/amazon</loc></url>
  <url><loc>https://spotmu.com/interest/ai-agents</loc></url>
</urlset>
"""


class SpotmuClientTests(unittest.TestCase):
    """1.3b-iii: mocked public payload; 1.3d sitemap parse."""

    def test_resolve_default_origin_is_the_locked_public_host(self) -> None:
        """Default origin is https://spotmu.com when env is unset."""

        resolved_base_url: str = resolve_spotmu_api_base_url()

        self.assertEqual(resolved_base_url, DEFAULT_SPOTMU_API_BASE_URL)

    def test_parse_overview_bullets_splits_newline_string(self) -> None:
        """Live public JSON sends overview_bullets as a newline string."""

        raw_bullets: str = "one\n\ntwo\nthree"
        parsed_bullets: list[str] = parse_overview_bullets(raw_bullets)

        self.assertEqual(parsed_bullets, ["one", "two", "three"])

    def test_parse_overview_bullets_accepts_a_list(self) -> None:
        """Forward-compat: list payloads are stripped, empties dropped."""

        parsed_bullets: list[str] = parse_overview_bullets(["  a  ", "", "b"])

        self.assertEqual(parsed_bullets, ["a", "b"])

    def test_fetch_maps_live_shaped_payload(self) -> None:
        """GET 200 JSON maps title, heading, split bullets, canonical URL."""

        http_client: httpx.Client = _client_returning_json(
            LIVE_SHAPED_INTEREST_PAYLOAD,
        )
        fetched_interest = fetch_spotmu_interest_by_slug(
            "ai-agents",
            http_client=http_client,
        )

        self.assertEqual(fetched_interest.slug, "ai-agents")
        self.assertEqual(fetched_interest.title, "AI Agents")
        self.assertEqual(
            fetched_interest.interest_heading,
            "Google Grants All Engineers Access to Anthropic's Claude for Coding",
        )
        self.assertEqual(len(fetched_interest.overview_bullets), 3)
        self.assertEqual(
            fetched_interest.overview_bullets[0],
            "Google grants all engineers access to Claude for coding",
        )
        self.assertEqual(
            fetched_interest.canonical_url,
            "https://spotmu.com/interest/ai-agents",
        )
        self.assertIsNone(fetched_interest.brand_kit_refs)
        self.assertEqual(
            fetched_interest.raw_payload["interest_hash_id"],
            "s4ce16604dd1accb",
        )
        self.assertEqual(fetched_interest.raw_payload["categories"], ["tech"])

    def test_fetch_raises_for_http_404(self) -> None:
        """Unknown slug is a typed not-found error, not an empty upsert."""

        http_client: httpx.Client = _client_returning_status(
            404,
            {"detail": "Interest not found"},
            content_type="application/json",
        )

        with self.assertRaises(SpotmuInterestNotFoundError) as raised_error:
            fetch_spotmu_interest_by_slug("missing-slug", http_client=http_client)

        self.assertIn("missing-slug", str(raised_error.exception))

    def test_fetch_raises_for_html_body(self) -> None:
        """SPA shell (wrong path) is a non-JSON error."""

        http_client: httpx.Client = _client_returning_text(
            200,
            "<!doctype html><html><body>Spotmu</body></html>",
            content_type="text/html",
        )

        with self.assertRaises(SpotmuInterestNotJsonError):
            fetch_spotmu_interest_by_slug("ai-agents", http_client=http_client)

    def test_fetch_raises_for_timeout(self) -> None:
        """Timeouts become SpotmuInterestTimeoutError."""

        http_client: httpx.Client = _client_raising_timeout()

        with self.assertRaises(SpotmuInterestTimeoutError):
            fetch_spotmu_interest_by_slug("ai-agents", http_client=http_client)

    def test_fetch_raises_for_unexpected_status(self) -> None:
        """Non-404 failures are request errors."""

        http_client: httpx.Client = _client_returning_status(
            503,
            {"detail": "unavailable"},
            content_type="application/json",
        )

        with self.assertRaises(SpotmuInterestRequestError):
            fetch_spotmu_interest_by_slug("ai-agents", http_client=http_client)

    def test_sitemap_xml_extracts_unique_interest_slugs(self) -> None:
        """Homepage loc is skipped; duplicate slugs appear once."""

        interest_slugs: list[str] = extract_interest_slugs_from_sitemap_xml(
            SAMPLE_SITEMAP_XML,
        )

        self.assertEqual(interest_slugs, ["ai-agents", "amazon"])

    def test_list_sitemap_slugs_respects_limit(self) -> None:
        """Discovery helper caps the returned slug list."""

        http_client: httpx.Client = _client_returning_text(
            200,
            SAMPLE_SITEMAP_XML,
            content_type="application/xml",
        )
        interest_slugs: list[str] = list_spotmu_interest_slugs_from_sitemap(
            limit=1,
            http_client=http_client,
        )

        self.assertEqual(interest_slugs, ["ai-agents"])

    def test_search_maps_live_shaped_array(self) -> None:
        """Guest search JSON array maps slug, title, and hash id."""

        http_client: httpx.Client = _client_returning_json_array(
            [
                {
                    "id": "33a69aa4-7609-4359-b35f-d34ef7f26113",
                    "interest_hash_id": "s69a0baf288c3c5d",
                    "title": "Artificial Intelligence",
                    "slug": "artificial-intelligence",
                    "interest_heading": "AI heading",
                },
                {"title": "Missing slug"},
            ],
        )
        search_hits = search_spotmu_interests("ai", http_client=http_client)

        self.assertEqual(len(search_hits), 1)
        self.assertEqual(search_hits[0].slug, "artificial-intelligence")
        self.assertEqual(search_hits[0].title, "Artificial Intelligence")
        self.assertEqual(search_hits[0].spotmu_interest_id, "s69a0baf288c3c5d")
        self.assertEqual(search_hits[0].interest_heading, "AI heading")

    def test_search_blank_query_skips_http(self) -> None:
        """Blank q returns [] without calling Spotmu."""

        http_client: httpx.Client = _client_raising_timeout()
        search_hits = search_spotmu_interests("   ", http_client=http_client)

        self.assertEqual(search_hits, [])


def _client_returning_json(payload: dict[str, object]) -> httpx.Client:
    """Return a client whose GET yields the given JSON object."""

    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        return httpx.Response(200, json=payload)

    mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
    http_client: httpx.Client = httpx.Client(transport=mock_transport)

    return http_client


def _client_returning_json_array(payload: list[object]) -> httpx.Client:
    """Return a client whose GET yields a JSON array."""

    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        return httpx.Response(
            200,
            json=payload,
            headers={"content-type": "application/json"},
        )

    mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
    http_client: httpx.Client = httpx.Client(transport=mock_transport)

    return http_client


def _client_returning_status(
    status_code: int,
    payload: dict[str, object],
    content_type: str,
) -> httpx.Client:
    """Return a client whose GET yields a JSON status payload."""

    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        return httpx.Response(
            status_code,
            json=payload,
            headers={"content-type": content_type},
        )

    mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
    http_client: httpx.Client = httpx.Client(transport=mock_transport)

    return http_client


def _client_returning_text(
    status_code: int,
    body_text: str,
    content_type: str,
) -> httpx.Client:
    """Return a client whose GET yields a raw text body."""

    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        return httpx.Response(
            status_code,
            text=body_text,
            headers={"content-type": content_type},
        )

    mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
    http_client: httpx.Client = httpx.Client(transport=mock_transport)

    return http_client


def _client_raising_timeout() -> httpx.Client:
    """Return a client whose GET always times out."""

    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        raise httpx.TimeoutException("mocked timeout")

    mock_transport: httpx.MockTransport = httpx.MockTransport(handler)
    http_client: httpx.Client = httpx.Client(transport=mock_transport)

    return http_client


if __name__ == "__main__":
    unittest.main()
