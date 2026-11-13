"""Content carousels: one kind of carousel, bound to a required skeleton.

A slide keeps its id, has a name, and points at most one album image.
Its text is one value per text element on that skeleton. Generated text
stays a draft until a person accepts it. ``slide_exclusions`` stores the
other slide ids it cannot be shown with. The carousel may point at
the album its images came from. ``generation_number`` starts at 1.
``editor_step`` remembers Basic, Instructions, Content, or Slides. A
carousel created through the API opens on Basic.
Rows that already exist keep their stored step. Research attaches as
an ordered list in ``carousel_research_items``. There is no
``research_id`` column. Instruction documents live in
``carousel_instructions``: the current body and a position, with no
title and no version. Drafted slide text comes from those documents.
``slide_draft_batches`` is the review state for one press of Generate.
A slide may point at that batch. Deleting the batch does not delete
the slide. The table is not the phase 8 snapshot, and it is not
``campaign_carousels``. ``carousel_generations`` is that snapshot:
the instruction bodies, the album and the image ids it held, the
research title and body, and the slides. ``carousel_assemblies`` is
one Final assembly for a carousel and generation. It hangs on the
snapshot through ``generation_id`` and is not the snapshot itself.
Its child rows are the reviewed carousels and the frozen frames.
Deleting a slide or an album image clears the frame pointer and
leaves the frame.

Skeletons still store a concrete image path. They do not reference
these rows.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.album import Album, AlbumImage
from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.enums import (
    SLIDE_TEXT_STATUS_ENUM,
    SlideTextStatus,
)
from app.models.research_item import (
    RESEARCH_BODY_CHECK_SQL,
    RESEARCH_BODY_MAX_CHARACTERS,
    ResearchItem,
)


if TYPE_CHECKING:
    from app.models.campaign import CampaignPost


CAROUSEL_NAME_CHECK_SQL: str = (
    "btrim(name) <> '' AND btrim(slug) <> ''"
)
CAROUSEL_GENERATION_NUMBER_DEFAULT: int = 1
CAROUSEL_EDITOR_STEP_DEFAULT: int = 3
CAROUSEL_CREATE_EDITOR_STEP: int = 0
CAROUSEL_GENERATION_CHECK_SQL: str = "generation_number >= 1"
CAROUSEL_EDITOR_STEP_CHECK_SQL: str = "editor_step IN (0, 1, 2, 3)"
CAROUSEL_RESEARCH_POSITION_CHECK_SQL: str = "position >= 0"
CAROUSEL_INSTRUCTION_POSITION_CHECK_SQL: str = "position >= 0"
# Same cap as a research body: 1,000,000 characters.
INSTRUCTION_BODY_MAX_CHARACTERS: int = RESEARCH_BODY_MAX_CHARACTERS
CAROUSEL_INSTRUCTION_BODY_CHECK_SQL: str = (
    f"char_length(body) <= {INSTRUCTION_BODY_MAX_CHARACTERS}"
)
SLIDE_POSITION_CHECK_SQL: str = "position >= 0"
SLIDE_NAME_CHECK_SQL: str = "btrim(name) <> ''"
SLIDE_FIELD_TEXT_CHECK_SQL: str = "btrim(label) <> '' AND btrim(value) <> ''"
SLIDE_DRAFT_BATCH_STATUS_CHECK_SQL: str = (
    "status IN ('pending', 'accepted', 'discarded')"
)
SLIDE_DRAFT_BATCH_SLIDE_COUNT_CHECK_SQL: str = "slide_count >= 1"
CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL: str = "generation_number >= 1"
CAROUSEL_ASSEMBLY_SLIDE_COUNT_CHECK_SQL: str = "slide_count >= 1"
ASSEMBLED_CAROUSEL_STATUS_CHECK_SQL: str = "status = 'draft'"
ASSEMBLED_POSITION_CHECK_SQL: str = "position >= 0"
ASSEMBLED_FRAME_BLOCK_REASON_CHECK_SQL: str = (
    "block_reason IS NULL OR block_reason IN "
    "('overlap', 'missing_asset', 'measure_error')"
)
CAROUSEL_GENERATION_POSITION_CHECK_SQL: str = "position >= 0"
CAROUSEL_GENERATION_SLIDE_NAME_CHECK_SQL: str = "btrim(name) <> ''"
CAROUSEL_GENERATION_EXCLUSION_NOT_SELF_CHECK_SQL: str = (
    "generation_slide_id <> excluded_generation_slide_id"
)


class Carousel(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Row in ``carousels``. Every carousel requires one skeleton.

    ``generation_number`` starts at 1. ``editor_step`` is 0 Basic, 1
    Instructions, 2 Content, or 3 Slides. The column default stays on
    Slides. Create stores Basic. ``carousel_editor_step_instructions``
    allows storing Instructions. ``carousel_editor_step_content`` moves
    a carousel to Content when its skeleton needs a picture and no album
    is attached.
    Default stays on Slides. The skeleton stays the one chosen at create.
    ``instructions`` is the current documents, ordered by position.
    Drafted slide text comes from those documents. ``draft_batches``
    records each press of Generate: pending review, accepted, or
    discarded. One carousel holds one pending set. ``generations`` is
    the snapshot of each generation. ``assemblies`` is the Final
    assembly for each generation. One generation holds one assembly.
    """

    __tablename__ = "carousels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_carousels_slug"),
        CheckConstraint(CAROUSEL_NAME_CHECK_SQL, name="name"),
        CheckConstraint(CAROUSEL_GENERATION_CHECK_SQL, name="generation_number"),
        CheckConstraint(CAROUSEL_EDITOR_STEP_CHECK_SQL, name="editor_step"),
    )

    skeleton_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skeletons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("albums.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generation_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=CAROUSEL_GENERATION_NUMBER_DEFAULT,
        server_default=str(CAROUSEL_GENERATION_NUMBER_DEFAULT),
    )
    editor_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=CAROUSEL_EDITOR_STEP_DEFAULT,
        server_default=str(CAROUSEL_EDITOR_STEP_DEFAULT),
    )

    slides: Mapped[list["Slide"]] = relationship(
        "Slide",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="Slide.position",
    )
    album: Mapped[Album | None] = relationship("Album")
    research_links: Mapped[list["CarouselResearchItem"]] = relationship(
        "CarouselResearchItem",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="CarouselResearchItem.position",
    )
    instructions: Mapped[list["CarouselInstruction"]] = relationship(
        "CarouselInstruction",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="CarouselInstruction.position",
    )
    draft_batches: Mapped[list["SlideDraftBatch"]] = relationship(
        "SlideDraftBatch",
        back_populates="carousel",
        cascade="all, delete-orphan",
    )
    assemblies: Mapped[list["CarouselAssembly"]] = relationship(
        "CarouselAssembly",
        back_populates="carousel",
        cascade="all, delete-orphan",
    )
    generations: Mapped[list["CarouselGeneration"]] = relationship(
        "CarouselGeneration",
        back_populates="carousel",
        cascade="all, delete-orphan",
        order_by="CarouselGeneration.generation_number",
    )


