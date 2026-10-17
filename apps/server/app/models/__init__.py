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
``SkeletonStatus`` (``draft``, ``live``) is stored the same way.
``skeleton_elements`` stores band, content kind, Spotmu text source, and
alignment the same way. ``carousels`` require a skeleton. ``slides`` keep a
stable id and a name. ``slide_element_texts`` stores one value per skeleton
text element. ``slide_exclusions`` stores the other slide ids a slide
cannot be shown with. ``slides.text_status`` is ``live`` or ``draft``.
A draft is generated text that is not live until a person accepts it.
``carousels.inspiration`` and ``carousels.rules`` steer that draft.
``album_images`` holds the files. A slide points at most one of them.
A carousel may point at the album those images came from. A campaign
stores the skeleton and the carousel it runs. ``campaign_carousels`` is
the latest assembly of live slides on that skeleton.

Table class names follow the 1.2 task-sheet identifiers (``Brand``,
``SourceItem``, …) rather than the style-guide ``Our`` + plural form, so
Alembic, reports, and later API layers share one name per object.

Import this package (not only ``Base``) so ``Base.metadata`` includes every
table. Alembic ``env.py`` depends on that.
"""

from app.models.account import Account
from app.models.album import Album, AlbumImage
from app.models.artifact import Artifact, ArtifactSlide
from app.models.base import Base
from app.models.brand import Brand
from app.models.campaign import (
    Campaign,
    CampaignAccount,
    CampaignCarousel,
    CampaignCarouselSlide,
    CampaignInterest,
)
from app.models.cluster import Cluster, cluster_source_items
from app.models.carousel import (
    Carousel,
    Slide,
    SlideElementText,
    SlideExclusion,
)
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
    SKELETON_ELEMENT_ALIGNMENT_ENUM,
    SKELETON_ELEMENT_BAND_ENUM,
    SKELETON_ELEMENT_CONTENT_KIND_ENUM,
    SKELETON_ELEMENT_TEXT_SOURCE_ENUM,
    SKELETON_STATUS_ENUM,
    RESOURCE_FILE_MEDIA_TYPE_ENUM,
    SLIDE_IMAGE_INTAKE_ENUM,
    SLIDE_IMAGE_LICENSE_ENUM,
    SLIDE_IMAGE_MEDIA_TYPE_ENUM,
    SLIDE_TEXT_STATUS_ENUM,
    AccountStatus,
    AdvertisementType,
    ArtifactStatus,
    BackgroundKind,
    CampaignStatus,
    CampaignType,
    OpsUserRole,
    ResourceFileMediaType,
    Platform,
    PostJobStatus,
    SourceType,
    SteerActionType,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonElementTextSource,
    SkeletonStatus,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)
from app.models.metric_snapshot import MetricSnapshot
from app.models.ops_user import OpsUser
from app.models.post_job import PostJob
from app.models.source_item import SourceItem
from app.models.steer_action import SteerAction
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement


__all__ = [
    "ACCOUNT_STATUS_ENUM",
    "ADVERTISEMENT_TYPE_ENUM",
    "ARTIFACT_STATUS_ENUM",
    "ARTIFACT_STATUS_TRANSITIONS",
    "BACKGROUND_KIND_ENUM",
    "Account",
    "AccountStatus",
    "Album",
    "AlbumImage",
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
    "CampaignCarousel",
    "CampaignCarouselSlide",
    "CampaignInterest",
    "CampaignStatus",
    "CampaignType",
    "Cluster",
    "Carousel",
    "RESOURCE_FILE_MEDIA_TYPE_ENUM",
    "ResourceFileMediaType",
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
    "SKELETON_ELEMENT_ALIGNMENT_ENUM",
    "SKELETON_ELEMENT_BAND_ENUM",
    "SKELETON_ELEMENT_CONTENT_KIND_ENUM",
    "SKELETON_ELEMENT_TEXT_SOURCE_ENUM",
    "SKELETON_STATUS_ENUM",
    "SLIDE_IMAGE_INTAKE_ENUM",
    "SLIDE_IMAGE_LICENSE_ENUM",
    "SLIDE_IMAGE_MEDIA_TYPE_ENUM",
    "SLIDE_TEXT_STATUS_ENUM",
    "SourceItem",
    "SourceType",
    "Slide",
    "SlideElementText",
    "SlideExclusion",
    "SlideImageIntake",
    "SlideImageLicense",
    "SlideImageMediaType",
    "SlideTextStatus",
    "SteerAction",
    "SteerActionType",
    "Skeleton",
    "SkeletonElement",
    "SkeletonElementAlignment",
    "SkeletonElementBand",
    "SkeletonElementContentKind",
    "SkeletonElementTextSource",
    "SkeletonStatus",
    "cluster_source_items",
]
