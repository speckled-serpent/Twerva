"""Alembic config plus the 1.2b–k domain revision."""

import ast
import unittest
from pathlib import Path


SERVER_ROOT_DIRECTORY: Path = Path(__file__).resolve().parents[1]
DOMAIN_REVISION_ID: str = "12bk_domain_schema"


class AlembicInitializationTests(unittest.TestCase):
    """1.2k: alembic.ini + env.py + one domain head."""

    def test_alembic_config_and_env_exist(self) -> None:
        """Keep the Alembic layout Alembic and later leaves expect."""

        alembic_ini_path: Path = SERVER_ROOT_DIRECTORY / "alembic.ini"
        alembic_env_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "env.py"
        script_template_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "script.py.mako"

        self.assertTrue(alembic_ini_path.is_file())
        self.assertTrue(alembic_env_path.is_file())
        self.assertTrue(script_template_path.is_file())

    def test_versions_directory_has_the_domain_revision(self) -> None:
        """Single head creating 1.2c–1.2j tables."""

        versions_directory: Path = SERVER_ROOT_DIRECTORY / "alembic" / "versions"
        revision_modules: list[Path] = list(versions_directory.glob("*.py"))
        revision_names: list[str] = [path.name for path in revision_modules]

        self.assertTrue(versions_directory.is_dir())
        self.assertEqual(revision_names, [f"{DOMAIN_REVISION_ID}.py"])

    def test_domain_revision_is_the_first_head(self) -> None:
        """Revision id is 12bk_domain_schema with no parent."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY / "alembic" / "versions" / f"{DOMAIN_REVISION_ID}.py"
        )
        revision_source: str = revision_path.read_text(encoding="utf-8")
        parsed_module: ast.Module = ast.parse(revision_source)
        assigned_values: dict[str, object] = {}

        for module_node in parsed_module.body:

            if not isinstance(module_node, ast.Assign):
                continue

            if len(module_node.targets) != 1:
                continue

            assignment_target: ast.expr = module_node.targets[0]

            if not isinstance(assignment_target, ast.Name):
                continue

            if isinstance(module_node.value, ast.Constant):
                assigned_values[assignment_target.id] = module_node.value.value

        self.assertEqual(assigned_values.get("revision"), DOMAIN_REVISION_ID)
        self.assertIsNone(assigned_values.get("down_revision"))

    def test_env_imports_models_package(self) -> None:
        """env.py must import app.models so target_metadata sees all tables."""

        alembic_env_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "env.py"
        env_source: str = alembic_env_path.read_text(encoding="utf-8")

        self.assertIn("from app.models import Base", env_source)
        self.assertNotIn("from app.models.base import Base", env_source)


if __name__ == "__main__":
    unittest.main()
