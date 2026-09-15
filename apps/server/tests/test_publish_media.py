"""Resolve slide asset_ref files from ARTIFACT_STORAGE_DIR (1.6c-iii)."""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import Artifact
from app.models.enums import ArtifactStatus
from app.publish.errors import PublishMediaMissingError, PublishMediaPathEscapeError
from app.publish.media import resolve_artifact_slide_media_paths
from app.storage.artifacts import write_artifact_slide_png_bytes


FIXED_BRAND_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MINIMAL_PNG_BYTES: bytes = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _artifact_with_slides(slides: list[object] | None) -> Artifact:
    """Build an unbound Artifact with the given slides JSON."""

    artifact: Artifact = Artifact(
        brand_id=FIXED_BRAND_ID,
        status=ArtifactStatus.APPROVED,
        format="carousel",
        slides=slides,
    )

    return artifact


class PublishMediaResolveTests(unittest.TestCase):
    """Missing files fail; path escape is rejected; order is preserved."""

    def test_resolve_returns_existing_files_in_slide_order(self) -> None:
        """Two asset_refs become two absolute paths."""

        artifact_identifier: uuid.UUID = uuid.uuid4()

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            first_asset_reference: str = write_artifact_slide_png_bytes(
                artifact_identifier,
                0,
                "cover",
                MINIMAL_PNG_BYTES,
                storage_directory,
            )
            second_asset_reference: str = write_artifact_slide_png_bytes(
                artifact_identifier,
                1,
                "heading",
                MINIMAL_PNG_BYTES,
                storage_directory,
            )
            artifact: Artifact = _artifact_with_slides(
                [
                    {"role": "cover", "text": "A", "asset_ref": first_asset_reference},
                    {"role": "heading", "text": "B"},
                    {"role": "bullet", "text": "C", "asset_ref": second_asset_reference},
                ],
            )
            resolved_media_paths: list[Path] = resolve_artifact_slide_media_paths(
                artifact,
                storage_directory,
            )

            self.assertEqual(len(resolved_media_paths), 2)
            self.assertEqual(
                resolved_media_paths[0].name,
                Path(first_asset_reference).name,
            )
            self.assertEqual(
                resolved_media_paths[1].name,
                Path(second_asset_reference).name,
            )
            self.assertTrue(resolved_media_paths[0].is_file())
            self.assertTrue(resolved_media_paths[1].is_file())

    def test_missing_asset_ref_file_raises(self) -> None:
        """A set asset_ref that is not on disk is an error."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            artifact: Artifact = _artifact_with_slides(
                [
                    {
                        "role": "cover",
                        "text": "missing",
                        "asset_ref": "no-such-dir/0_cover.png",
                    },
                ],
            )

            with self.assertRaises(PublishMediaMissingError):
                resolve_artifact_slide_media_paths(artifact, storage_directory)

    def test_path_escape_is_rejected(self) -> None:
        """asset_ref may not walk above ARTIFACT_STORAGE_DIR."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            artifact: Artifact = _artifact_with_slides(
                [
                    {
                        "role": "cover",
                        "text": "escape",
                        "asset_ref": "../outside.png",
                    },
                ],
            )

            with self.assertRaises(PublishMediaPathEscapeError):
                resolve_artifact_slide_media_paths(artifact, storage_directory)

    def test_null_slides_returns_empty_list(self) -> None:
        """No slides means no media files (mock can still succeed)."""

        with TemporaryDirectory() as temporary_directory_name:
            storage_directory: Path = Path(temporary_directory_name)
            artifact: Artifact = _artifact_with_slides(None)
            resolved_media_paths: list[Path] = resolve_artifact_slide_media_paths(
                artifact,
                storage_directory,
            )

            self.assertEqual(resolved_media_paths, [])


if __name__ == "__main__":
    unittest.main()
