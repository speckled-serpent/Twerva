"""Content carousels: one kind of carousel, bound to a required skeleton.

A slide keeps its id, has a name, and points at most one album image.
Its text is one value per text element on that skeleton. Generated text
stays a draft until a person accepts it. ``slide_exclusions`` stores the
other slide ids it cannot be shown with. The carousel stores inspiration
and rules for that draft, and may point at the album its images came
from. Skeletons still store a concrete image path. They do not reference
these rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.album import Album, AlbumImage
from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    SLIDE_TEXT_STATUS_ENUM,
    SlideTextStatus,
)


CAROUSEL_NAME_CHECK_SQL: str = (
    "btrim(name) <> '' AND btrim(slug) <> ''"
)
SLIDE_POSITION_CHECK_SQL: str = "position >= 0"
SLIDE_NAME_CHECK_SQL: str = "btrim(name) <> ''"
SLIDE_FIELD_TEXT_CHECK_SQL: str = "btrim(label) <> '' AND btrim(value) <> ''"


class Carousel(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``carousels``. Every carousel requires one skeleton."""

    __tablename__ = "carousels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_carousels_slug"),
        CheckConstraint(CAROUSEL_NAME_CHECK_SQL, name="name"),
    )

    skeleton_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeletons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    inspiration: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    rules: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("albums.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    slides: Mapped[list["Slide"]] = relationship(
        "Slide",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="Slide.position",
    )
    album: Mapped[Album | None] = relationship("Album")


class Slide(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One piece of content inside a carousel. The id stays; the name is set."""

    __tablename__ = "slides"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_slides_carousel_id_position",
        ),
        CheckConstraint(SLIDE_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(SLIDE_NAME_CHECK_SQL, name="name"),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    text_status: Mapped[SlideTextStatus] = mapped_column(
        SLIDE_TEXT_STATUS_ENUM,
        nullable=False,
        default=SlideTextStatus.LIVE,
        server_default="live",
    )
    album_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("album_images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    carousel: Mapped[Carousel] = relationship("Carousel", back_populates="slides")
    element_texts: Mapped[list["SlideElementText"]] = relationship(
        "SlideElementText",
        back_populates="slide",
        cascade="all, delete-orphan",
    )
    album_image: Mapped[AlbumImage | None] = relationship(
        "AlbumImage",
        foreign_keys=[album_image_id],
    )
    exclusions: Mapped[list["SlideExclusion"]] = relationship(
        "SlideExclusion",
        foreign_keys="SlideExclusion.slide_id",
        back_populates="slide",
        cascade="all, delete-orphan",
    )

    @property
    def images(self) -> list[AlbumImage]:
        """The album image this slide points at, or an empty list.

        Slide reads still expose ``images`` so a slide has at most one
        image. The row itself lives on the album.
        """

        if self.album_image is None:

            return []

        return [self.album_image]

    @images.setter
    def images(self, rows: list[AlbumImage]) -> None:
        """Point the slide at the only image, or clear the pointer."""

        if len(rows) == 0:
            self.album_image = None
            self.album_image_id = None

            return

        self.album_image = rows[0]
        self.album_image_id = rows[0].id


class SlideExclusion(Base, UuidPrimaryKeyMixin):
    """One other slide this slide cannot be shown with.

    The pair is stored in both directions. Deleting either slide removes
    both rows because each foreign key cascades.
    """

    __tablename__ = "slide_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "slide_id",
            "excluded_slide_id",
            name="uq_slide_exclusions_slide_id_excluded_slide_id",
        ),
        CheckConstraint(
            "slide_id <> excluded_slide_id",
            name="not_self",
        ),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    excluded_slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    slide: Mapped[Slide] = relationship(
        "Slide",
        foreign_keys=[slide_id],
        back_populates="exclusions",
    )
    excluded_slide: Mapped[Slide] = relationship(
        "Slide",
        foreign_keys=[excluded_slide_id],
    )


class SlideElementText(Base, UuidPrimaryKeyMixin):
    """The text a slide stores for one skeleton text element."""

    __tablename__ = "slide_element_texts"
    __table_args__ = (
        UniqueConstraint(
            "slide_id",
            "skeleton_element_id",
            name="uq_slide_element_texts_slide_id_skeleton_element_id",
        ),
    )

    slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skeleton_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeleton_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    draft_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    slide: Mapped[Slide] = relationship("Slide", back_populates="element_texts")