class SlideDraftBatch(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One generated set, waiting for review or already settled.

    ``status`` is ``pending``, ``accepted``, or ``discarded``. One
    carousel holds one pending row. ``slide_count`` is the count that
    press asked for. Deleting the carousel removes the row. Deleting
    the row does not delete the slides that point at it. This is the
    review state for one press of Generate. It is not the phase 8
    snapshot, and it is not ``campaign_carousels``.
    """

    __tablename__ = "slide_draft_batches"
    __table_args__ = (
        CheckConstraint(SLIDE_DRAFT_BATCH_STATUS_CHECK_SQL, name="status"),
        CheckConstraint(SLIDE_DRAFT_BATCH_SLIDE_COUNT_CHECK_SQL, name="slide_count"),
        Index(
            "uq_slide_draft_batches_one_pending_carousel",
            "carousel_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)

    carousel: Mapped[Carousel] = relationship(
        "Carousel",
        back_populates="draft_batches",
    )
    slides: Mapped[list["Slide"]] = relationship(
        "Slide",
        back_populates="draft_batch",
    )


class CarouselAssembly(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One Final assembly for a carousel and generation.

    ``generation_number`` is the carousel's generation at assemble time.
    ``generation_id`` hangs this row on that generation's snapshot.
    One carousel holds one row per generation, so a later generation
    can keep this row without copying frames. ``slide_count`` is the
    cap drawn for that assemble. Deleting the carousel removes the row.
    Deleting the generation is refused while this row still points at
    it. This is not a generation snapshot, and it is not
    ``campaign_carousels``.
    """

    __tablename__ = "carousel_assemblies"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "generation_number",
            name="uq_carousel_assemblies_carousel_id_generation_number",
        ),
        CheckConstraint(
            CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
            name="generation_number",
        ),
        CheckConstraint(
            CAROUSEL_ASSEMBLY_SLIDE_COUNT_CHECK_SQL,
            name="slide_count",
        ),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generations.id",
            name="fk_carousel_assemblies_generation_id_carousel_generations",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    )
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)

    carousel: Mapped[Carousel] = relationship(
        "Carousel",
        back_populates="assemblies",
    )
    generation: Mapped["CarouselGeneration"] = relationship(
        "CarouselGeneration",
        back_populates="assembly",
    )
    assembled_carousels: Mapped[list["AssembledCarousel"]] = relationship(
        "AssembledCarousel",
        back_populates="assembly",
        cascade="all, delete-orphan",
        order_by="AssembledCarousel.position",
    )


