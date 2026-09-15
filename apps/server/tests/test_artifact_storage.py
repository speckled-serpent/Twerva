"""Local artifact file helper (1.4b-ii). No S3."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from app.storage.artifacts import (
    ensure_artifact_storage_directory,
    sanitize_slide_role,
    write_artifact_slide_png_bytes,
)


MINIMAL_PNG_BYTES: bytes = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ArtifactStorageTests(unittest.TestCase):
    """Write helper creates `{artifact_id}/{slide_index}_{role}.png`."""

    def test_write_returns_relative_asset_ref_and_creates_png(self) -> None:
        """Bytes land under the artifact folder; asset_ref is relative."""

        artifact_identifier: uuid.UUID = uuid.uuid4()

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            relative_asset_reference: str = write_artifact_slide_png_bytes(
                artifact_identifier,
                0,
                "cover",
                MINIMAL_PNG_BYTES,
                storage_directory,
            )
            expected_relative_reference: str = f"{artifact_identifier}/0_cover.png"
            stored_path: Path = storage_directory / relative_asset_reference

            self.assertEqual(relative_asset_reference, expected_relative_reference)
            self.assertTrue(stored_path.is_file())
            self.assertEqual(stored_path.read_bytes(), MINIMAL_PNG_BYTES)

    def test_ensure_creates_missing_directory(self) -> None:
        """The store root is created when it does not exist."""

        with TemporaryDirectory() as temporary_directory_name:
            missing_directory: Path = Path(temporary_directory_name) / "artifacts"
            resolved_directory: Path = ensure_artifact_storage_directory(missing_directory)

            self.assertTrue(resolved_directory.is_dir())

    def test_sanitize_slide_role_strips_unsafe_characters(self) -> None:
        """Role tokens stay filename-safe."""

        self.assertEqual(sanitize_slide_role("Cover"), "cover")
        self.assertEqual(sanitize_slide_role("bullet-1"), "bullet1")
        self.assertEqual(sanitize_slide_role("***"), "slide")


if __name__ == "__main__":
    unittest.main()
