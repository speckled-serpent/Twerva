"""Settings fail-fast and local DATABASE_URL loading."""

import os
import unittest

from app.settings import (
    DEFAULT_ARTIFACT_STORAGE_DIR,
    DEFAULT_PUBLISH_ADAPTER,
    DEFAULT_SPOTMU_API_BASE_URL,
    TEST_PLACEHOLDER_DATABASE_URL,
    MissingDatabaseUrlError,
    clear_settings_cache,
    get_settings,
)


class SettingsTests(unittest.TestCase):
    """DATABASE_URL is required outside tests and normalized for psycopg3."""

    def setUp(self) -> None:
        """Snapshot environment keys that settings tests mutate."""

        self.previous_database_url: str | None = os.environ.pop("DATABASE_URL", None)
        self.previous_spotmu_api_base_url: str | None = os.environ.pop(
            "SPOTMU_API_BASE_URL",
            None,
        )
        self.previous_artifact_storage_dir: str | None = os.environ.pop(
            "ARTIFACT_STORAGE_DIR",
            None,
        )
        self.previous_publish_adapter: str | None = os.environ.pop(
            "PUBLISH_ADAPTER",
            None,
        )
        self.previous_ayrshare_api_key: str | None = os.environ.pop(
            "AYRSHARE_API_KEY",
            None,
        )
        self.previous_twerva_environment: str | None = os.environ.pop("TWERVA_ENV", None)
        self.previous_twerva_testing: str | None = os.environ.pop("TWERVA_TESTING", None)
        self.previous_pytest_current_test: str | None = os.environ.pop(
            "PYTEST_CURRENT_TEST",
            None,
        )
        clear_settings_cache()

    def tearDown(self) -> None:
        """Restore the process environment and drop the settings cache."""

        self._restore_environment_variable("DATABASE_URL", self.previous_database_url)
        self._restore_environment_variable(
            "SPOTMU_API_BASE_URL",
            self.previous_spotmu_api_base_url,
        )
        self._restore_environment_variable(
            "ARTIFACT_STORAGE_DIR",
            self.previous_artifact_storage_dir,
        )
        self._restore_environment_variable(
            "PUBLISH_ADAPTER",
            self.previous_publish_adapter,
        )
        self._restore_environment_variable(
            "AYRSHARE_API_KEY",
            self.previous_ayrshare_api_key,
        )
        self._restore_environment_variable("TWERVA_ENV", self.previous_twerva_environment)
        self._restore_environment_variable("TWERVA_TESTING", self.previous_twerva_testing)
        self._restore_environment_variable(
            "PYTEST_CURRENT_TEST",
            self.previous_pytest_current_test,
        )
        clear_settings_cache()

    def test_missing_database_url_fails_fast_outside_tests(self) -> None:
        """Raise when DATABASE_URL is absent and no test flag is set."""

        with self.assertRaises(MissingDatabaseUrlError):
            get_settings()

    def test_test_environment_uses_placeholder_when_url_missing(self) -> None:
        """Accept a placeholder URL when TWERVA_ENV=test."""

        os.environ["TWERVA_ENV"] = "test"
        settings_database_url: str = get_settings().database_url

        self.assertEqual(settings_database_url, TEST_PLACEHOLDER_DATABASE_URL)

    def test_postgresql_url_is_rewritten_to_psycopg3_dialect(self) -> None:
        """Bare postgresql:// URLs become postgresql+psycopg://."""

        os.environ["DATABASE_URL"] = "postgresql://twerva:twerva@127.0.0.1:5432/twerva"
        normalized_database_url: str = get_settings().database_url

        self.assertEqual(
            normalized_database_url,
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva",
        )

    def test_explicit_psycopg3_url_is_unchanged(self) -> None:
        """Leave postgresql+psycopg:// URLs untouched."""

        explicit_database_url: str = (
            "postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva"
        )
        os.environ["DATABASE_URL"] = explicit_database_url
        loaded_database_url: str = get_settings().database_url

        self.assertEqual(loaded_database_url, explicit_database_url)

    def test_spotmu_api_base_url_defaults_to_public_origin(self) -> None:
        """SPOTMU_API_BASE_URL defaults to the locked https://spotmu.com origin."""

        os.environ["TWERVA_ENV"] = "test"
        loaded_spotmu_api_base_url: str = get_settings().spotmu_api_base_url

        self.assertEqual(loaded_spotmu_api_base_url, DEFAULT_SPOTMU_API_BASE_URL)

    def test_artifact_storage_dir_defaults_to_server_path(self) -> None:
        """ARTIFACT_STORAGE_DIR defaults to /opt/twerva/artifacts."""

        os.environ["TWERVA_ENV"] = "test"
        loaded_artifact_storage_dir: str = get_settings().artifact_storage_dir

        self.assertEqual(loaded_artifact_storage_dir, DEFAULT_ARTIFACT_STORAGE_DIR)

    def test_artifact_storage_dir_can_be_overridden(self) -> None:
        """Local README path ./data/artifacts is accepted from the environment."""

        os.environ["TWERVA_ENV"] = "test"
        os.environ["ARTIFACT_STORAGE_DIR"] = "./data/artifacts"
        loaded_artifact_storage_dir: str = get_settings().artifact_storage_dir

        self.assertEqual(loaded_artifact_storage_dir, "./data/artifacts")

    def test_publish_adapter_defaults_to_mock(self) -> None:
        """PUBLISH_ADAPTER defaults to mock so CI needs no vendor keys."""

        os.environ["TWERVA_ENV"] = "test"
        loaded_publish_adapter: str = get_settings().publish_adapter

        self.assertEqual(loaded_publish_adapter, DEFAULT_PUBLISH_ADAPTER)

    def test_publish_adapter_can_be_overridden(self) -> None:
        """PUBLISH_ADAPTER=ayrshare is accepted from the environment."""

        os.environ["TWERVA_ENV"] = "test"
        os.environ["PUBLISH_ADAPTER"] = "ayrshare"
        loaded_publish_adapter: str = get_settings().publish_adapter

        self.assertEqual(loaded_publish_adapter, "ayrshare")

    def _restore_environment_variable(self, variable_name: str, previous_value: str | None,
    ) -> None:
        """Put a mutated environment variable back, or remove it if it was unset."""

        if previous_value is None:
            os.environ.pop(variable_name, None)

            return

        os.environ[variable_name] = previous_value


if __name__ == "__main__":
    unittest.main()
