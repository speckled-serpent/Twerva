"""Closed vocabularies stored as native Postgres ENUM types.

See `docs/planning/domain_statuses.md` for the locked approach, allowed
transitions, and query conventions. This module is the in-code source of
truth for the stored strings.
"""

import enum

from sqlalchemy import Enum


class ArtifactStatus(enum.StrEnum):
    """Lifecycle of an Artifact. Reject is terminal for MVP."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class PostJobStatus(enum.StrEnum):
    """Lifecycle of a PostJob (schedule → publish → measure, with retry)."""

    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    MEASURED = "measured"


class Platform(enum.StrEnum):
    """Publish target. Phase 1 is Instagram + TikTok only."""

    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class SourceType(enum.StrEnum):
    """Origin of a SourceItem.

    Phase 1 uses `spotmu_interest` only. `brand_product` and
    `editorial_brief` are reserved values so the enum does not need a
    rewrite when those flows land; do not build those ingest paths here.
    """

    SPOTMU_INTEREST = "spotmu_interest"
    BRAND_PRODUCT = "brand_product"
    EDITORIAL_BRIEF = "editorial_brief"


class AccountStatus(enum.StrEnum):
    """Operational state of a platform Account."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class SteerActionType(enum.StrEnum):
    """Coarse steer decision attached to a Cluster (1.7c HTTP API)."""

    KILL = "kill"
    PAUSE = "pause"
    DOUBLE_DOWN = "double_down"
    RESUME = "resume"


class OpsUserRole(enum.StrEnum):
    """Operator role on `ops_users` (console RBAC, not social `accounts`)."""

    ADMIN = "admin"
    READER = "reader"


class CampaignType(enum.StrEnum):
    """Origin of a Campaign definition.

    `spotmu` is the production create path (requires ≥1 linked account).
    `spotmu_test` is the same create flow without required accounts.
    `other` is reserved; the API rejects create for it.
    """

    SPOTMU = "spotmu"
    SPOTMU_TEST = "spotmu_test"
    OTHER = "other"


class AdvertisementType(enum.StrEnum):
    """Ad format stored on a Campaign. Only carousel is implemented."""

    CAROUSEL = "carousel"


class CampaignStatus(enum.StrEnum):
    """Lifecycle of a Campaign.

    Create persists `ready`. Start / pause / resume / finish flip status
    only; they do not ingest or generate.
    """

    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class ThemeStatus(enum.StrEnum):
    """Whether a Theme is still being edited or used for posts that ship.

    A name-only create stores `draft`. `POST /api/v1/themes` may set
    `draft` or `live` when the body includes `status`. `PATCH` may set
    either value too. Shipping generate does not read this value yet.
    """

    DRAFT = "draft"
    LIVE = "live"


class BackgroundKind(enum.StrEnum):
    """The one background on a Theme. Picture, color, or gradient.

    Texture is dropped for now. It may return later as a default album
    of texture images.
    """

    PICTURE = "picture"
    COLOR = "color"
    GRADIENT = "gradient"


class ThemeElementBand(enum.StrEnum):
    """Vertical band a theme element stacks in. Bands do not push each other."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class ThemeElementContentKind(enum.StrEnum):
    """Whether a theme element draws text or one image file."""

    TEXT = "text"
    IMAGE = "image"


class ThemeElementTextSource(enum.StrEnum):
    """Spotmu field a text element reads. No other source keys.

    Maps to ``source_items.title``, ``source_items.interest_heading``,
    ``source_items.overview_bullets``, and ``source_items.canonical_url``.
    """

    TITLE = "title"
    INTEREST_HEADING = "interest_heading"
    OVERVIEW_BULLETS = "overview_bullets"
    CANONICAL_URL = "canonical_url"


class ThemeElementAlignment(enum.StrEnum):
    """Horizontal alignment of a text element's content."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class ContentSourceKind(enum.StrEnum):
    """Whether a content source is an album of units or a resource file."""

    ALBUM = "album"
    RESOURCE = "resource"


class ResourceFileMediaType(enum.StrEnum):
    """Stored type of one resource file. The bytes are the upload."""

    MARKDOWN = "markdown"
    PLAIN = "plain"


class UnitImageMediaType(enum.StrEnum):
    """Stored type of one unit image. SVG has no pixel size."""

    SVG = "svg"
    PNG = "png"
    JPEG = "jpeg"


class UnitImageLicense(enum.StrEnum):
    """Allowlist for a unit image. Anything else cannot be stored."""

    CC0 = "cc0"
    PUBLIC_DOMAIN = "public_domain"
    OWNED = "owned"
    LICENSED = "licensed"


class UnitImageIntake(enum.StrEnum):
    """How a unit image's bytes arrived. Phase 1 seeds ``upload`` only."""

    UPLOAD = "upload"
    URL = "url"


ARTIFACT_STATUS_TRANSITIONS: dict[ArtifactStatus, frozenset[ArtifactStatus]] = {
    ArtifactStatus.DRAFT: frozenset(
        {ArtifactStatus.APPROVED, ArtifactStatus.REJECTED},
    ),
    ArtifactStatus.APPROVED: frozenset({ArtifactStatus.REJECTED}),
    ArtifactStatus.REJECTED: frozenset(),
}

