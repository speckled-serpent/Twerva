"""Build a PublishAdapter from process settings (1.6b-iii)."""

from __future__ import annotations

from app.publish.adapter import PublishAdapter
from app.publish.ayrshare import AyrsharePublishAdapter
from app.publish.errors import (
    PublishAdapterNotConfiguredError,
    PublishAdapterUnknownError,
)
from app.publish.mock import MockPublishAdapter
from app.settings import Settings, get_settings


MOCK_PUBLISH_ADAPTER_NAME: str = "mock"
AYRSHARE_PUBLISH_ADAPTER_NAME: str = "ayrshare"
AYRSHARE_API_KEY_SETTING_NAME: str = "AYRSHARE_API_KEY"


def get_publish_adapter(settings: Settings | None = None) -> PublishAdapter:
    """Return the configured adapter. Mock is the CI/default path.

    Args:
        settings: Override for tests; default is `get_settings()`.

    Returns:
        A `PublishAdapter` implementation.

    Raises:
        PublishAdapterUnknownError: Name is not `mock` or `ayrshare`.
        PublishAdapterNotConfiguredError: `ayrshare` without `AYRSHARE_API_KEY`.
    """

    resolved_settings: Settings

    if settings is None:
        resolved_settings = get_settings()
    else:
        resolved_settings = settings

    adapter_name: str = resolved_settings.publish_adapter.strip().lower()

    if adapter_name == MOCK_PUBLISH_ADAPTER_NAME:
        mock_publish_adapter: MockPublishAdapter = MockPublishAdapter()

        return mock_publish_adapter

    if adapter_name == AYRSHARE_PUBLISH_ADAPTER_NAME:
        ayrshare_publish_adapter: AyrsharePublishAdapter = (
            _build_ayrshare_publish_adapter(resolved_settings.ayrshare_api_key)
        )

        return ayrshare_publish_adapter

    raise PublishAdapterUnknownError(adapter_name)


def _build_ayrshare_publish_adapter(ayrshare_api_key: str) -> AyrsharePublishAdapter:
    """Require an API key; still do not send HTTP in 1.6."""

    stripped_api_key: str = ayrshare_api_key.strip()

    if stripped_api_key == "":
        raise PublishAdapterNotConfiguredError(
            AYRSHARE_PUBLISH_ADAPTER_NAME,
            AYRSHARE_API_KEY_SETTING_NAME,
        )

    ayrshare_publish_adapter: AyrsharePublishAdapter = AyrsharePublishAdapter(
        stripped_api_key,
    )

    return ayrshare_publish_adapter
