"""Album create, reorder, upload, and delete. No carousel attach screen."""

import io
import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from app.api.v1.albums import (
    create_album,
    delete_album,
    delete_album_image,
    get_album,
    list_albums,
    patch_album,
    upload_album_image,
)
from app.api.v1.schemas import (
    AlbumCreateRequest,
    AlbumImageWrite,
    AlbumListItemResponse,
    AlbumPatchRequest,
    AlbumReadResponse,
)
from app.carousels.image_store import LocalAlbumImageStore
from app.models.album import Album, AlbumImage
from app.models.enums import SlideImageIntake, SlideImageLicense, SlideImageMediaType


class _ScalarResult:
    """Stand-in for ``session.scalars(...).all()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows: list[object] = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _MemoryAlbumSession:
    """Enough of a session to create an album and read it back."""

    def __init__(self) -> None:
        self.albums: list[Album] = []
        self.used_path: str | None = None
        self.commit_count: int = 0

    def add(self, row: object) -> None:
        if isinstance(row, Album) and row not in self.albums:
            self.albums.append(row)

    def delete(self, row: object) -> None:
        if isinstance(row, Album):
            self.albums = [
                album for album in self.albums if album.id != row.id
            ]

        if isinstance(row, AlbumImage):
            for album in self.albums:
                album.images = [
                    image for image in list(album.images) if image.id != row.id
                ]

    def flush(self) -> None:
        return

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        return

    def refresh(self, row: object) -> None:
        persisted_at: datetime = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)

        if getattr(row, "created_at", None) is None:
            setattr(row, "created_at", persisted_at)

        if hasattr(row, "updated_at"):
            setattr(row, "updated_at", persisted_at)

    def get(self, model: type[object], row_id: uuid.UUID) -> object | None:
        if model is Album:
            for album in self.albums:
                if album.id == row_id:
                    return album

        if model is AlbumImage:
            for album in self.albums:
                for image in list(album.images):
                    if image.id == row_id:
                        return image

        return None

    def scalars(self, statement: object) -> _ScalarResult:
        sql: str = str(statement)

        if "background_asset_ref" in sql or "image_asset_ref" in sql:
            if self.used_path is None:
                return _ScalarResult([])

            return _ScalarResult([self.used_path])

        if "albums.slug" in sql and "albums.name" not in sql:
            return _ScalarResult([album.slug for album in self.albums])

        if "FROM albums" in sql:
            return _ScalarResult(list(self.albums))

        return _ScalarResult([])


class AlbumWriteTests(unittest.TestCase):
    """Name, order, and the rule that a patch cannot drop an image."""

    def test_create_lists_and_renames_without_changing_the_slug(self) -> None:
        """A second album with the same name gets a suffixed slug."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()
        first: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Harbor"),
            session,
            None,
        )
        second: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Harbor"),
            session,
            None,
        )
        renamed: AlbumReadResponse = patch_album(
            first.id,
            AlbumPatchRequest(name="Outer harbor", images=[]),
            session,
            None,
        )
        listed: list[AlbumListItemResponse] = list_albums(session)

        self.assertEqual(first.slug, "harbor")
        self.assertEqual(first.images, [])
        self.assertEqual(second.slug, "harbor-2")
        self.assertEqual(renamed.name, "Outer harbor")
        self.assertEqual(renamed.slug, "harbor")
        self.assertEqual(len(listed), 2)

    def test_blank_name_is_rejected(self) -> None:
        """A blank name does not create a row."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()

        with self.assertRaises(HTTPException) as raised:
            create_album(AlbumCreateRequest(name="  "), session, None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(session.albums, [])

    def test_patch_reorders_and_refuses_a_missing_image(self) -> None:
        """Order is the patch list. A stale list that drops a row is 400."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()
        created: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Lamps"),
            session,
            None,
        )
        album: Album | None = session.get(Album, created.id)
        self.assertIsNotNone(album)
        assert album is not None
        first_image: AlbumImage = _stored_image(album, 0, "albums/lamps/first.jpg")
        second_image: AlbumImage = _stored_image(album, 1, "albums/lamps/second.jpg")
        album.images = [first_image, second_image]
        reordered: AlbumReadResponse = patch_album(
            created.id,
            AlbumPatchRequest(
                name="Lamps",
                images=[
                    _image_write(second_image.id, "Second"),
                    _image_write(first_image.id, "First"),
                ],
            ),
            session,
            None,
        )

        self.assertEqual([image.id for image in reordered.images], [second_image.id, first_image.id])
        self.assertEqual([image.position for image in reordered.images], [0, 1])
        self.assertEqual(reordered.images[0].alt_text, "Second")

        with self.assertRaises(HTTPException) as raised:
            patch_album(
                created.id,
                AlbumPatchRequest(name="Lamps", images=[_image_write(first_image.id, "Only")]),
                session,
                None,
            )

        self.assertEqual(raised.exception.status_code, 400)
        kept: AlbumReadResponse = get_album(created.id, session)
        self.assertEqual(len(kept.images), 2)

    def test_upload_stores_under_the_album_and_delete_removes_the_file(self) -> None:
        """An album-page upload is ``albums/<album>/<image>.ext``. Delete unlinks it."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()
        created: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Scans"),
            session,
            None,
        )

        with tempfile.TemporaryDirectory() as storage_directory:
            root: Path = Path(storage_directory)
            store: LocalAlbumImageStore = LocalAlbumImageStore(root)

            with patch("app.api.v1.albums.configured_album_image_store", return_value=store), patch(
                "app.carousels.image_store.configured_album_image_store",
                return_value=store,
            ):
                uploaded = upload_album_image(
                    created.id,
                    UploadFile(file=io.BytesIO(_jpeg_bytes()), filename="scan.jpg"),
                    SlideImageLicense.CC0,
                    "bench",
                    "Scan",
                    "",
                    session,
                    None,
                )
                image_path: Path = root / uploaded.relative_path
                path_parts: list[str] = uploaded.relative_path.split("/")
                self.assertTrue(image_path.is_file())
                self.assertEqual(path_parts[0], "albums")
                self.assertEqual(path_parts[1], str(created.id))
                self.assertEqual(len(path_parts), 3)
                loaded: AlbumReadResponse = get_album(created.id, session)
                self.assertEqual(len(loaded.images), 1)
                delete_album_image(created.id, uploaded.id, session, None)
                self.assertFalse(image_path.exists())

        emptied: AlbumReadResponse = get_album(created.id, session)
        self.assertEqual(emptied.images, [])

    def test_delete_blocks_when_a_skeleton_stores_the_path(self) -> None:
        """A path still on a skeleton is 409 and the album stays."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()
        created: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Default"),
            session,
            None,
        )
        album: Album | None = session.get(Album, created.id)
        assert album is not None
        image: AlbumImage = _stored_image(album, 0, "theme-defaults/hong-kong-skyline.jpg")
        album.images = [image]
        session.used_path = image.relative_path

        with self.assertRaises(HTTPException) as raised:
            delete_album(created.id, session, None)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIsNotNone(session.get(Album, created.id))

    def test_delete_removes_an_unused_album(self) -> None:
        """An album whose files are not on a skeleton is removed."""

        session: _MemoryAlbumSession = _MemoryAlbumSession()
        created: AlbumReadResponse = create_album(
            AlbumCreateRequest(name="Spare"),
            session,
            None,
        )
        delete_album(created.id, session, None)

        with self.assertRaises(HTTPException) as raised:
            get_album(created.id, session)

        self.assertEqual(raised.exception.status_code, 404)


def _stored_image(album: Album, position: int, relative_path: str) -> AlbumImage:
    """Return an image row already on the album. No bytes."""

    image: AlbumImage = AlbumImage(
        id=uuid.uuid4(),
        album_id=album.id,
        position=position,
        relative_path=relative_path,
        media_type=SlideImageMediaType.JPEG,
        byte_size=12,
        width=8,
        height=8,
        alt_text=None,
        license=SlideImageLicense.OWNED,
        source="bench",
        license_note="",
        intake=SlideImageIntake.UPLOAD,
        thumbnail_path=None,
    )

    return image


def _image_write(image_id: uuid.UUID, alt_text: str) -> AlbumImageWrite:
    """Return a patch row that keeps the license and changes the alt text."""

    image_write: AlbumImageWrite = AlbumImageWrite(
        id=image_id,
        alt_text=alt_text,
        license=SlideImageLicense.OWNED,
        source="bench",
        license_note="",
    )

    return image_write


def _jpeg_bytes() -> bytes:
    """Return a tiny JPEG the intake checks accept."""

    buffer: io.BytesIO = io.BytesIO()
    image: Image.Image = Image.new("RGB", (8, 8), (20, 80, 140))
    image.save(buffer, format="JPEG")

    return buffer.getvalue()
