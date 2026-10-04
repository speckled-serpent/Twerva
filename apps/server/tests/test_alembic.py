"""Alembic config plus the 1.2b–k domain revision."""

import ast
import unittest
from pathlib import Path


SERVER_ROOT_DIRECTORY: Path = Path(__file__).resolve().parents[1]
DOMAIN_REVISION_ID: str = "12bk_domain_schema"
OPS_USERS_REVISION_ID: str = "ops_users_web_auth"
OPS_USERS_ROLE_REVISION_ID: str = "ops_users_role_rbac"
ARTIFACT_TEMPLATE_ID_REVISION_ID: str = "artifact_template_id"
CAMPAIGNS_CREATE_UI_REVISION_ID: str = "campaigns_create_ui"
CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID: str = "campaign_status_lifecycle"
CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID: str = "campaign_type_spotmu_test"
THEMES_BACKGROUND_REVISION_ID: str = "themes_background"
THEMES_CREATE_REVISION_ID: str = "themes_create"
THEMES_STATUS_REVISION_ID: str = "themes_status"
THEMES_SPACING_REVISION_ID: str = "themes_spacing"


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

    def test_versions_directory_has_domain_and_ops_users_revisions(self) -> None:
        """Domain schema plus ops_users auth revision."""

        versions_directory: Path = SERVER_ROOT_DIRECTORY / "alembic" / "versions"
        revision_modules: list[Path] = list(versions_directory.glob("*.py"))
        revision_names: list[str] = sorted(path.name for path in revision_modules)

        self.assertTrue(versions_directory.is_dir())
        self.assertEqual(
            revision_names,
            [
                f"{DOMAIN_REVISION_ID}.py",
                f"{ARTIFACT_TEMPLATE_ID_REVISION_ID}.py",
                f"{CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID}.py",
                f"{CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID}.py",
                f"{CAMPAIGNS_CREATE_UI_REVISION_ID}.py",
                f"{OPS_USERS_ROLE_REVISION_ID}.py",
                f"{OPS_USERS_REVISION_ID}.py",
                f"{THEMES_BACKGROUND_REVISION_ID}.py",
                f"{THEMES_CREATE_REVISION_ID}.py",
                f"{THEMES_SPACING_REVISION_ID}.py",
                f"{THEMES_STATUS_REVISION_ID}.py",
            ],
        )

    def test_domain_revision_is_the_first_head(self) -> None:
        """Revision id is 12bk_domain_schema with no parent."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY / "alembic" / "versions" / f"{DOMAIN_REVISION_ID}.py"
        )
        revision_source: str = revision_path.read_text(encoding="utf-8")
        parsed_module: ast.Module = ast.parse(revision_source)
        assigned_values: dict[str, object] = {}

        for module_node in parsed_module.body:

            if isinstance(module_node, ast.AnnAssign):
                annotation_target: ast.expr = module_node.target

                if (
                    isinstance(annotation_target, ast.Name)
                    and isinstance(module_node.value, ast.Constant)
                ):
                    assigned_values[annotation_target.id] = module_node.value.value

                continue

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

    def test_ops_users_revision_follows_domain_schema(self) -> None:
        """ops_users_web_auth follows 12bk_domain_schema."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY / "alembic" / "versions" / f"{OPS_USERS_REVISION_ID}.py",
        )

        self.assertEqual(assigned_values.get("revision"), OPS_USERS_REVISION_ID)
        self.assertEqual(assigned_values.get("down_revision"), DOMAIN_REVISION_ID)

    def test_ops_users_role_revision_follows_ops_users_web_auth(self) -> None:
        """ops_users_role_rbac follows ops_users_web_auth."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{OPS_USERS_ROLE_REVISION_ID}.py",
        )

        self.assertEqual(assigned_values.get("revision"), OPS_USERS_ROLE_REVISION_ID)
        self.assertEqual(assigned_values.get("down_revision"), OPS_USERS_REVISION_ID)

    def test_artifact_template_id_revision_follows_ops_users_role(self) -> None:
        """artifact_template_id follows ops_users_role_rbac."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{ARTIFACT_TEMPLATE_ID_REVISION_ID}.py",
        )

        self.assertEqual(assigned_values.get("revision"), ARTIFACT_TEMPLATE_ID_REVISION_ID)
        self.assertEqual(
            assigned_values.get("down_revision"),
            OPS_USERS_ROLE_REVISION_ID,
        )

    def test_campaigns_create_ui_revision_follows_artifact_template_id(self) -> None:
        """campaigns_create_ui follows artifact_template_id."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGNS_CREATE_UI_REVISION_ID}.py",
        )

        self.assertEqual(
            assigned_values.get("revision"),
            CAMPAIGNS_CREATE_UI_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            ARTIFACT_TEMPLATE_ID_REVISION_ID,
        )

    def test_campaign_status_lifecycle_revision_follows_campaigns_create_ui(self) -> None:
        """campaign_status_lifecycle follows campaigns_create_ui."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            CAMPAIGNS_CREATE_UI_REVISION_ID,
        )
        self.assertIn(
            "ALTER TYPE campaign_status RENAME VALUE 'not_started' TO 'ready'",
            revision_source,
        )
        self.assertIn("ADD VALUE 'running'", revision_source)
        self.assertIn("ADD VALUE 'paused'", revision_source)
        self.assertIn("ADD VALUE 'finished'", revision_source)

    def test_campaign_type_spotmu_test_revision_follows_lifecycle(self) -> None:
        """campaign_type_spotmu_test follows campaign_status_lifecycle."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID,
        )
        self.assertIn("ADD VALUE 'spotmu_test'", revision_source)

    def test_themes_create_revision_follows_campaign_type_spotmu_test(self) -> None:
        """themes_create follows campaign_type_spotmu_test and seeds templates."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_CREATE_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_CREATE_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), THEMES_CREATE_REVISION_ID)
        self.assertEqual(
            assigned_values.get("down_revision"),
            CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID,
        )
        self.assertIn('op.create_table(\n        "themes"', revision_source)
        self.assertIn("spotmu_paper_v1", revision_source)
        self.assertIn("spotmu_bold_v1", revision_source)
        self.assertNotIn("DROP TYPE advertisement_type", revision_source)

    def test_themes_status_revision_follows_themes_create(self) -> None:
        """themes_status follows themes_create and backfills draft."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_STATUS_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_STATUS_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), THEMES_STATUS_REVISION_ID)
        self.assertEqual(assigned_values.get("down_revision"), THEMES_CREATE_REVISION_ID)
        self.assertIn("CREATE TYPE theme_status AS ENUM ('draft', 'live')", revision_source)
        self.assertIn("Spotmu Paper v1", revision_source)
        self.assertIn("Spotmu Bold v1", revision_source)
        self.assertIn("SET status = 'draft'::theme_status", revision_source)
        self.assertIn("'draft'::theme_status", revision_source)
        self.assertIn("DROP TYPE theme_status", revision_source)

    def test_themes_spacing_revision_follows_themes_status(self) -> None:
        """themes_spacing follows themes_status and backfills 96 / 0 / 0."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_SPACING_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_SPACING_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), THEMES_SPACING_REVISION_ID)
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEMES_STATUS_REVISION_ID,
        )
        self.assertIn("page_margin", revision_source)
        self.assertIn("element_gap", revision_source)
        self.assertIn("element_margin", revision_source)
        self.assertIn("DEFAULT_PAGE_MARGIN: int = 96", revision_source)
        self.assertIn("DEFAULT_ELEMENT_GAP: int = 0", revision_source)
        self.assertIn("DEFAULT_ELEMENT_MARGIN: int = 0", revision_source)
        self.assertIn("SET page_margin = {DEFAULT_PAGE_MARGIN}", revision_source)
        self.assertIn("element_gap = {DEFAULT_ELEMENT_GAP}", revision_source)
        self.assertIn("element_margin = {DEFAULT_ELEMENT_MARGIN}", revision_source)
        self.assertIn("Spotmu Paper v1", revision_source)
        self.assertIn("Spotmu Bold v1", revision_source)
        self.assertIn('op.drop_column("themes", "page_margin")', revision_source)

    def test_themes_background_revision_is_the_current_head(self) -> None:
        """themes_background follows themes_spacing and backfills paper."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_BACKGROUND_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_BACKGROUND_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            THEMES_BACKGROUND_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEMES_SPACING_REVISION_ID,
        )
        self.assertIn(
            "('picture', 'color', 'gradient', 'texture')",
            revision_source,
        )
        self.assertIn("#F6F1E8", revision_source)
        self.assertIn("background_gradient", revision_source)
        self.assertIn("background_asset_ref", revision_source)
        self.assertIn("Spotmu Paper v1", revision_source)
        self.assertIn("Spotmu Bold v1", revision_source)
        self.assertIn("DROP TYPE background_kind", revision_source)

    def test_env_imports_models_package(self) -> None:
        """env.py must import app.models so target_metadata sees all tables."""

        alembic_env_path: Path = SERVER_ROOT_DIRECTORY / "alembic" / "env.py"
        env_source: str = alembic_env_path.read_text(encoding="utf-8")

        self.assertIn("from app.models import Base", env_source)
        self.assertNotIn("from app.models.base import Base", env_source)


def _revision_module_constants(revision_path: Path) -> dict[str, object]:
    """Parse module-level `revision` / `down_revision` constants from a file."""

    revision_source: str = revision_path.read_text(encoding="utf-8")
    parsed_module: ast.Module = ast.parse(revision_source)
    assigned_values: dict[str, object] = {}

    for module_node in parsed_module.body:

        if isinstance(module_node, ast.AnnAssign):
            annotation_target: ast.expr = module_node.target

            if (
                isinstance(annotation_target, ast.Name)
                and isinstance(module_node.value, ast.Constant)
            ):
                assigned_values[annotation_target.id] = module_node.value.value

            continue

        if not isinstance(module_node, ast.Assign):
            continue

        if len(module_node.targets) != 1:
            continue

        assignment_target: ast.expr = module_node.targets[0]

        if not isinstance(assignment_target, ast.Name):
            continue

        if isinstance(module_node.value, ast.Constant):
            assigned_values[assignment_target.id] = module_node.value.value

    return assigned_values


if __name__ == "__main__":
    unittest.main()
