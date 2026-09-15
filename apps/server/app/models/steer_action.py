"""Steer action — append-only cluster decision (kill/pause/double_down/resume)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UuidPrimaryKeyMixin
from app.models.enums import STEER_ACTION_TYPE_ENUM, SteerActionType


if TYPE_CHECKING:
    from app.models.cluster import Cluster


class SteerAction(Base, UuidPrimaryKeyMixin):
    """Row in `steer_actions`.

    `action` is a native Postgres ENUM (`steer_action_type`) whose values
    are `kill`, `pause`, `double_down`, `resume` — the same closed set
    1.2j-i listed as a check constraint. No updated_at: steer rows are
    append-only for MVP. `created_by` is freeform (`human`, agent name).
    HTTP create is `POST /api/v1/clusters/{id}/steer` (1.7c).
    """

    __tablename__ = "steer_actions"
    __table_args__ = (
        Index("ix_steer_actions_cluster_id", "cluster_id"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id"),
        nullable=False,
    )
    action: Mapped[SteerActionType] = mapped_column(
        STEER_ACTION_TYPE_ENUM,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    cluster: Mapped["Cluster"] = relationship(
        "Cluster",
        back_populates="steer_actions",
    )
