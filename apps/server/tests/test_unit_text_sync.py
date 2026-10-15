"""Adding a theme text element fills empty slots on bound units.

Removing the element drops those rows through ON DELETE CASCADE.
Draft copy lives on ``unit_element_texts.draft_value``, not a second table.
"""

import os
import unittest
import uuid

os.environ.setdefault("TWERVA_ENV", "test")

from sqlalchemy import Select, create_engine, select, text
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.schemas import (
    SourceCreateRequest,
    SourceReadResponse,
    ThemeCreateRequest,
    ThemeElementCreateRequest,
    ThemeElementPatchRequest,
    ThemeElementReadResponse,
    ThemeReadResponse,
    UnitElementTextWrite,
    UnitReadResponse,
    UnitWriteRequest,
)
from app.api.v1.source_writes import (
    create_content_source,
    create_unit,
    delete_content_source,
)
from app.api.v1.theme_elements import (
    create_theme_element,
    delete_theme_element,
    patch_theme_element,
)
from app.api.v1.themes import create_theme, delete_theme_by_id
from app.models.content_source import Unit, UnitElementText, UnitImage
from app.models.enums import (
    ThemeElementAlignment,
    ThemeElementBand,
    ThemeElementContentKind,
    ThemeElementTextSource,
    UnitTextStatus,
)
from app.models.theme_element import ThemeElement
from app.sources.unit_text_sync import sync_empty_texts_for_theme_element


CANDIDATE_DATABASE_URLS: tuple[str, ...] = (
    os.environ.get("TWERVA_TEST_DATABASE_URL", "").strip(),
    os.environ.get("DATABASE_URL", "").strip(),
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva_test",
    "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
)
THEME_ELEMENT_TEXT_FK: str = (
    "fk_unit_element_texts_theme_element_id_theme_elements"
)


def _connect_test_engine() -> Engine | None:
    """Return an engine for the first reachable candidate URL, if any."""

    for candidate_database_url in CANDIDATE_DATABASE_URLS:

        if candidate_database_url == "":
            continue

        normalized_database_url: str = candidate_database_url

        if normalized_database_url.startswith("postgresql://"):
            remainder: str = normalized_database_url[len("postgresql://"):]
            normalized_database_url = f"postgresql+psycopg://{remainder}"

        candidate_engine: Engine | None = None

        try:
            candidate_engine = create_engine(normalized_database_url)
            with candidate_engine.connect() as our_database_connection:
                our_database_connection.execute(text("SELECT 1"))
        except OperationalError:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        except Exception:

            if candidate_engine is not None:
                candidate_engine.dispose()

            continue
        else:

            return candidate_engine

    return None


TEST_ENGINE: Engine | None = _connect_test_engine()


def _text_element_request(
    text_source: ThemeElementTextSource,
) -> ThemeElementCreateRequest:
    """One clear text element on the top band."""

    text_request: ThemeElementCreateRequest = ThemeElementCreateRequest(
        band=ThemeElementBand.TOP,
        content_kind=ThemeElementContentKind.TEXT,
        text_source=text_source,
        font_family="DejaVu Sans",
        font_size=28,
        font_color="#112233",
        alignment=ThemeElementAlignment.LEFT,
    )

    return text_request


