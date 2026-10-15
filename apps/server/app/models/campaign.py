"""Campaign — marketing definition plus the theme and source it runs.

Start does not ingest or generate. Run assembles live units into
carousels and does not generate text.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    ADVERTISEMENT_TYPE_ENUM,
    CAMPAIGN_STATUS_ENUM,
    CAMPAIGN_TYPE_ENUM,
    AdvertisementType,
    CampaignStatus,
    CampaignType,
)


if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.content_source import ContentSource, Unit
    from app.models.ops_user import OpsUser
    from app.models.theme import Theme


class Campaign(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `campaigns`.

    Create stores a definition: name, unique slug/hashtag, type,
    carousel format, platforms JSON, and `ready` status. Accounts
    and Spotmu interests live on the join tables. A new campaign also
    stores the theme and the one source bound to that theme. Rows
    saved before that choice keep both empty. Creating a campaign
    does not ingest interests or generate text. Start / pause /
    resume / finish change status only. Run replaces ``carousels``.
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_campaigns_slug"),
        UniqueConstraint("hashtag", name="uq_campaigns_hashtag"),
        Index("ix_campaigns_created_by", "created_by"),
        Index("ix_campaigns_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    hashtag: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_type: Mapped[CampaignType] = mapped_column(
        CAMPAIGN_TYPE_ENUM,
        nullable=False,
    )
    advertisement_type: Mapped[AdvertisementType] = mapped_column(
        ADVERTISEMENT_TYPE_ENUM,
        nullable=False,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        CAMPAIGN_STATUS_ENUM,
        nullable=False,
        default=CampaignStatus.READY,
        server_default=CampaignStatus.READY.value,
    )
    platforms: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_users.id"),
        nullable=True,
    )
    theme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    created_by_user: Mapped["OpsUser | None"] = relationship(
        "OpsUser",
    )
    theme: Mapped["Theme | None"] = relationship("Theme")
    source: Mapped["ContentSource | None"] = relationship("ContentSource")
    carousels: Mapped[list["CampaignCarousel"]] = relationship(
        "CampaignCarousel",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignCarousel.position",
    )
    account_links: Mapped[list["CampaignAccount"]] = relationship(
        "CampaignAccount",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    interest_links: Mapped[list["CampaignInterest"]] = relationship(
        "CampaignInterest",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class CampaignAccount(Base):
    """Join row: campaign ↔ existing Twerva social account."""

    __tablename__ = "campaign_accounts"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "account_id",
            name="uq_campaign_accounts_campaign_id_account_id",
        ),
        Index("ix_campaign_accounts_campaign_id", "campaign_id"),
        Index("ix_campaign_accounts_account_id", "account_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    campaign: Mapped[Campaign] = relationship(
        "Campaign",
        back_populates="account_links",
    )
    account: Mapped["Account"] = relationship("Account")


class CampaignInterest(Base, UuidPrimaryKeyMixin):
    """Spotmu interest snapshot attached to a campaign (no ingest)."""

    __tablename__ = "campaign_interests"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "spotmu_slug",
            name="uq_campaign_interests_campaign_id_spotmu_slug",
        ),
        Index("ix_campaign_interests_campaign_id", "campaign_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    spotmu_slug: Mapped[str] = mapped_column(Text, nullable=False)
    spotmu_interest_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped[Campaign] = relationship(
        "Campaign",
        back_populates="interest_links",
    )


class CampaignCarousel(Base, UuidPrimaryKeyMixin):
    """One carousel from the latest run. Slides use the campaign theme."""

    __tablename__ = "campaign_carousels"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "position",
            name="uq_campaign_carousels_campaign_id_position",
        ),
        Index("ix_campaign_carousels_campaign_id", "campaign_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    campaign: Mapped[Campaign] = relationship(
        "Campaign",
        back_populates="carousels",
    )
    slides: Mapped[list["CampaignCarouselSlide"]] = relationship(
        "CampaignCarouselSlide",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="CampaignCarouselSlide.position",
    )


class CampaignCarouselSlide(Base, UuidPrimaryKeyMixin):
    """One live unit on a carousel, in frame order."""

    __tablename__ = "campaign_carousel_slides"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_campaign_carousel_slides_carousel_id_position",
        ),
        UniqueConstraint(
            "carousel_id",
            "unit_id",
            name="uq_campaign_carousel_slides_carousel_id_unit_id",
        ),
        Index("ix_campaign_carousel_slides_carousel_id", "carousel_id"),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_carousels.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    carousel: Mapped[CampaignCarousel] = relationship(
        "CampaignCarousel",
        back_populates="slides",
    )
    unit: Mapped["Unit"] = relationship("Unit")
