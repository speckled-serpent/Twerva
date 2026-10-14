"""Resource upload, replace, provenance, and safe Markdown rendering."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TWERVA_ENV", "test")

from fastapi import HTTPException

from app.api.v1.schemas import SourcePatchRequest
from app.api.v1.source_resources import create_resource_source, replace_resource_bytes
from app.api.v1.source_writes import delete_content_source, patch_content_source
from app.api.v1.sources import get_content_source
from app.models.content_source import RESOURCE_FILE_MAX_BYTES
from app.models.enums import ContentSourceKind, ResourceFileMediaType
from app.sources.resource_markdown import render_markdown_document
from app.sources.resource_store import LocalResourceFileStore
from app.themes.default_images import resolve_theme_image_path
from app.sources.default_album import default_unit_seeds
from tests.test_source_writes import _MemorySourceSession


MARKDOWN_BODY: bytes = b"# Harbor\n\n<script>alert(1)</script>\n\n[go](javascript:alert(1))\n"
PLAIN_BODY: bytes = b"A lamp on the desk.\n"


class MarkdownRenderTests(unittest.TestCase):
    """Rendered HTML escapes raw markup and refuses unsafe links."""

    def test_script_and_javascript_links_stay_text(self) -> None:
        """A heading renders. A script tag and a javascript URL do not."""

        rendered: str = render_markdown_document(MARKDOWN_BODY.decode("utf-8"))

        self.assertIn("<h1>Harbor</h1>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("href=\"javascript:", rendered)
        self.assertIn("javascript:alert(1)", rendered)


class ResourceFileTests(unittest.TestCase):
    """Rows and files appear together, or not at all."""

    def test_markdown_upload_round_trips_and_txt_works(self) -> None:
        """The stored bytes match the upload. A txt file is plain text."""

        session, store, directory = _resource_session()

        with patch(
            "app.sources.resource_store.configured_resource_file_store",
            return_value=store,
        ):
            created = create_resource_source(
                " Harbor notes ",
                "  museum scan  ",
                "notes.md",
                MARKDOWN_BODY,
                session,
                store,
            )
            reloaded = get_content_source(created.id, session)
            plain = create_resource_source(
                "Desk",
                "owned scan",
                "desk.TXT",
                PLAIN_BODY,
                session,
                store,
            )

        self.assertEqual(created.kind, ContentSourceKind.RESOURCE)
        self.assertEqual(created.resource.provenance, "museum scan")
        self.assertEqual(created.resource.media_type, ResourceFileMediaType.MARKDOWN)
        self.assertEqual(created.resource.body, MARKDOWN_BODY.decode("utf-8"))
        self.assertEqual(created.resource.rendered_html, reloaded.resource.rendered_html)
        self.assertTrue(created.resource.relative_path.endswith("/body.md"))
        stored_bytes: bytes = (directory / created.resource.relative_path).read_bytes()
        self.assertEqual(stored_bytes, MARKDOWN_BODY)
        self.assertEqual(plain.resource.media_type, ResourceFileMediaType.PLAIN)
        self.assertIsNone(plain.resource.rendered_html)
        self.assertEqual(plain.resource.body, PLAIN_BODY.decode("utf-8"))
        self.assertTrue((directory / plain.resource.relative_path).read_bytes() == PLAIN_BODY)

    def test_pdf_and_blank_note_leave_no_row_or_file(self) -> None:
        """A PDF and a missing note are 400. Nothing is written."""

        session, store, directory = _resource_session()
        commits_before: int = session.commit_count

        with self.assertRaises(HTTPException) as pdf_error:
            create_resource_source(
                "Bad",
                "somewhere",
                "scan.pdf",
                b"%PDF-1.4\n",
                session,
                store,
            )

        with self.assertRaises(HTTPException) as note_error:
            create_resource_source(
                "Bad",
                "   ",
                "notes.md",
                b"# Hi\n",
                session,
                store,
            )

        with self.assertRaises(HTTPException) as disguised_error:
            create_resource_source(
                "Bad",
                "somewhere",
                "notes.md",
                b"%PDF-1.4 disguised\n",
                session,
                store,
            )

        oversize: bytes = b"# " + (b"a" * RESOURCE_FILE_MAX_BYTES)

        with self.assertRaises(HTTPException) as size_error:
            create_resource_source(
                "Bad",
                "somewhere",
                "notes.md",
                oversize,
                session,
                store,
            )

        self.assertEqual(pdf_error.exception.status_code, 400)
        self.assertEqual(note_error.exception.status_code, 400)
        self.assertEqual(disguised_error.exception.status_code, 400)
        self.assertEqual(size_error.exception.status_code, 400)
        self.assertEqual(session.commit_count, commits_before)
        self.assertEqual(session.sources, [])
        self.assertEqual(list(directory.rglob("*")), [])

    def test_replace_provenance_and_delete(self) -> None:
        """Replace swaps the bytes. A blank note writes nothing. Delete removes the file."""

        session, store, directory = _resource_session()

        with patch(
            "app.sources.resource_store.configured_resource_file_store",
            return_value=store,
        ):
            created = create_resource_source(
                "Harbor notes",
                "museum scan",
                "notes.md",
                MARKDOWN_BODY,
                session,
                store,
            )
            commits_before: int = session.commit_count

            with self.assertRaises(HTTPException) as blank_note:
                patch_content_source(
                    created.id,
                    SourcePatchRequest(name="Harbor notes", provenance="  "),
                    session,
                    None,
                )

            self.assertEqual(blank_note.exception.status_code, 400)
            self.assertEqual(session.commit_count, commits_before)
            self.assertEqual(
                get_content_source(created.id, session).resource.provenance,
                "museum scan",
            )

            renamed = patch_content_source(
                created.id,
                SourcePatchRequest(name="Outer harbor", provenance="gift from the desk"),
                session,
                None,
            )
            replaced = replace_resource_bytes(
                created.id,
                "desk.txt",
                PLAIN_BODY,
                session,
                store,
            )

            self.assertEqual(renamed.resource.provenance, "gift from the desk")
            self.assertEqual(replaced.resource.media_type, ResourceFileMediaType.PLAIN)
            self.assertEqual(replaced.resource.body, PLAIN_BODY.decode("utf-8"))
            self.assertFalse((directory / created.resource.relative_path).exists())
            self.assertEqual(
                (directory / replaced.resource.relative_path).read_bytes(),
                PLAIN_BODY,
            )

            package_path: Path = resolve_theme_image_path(
                default_unit_seeds()[0].relative_path,
                directory,
            )
            delete_content_source(created.id, session, None)

        self.assertFalse((directory / replaced.resource.relative_path).exists())
        self.assertTrue(package_path.is_file())
        self.assertEqual(len(session.deleted), 1)


def _resource_session() -> tuple[_MemorySourceSession, LocalResourceFileStore, Path]:
    """Return a memory session and a temp artifact directory."""

    session: _MemorySourceSession = _MemorySourceSession()
    directory: Path = Path(tempfile.mkdtemp(prefix="twerva-resources-"))
    file_store: LocalResourceFileStore = LocalResourceFileStore(directory)

    return session, file_store, directory
