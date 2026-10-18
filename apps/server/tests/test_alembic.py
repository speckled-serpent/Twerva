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
THEME_ELEMENTS_REVISION_ID: str = "theme_elements"
THEMES_BACKGROUND_REVISION_ID: str = "themes_background"
THEMES_CREATE_REVISION_ID: str = "themes_create"
THEMES_STATUS_REVISION_ID: str = "themes_status"
THEMES_SPACING_REVISION_ID: str = "themes_spacing"
THEMES_DROP_TEXTURE_REVISION_ID: str = "themes_drop_texture"
THEMES_ELEMENT_RECTANGLE_REVISION_ID: str = "themes_element_rectangle"
SOURCES_DEFAULT_ALBUM_REVISION_ID: str = "sources_default_album"
SOURCES_RESOURCE_FILES_REVISION_ID: str = "sources_resource_files"
SOURCES_THEME_BOUND_REVISION_ID: str = "sources_theme_bound"
UNIT_ELEMENT_TEXTS_REVISION_ID: str = "unit_element_texts"
UNIT_EXCLUSIONS_REVISION_ID: str = "unit_exclusions"
UNIT_TEXT_DRAFTS_REVISION_ID: str = "unit_text_drafts"
CAMPAIGN_THEME_SOURCE_REVISION_ID: str = "campaign_theme_source"
THEME_ELEMENT_NAMES_REVISION_ID: str = "theme_element_names"
THEME_ELEMENT_TEXT_OPTIONAL_REVISION_ID: str = "theme_element_text_optional"
SKELETONS_CAROUSELS_SLIDES_REVISION_ID: str = "skeletons_carousels_slides"
ALBUMS_FROM_SLIDES_REVISION_ID: str = "albums_from_slides"
RESEARCH_ITEMS_REVISION_ID: str = "research_items"
CAROUSEL_STEPS_REVISION_ID: str = "carousel_steps"
CAROUSEL_EDITOR_STEP_CONTENT_REVISION_ID: str = "carousel_editor_step_content"


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
                f"{ALBUMS_FROM_SLIDES_REVISION_ID}.py",
                f"{ARTIFACT_TEMPLATE_ID_REVISION_ID}.py",
                f"{CAMPAIGN_STATUS_LIFECYCLE_REVISION_ID}.py",
                f"{CAMPAIGN_THEME_SOURCE_REVISION_ID}.py",
                f"{CAMPAIGN_TYPE_SPOTMU_TEST_REVISION_ID}.py",
                f"{CAMPAIGNS_CREATE_UI_REVISION_ID}.py",
                f"{CAROUSEL_EDITOR_STEP_CONTENT_REVISION_ID}.py",
                f"{CAROUSEL_STEPS_REVISION_ID}.py",
                f"{OPS_USERS_ROLE_REVISION_ID}.py",
                f"{OPS_USERS_REVISION_ID}.py",
                f"{RESEARCH_ITEMS_REVISION_ID}.py",
                f"{SKELETONS_CAROUSELS_SLIDES_REVISION_ID}.py",
                f"{SOURCES_DEFAULT_ALBUM_REVISION_ID}.py",
                f"{SOURCES_RESOURCE_FILES_REVISION_ID}.py",
                f"{SOURCES_THEME_BOUND_REVISION_ID}.py",
                f"{THEME_ELEMENT_NAMES_REVISION_ID}.py",
                f"{THEME_ELEMENT_TEXT_OPTIONAL_REVISION_ID}.py",
                f"{THEME_ELEMENTS_REVISION_ID}.py",
                f"{THEMES_BACKGROUND_REVISION_ID}.py",
                f"{THEMES_CREATE_REVISION_ID}.py",
                f"{THEMES_DROP_TEXTURE_REVISION_ID}.py",
                f"{THEMES_ELEMENT_RECTANGLE_REVISION_ID}.py",
                f"{THEMES_SPACING_REVISION_ID}.py",
                f"{THEMES_STATUS_REVISION_ID}.py",
                f"{UNIT_ELEMENT_TEXTS_REVISION_ID}.py",
                f"{UNIT_EXCLUSIONS_REVISION_ID}.py",
                f"{UNIT_TEXT_DRAFTS_REVISION_ID}.py",
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

    def test_themes_background_revision_follows_themes_spacing(self) -> None:
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

    def test_theme_elements_revision_is_the_current_head(self) -> None:
        """theme_elements follows themes_background and locks the content check."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEME_ELEMENTS_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEME_ELEMENTS_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), THEME_ELEMENTS_REVISION_ID)
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEMES_BACKGROUND_REVISION_ID,
        )
        self.assertIn("CREATE TYPE theme_element_band AS ENUM", revision_source)
        self.assertIn("('top', 'middle', 'bottom')", revision_source)
        self.assertIn("('text', 'image')", revision_source)
        self.assertIn(
            "('title', 'interest_heading', 'overview_bullets', 'canonical_url')",
            revision_source,
        )
        self.assertIn("('left', 'center', 'right')", revision_source)
        self.assertIn("THEME_ELEMENT_CONTENT_CHECK_SQL", revision_source)
        self.assertIn("ondelete=\"CASCADE\"", revision_source)
        self.assertIn("uq_theme_elements_theme_id_band_sort_order", revision_source)
        self.assertIn('name="content"', revision_source)
        self.assertIn("ck_theme_elements_content", revision_source)
        self.assertNotIn('"x"', revision_source)
        self.assertNotIn('"y"', revision_source)
        self.assertNotIn('"width"', revision_source)
        self.assertIn("DROP TYPE theme_element_band", revision_source)

    def test_themes_drop_texture_follows_theme_elements(self) -> None:
        """Texture rows become picture and keep their asset ref."""

        assigned_values: dict[str, object] = _revision_module_constants(
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_DROP_TEXTURE_REVISION_ID}.py",
        )
        revision_source: str = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_DROP_TEXTURE_REVISION_ID}.py"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            THEMES_DROP_TEXTURE_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEME_ELEMENTS_REVISION_ID,
        )
        self.assertIn("SET background_kind = 'picture'", revision_source)
        self.assertIn("WHERE background_kind = 'texture'", revision_source)
        self.assertIn(
            "('picture', 'color', 'gradient')",
            revision_source,
        )
        self.assertNotIn("background_asset_ref = NULL", revision_source)

    def test_themes_element_rectangle_follows_drop_texture(self) -> None:
        """Opacity and radius follow the texture drop and default existing rows."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEMES_ELEMENT_RECTANGLE_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            THEMES_ELEMENT_RECTANGLE_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEMES_DROP_TEXTURE_REVISION_ID,
        )
        self.assertIn('server_default="100"', revision_source)
        self.assertIn('server_default="0"', revision_source)
        self.assertIn("ck_theme_elements_rectangle_style", revision_source)
        self.assertIn("rectangle_opacity >= 0 AND rectangle_opacity <= 100", revision_source)
        self.assertIn("rectangle_radius >= 0 AND rectangle_radius <= 10000", revision_source)
        self.assertIn('op.drop_column("theme_elements", "rectangle_opacity")', revision_source)
        self.assertIn('op.drop_column("theme_elements", "rectangle_radius")', revision_source)

    def test_sources_default_album_follows_element_rectangle(self) -> None:
        """Content sources follow the rectangle revision and do not touch themes."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{SOURCES_DEFAULT_ALBUM_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            SOURCES_DEFAULT_ALBUM_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEMES_ELEMENT_RECTANGLE_REVISION_ID,
        )
        self.assertIn("CREATE TYPE content_source_kind AS ENUM", revision_source)
        self.assertIn("('album', 'resource')", revision_source)
        self.assertIn(
            "('cc0', 'public_domain', 'owned', 'licensed')",
            revision_source,
        )
        self.assertIn('op.create_table(\n        "sources"', revision_source)
        self.assertIn('op.create_table(\n        "units"', revision_source)
        self.assertIn('op.create_table(\n        "unit_fields"', revision_source)
        self.assertIn('op.create_table(\n        "unit_images"', revision_source)
        self.assertIn('"tags"', revision_source)
        self.assertIn("default_unit_seeds", revision_source)
        self.assertIn("ON CONFLICT (slug) DO NOTHING", revision_source)
        self.assertNotIn("UPDATE themes", revision_source)
        self.assertNotIn("background_asset_ref", revision_source)
        self.assertIn("DROP TYPE content_source_kind", revision_source)

    def test_resource_files_follow_the_default_album(self) -> None:
        """Resource files are the next revision and do not rewrite themes."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{SOURCES_RESOURCE_FILES_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            SOURCES_RESOURCE_FILES_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            SOURCES_DEFAULT_ALBUM_REVISION_ID,
        )
        self.assertIn('op.create_table(\n        "resource_files"', revision_source)
        self.assertIn("('markdown', 'plain')", revision_source)
        self.assertIn("ck_resource_files_provenance", revision_source)
        self.assertIn("DROP TYPE resource_file_media_type", revision_source)
        self.assertNotIn("UPDATE themes", revision_source)

    def test_theme_bound_sources_follow_resource_files(self) -> None:
        """The theme-bound revision is the head after resource files."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{SOURCES_THEME_BOUND_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            SOURCES_THEME_BOUND_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            SOURCES_RESOURCE_FILES_REVISION_ID,
        )
        self.assertIn("fk_sources_theme_id_themes", revision_source)
        self.assertIn("uq_unit_images_unit_id", revision_source)
        self.assertIn("ck_units_name", revision_source)
        self.assertIn("DROP TYPE content_source_kind", revision_source)
        self.assertIn('op.drop_table("resource_files")', revision_source)
        self.assertIn("Refusing to delete image paths", revision_source)

    def test_unit_element_texts_follow_theme_bound_sources(self) -> None:
        """Theme text rows replace free text, tags, and labeled fields."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{UNIT_ELEMENT_TEXTS_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            UNIT_ELEMENT_TEXTS_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            SOURCES_THEME_BOUND_REVISION_ID,
        )
        self.assertIn('op.create_table(\n        "unit_element_texts"', revision_source)
        self.assertIn(
            'name="fk_unit_element_texts_theme_element_id_theme_elements"',
            revision_source,
        )
        self.assertIn('ondelete="CASCADE"', revision_source)
        self.assertIn('op.drop_column("units", "free_text")', revision_source)
        self.assertIn('op.drop_column("units", "tags")', revision_source)
        self.assertIn('op.drop_table("unit_fields")', revision_source)

    def test_unit_exclusions_follow_unit_element_texts(self) -> None:
        """Exclusion pairs are the revision after theme text on the unit."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{UNIT_EXCLUSIONS_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            UNIT_EXCLUSIONS_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            UNIT_ELEMENT_TEXTS_REVISION_ID,
        )
        self.assertIn('op.create_table(\n        "unit_exclusions"', revision_source)
        self.assertIn("ck_unit_exclusions_not_self", revision_source)
        self.assertIn('op.drop_table("unit_exclusions")', revision_source)

    def test_unit_text_drafts_follow_unit_exclusions(self) -> None:
        """Inspiration, rules, and draft text follow exclusion pairs."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{UNIT_TEXT_DRAFTS_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            UNIT_TEXT_DRAFTS_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            UNIT_EXCLUSIONS_REVISION_ID,
        )
        self.assertIn('sa.Column("inspiration"', revision_source)
        self.assertIn('sa.Column("rules"', revision_source)
        self.assertIn("unit_text_status", revision_source)
        self.assertIn('sa.Column("draft_value"', revision_source)
        self.assertIn('op.drop_column("sources", "inspiration")', revision_source)

    def test_campaign_theme_source_follows_unit_text_drafts(self) -> None:
        """Theme and source on a campaign follow drafted unit text."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAMPAIGN_THEME_SOURCE_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            CAMPAIGN_THEME_SOURCE_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            UNIT_TEXT_DRAFTS_REVISION_ID,
        )
        self.assertIn('sa.Column("theme_id"', revision_source)
        self.assertIn('sa.Column("source_id"', revision_source)
        self.assertIn('op.create_table(\n        "campaign_carousels"', revision_source)
        self.assertIn("nullable=True", revision_source)
        self.assertIn('op.drop_column("campaigns", "theme_id")', revision_source)
        self.assertIn('op.drop_table("campaign_carousels")', revision_source)

    def test_theme_element_names_follow_campaign_theme_source(self) -> None:
        """Names are backfilled, then locked as non-blank."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEME_ELEMENT_NAMES_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            THEME_ELEMENT_NAMES_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            CAMPAIGN_THEME_SOURCE_REVISION_ID,
        )
        self.assertIn('sa.Column("name", sa.Text(), nullable=True)', revision_source)
        self.assertIn("THEN 'Title'", revision_source)
        self.assertIn("THEN 'Interest heading'", revision_source)
        self.assertIn("THEN 'Overview bullets'", revision_source)
        self.assertIn("THEN 'Canonical URL'", revision_source)
        self.assertIn("THEN 'Text ('", revision_source)
        self.assertIn("ELSE 'Image ('", revision_source)
        self.assertIn('op.alter_column("theme_elements", "name", nullable=False)', revision_source)
        self.assertIn("ck_theme_elements_name", revision_source)
        self.assertIn("THEME_ELEMENT_NAME_CHECK_SQL", revision_source)
        self.assertIn('op.drop_column("theme_elements", "name")', revision_source)

    def test_theme_element_text_source_may_be_omitted(self) -> None:
        """Text rows may store a null text_source. Downgrade requires one."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{THEME_ELEMENT_TEXT_OPTIONAL_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            THEME_ELEMENT_TEXT_OPTIONAL_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEME_ELEMENT_NAMES_REVISION_ID,
        )
        self.assertIn("THEME_ELEMENT_CONTENT_CHECK_SQL", revision_source)
        self.assertIn('CONTENT_CHECK_LOGICAL_NAME: str = "content"', revision_source)
        self.assertIn("ck_theme_elements_content", revision_source)
        self.assertIn("ck_theme_elements_ck_theme_elements_content", revision_source)
        self.assertIn("DROP CONSTRAINT IF EXISTS", revision_source)
        self.assertIn("text_source IS NOT NULL", revision_source)
        self.assertIn(
            'op.create_check_constraint(\n        CONTENT_CHECK_LOGICAL_NAME,',
            revision_source,
        )
        self.assertNotIn("op.drop_constraint(", revision_source)

    def test_rename_follows_optional_text_source(self) -> None:
        """Themes, sources, and units are renamed in place after the last check."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{SKELETONS_CAROUSELS_SLIDES_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            SKELETONS_CAROUSELS_SLIDES_REVISION_ID,
        )
        self.assertEqual(
            assigned_values.get("down_revision"),
            THEME_ELEMENT_TEXT_OPTIONAL_REVISION_ID,
        )
        self.assertIn('op.rename_table(old_name, new_name)', revision_source)
        self.assertIn('"themes", "skeletons"', revision_source)
        self.assertIn('"sources", "carousels"', revision_source)
        self.assertIn('"units", "slides"', revision_source)
        self.assertIn("ck_sources_ck_sources_name", revision_source)
        self.assertIn("ck_sources_name", revision_source)
        self.assertNotIn("op.create_check_constraint(", revision_source)
        self.assertNotIn("op.drop_constraint(", revision_source)

    def test_albums_follow_the_rename(self) -> None:
        """Slide images move onto albums after the rename, with short check names."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{ALBUMS_FROM_SLIDES_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), ALBUMS_FROM_SLIDES_REVISION_ID)
        self.assertLessEqual(len(str(assigned_values.get("revision"))), 32)
        self.assertEqual(
            assigned_values.get("down_revision"),
            SKELETONS_CAROUSELS_SLIDES_REVISION_ID,
        )
        self.assertIn('op.create_check_constraint("name", "albums"', revision_source)
        self.assertIn('op.create_check_constraint("position", "album_images"', revision_source)
        self.assertNotIn("ck_albums_ck_", revision_source)
        self.assertNotIn("ck_album_images_ck_", revision_source)
        self.assertIn("INSERT INTO album_images", revision_source)
        self.assertIn('op.drop_table("slide_images")', revision_source)

    def test_research_follows_albums(self) -> None:
        """Research items follow albums, with short check names."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{RESEARCH_ITEMS_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), RESEARCH_ITEMS_REVISION_ID)
        self.assertLessEqual(len(str(assigned_values.get("revision"))), 32)
        self.assertEqual(
            assigned_values.get("down_revision"),
            ALBUMS_FROM_SLIDES_REVISION_ID,
        )
        self.assertIn('op.create_table(\n        "research_items"', revision_source)
        self.assertIn('op.create_check_constraint("title", "research_items"', revision_source)
        self.assertIn('op.create_check_constraint("body", "research_items"', revision_source)
        self.assertIn("char_length(body) <= 1000000", revision_source)
        self.assertNotIn("ck_research_items_ck_", revision_source)
        self.assertIn('op.drop_table("research_items")', revision_source)
        self.assertNotIn('op.create_table(\n        "resource_files"', revision_source)

    def test_carousel_steps_follow_research(self) -> None:
        """Generation, editor step, and the research link follow research items."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAROUSEL_STEPS_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(assigned_values.get("revision"), CAROUSEL_STEPS_REVISION_ID)
        self.assertLessEqual(len(str(assigned_values.get("revision"))), 32)
        self.assertEqual(
            assigned_values.get("down_revision"),
            RESEARCH_ITEMS_REVISION_ID,
        )
        self.assertIn(
            'op.create_check_constraint(\n        "generation_number",',
            revision_source,
        )
        self.assertIn(
            'op.create_check_constraint(\n        "editor_step",',
            revision_source,
        )
        self.assertIn(
            'op.create_check_constraint(\n        "position",',
            revision_source,
        )
        self.assertIn('op.create_table(\n        "carousel_research_items"', revision_source)
        self.assertIn("CAROUSEL_GENERATION_CHECK_SQL", revision_source)
        self.assertIn("CAROUSEL_EDITOR_STEP_CHECK_SQL", revision_source)
        self.assertIn("CAROUSEL_RESEARCH_POSITION_CHECK_SQL", revision_source)
        self.assertNotIn("ck_carousels_ck_", revision_source)
        self.assertNotIn("ck_carousel_research_items_ck_", revision_source)
        self.assertNotIn('"research_id"', revision_source)
        self.assertIn('op.drop_table("carousel_research_items")', revision_source)
        self.assertIn('op.drop_column("carousels", "generation_number")', revision_source)
        self.assertIn('op.drop_column("carousels", "editor_step")', revision_source)

    def test_editor_step_content_follows_carousel_steps(self) -> None:
        """Picture carousels with no album move to Content. The chain stays short."""

        revision_path: Path = (
            SERVER_ROOT_DIRECTORY
            / "alembic"
            / "versions"
            / f"{CAROUSEL_EDITOR_STEP_CONTENT_REVISION_ID}.py"
        )
        assigned_values: dict[str, object] = _revision_module_constants(revision_path)
        revision_source: str = revision_path.read_text(encoding="utf-8")

        self.assertEqual(
            assigned_values.get("revision"),
            CAROUSEL_EDITOR_STEP_CONTENT_REVISION_ID,
        )
        self.assertLessEqual(len(str(assigned_values.get("revision"))), 32)
        self.assertEqual(
            assigned_values.get("down_revision"),
            CAROUSEL_STEPS_REVISION_ID,
        )
        self.assertIn("UPDATE carousels", revision_source)
        self.assertIn("editor_step = :editor_step", revision_source)
        self.assertIn("'picture'::background_kind", revision_source)
        self.assertIn("'image'::skeleton_element_content_kind", revision_source)
        self.assertIn("album_id IS NULL", revision_source)
        self.assertNotIn("op.create_check_constraint(", revision_source)
        self.assertNotIn("research_items", revision_source)
        self.assertIn("SET editor_step = :slides_step", revision_source)

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