CAMPAIGN_STATUS_TRANSITIONS: dict[CampaignStatus, frozenset[CampaignStatus]] = {
    CampaignStatus.READY: frozenset({CampaignStatus.RUNNING}),
    CampaignStatus.RUNNING: frozenset(
        {CampaignStatus.PAUSED, CampaignStatus.FINISHED},
    ),
    CampaignStatus.PAUSED: frozenset(
        {CampaignStatus.RUNNING, CampaignStatus.FINISHED},
    ),
    CampaignStatus.FINISHED: frozenset(),
}

POST_JOB_STATUS_TRANSITIONS: dict[PostJobStatus, frozenset[PostJobStatus]] = {
    PostJobStatus.SCHEDULED: frozenset({PostJobStatus.PUBLISHING}),
    PostJobStatus.PUBLISHING: frozenset(
        {PostJobStatus.PUBLISHED, PostJobStatus.FAILED},
    ),
    PostJobStatus.PUBLISHED: frozenset(
        {PostJobStatus.FAILED, PostJobStatus.MEASURED},
    ),
    PostJobStatus.FAILED: frozenset(
        {
            PostJobStatus.SCHEDULED,
            PostJobStatus.PUBLISHING,
            PostJobStatus.MEASURED,
        },
    ),
    PostJobStatus.MEASURED: frozenset(),
}


def as_postgres_enum(enum_class: type[enum.StrEnum], type_name: str) -> Enum:
    """Map a StrEnum to a native Postgres ENUM column type.

    Args:
        enum_class: Closed vocabulary whose `.value` strings are stored.
        type_name: Stable Postgres type name (must match the migration).

    Returns:
        A SQLAlchemy Enum that persists member values, not member names.
    """

    postgres_enum: Enum = Enum(
        enum_class,
        name=type_name,
        native_enum=True,
        values_callable=_stored_enum_values,
        validate_strings=True,
    )

    return postgres_enum


def _stored_enum_values(enum_class: type[enum.Enum]) -> list[str]:
    """Return lowercase stored values for a SQLAlchemy native enum."""

    stored_values: list[str] = [member.value for member in enum_class]

    return stored_values


ARTIFACT_STATUS_ENUM: Enum = as_postgres_enum(ArtifactStatus, "artifact_status")
POST_JOB_STATUS_ENUM: Enum = as_postgres_enum(PostJobStatus, "post_job_status")
PLATFORM_ENUM: Enum = as_postgres_enum(Platform, "platform")
SOURCE_TYPE_ENUM: Enum = as_postgres_enum(SourceType, "source_type")
ACCOUNT_STATUS_ENUM: Enum = as_postgres_enum(AccountStatus, "account_status")
STEER_ACTION_TYPE_ENUM: Enum = as_postgres_enum(SteerActionType, "steer_action_type")
OPS_USER_ROLE_ENUM: Enum = as_postgres_enum(OpsUserRole, "ops_user_role")
CAMPAIGN_TYPE_ENUM: Enum = as_postgres_enum(CampaignType, "campaign_type")
ADVERTISEMENT_TYPE_ENUM: Enum = as_postgres_enum(
    AdvertisementType,
    "advertisement_type",
)
CAMPAIGN_STATUS_ENUM: Enum = as_postgres_enum(CampaignStatus, "campaign_status")
THEME_STATUS_ENUM: Enum = as_postgres_enum(ThemeStatus, "theme_status")
BACKGROUND_KIND_ENUM: Enum = as_postgres_enum(BackgroundKind, "background_kind")
THEME_ELEMENT_BAND_ENUM: Enum = as_postgres_enum(
    ThemeElementBand,
    "theme_element_band",
)
THEME_ELEMENT_CONTENT_KIND_ENUM: Enum = as_postgres_enum(
    ThemeElementContentKind,
    "theme_element_content_kind",
)
THEME_ELEMENT_TEXT_SOURCE_ENUM: Enum = as_postgres_enum(
    ThemeElementTextSource,
    "theme_element_text_source",
)
THEME_ELEMENT_ALIGNMENT_ENUM: Enum = as_postgres_enum(
    ThemeElementAlignment,
    "theme_element_alignment",
)
CONTENT_SOURCE_KIND_ENUM: Enum = as_postgres_enum(
    ContentSourceKind,
    "content_source_kind",
)
UNIT_IMAGE_MEDIA_TYPE_ENUM: Enum = as_postgres_enum(
    UnitImageMediaType,
    "unit_image_media_type",
)
UNIT_IMAGE_LICENSE_ENUM: Enum = as_postgres_enum(
    UnitImageLicense,
    "unit_image_license",
)
UNIT_IMAGE_INTAKE_ENUM: Enum = as_postgres_enum(
    UnitImageIntake,
    "unit_image_intake",
)
RESOURCE_FILE_MEDIA_TYPE_ENUM: Enum = as_postgres_enum(
    ResourceFileMediaType,
    "resource_file_media_type",
)