@unittest.skipIf(TEST_ENGINE is None, "Postgres is not reachable for unit text sync tests")
class ThemeElementUnitTextSyncTests(unittest.TestCase):
    """Add fills empty slots. Delete cascades. Live units stay live."""

    def setUp(self) -> None:
        """Two themes with units, one of them already a draft."""

        if TEST_ENGINE is None:
            self.skipTest("Postgres is not reachable for unit text sync tests")

        self.SessionFactory: sessionmaker[Session] = sessionmaker(
            bind=TEST_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.our_database_session: Session = self.SessionFactory()
        self.run_suffix: str = uuid.uuid4().hex[:8]
        self.theme_ids: list[uuid.UUID] = []
        self.source_ids: list[uuid.UUID] = []
        paper: ThemeReadResponse = create_theme(
            ThemeCreateRequest(
                name=f"Paper {self.run_suffix}",
                elements=[_text_element_request(ThemeElementTextSource.TITLE)],
            ),
            self.our_database_session,
            None,
        )
        other: ThemeReadResponse = create_theme(
            ThemeCreateRequest(
                name=f"Other {self.run_suffix}",
                elements=[_text_element_request(ThemeElementTextSource.TITLE)],
            ),
            self.our_database_session,
            None,
        )
        blank: ThemeReadResponse = create_theme(
            ThemeCreateRequest(name=f"Blank {self.run_suffix}"),
            self.our_database_session,
            None,
        )
        self.paper_theme_id: uuid.UUID = paper.id
        self.other_theme_id: uuid.UUID = other.id
        self.blank_theme_id: uuid.UUID = blank.id
        self.paper_title_id: uuid.UUID = paper.elements[0].id
        self.other_title_id: uuid.UUID = other.elements[0].id
        self.theme_ids.extend([paper.id, other.id, blank.id])
        harbor_source: SourceReadResponse = create_content_source(
            SourceCreateRequest(name=f"Harbor {self.run_suffix}", theme_id=paper.id),
            self.our_database_session,
            None,
        )
        desert_source: SourceReadResponse = create_content_source(
            SourceCreateRequest(name=f"Desert {self.run_suffix}", theme_id=paper.id),
            self.our_database_session,
            None,
        )
        other_source: SourceReadResponse = create_content_source(
            SourceCreateRequest(name=f"Elsewhere {self.run_suffix}", theme_id=other.id),
            self.our_database_session,
            None,
        )
        blank_source: SourceReadResponse = create_content_source(
            SourceCreateRequest(name=f"Empty {self.run_suffix}", theme_id=blank.id),
            self.our_database_session,
            None,
        )
        self.source_ids.extend(
            [harbor_source.id, desert_source.id, other_source.id, blank_source.id],
        )
        harbor_unit: UnitReadResponse = create_unit(
            harbor_source.id,
            UnitWriteRequest(
                name="Harbor lamp",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=self.paper_title_id,
                        value="Fog",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        desert_unit: UnitReadResponse = create_unit(
            desert_source.id,
            UnitWriteRequest(
                name="Desert lamp",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=self.paper_title_id,
                        value="Dune",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        other_unit: UnitReadResponse = create_unit(
            other_source.id,
            UnitWriteRequest(
                name="Other lamp",
                texts=[
                    UnitElementTextWrite(
                        theme_element_id=self.other_title_id,
                        value="Stay",
                    ),
                ],
            ),
            self.our_database_session,
            None,
        )
        blank_unit: UnitReadResponse = create_unit(
            blank_source.id,
            UnitWriteRequest(name="Blank lamp"),
            self.our_database_session,
            None,
        )
        self.harbor_unit_id: uuid.UUID = harbor_unit.id
        self.desert_unit_id: uuid.UUID = desert_unit.id
        self.other_unit_id: uuid.UUID = other_unit.id
        self.blank_unit_id: uuid.UUID = blank_unit.id
        self._mark_desert_as_draft()

    def tearDown(self) -> None:
        """Remove the sources, then the themes."""

        if getattr(self, "our_database_session", None) is None:

            return

        try:
            self._delete_fixtures()
        finally:
            self.our_database_session.close()

    def test_adding_a_text_element_writes_empty_slots(self) -> None:
        """Every unit on the theme gets an empty row. Live units stay live."""

        heading: ThemeElementReadResponse = create_theme_element(
            self.paper_theme_id,
            _text_element_request(ThemeElementTextSource.INTEREST_HEADING),
            self.our_database_session,
            None,
        )
        heading_rows: dict[uuid.UUID, UnitElementText] = self._rows_for_element(
            heading.id,
        )
        harbor_heading: UnitElementText = heading_rows[self.harbor_unit_id]
        desert_heading: UnitElementText = heading_rows[self.desert_unit_id]

        self.assertEqual(set(heading_rows), {self.harbor_unit_id, self.desert_unit_id})
        self.assertEqual(harbor_heading.value, "")
        self.assertIsNone(harbor_heading.draft_value)
        self.assertEqual(desert_heading.value, "")
        self.assertEqual(desert_heading.draft_value, "")
        self.assertEqual(self._status(self.harbor_unit_id), UnitTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_unit_id), UnitTextStatus.DRAFT)
        self.assertEqual(self._value(self.harbor_unit_id, self.paper_title_id), "Fog")
        self.assertIsNone(self._draft(self.harbor_unit_id, self.paper_title_id))
        self.assertEqual(self._value(self.desert_unit_id, self.paper_title_id), "Dune")
        self.assertEqual(self._draft(self.desert_unit_id, self.paper_title_id), "Dry wind")
        self.assertNotIn(self.other_unit_id, heading_rows)
        self.assertEqual(self._value(self.other_unit_id, self.other_title_id), "Stay")
        self.assertEqual(self._rows_for_unit(self.blank_unit_id), {})
        self.assertEqual(self._image_count(self.harbor_unit_id), 0)

        stored_heading: ThemeElement | None = self.our_database_session.get(
            ThemeElement,
            heading.id,
        )
        self.assertIsNotNone(stored_heading)
        assert stored_heading is not None
        sync_empty_texts_for_theme_element(
            stored_heading,
            self.our_database_session,
        )
        self.our_database_session.commit()
        second_pass: dict[uuid.UUID, UnitElementText] = self._rows_for_element(
            heading.id,
        )

        self.assertEqual(set(second_pass), {self.harbor_unit_id, self.desert_unit_id})
        self.assertEqual(second_pass[self.harbor_unit_id].id, harbor_heading.id)

        blank_heading: ThemeElementReadResponse = create_theme_element(
            self.blank_theme_id,
            _text_element_request(ThemeElementTextSource.CANONICAL_URL),
            self.our_database_session,
            None,
        )
        blank_rows: dict[uuid.UUID, UnitElementText] = self._rows_for_element(
            blank_heading.id,
        )

        self.assertEqual(set(blank_rows), {self.blank_unit_id})
        self.assertEqual(blank_rows[self.blank_unit_id].value, "")
        self.assertIsNone(blank_rows[self.blank_unit_id].draft_value)
        self.assertEqual(self._status(self.blank_unit_id), UnitTextStatus.LIVE)

    def test_deleting_a_text_element_drops_its_rows(self) -> None:
        """CASCADE removes live and draft slots. The other element stays."""

        delete_action: str = self._theme_element_delete_action()
        heading: ThemeElementReadResponse = create_theme_element(
            self.paper_theme_id,
            _text_element_request(ThemeElementTextSource.OVERVIEW_BULLETS),
            self.our_database_session,
            None,
        )

        self.assertEqual(delete_action, "c")
        self.assertEqual(
            set(self._rows_for_element(heading.id)),
            {self.harbor_unit_id, self.desert_unit_id},
        )

        delete_theme_element(
            self.paper_theme_id,
            heading.id,
            self.our_database_session,
            None,
        )

        self.assertEqual(self._rows_for_element(heading.id), {})
        self.assertEqual(self._value(self.harbor_unit_id, self.paper_title_id), "Fog")
        self.assertEqual(self._value(self.desert_unit_id, self.paper_title_id), "Dune")
        self.assertEqual(self._draft(self.desert_unit_id, self.paper_title_id), "Dry wind")
        self.assertEqual(self._value(self.other_unit_id, self.other_title_id), "Stay")
        self.assertEqual(self._status(self.harbor_unit_id), UnitTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_unit_id), UnitTextStatus.DRAFT)
        self.assertEqual(self._image_count(self.harbor_unit_id), 0)
        self.assertEqual(self._image_count(self.desert_unit_id), 0)

    def test_an_image_element_does_not_write_text(self) -> None:
        """A new image element leaves unit text and unit images unchanged."""

        before: dict[uuid.UUID, str] = {
            self.harbor_unit_id: self._value(self.harbor_unit_id, self.paper_title_id),
            self.desert_unit_id: self._value(self.desert_unit_id, self.paper_title_id),
        }
        image_element: ThemeElementReadResponse = create_theme_element(
            self.paper_theme_id,
            ThemeElementCreateRequest(
                band=ThemeElementBand.MIDDLE,
                content_kind=ThemeElementContentKind.IMAGE,
                image_asset_ref="logos/mark.png",
            ),
            self.our_database_session,
            None,
        )

        self.assertEqual(self._rows_for_element(image_element.id), {})
        self.assertEqual(
            self._value(self.harbor_unit_id, self.paper_title_id),
            before[self.harbor_unit_id],
        )
        self.assertEqual(
            self._value(self.desert_unit_id, self.paper_title_id),
            before[self.desert_unit_id],
        )
        self.assertEqual(self._image_count(self.harbor_unit_id), 0)
        self.assertEqual(self._image_count(self.desert_unit_id), 0)

    def test_turning_an_image_element_into_text_writes_empty_slots(self) -> None:
        """A kind change that creates a text element fills the same empty slots."""

        image_element: ThemeElementReadResponse = create_theme_element(
            self.paper_theme_id,
            ThemeElementCreateRequest(
                band=ThemeElementBand.BOTTOM,
                content_kind=ThemeElementContentKind.IMAGE,
                image_asset_ref="logos/mark.png",
            ),
            self.our_database_session,
            None,
        )
        text_element: ThemeElementReadResponse = patch_theme_element(
            self.paper_theme_id,
            image_element.id,
            ThemeElementPatchRequest(
                content_kind=ThemeElementContentKind.TEXT,
                text_source=ThemeElementTextSource.CANONICAL_URL,
                font_family="DejaVu Sans",
                font_size=20,
                font_color="#112233",
                alignment=ThemeElementAlignment.LEFT,
                image_asset_ref=None,
            ),
            self.our_database_session,
            None,
        )
        text_rows: dict[uuid.UUID, UnitElementText] = self._rows_for_element(
            text_element.id,
        )

        self.assertEqual(text_element.content_kind, ThemeElementContentKind.TEXT)
        self.assertEqual(set(text_rows), {self.harbor_unit_id, self.desert_unit_id})
        self.assertEqual(text_rows[self.harbor_unit_id].value, "")
        self.assertIsNone(text_rows[self.harbor_unit_id].draft_value)
        self.assertEqual(text_rows[self.desert_unit_id].value, "")
        self.assertEqual(text_rows[self.desert_unit_id].draft_value, "")
        self.assertEqual(self._status(self.harbor_unit_id), UnitTextStatus.LIVE)
        self.assertEqual(self._status(self.desert_unit_id), UnitTextStatus.DRAFT)
        self.assertEqual(self._image_count(self.harbor_unit_id), 0)

    def _mark_desert_as_draft(self) -> None:
        """Store a draft beside the desert unit's live title."""

        desert_unit: Unit | None = self.our_database_session.get(Unit, self.desert_unit_id)
        self.assertIsNotNone(desert_unit)
        assert desert_unit is not None
        desert_unit.text_status = UnitTextStatus.DRAFT

        for element_text in list(desert_unit.element_texts):
            element_text.draft_value = "Dry wind"

        self.our_database_session.commit()

    def _delete_fixtures(self) -> None:
        """Drop sources before themes. Themes are still referenced until then."""

        self.our_database_session.rollback()

        for source_id in list(self.source_ids):
            delete_content_source(source_id, self.our_database_session, None)

        for theme_id in list(self.theme_ids):
            delete_theme_by_id(theme_id, self.our_database_session, None)

    def _rows_for_element(
        self,
        theme_element_id: uuid.UUID,
    ) -> dict[uuid.UUID, UnitElementText]:
        """Reload text rows for one theme element, keyed by unit."""

        self.our_database_session.expire_all()
        statement: Select[tuple[UnitElementText]] = select(UnitElementText).where(
            UnitElementText.theme_element_id == theme_element_id,
        )
        stored_rows: list[UnitElementText] = list(
            self.our_database_session.scalars(statement).all(),
        )
        rows_by_unit: dict[uuid.UUID, UnitElementText] = {
            stored_row.unit_id: stored_row for stored_row in stored_rows
        }

        return rows_by_unit

    def _rows_for_unit(self, unit_id: uuid.UUID) -> dict[uuid.UUID, UnitElementText]:
        """Reload one unit's text rows, keyed by theme element."""

        self.our_database_session.expire_all()
        statement: Select[tuple[UnitElementText]] = select(UnitElementText).where(
            UnitElementText.unit_id == unit_id,
        )
        stored_rows: list[UnitElementText] = list(
            self.our_database_session.scalars(statement).all(),
        )
        rows_by_element: dict[uuid.UUID, UnitElementText] = {
            stored_row.theme_element_id: stored_row for stored_row in stored_rows
        }

        return rows_by_element

    def _stored_text(
        self,
        unit_id: uuid.UUID,
        theme_element_id: uuid.UUID,
    ) -> UnitElementText:
        """Return the one row for this unit and element."""

        stored_text: UnitElementText | None = self._rows_for_unit(unit_id).get(
            theme_element_id,
        )
        self.assertIsNotNone(stored_text)
        assert stored_text is not None

        return stored_text

    def _value(self, unit_id: uuid.UUID, theme_element_id: uuid.UUID) -> str:
        """Return the live string for one slot."""

        stored_value: str = self._stored_text(unit_id, theme_element_id).value

        return stored_value

    def _draft(self, unit_id: uuid.UUID, theme_element_id: uuid.UUID) -> str | None:
        """Return the draft string for one slot, or null when there is none."""

        draft_value: str | None = self._stored_text(unit_id, theme_element_id).draft_value

        return draft_value

    def _status(self, unit_id: uuid.UUID) -> UnitTextStatus:
        """Reload the unit and return its text status."""

        self.our_database_session.expire_all()
        found_unit: Unit | None = self.our_database_session.get(Unit, unit_id)
        self.assertIsNotNone(found_unit)
        assert found_unit is not None
        text_status: UnitTextStatus = found_unit.text_status

        return text_status

    def _image_count(self, unit_id: uuid.UUID) -> int:
        """Return how many images this unit stores."""

        self.our_database_session.expire_all()
        statement: Select[tuple[UnitImage]] = select(UnitImage).where(
            UnitImage.unit_id == unit_id,
        )
        stored_images: list[UnitImage] = list(
            self.our_database_session.scalars(statement).all(),
        )
        image_count: int = len(stored_images)

        return image_count

    def _theme_element_delete_action(self) -> str:
        """Return Postgres' ON DELETE action for the theme-element text key."""

        action_statement: TextClause = text(
            "SELECT confdeltype FROM pg_constraint WHERE conname = :constraint_name",
        )
        delete_action: str | None = self.our_database_session.execute(
            action_statement,
            {"constraint_name": THEME_ELEMENT_TEXT_FK},
        ).scalar_one()

        return str(delete_action)
