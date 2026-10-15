"""Draft theme text from a source's inspiration and rules.

The call sits behind one interface. ``openai`` uses ``OPENAI_API_KEY``
and ``OPENAI_MODEL``. ``fake`` returns deterministic text for tests and
local checks. A missing key does not call the network.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.settings import Settings


GENERATE_DISABLED_DETAIL: str = "Generate is off until OPENAI_API_KEY is set."
UNKNOWN_PROVIDER_DETAIL: str = "TEXT_GENERATION_PROVIDER must be openai or fake."
TEXT_GENERATION_FAILED_DETAIL: str = "The text draft could not be generated."
OPENAI_CHAT_COMPLETIONS_URL: str = "https://api.openai.com/v1/chat/completions"
DRAFTED_UNIT_NAME: str = "Drafted unit"
MAX_DRAFTED_NAME_LENGTH: int = 200


class TextGenerationError(Exception):
    """The provider ran and did not return a usable draft."""


class TextGenerationUnavailable(Exception):
    """Generate is off. The detail is safe to show an operator."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail: str = detail


@dataclass(frozen=True)
class TextElementPrompt:
    """One theme text element the draft must fill."""

    theme_element_id: uuid.UUID
    label: str


@dataclass(frozen=True)
class DraftedUnitText:
    """A name and one string per requested text element."""

    name: str
    values_by_element_id: dict[uuid.UUID, str]


@dataclass(frozen=True)
class TextGenerationAvailability:
    """Whether Generate can run in this process."""

    available: bool
    detail: str


class TextGenerationProvider:
    """Drafts one unit's theme text. Implementations do not write rows."""

    def draft_unit_text(
        self,
        inspiration: str,
        rules: str,
        unit_name: str | None,
        elements: Sequence[TextElementPrompt],
    ) -> DraftedUnitText:
        """Return drafted copy for these elements.

        Args:
            inspiration: The source's inspiration. May be empty.
            rules: The source's rules. May be empty.
            unit_name: The unit being rewritten, or null for a new unit.
            elements: Theme text elements, in frame order.

        Returns:
            A name and one value per element.

        Raises:
            TextGenerationError: The provider did not return a draft.
        """

        raise NotImplementedError


class FakeTextGenerationProvider(TextGenerationProvider):
    """Deterministic drafts. No network."""

    def draft_unit_text(
        self,
        inspiration: str,
        rules: str,
        unit_name: str | None,
        elements: Sequence[TextElementPrompt],
    ) -> DraftedUnitText:
        """Fill each element from its label, the inspiration, and the rules."""

        drafted_name: str = _drafted_name(inspiration, unit_name)
        values_by_element_id: dict[uuid.UUID, str] = {}

        for element in elements:
            pieces: list[str] = [element.label]
            trimmed_inspiration: str = inspiration.strip()
            trimmed_rules: str = rules.strip()

            if trimmed_inspiration != "":
                pieces.append(trimmed_inspiration)

            if trimmed_rules != "":
                pieces.append(trimmed_rules)

            values_by_element_id[element.theme_element_id] = ". ".join(pieces)

        drafted_text: DraftedUnitText = DraftedUnitText(
            name=drafted_name,
            values_by_element_id=values_by_element_id,
        )

        return drafted_text


