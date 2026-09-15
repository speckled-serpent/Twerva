"""Health endpoint stays independent of DATABASE_URL."""

import ast
import asyncio
import os
import unittest
from pathlib import Path

from app.main import HealthStatusResponse, get_health_status


MAIN_MODULE_PATH: Path = Path(__file__).resolve().parents[1] / "app" / "main.py"


class HealthStatusTests(unittest.TestCase):
    """Liveness payload does not load settings or open Postgres."""

    def test_get_health_status_returns_ok_without_database_url(self) -> None:
        """Return status ok even when DATABASE_URL is unset."""

        previous_database_url: str | None = os.environ.pop("DATABASE_URL", None)

        try:
            health_status_response: HealthStatusResponse = asyncio.run(
                get_health_status(),
            )
        finally:

            if previous_database_url is not None:
                os.environ["DATABASE_URL"] = previous_database_url

        self.assertEqual(health_status_response.status, "ok")

    def test_main_module_does_not_import_models_or_database(self) -> None:
        """GET /health must not pull in models or the engine (1.2a pattern)."""

        main_source: str = MAIN_MODULE_PATH.read_text(encoding="utf-8")
        parsed_module: ast.Module = ast.parse(main_source)
        imported_module_names: list[str] = []

        for module_node in parsed_module.body:

            if isinstance(module_node, ast.Import):

                for alias in module_node.names:
                    imported_module_names.append(alias.name)

            if isinstance(module_node, ast.ImportFrom):
                module_name: str = module_node.module or ""
                imported_module_names.append(module_name)

        self.assertNotIn("app.db", imported_module_names)
        self.assertNotIn("app.models", imported_module_names)
        self.assertNotIn("app.settings", imported_module_names)

        for imported_module_name in imported_module_names:
            self.assertFalse(imported_module_name.startswith("app.models"))
            self.assertFalse(imported_module_name.startswith("app.db"))


if __name__ == "__main__":
    unittest.main()
