"""Replace the current generation snapshot from the working rows."""

from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.carousels.editing import new_row_id
from app.carousels.generations import replace_current_generation_snapshot
from app.models.album import Album, AlbumImage
from app.models.artifact import Artifact
from app.models.campaign import CampaignCarousel
from app.models.carousel import (
    Carousel,
    CarouselGeneration,
    CarouselGenerationInstruction,
    CarouselGenerationSlide,
    CarouselGenerationSlideText,
    CarouselInstruction,
    CarouselResearchItem,
    Slide,
    SlideDraftBatch,
    SlideElementText,
    SlideExclusion,
)
from app.models.enums import (
    AdvertisementType,
    BackgroundKind,
    SkeletonElementAlignment,
    SkeletonElementBand,
    SkeletonElementContentKind,
    SkeletonStatus,
    SlideImageIntake,
    SlideImageLicense,
    SlideImageMediaType,
    SlideTextStatus,
)
from app.models.research_item import ResearchItem
from app.models.skeleton import Skeleton
from app.models.skeleton_element import SkeletonElement
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
OLDER_BODY: str = "Older line"
BLANK_BODY: str = ""
KEPT_BODY: str = "Keep the harbor."
STALE_BODY: str = "Wrong"
LIVE_VALUE: str = "Reviewed line"
DRAFT_VALUE: str = "Unreviewed line"
FIRST_RESEARCH_TITLE: str = "Tides"
FIRST_RESEARCH_BODY: str = "The water is cold."
SECOND_RESEARCH_TITLE: str = "Quay"
SECOND_RESEARCH_BODY: str = "The stones are wet."