class OpenAITextGenerationProvider(TextGenerationProvider):
    """Chat completions against api.openai.com. The key stays in the header."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key: str = api_key
        self._model: str = model

    def draft_unit_text(
        self,
        inspiration: str,
        rules: str,
        unit_name: str | None,
        elements: Sequence[TextElementPrompt],
    ) -> DraftedUnitText:
        """Ask the configured model for one JSON draft."""

        request_body: dict[str, object] = _openai_request_body(
            self._model,
            inspiration,
            rules,
            unit_name,
            elements,
        )

        try:
            response: httpx.Response = httpx.post(
                OPENAI_CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=request_body,
                timeout=30.0,
            )
        except httpx.HTTPError as request_error:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL) from request_error

        if response.status_code >= 400:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

        try:
            response_body: object = response.json()
        except json.JSONDecodeError as decode_error:
            raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL) from decode_error

        return drafted_text_from_openai_response(response_body, elements, unit_name)


def text_generation_availability(settings: Settings) -> TextGenerationAvailability:
    """Return whether Generate is on, and the message when it is off.

    Args:
        settings: Process settings. The key is not copied into the result.

    Returns:
        Availability. ``detail`` is empty when Generate can run.
    """

    provider_name: str = settings.text_generation_provider

    if provider_name == "fake":
        available: TextGenerationAvailability = TextGenerationAvailability(
            available=True,
            detail="",
        )

        return available

    if provider_name == "openai":

        if settings.openai_api_key == "":
            missing_key: TextGenerationAvailability = TextGenerationAvailability(
                available=False,
                detail=GENERATE_DISABLED_DETAIL,
            )

            return missing_key

        configured: TextGenerationAvailability = TextGenerationAvailability(
            available=True,
            detail="",
        )

        return configured

    unknown_provider: TextGenerationAvailability = TextGenerationAvailability(
        available=False,
        detail=UNKNOWN_PROVIDER_DETAIL,
    )

    return unknown_provider


def require_text_generation_provider(settings: Settings) -> TextGenerationProvider:
    """Return the provider for this process.

    Args:
        settings: Process settings.

    Returns:
        The fake provider, or OpenAI when a key is set.

    Raises:
        TextGenerationUnavailable: Generate is off.
    """

    availability: TextGenerationAvailability = text_generation_availability(settings)

    if not availability.available:
        raise TextGenerationUnavailable(availability.detail)

    if settings.text_generation_provider == "fake":
        fake_provider: FakeTextGenerationProvider = FakeTextGenerationProvider()

        return fake_provider

    openai_provider: OpenAITextGenerationProvider = OpenAITextGenerationProvider(
        settings.openai_api_key,
        settings.openai_model,
    )

    return openai_provider


def drafted_text_from_openai_response(
    response_body: object,
    elements: Sequence[TextElementPrompt],
    unit_name: str | None,
) -> DraftedUnitText:
    """Read the chat completion JSON into one draft.

    Args:
        response_body: Parsed OpenAI response.
        elements: Elements the draft must cover.
        unit_name: Current name, used when the model omits one.

    Returns:
        One value per element. A missing element is an empty string.

    Raises:
        TextGenerationError: The body is not the expected JSON object.
    """

    if not isinstance(response_body, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    choices: object = response_body.get("choices")

    if not isinstance(choices, list) or len(choices) == 0:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    first_choice: object = choices[0]

    if not isinstance(first_choice, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    message: object = first_choice.get("message")

    if not isinstance(message, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    content: object = message.get("content")

    if not isinstance(content, str):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    try:
        parsed_content: object = json.loads(content)
    except json.JSONDecodeError as decode_error:
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL) from decode_error

    if not isinstance(parsed_content, dict):
        raise TextGenerationError(TEXT_GENERATION_FAILED_DETAIL)

    raw_name: object = parsed_content.get("name", "")
    drafted_name: str = _drafted_name(
        raw_name if isinstance(raw_name, str) else "",
        unit_name,
    )
    raw_texts: object = parsed_content.get("texts")
    value_by_id: dict[str, str] = {}

    if isinstance(raw_texts, list):

        for item in raw_texts:

            if not isinstance(item, dict):
                continue

            element_id: object = item.get("theme_element_id")
            value: object = item.get("value")

            if isinstance(element_id, str) and isinstance(value, str):
                value_by_id[element_id] = value

    values_by_element_id: dict[uuid.UUID, str] = {
        element.theme_element_id: value_by_id.get(str(element.theme_element_id), "")
        for element in elements
    }
    drafted_text: DraftedUnitText = DraftedUnitText(
        name=drafted_name,
        values_by_element_id=values_by_element_id,
    )

    return drafted_text


def _drafted_name(inspiration: str, unit_name: str | None) -> str:
    """Prefer the unit's current name, then a short inspiration, then a fallback."""

    if unit_name is not None and unit_name.strip() != "":
        current_name: str = " ".join(unit_name.split())

        return current_name[:MAX_DRAFTED_NAME_LENGTH]

    collapsed_inspiration: str = " ".join(inspiration.split())

    if collapsed_inspiration == "":

        return DRAFTED_UNIT_NAME

    return collapsed_inspiration[:MAX_DRAFTED_NAME_LENGTH]


def _openai_request_body(
    model: str,
    inspiration: str,
    rules: str,
    unit_name: str | None,
    elements: Sequence[TextElementPrompt],
) -> dict[str, object]:
    """Build the chat completion body. The key is not part of the body."""

    element_lines: list[str] = [
        f"{element.theme_element_id} ({element.label})" for element in elements
    ]
    name_line: str = unit_name if unit_name is not None else ""
    user_prompt: str = (
        "Draft short carousel text.\n"
        f"Inspiration: {inspiration}\n"
        f"Rules: {rules}\n"
        f"Current unit name: {name_line}\n"
        "Text elements:\n"
        + "\n".join(element_lines)
        + "\nReturn JSON with name and texts. "
        "texts is a list of theme_element_id and value."
    )
    request_body: dict[str, object] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You draft short text for a carousel unit. Reply with JSON only.",
            },
            {"role": "user", "content": user_prompt},
        ],
    }

    return request_body
