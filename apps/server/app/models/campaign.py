"""Campaign — marketing definition (not started). No generate/publish."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint, text
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
    from app.models.ops_user import OpsUser


class Campaign(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in `campaigns`.

    Create stores a definition only: name, unique slug/hashtag, type,
    carousel format, platforms JSON, and `not_started` status. Accounts
    and Spotmu interests live on the join tables. Creating a campaign
    does not ingest interests or generate carousels.
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
        default=CampaignStatus.NOT_STARTED,
        server_default=CampaignStatus.NOT_STARTED.value,
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

    created_by_user: Mapped["OpsUser | None"] = relationship(
        "OpsUser",
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