def _postgres_available() -> bool:
    """Return whether the local Postgres admin database accepts a connection."""

    admin_engine: Engine | None = None

    try:
        admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:

        return False
    else:

        return True
    finally:

        if admin_engine is not None:
            admin_engine.dispose()


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for generation tests")
class ReplaceCurrentGenerationSnapshotTests(unittest.TestCase):
    """The current snapshot matches the working rows. An older generation stays."""

    def setUp(self) -> None:
        """Create an empty database at the current head."""

        self.database_name: str = f"twerva_genrep_{uuid.uuid4().hex[:10]}"
        self.database_url: str = (
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/"
            f"{self.database_name}"
        )
        self.previous_database_url: str | None = os.environ.get("DATABASE_URL")
        self.admin_engine: Engine = create_engine(
            ADMIN_DATABASE_URL,
            isolation_level="AUTOCOMMIT",
        )

        with self.admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{self.database_name}"'))

        os.environ["DATABASE_URL"] = self.database_url
        clear_settings_cache()
        self.database_engine: Engine = create_engine(self.database_url)
        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))
        command.upgrade(alembic_config, "head")

    def tearDown(self) -> None:
        """Drop the empty database and restore the previous URL."""

        clear_settings_cache()
        self.database_engine.dispose()

        if self.previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self.previous_database_url

        clear_settings_cache()

        with self.admin_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": self.database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{self.database_name}"'))

        self.admin_engine.dispose()

    def test_replace_copies_the_working_rows_and_leaves_the_other_generation(self) -> None:
        """Generation 1 matches the carousel. Generation 2 keeps its own body."""

        with Session(self.database_engine) as session:
            element: SkeletonElement = self._text_element(session)
            carousel: Carousel = self._full_carousel(session, element)
            older: CarouselGeneration = self._older_generation(session, carousel)
            self._stale_current_generation(session, carousel)
            empty: Carousel = self._empty_carousel(session, element.skeleton_id)
            self._stale_current_generation(session, empty)
            before_counts: tuple[int, int, int] = self._foreign_counts(session)
            working_slide_ids: set[uuid.UUID] = {slide.id for slide in list(carousel.slides)}
            session.commit()
            carousel_id: uuid.UUID = carousel.id
            empty_id: uuid.UUID = empty.id
            older_id: uuid.UUID = older.id

        with Session(self.database_engine) as session:
            replace_current_generation_snapshot(carousel_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_full_snapshot(session, carousel_id)
            self._assert_older_generation(session, older_id)
            self.assertEqual(self._working_slide_ids(session, carousel_id), working_slide_ids)
            self.assertEqual(self._generation_number(session, carousel_id), 1)
            self.assertEqual(self._foreign_counts(session), before_counts)
            replace_current_generation_snapshot(carousel_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_full_snapshot(session, carousel_id)
            self._assert_older_generation(session, older_id)
            self.assertEqual(self._working_slide_ids(session, carousel_id), working_slide_ids)
            replace_current_generation_snapshot(empty_id, session)
            session.commit()

        with Session(self.database_engine) as session:
            self._assert_empty_snapshot(session, empty_id)
            self._assert_older_generation(session, older_id)
            self._assert_full_snapshot(session, carousel_id)
            self.assertEqual(self._foreign_counts(session), before_counts)

    def _assert_full_snapshot(self, session: Session, carousel_id: uuid.UUID) -> None:
        """The current snapshot matches the two documents, images, and slides."""

        carousel: Carousel = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = self._current_generation(session, carousel)
        bodies: list[str] = [
            instruction.body
            for instruction in sorted(list(generation.instructions), key=_position)
        ]
        research_rows: list[tuple[str, str]] = [
            (research.title, research.body)
            for research in sorted(list(generation.research_items), key=_position)
        ]
        image_ids: list[uuid.UUID | None] = [
            image.album_image_id
            for image in sorted(list(generation.images), key=_position)
        ]
        album_image_ids: list[uuid.UUID] = [
            image.id for image in sorted(list(carousel.album.images), key=_position)
        ]
        slides: list[CarouselGenerationSlideView] = [
            _slide_view(slide)
            for slide in sorted(list(generation.slides), key=_position)
        ]
        exclusion_pairs: set[tuple[uuid.UUID | None, uuid.UUID | None]] = set()

        for slide in list(generation.slides):

            for exclusion in list(slide.exclusions):
                exclusion_pairs.add((
                    slide.source_slide_id,
                    exclusion.excluded_generation_slide.source_slide_id,
                ))

        self.assertEqual(generation.album_id, carousel.album_id)
        self.assertEqual(bodies, [BLANK_BODY, KEPT_BODY])
        self.assertEqual(
            research_rows,
            [
                (FIRST_RESEARCH_TITLE, FIRST_RESEARCH_BODY),
                (SECOND_RESEARCH_TITLE, SECOND_RESEARCH_BODY),
            ],
        )
        self.assertEqual(image_ids, album_image_ids)
        self.assertEqual(len(slides), 2)
        self.assertEqual(slides[0].name, "Quay")
        self.assertEqual(slides[0].text_status, SlideTextStatus.LIVE)
        self.assertEqual(slides[0].value, LIVE_VALUE)
        self.assertIsNone(slides[0].draft_value)
        self.assertEqual(slides[0].album_image_id, album_image_ids[0])
        self.assertEqual(slides[1].name, "Draft quay")
        self.assertEqual(slides[1].text_status, SlideTextStatus.DRAFT)
        self.assertEqual(slides[1].value, "")
        self.assertEqual(slides[1].draft_value, DRAFT_VALUE)
        self.assertEqual(slides[1].album_image_id, album_image_ids[1])
        self.assertEqual(
            exclusion_pairs,
            {
                (slides[0].source_slide_id, slides[1].source_slide_id),
                (slides[1].source_slide_id, slides[0].source_slide_id),
            },
        )
        self.assertEqual(len(list(carousel.instructions)), 2)
        self.assertEqual(len(list(carousel.research_links)), 2)
        self.assertEqual(len(list(carousel.album.images)), 2)

    def _assert_empty_snapshot(self, session: Session, carousel_id: uuid.UUID) -> None:
        """A carousel with no album and no research stores empty child lists."""

        carousel: Carousel = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation: CarouselGeneration = self._current_generation(session, carousel)

        self.assertIsNone(carousel.album_id)
        self.assertIsNone(generation.album_id)
        self.assertEqual(list(generation.instructions), [])
        self.assertEqual(list(generation.research_items), [])
        self.assertEqual(list(generation.images), [])
        self.assertEqual(list(generation.slides), [])
        self.assertEqual(carousel.generation_number, 1)

    def _assert_older_generation(self, session: Session, generation_id: uuid.UUID) -> None:
        """Generation 2 still has the body it was given."""

        generation: CarouselGeneration | None = session.get(CarouselGeneration, generation_id)

        self.assertIsNotNone(generation)
        assert generation is not None
        bodies: list[str] = [instruction.body for instruction in list(generation.instructions)]

        self.assertEqual(generation.generation_number, 2)
        self.assertEqual(bodies, [OLDER_BODY])

    def _full_carousel(self, session: Session, element: SkeletonElement) -> Carousel:
        """Store two of each working row, including one blank instruction."""

        album: Album = Album(id=new_row_id(), name="Harbor", slug=f"harbor-{uuid.uuid4().hex[:8]}")
        first_image: AlbumImage = _album_image(album.id, 0, "albums/generation-probe-a.png")
        second_image: AlbumImage = _album_image(album.id, 1, "albums/generation-probe-b.png")
        album.images = [first_image, second_image]
        first_research: ResearchItem = ResearchItem(
            id=new_row_id(),
            title=FIRST_RESEARCH_TITLE,
            slug=f"tides-{uuid.uuid4().hex[:8]}",
            body=FIRST_RESEARCH_BODY,
        )
        second_research: ResearchItem = ResearchItem(
            id=new_row_id(),
            title=SECOND_RESEARCH_TITLE,
            slug=f"quay-{uuid.uuid4().hex[:8]}",
            body=SECOND_RESEARCH_BODY,
        )
        carousel: Carousel = Carousel(
            id=new_row_id(),
            skeleton_id=element.skeleton_id,
            name="Harbor",
            slug=f"harbor-{uuid.uuid4().hex[:8]}",
            album_id=album.id,
            generation_number=1,
            editor_step=3,
        )
        carousel.album = album
        carousel.instructions = [
            CarouselInstruction(
                id=new_row_id(),
                carousel_id=carousel.id,
                position=0,
                body=BLANK_BODY,
            ),
            CarouselInstruction(
                id=new_row_id(),
                carousel_id=carousel.id,
                position=1,
                body=KEPT_BODY,
            ),
        ]
        carousel.research_links = [
            CarouselResearchItem(
                id=new_row_id(),
                carousel_id=carousel.id,
                research_item_id=first_research.id,
                position=0,
            ),
            CarouselResearchItem(
                id=new_row_id(),
                carousel_id=carousel.id,
                research_item_id=second_research.id,
                position=1,
            ),
        ]
        carousel.research_links[0].research_item = first_research
        carousel.research_links[1].research_item = second_research
        live_slide: Slide = _slide(
            carousel.id,
            0,
            "Quay",
            SlideTextStatus.LIVE,
            first_image.id,
        )
        draft_slide: Slide = _slide(
            carousel.id,
            1,
            "Draft quay",
            SlideTextStatus.DRAFT,
            second_image.id,
        )
        live_slide.element_texts = [
            _element_text(live_slide.id, element.id, LIVE_VALUE, None),
        ]
        draft_slide.element_texts = [
            _element_text(draft_slide.id, element.id, "", DRAFT_VALUE),
        ]
        live_slide.exclusions = [
            SlideExclusion(
                id=new_row_id(),
                slide_id=live_slide.id,
                excluded_slide_id=draft_slide.id,
            ),
        ]
        draft_slide.exclusions = [
            SlideExclusion(
                id=new_row_id(),
                slide_id=draft_slide.id,
                excluded_slide_id=live_slide.id,
            ),
        ]
        carousel.slides = [live_slide, draft_slide]
        session.add(album)
        session.add(first_research)
        session.add(second_research)
        session.add(carousel)
        session.flush()

        return carousel

    def _empty_carousel(self, session: Session, skeleton_id: uuid.UUID) -> Carousel:
        """Store a carousel with no album, research, instructions, or slides."""

        carousel: Carousel = Carousel(
            id=new_row_id(),
            skeleton_id=skeleton_id,
            name="Empty",
            slug=f"empty-{uuid.uuid4().hex[:8]}",
            album_id=None,
            generation_number=1,
            editor_step=0,
        )
        session.add(carousel)
        session.flush()

        return carousel

    def _older_generation(self, session: Session, carousel: Carousel) -> CarouselGeneration:
        """Insert generation 2 with a body the replace must not change."""

        generation: CarouselGeneration = CarouselGeneration(
            id=new_row_id(),
            carousel_id=carousel.id,
            generation_number=2,
            album_id=None,
        )
        generation.instructions = [
            CarouselGenerationInstruction(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                body=OLDER_BODY,
            ),
        ]
        carousel.generations.append(generation)
        session.add(generation)
        session.flush()

        return generation

    def _stale_current_generation(self, session: Session, carousel: Carousel) -> None:
        """Put a wrong body on generation 1 so replace has to delete it."""

        generation: CarouselGeneration = CarouselGeneration(
            id=new_row_id(),
            carousel_id=carousel.id,
            generation_number=1,
            album_id=None,
        )
        generation.instructions = [
            CarouselGenerationInstruction(
                id=new_row_id(),
                generation_id=generation.id,
                position=0,
                body=STALE_BODY,
            ),
        ]
        carousel.generations.append(generation)
        session.add(generation)
        session.flush()

    def _text_element(self, session: Session) -> SkeletonElement:
        """Store one text element the slide texts can point at."""

        skeleton: Skeleton = Skeleton(
            id=new_row_id(),
            name="Probe paper",
            slug=f"probe-paper-{uuid.uuid4().hex[:8]}",
            advertisement_type=AdvertisementType.CAROUSEL,
            status=SkeletonStatus.DRAFT,
            background_kind=BackgroundKind.COLOR,
        )
        element: SkeletonElement = SkeletonElement(
            id=new_row_id(),
            skeleton_id=skeleton.id,
            band=SkeletonElementBand.MIDDLE,
            sort_order=0,
            content_kind=SkeletonElementContentKind.TEXT,
            name="Claim",
            font_family="Georgia",
            font_size=48,
            font_color="#111111",
            alignment=SkeletonElementAlignment.LEFT,
        )
        skeleton.elements = [element]
        session.add(skeleton)
        session.flush()

        return element

    def _current_generation(self, session: Session, carousel: Carousel) -> CarouselGeneration:
        """Return the snapshot whose number matches the carousel."""

        for generation in list(carousel.generations):

            if generation.generation_number == carousel.generation_number:

                return generation

        self.fail("current generation is missing")

    def _working_slide_ids(self, session: Session, carousel_id: uuid.UUID) -> set[uuid.UUID]:
        """Return the working slide ids. The snapshot must not delete them."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        slide_ids: set[uuid.UUID] = {slide.id for slide in list(carousel.slides)}

        return slide_ids

    def _generation_number(self, session: Session, carousel_id: uuid.UUID) -> int:
        """Return the stored generation number."""

        carousel: Carousel | None = session.get(Carousel, carousel_id)
        assert carousel is not None
        generation_number: int = carousel.generation_number

        return generation_number

    def _foreign_counts(self, session: Session) -> tuple[int, int, int]:
        """Return artifact, campaign-carousel, and draft-batch counts."""

        artifact_count: int = _table_count(session, Artifact)
        campaign_count: int = _table_count(session, CampaignCarousel)
        batch_count: int = _table_count(session, SlideDraftBatch)
        counts: tuple[int, int, int] = (artifact_count, campaign_count, batch_count)

        return counts


class CarouselGenerationSlideView:
    """The copied slide fields the assertion compares."""

    def __init__(
        self,
        source_slide_id: uuid.UUID | None,
        name: str,
        text_status: SlideTextStatus,
        album_image_id: uuid.UUID | None,
        value: str,
        draft_value: str | None,
    ) -> None:
        self.source_slide_id: uuid.UUID | None = source_slide_id
        self.name: str = name
        self.text_status: SlideTextStatus = text_status
        self.album_image_id: uuid.UUID | None = album_image_id
        self.value: str = value
        self.draft_value: str | None = draft_value


def _slide_view(slide: CarouselGenerationSlide) -> CarouselGenerationSlideView:
    """Read one copied slide into the fields the test compares."""

    copied: CarouselGenerationSlide = slide
    copied_texts: list[CarouselGenerationSlideText] = list(copied.texts)
    element_text: CarouselGenerationSlideText | None = None

    if len(copied_texts) > 0:
        element_text = copied_texts[0]

    value: str = "" if element_text is None else element_text.value
    draft_value: str | None = None if element_text is None else element_text.draft_value
    view: CarouselGenerationSlideView = CarouselGenerationSlideView(
        copied.source_slide_id,
        copied.name,
        copied.text_status,
        copied.album_image_id,
        value,
        draft_value,
    )

    return view


def _album_image(album_id: uuid.UUID, position: int, relative_path: str) -> AlbumImage:
    """Return one stored album image. The file itself is not written."""

    image: AlbumImage = AlbumImage(
        id=new_row_id(),
        album_id=album_id,
        position=position,
        relative_path=relative_path,
        media_type=SlideImageMediaType.PNG,
        byte_size=8,
        width=8,
        height=8,
        license=SlideImageLicense.CC0,
        source="probe",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
    )

    return image


def _slide(
    carousel_id: uuid.UUID,
    position: int,
    name: str,
    text_status: SlideTextStatus,
    album_image_id: uuid.UUID,
) -> Slide:
    """Return one working slide."""

    slide: Slide = Slide(
        id=new_row_id(),
        carousel_id=carousel_id,
        position=position,
        name=name,
        text_status=text_status,
        album_image_id=album_image_id,
    )

    return slide


def _element_text(
    slide_id: uuid.UUID,
    element_id: uuid.UUID,
    value: str,
    draft_value: str | None,
) -> SlideElementText:
    """Return one working element text."""

    element_text: SlideElementText = SlideElementText(
        id=new_row_id(),
        slide_id=slide_id,
        skeleton_element_id=element_id,
        value=value,
        draft_value=draft_value,
    )

    return element_text


def _position(row: object) -> int:
    """Return a stored position."""

    position: int = int(getattr(row, "position"))

    return position


def _table_count(session: Session, model: type[object]) -> int:
    """Return how many rows one mapped table holds."""

    counted: int = int(session.scalar(select(func.count()).select_from(model)) or 0)

    return counted


if __name__ == "__main__":
    unittest.main()
