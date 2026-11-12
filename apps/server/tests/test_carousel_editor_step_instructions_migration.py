"""Allow editor step 1, then put those rows back on Basic."""

import os
import unittest
import uuid
from pathlib import Path

os.environ.setdefault("TWERVA_ENV", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.carousels.default_carousel import DEFAULT_ALBUM_SLUG
from app.settings import clear_settings_cache


SERVER_ROOT: Path = Path(__file__).resolve().parents[1]
ADMIN_DATABASE_URL: str = "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/postgres"
INSTRUCTIONS_REVISION: str = "carousel_instructions"
OPEN_INSTRUCTIONS_REVISION: str = "carousel_editor_step_instructions"
EDITOR_STEP_BASIC: int = 0
EDITOR_STEP_INSTRUCTIONS: int = 1
EDITOR_STEP_CONTENT: int = 2
EDITOR_STEP_SLIDES: int = 3


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


@unittest.skipIf(not _postgres_available(), "Postgres is not reachable for migration tests")
class CarouselEditorStepInstructionsMigrationTests(unittest.TestCase):
    """Upgrade, downgrade, and upgrade again while carousel rows already exist."""

    def setUp(self) -> None:
        """Create an empty database and point settings at it."""

        self.database_name: str = f"twerva_step1_{uuid.uuid4().hex[:10]}"
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

    def test_upgrade_allows_step_1_and_downgrade_returns_it_to_basic(self) -> None:
        """Existing 0, 2, and 3 stay. A stored 1 becomes 0 on the way down."""

        self._upgrade(INSTRUCTIONS_REVISION)
        self._insert_rows()
        before_steps: dict[str, int] = self._editor_steps()
        before_guidance: dict[str, tuple[str, str]] = self._guidance()
        before_check: str = self._editor_step_check()

        self.assertEqual(before_steps[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self.assertEqual(before_steps["basic-notes"], EDITOR_STEP_BASIC)
        self.assertEqual(before_steps["content-notes"], EDITOR_STEP_CONTENT)
        self.assertEqual(before_steps["slide-notes"], EDITOR_STEP_SLIDES)

        self._upgrade(OPEN_INSTRUCTIONS_REVISION)
        self.assertEqual(self._editor_steps(), before_steps)
        self.assertEqual(self._guidance(), before_guidance)
        self.assertNotEqual(self._editor_step_check(), before_check)
        self.assertEqual(self._version_num_length(), 64)
        self._set_editor_step("basic-notes", EDITOR_STEP_INSTRUCTIONS)
        self._assert_rejected_step("content-notes", 4)
        self.assertEqual(self._editor_steps()["content-notes"], EDITOR_STEP_CONTENT)
        self.assertEqual(self._editor_steps()["basic-notes"], EDITOR_STEP_INSTRUCTIONS)
        self.assertEqual(self._guidance(), before_guidance)

        self._downgrade(INSTRUCTIONS_REVISION)
        downgraded: dict[str, int] = self._editor_steps()

        self.assertEqual(downgraded[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self.assertEqual(downgraded["basic-notes"], EDITOR_STEP_BASIC)
        self.assertEqual(downgraded["content-notes"], EDITOR_STEP_CONTENT)
        self.assertEqual(downgraded["slide-notes"], EDITOR_STEP_SLIDES)
        self.assertEqual(self._editor_step_check(), before_check)
        self.assertEqual(self._guidance(), before_guidance)
        self._assert_rejected_step("slide-notes", EDITOR_STEP_INSTRUCTIONS)
        self.assertEqual(self._editor_steps()["slide-notes"], EDITOR_STEP_SLIDES)

        self._upgrade(OPEN_INSTRUCTIONS_REVISION)
        self.assertEqual(self._editor_steps()["basic-notes"], EDITOR_STEP_BASIC)
        self.assertEqual(self._editor_steps()[DEFAULT_ALBUM_SLUG], EDITOR_STEP_SLIDES)
        self._set_editor_step("slide-notes", EDITOR_STEP_INSTRUCTIONS)
        self.assertEqual(self._editor_steps()["slide-notes"], EDITOR_STEP_INSTRUCTIONS)
        self.assertEqual(self._guidance()["basic-notes"], ("Harbor fog", "Keep it short"))

    def _insert_rows(self) -> None:
        """Add carousels on Basic, Content, and Slides beside Default."""

        self._insert_carousel("basic-notes", EDITOR_STEP_BASIC, "Harbor fog", "Keep it short")
        self._insert_carousel("content-notes", EDITOR_STEP_CONTENT, "", "")
        self._insert_carousel("slide-notes", EDITOR_STEP_SLIDES, "", "Name the quay")

    def _insert_carousel(
        self,
        slug: str,
        editor_step: int,
        inspiration: str,
        rules: str,
    ) -> None:
        """Insert one carousel on Default's skeleton."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO carousels (
                        skeleton_id, name, slug, inspiration, rules, editor_step
                    )
                    SELECT skeleton_id, :name, :slug, :inspiration, :rules, :editor_step
                    FROM carousels
                    WHERE slug = :default_slug
                    """
                ),
                {
                    "name": slug,
                    "slug": slug,
                    "inspiration": inspiration,
                    "rules": rules,
                    "editor_step": editor_step,
                    "default_slug": DEFAULT_ALBUM_SLUG,
                },
            )

    def _set_editor_step(self, slug: str, editor_step: int) -> None:
        """Store one editor step."""

        with self.database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE carousels
                    SET editor_step = :editor_step
                    WHERE slug = :slug
                    """
                ),
                {"slug": slug, "editor_step": editor_step},
            )

    def _assert_rejected_step(self, slug: str, editor_step: int) -> None:
        """A refused step does not save."""

        with self.assertRaises(IntegrityError):
            self._set_editor_step(slug, editor_step)

    def _editor_steps(self) -> dict[str, int]:
        """Return editor_step keyed by carousel slug."""

        with self.database_engine.connect() as connection:
            steps: dict[str, int] = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    text("SELECT slug, editor_step FROM carousels"),
                ).fetchall()
            }

        return steps

    def _guidance(self) -> dict[str, tuple[str, str]]:
        """Return inspiration and rules keyed by carousel slug."""

        with self.database_engine.connect() as connection:
            guidance: dict[str, tuple[str, str]] = {
                str(row[0]): (str(row[1]), str(row[2]))
                for row in connection.execute(
                    text("SELECT slug, inspiration, rules FROM carousels"),
                ).fetchall()
            }

        return guidance

    def _editor_step_check(self) -> str:
        """Return the ``editor_step`` check definition."""

        with self.database_engine.connect() as connection:
            definition: str = str(
                connection.execute(
                    text(
                        """
                        SELECT pg_get_constraintdef(pg_constraint.oid)
                        FROM pg_constraint
                        JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                        WHERE pg_class.relname = 'carousels'
                          AND pg_constraint.conname = 'ck_carousels_editor_step'
                        """
                    ),
                ).scalar_one(),
            )

        return definition

    def _version_num_length(self) -> int:
        """Return the character limit of ``alembic_version.version_num``."""

        with self.database_engine.connect() as connection:
            length: int = int(
                connection.execute(
                    text(
                        """
                        SELECT character_maximum_length
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'alembic_version'
                          AND column_name = 'version_num'
                        """
                    ),
                ).scalar_one(),
            )

        return length

    def _upgrade(self, revision: str) -> None:
        """Run alembic upgrade against this test database."""

        clear_settings_cache()
        command.upgrade(self._alembic_config(), revision)

    def _downgrade(self, revision: str) -> None:
        """Run alembic downgrade against this test database."""

        clear_settings_cache()
        command.downgrade(self._alembic_config(), revision)

    def _alembic_config(self) -> Config:
        """Return Alembic config for the server tree."""

        alembic_config: Config = Config(str(SERVER_ROOT / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(SERVER_ROOT / "alembic"))

        return alembic_config


if __name__ == "__main__":
    unittest.main()
