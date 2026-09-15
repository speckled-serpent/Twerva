"""Alembic is initialized with an empty revision chain."""

import unittest
from pathlib import Path


SERVER_ROOT_DIRECTORY: Path = Path(__file__).resolve().parents[1]


class AlembicInitializationTests(unittest.TestCase):
    """1.2a-iv: alembic.ini + env.py present; no domain migrations yet."""

    def test_alembic_config_and_env_exist(self) -> None:
        """Keep the Alembic layout Alembic and 1.2b+ expect."""

        alembic_ini_path: Path = SERVER_ROOT_DIRECTORY / "alembic.ini"
        alembic_env_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "env.py"
        script_template_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "script.py.mako"

        self.assertTrue(alembic_ini_path.is_file())
        self.assertTrue(alembic_env_path.is_file())
        self.assertTrue(script_template_path.is_file())

    def test_versions_directory_has_no_revision_modules(self) -> None:
        """Empty chain — first domain revision belongs to 1.2b+."""

        versions_directory: Path = SERVER_ROOT_DIRECTORY / "alembic" / "versions"
        revision_modules: list[Path] = list(versions_directory.glob("*.py"))

        self.assertTrue(versions_directory.is_dir())
        self.assertEqual(revision_modules, [])