class CarouselGeneration(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One snapshot of a carousel generation.

    ``generation_number`` matches ``carousels.generation_number`` for
    the generation this row froze. ``album_id`` is the album attached
    then. Image ids, instruction bodies, research copies, and slides
    live on the child tables. Deleting the carousel removes this row.
    An assembly that still points here refuses that delete.
    """

    __tablename__ = "carousel_generations"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "generation_number",
            name="uq_carousel_generations_carousel_id_generation_number",
        ),
        CheckConstraint(
            CAROUSEL_ASSEMBLY_GENERATION_CHECK_SQL,
            name="generation_number",
        ),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousels.id",
            name="fk_carousel_generations_carousel_id_carousels",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    generation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "albums.id",
            name="fk_carousel_generations_album_id_albums",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    carousel: Mapped[Carousel] = relationship(
        "Carousel",
        back_populates="generations",
    )
    instructions: Mapped[list["CarouselGenerationInstruction"]] = relationship(
        "CarouselGenerationInstruction",
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="CarouselGenerationInstruction.position",
    )
    research_items: Mapped[list["CarouselGenerationResearch"]] = relationship(
        "CarouselGenerationResearch",
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="CarouselGenerationResearch.position",
    )
    images: Mapped[list["CarouselGenerationImage"]] = relationship(
        "CarouselGenerationImage",
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="CarouselGenerationImage.position",
    )
    slides: Mapped[list["CarouselGenerationSlide"]] = relationship(
        "CarouselGenerationSlide",
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="CarouselGenerationSlide.position",
    )
    assembly: Mapped["CarouselAssembly | None"] = relationship(
        "CarouselAssembly",
        back_populates="generation",
        uselist=False,
    )


class CarouselGenerationInstruction(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One copied instruction body on a generation.

    ``body`` is the text at snapshot time, including an empty string.
    There is no title and no version. Deleting the generation removes
    this row.
    """

    __tablename__ = "carousel_generation_instructions"
    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_instructions_generation_id_position",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_POSITION_CHECK_SQL,
            name="position",
        ),
        CheckConstraint(
            CAROUSEL_INSTRUCTION_BODY_CHECK_SQL,
            name="body",
        ),
    )

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generations.id",
            name="fk_cgen_instructions_generation_id_cgen",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    generation: Mapped[CarouselGeneration] = relationship(
        "CarouselGeneration",
        back_populates="instructions",
    )


class CarouselGenerationResearch(Base, UuidPrimaryKeyMixin):
    """One copied research document on a generation.

    ``title`` and ``body`` are the library text at snapshot time.
    ``research_item_id`` clears when that library row is deleted, and
    the copied title and body stay. Deleting the generation removes
    this row.
    """

    __tablename__ = "carousel_generation_research"
    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_research_generation_id_position",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_POSITION_CHECK_SQL,
            name="position",
        ),
        CheckConstraint(RESEARCH_BODY_CHECK_SQL, name="body"),
    )

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generations.id",
            name="fk_cgen_research_generation_id_cgen",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    research_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "research_items.id",
            name="fk_cgen_research_research_item_id_research_items",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    generation: Mapped[CarouselGeneration] = relationship(
        "CarouselGeneration",
        back_populates="research_items",
    )


class CarouselGenerationImage(Base, UuidPrimaryKeyMixin):
    """One album image id copied onto a generation.

    The bytes stay on the album. Deleting the image clears
    ``album_image_id`` and leaves this position. Deleting the
    generation removes this row.
    """

    __tablename__ = "carousel_generation_images"
    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_images_generation_id_position",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_POSITION_CHECK_SQL,
            name="position",
        ),
    )

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generations.id",
            name="fk_cgen_images_generation_id_cgen",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    album_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "album_images.id",
            name="fk_cgen_images_album_image_id_album_images",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    generation: Mapped[CarouselGeneration] = relationship(
        "CarouselGeneration",
        back_populates="images",
    )


