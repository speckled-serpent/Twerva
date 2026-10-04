"""ORM models for the Twerva Phase 1 domain.

UUID primary-key convention (1.2b-i)
------------------------------------
Every domain table uses a Postgres ``UUID`` primary key. The database
generates values with ``gen_random_uuid()`` (server default). Application
code may omit ``id`` on insert. The first domain migration enables the
``pgcrypto`` extension so the function exists on images that do not ship
it in core (PostgreSQL 13+ also provides ``gen_random_uuid()`` in core).

Closed vocabularies are native Postgres ENUM types. Allowed values and
``PostJobStatus`` / ``CampaignStatus`` transitions live in
``app.models.enums`` and ``docs/planning/domain_statuses.md``.
``ThemeStatus`` (``draft``, ``live``) is stored the same way.

Table class names follow the 1.2 task-sheet identifiers (``Brand``,
``SourceItem``, …) rather than the style-guide ``Our`` + plural form, so
Alembic, reports, and later API layers share one name per object.

Import this package (not only ``Base``) so ``Base.metadata`` includes every
table. Alembic ``env.py`` depends on that.
"""

from app.models.account import Account
from app.models.artifact import Artifact, ArtifactSlide
from app.models.base import Base
from app.models.brand import Brand
from app.models.campaign import Campaign, CampaignAccount, CampaignInterest
from app.models.cluster import Cluster, cluster_source_items
from app.models.enums import (
    ACCOUNT_STATUS_ENUM,
    ADVERTISEMENT_TYPE_ENUM,
    ARTIFACT_STATUS_ENUM,
    ARTIFACT_STATUS_TRANSITIONS,
    BACKGROUND_KIND_ENUM,
    CAMPAIGN_STATUS_ENUM,
    CAMPAIGN_STATUS_TRANSITIONS,
    CAMPAIGN_TYPE_ENUM,
    OPS_USER_ROLE_ENUM,
    PLATFORM_ENUM,
    POST_JOB_STATUS_ENUM,
    POST_JOB_STATUS_TRANSITIONS,
    SOURCE_TYPE_ENUM,
    STEER_ACTION_TYPE_ENUM,
    THEME_STATUS_ENUM,
    AccountStatus,
    AdvertisementType,
    ArtifactStatus,
    BackgroundKind,
    CampaignStatus,
    CampaignType,
    OpsUserRole,
    Platform,
    PostJobStatus,
    SourceType,
    SteerActionType,
    ThemeStatus,
)
from app.models.metric_snapshot import MetricSnapshot
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.models.source_item import SourceItem
from app.models.steer_action import SteerAction
from app.models.theme import Theme


__all__ = [
    "ACCOUNT_STATUS_ENUM",
    "ADVERTISEMENT_TYPE_ENUM",
    "ARTIFACT_STATUS_ENUM",
    "ARTIFACT_STATUS_TRANSITIONS",
    "BACKGROUND_KIND_ENUM",
    "Account",
    "AccountStatus",
    "AdvertisementType",
    "Artifact",
    "ArtifactSlide",
    "ArtifactStatus",
    "BackgroundKind",
    "Base",
    "Brand",
    "CAMPAIGN_STATUS_ENUM",
    "CAMPAIGN_STATUS_TRANSITIONS",
    "CAMPAIGN_TYPE_ENUM",
    "Campaign",
    "CampaignAccount",
    "CampaignInterest",
    "CampaignStatus",
    "CampaignType",
    "Cluster",
    "MetricSnapshot",
    "OPS_USER_ROLE_ENUM",
    "OpsUser",
    "OpsUserRole",
    "PLATFORM_ENUM",
    "POST_JOB_STATUS_ENUM",
    "POST_JOB_STATUS_TRANSITIONS",
    "Platform",
    "PostJob",
    "PostJobStatus",
    "SOURCE_TYPE_ENUM",
    "STEER_ACTION_TYPE_ENUM",
    "THEME_STATUS_ENUM",
    "SourceItem",
    "SourceType",
    "SteerAction",
    "SteerActionType",
    "Theme",
    "ThemeStatus",
    "cluster_source_items",
]