class CarouselGenerationSlide(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One copied slide on a generation.

    ``source_slide_id`` is the working slide this row was copied from.
    Deleting that slide clears the pointer and leaves this row.
    ``text_status`` is ``draft`` or ``live``. There is no
    ``draft_batch_id``. Deleting the generation removes this row.
    """

    __tablename__ = "carousel_generation_slides"
    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "position",
            name="uq_carousel_generation_slides_generation_id_position",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_POSITION_CHECK_SQL,
            name="position",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_SLIDE_NAME_CHECK_SQL,
            name="name",
        ),
    )

    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generations.id",
            name="fk_cgen_slides_generation_id_cgen",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    text_status: Mapped[SlideTextStatus] = mapped_column(
        SLIDE_TEXT_STATUS_ENUM,
        nullable=False,
    )
    album_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "album_images.id",
            name="fk_cgen_slides_album_image_id_album_images",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    source_slide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "slides.id",
            name="fk_cgen_slides_source_slide_id_slides",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    generation: Mapped[CarouselGeneration] = relationship(
        "CarouselGeneration",
        back_populates="slides",
    )
    texts: Mapped[list["CarouselGenerationSlideText"]] = relationship(
        "CarouselGenerationSlideText",
        back_populates="generation_slide",
        cascade="all, delete-orphan",
    )
    exclusions: Mapped[list["CarouselGenerationSlideExclusion"]] = relationship(
        "CarouselGenerationSlideExclusion",
        foreign_keys="CarouselGenerationSlideExclusion.generation_slide_id",
        back_populates="generation_slide",
        cascade="all, delete-orphan",
    )


class CarouselGenerationSlideText(Base, UuidPrimaryKeyMixin):
    """Copied text for one skeleton element on a generation slide.

    ``skeleton_element_id`` is stored without a foreign key, so
    deleting the element does not remove a previous generation's text.
    ``value`` is the live copy. ``draft_value`` is the unaccepted copy.
    """

    __tablename__ = "carousel_generation_slide_texts"
    __table_args__ = (
        UniqueConstraint(
            "generation_slide_id",
            "skeleton_element_id",
            name="uq_cgen_slide_texts_slide_id_element_id",
        ),
    )

    generation_slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generation_slides.id",
            name="fk_cgen_slide_texts_generation_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    skeleton_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    draft_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    generation_slide: Mapped[CarouselGenerationSlide] = relationship(
        "CarouselGenerationSlide",
        back_populates="texts",
    )


class CarouselGenerationSlideExclusion(Base, UuidPrimaryKeyMixin):
    """One other generation slide this snapshot slide cannot be shown with.

    The pair is stored in both directions. Deleting either snapshot
    slide removes both rows.
    """

    __tablename__ = "carousel_generation_slide_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "generation_slide_id",
            "excluded_generation_slide_id",
            name="uq_cgen_slide_exclusions_pair",
        ),
        CheckConstraint(
            CAROUSEL_GENERATION_EXCLUSION_NOT_SELF_CHECK_SQL,
            name="not_self",
        ),
        Index(
            "ix_cgen_slide_exclusions_generation_slide_id",
            "generation_slide_id",
        ),
        Index(
            "ix_cgen_slide_exclusions_excluded_slide_id",
            "excluded_generation_slide_id",
        ),
    )

    generation_slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generation_slides.id",
            name="fk_cgen_slide_exclusions_generation_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    excluded_generation_slide_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "carousel_generation_slides.id",
            name="fk_cgen_slide_exclusions_excluded_slide_id_cgen_slides",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    generation_slide: Mapped[CarouselGenerationSlide] = relationship(
        "CarouselGenerationSlide",
        foreign_keys=[generation_slide_id],
        back_populates="exclusions",
    )
    excluded_generation_slide: Mapped[CarouselGenerationSlide] = relationship(
        "CarouselGenerationSlide",
        foreign_keys=[excluded_generation_slide_id],
    )


class AssembledCarousel(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One carousel an operator reviews, inside one assembly.

    ``status`` is ``draft``. ``caption`` and ``cta_url`` may be empty.
    There is no hashtag column. Deleting the assembly removes the row.
    """

    __tablename__ = "assembled_carousels"
    __table_args__ = (
        UniqueConstraint(
            "assembly_id",
            "position",
            name="uq_assembled_carousels_assembly_id_position",
        ),
        CheckConstraint(ASSEMBLED_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(ASSEMBLED_CAROUSEL_STATUS_CHECK_SQL, name="status"),
    )

    assembly_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousel_assemblies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    assembly: Mapped[CarouselAssembly] = relationship(
        "CarouselAssembly",
        back_populates="assembled_carousels",
    )
    frames: Mapped[list["AssembledCarouselFrame"]] = relationship(
        "AssembledCarouselFrame",
        back_populates="assembled_carousel",
        cascade="all, delete-orphan",
        order_by="AssembledCarouselFrame.position",
    )
    campaign_posts: Mapped[list["CampaignPost"]] = relationship(
        "CampaignPost",
        back_populates="assembled_carousel",
    )


class AssembledCarouselFrame(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One frozen frame inside an assembled carousel.

    ``asset_ref`` is the PNG under the artifact store. ``slide_id`` and
    ``album_image_id`` are the sources used to draw it. Deleting either
    source clears that pointer and leaves this row. ``blocked`` is true
    when the skeleton could not draw a shippable frame. ``block_reason``
    is ``overlap``, ``missing_asset``, or ``measure_error``.
    """

    __tablename__ = "assembled_carousel_frames"
    __table_args__ = (
        UniqueConstraint(
            "assembled_carousel_id",
            "position",
            name="uq_assembled_carousel_frames_assembled_carousel_id_position",
        ),
        CheckConstraint(ASSEMBLED_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(
            ASSEMBLED_FRAME_BLOCK_REASON_CHECK_SQL,
            name="block_reason",
        ),
    )

    assembled_carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "assembled_carousels.id",
            name="fk_frames_assembled_carousel_id_assembled_carousels",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    slide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slides.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    album_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("album_images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_ref: Mapped[str] = mapped_column(Text, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    assembled_carousel: Mapped[AssembledCarousel] = relationship(
        "AssembledCarousel",
        back_populates="frames",
    )
    slide: Mapped["Slide | None"] = relationship(
        "Slide",
        back_populates="assembled_frames",
    )
    album_image: Mapped[AlbumImage | None] = relationship(
        "AlbumImage",
        foreign_keys=[album_image_id],
    )


class Slide(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One piece of content inside a carousel. The id stays; the name is set.

    ``draft_batch_id`` points at the generated set from one press of
    Generate, when this slide belongs to that set. Clearing the batch
    leaves the slide. ``text_status`` stays ``draft`` or ``live``, and
    the server default stays ``live``.
    """

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
    draft_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slide_draft_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    carousel: Mapped[Carousel] = relationship("Carousel", back_populates="slides")
    draft_batch: Mapped[SlideDraftBatch | None] = relationship(
        "SlideDraftBatch",
        back_populates="slides",
    )
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
    assembled_frames: Mapped[list[AssembledCarouselFrame]] = relationship(
        "AssembledCarouselFrame",
        back_populates="slide",
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


class CarouselResearchItem(Base, UuidPrimaryKeyMixin):
    """One research document attached to a carousel, in order.

    The pair is unique. ``position`` is unique inside the carousel and
    starts at zero. Deleting the carousel or the research item removes
    this row. The carousel has no ``research_id`` column.
    """

    __tablename__ = "carousel_research_items"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "research_item_id",
            name="uq_carousel_research_items_carousel_id_research_item_id",
        ),
        UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_carousel_research_items_carousel_id_position",
        ),
        CheckConstraint(CAROUSEL_RESEARCH_POSITION_CHECK_SQL, name="position"),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    research_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    carousel: Mapped[Carousel] = relationship(
        "Carousel",
        back_populates="research_links",
    )
    research_item: Mapped[ResearchItem] = relationship("ResearchItem")


class CarouselInstruction(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """One instruction document on a carousel, in order.

    ``position`` starts at zero and is unique inside the carousel.
    ``body`` is the current text, including an empty string. There is
    no title and no version. Deleting the carousel removes this row.
    """

    __tablename__ = "carousel_instructions"
    __table_args__ = (
        UniqueConstraint(
            "carousel_id",
            "position",
            name="uq_carousel_instructions_carousel_id_position",
        ),
        CheckConstraint(CAROUSEL_INSTRUCTION_POSITION_CHECK_SQL, name="position"),
        CheckConstraint(CAROUSEL_INSTRUCTION_BODY_CHECK_SQL, name="body"),
    )

    carousel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carousels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    carousel: Mapped[Carousel] = relationship(
        "Carousel",
        back_populates="instructions",
    )
