"""Create, replace, and stream a resource file.

A failure writes nothing. Replacing the file is a new upload. Readers
may GET the bytes. Admins upload, replace, and delete.
"""

from __future__ import annotations

import uuid

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.persist import commit_database_session_or_raise_conflict
from app.api.v1.schemas import SourceReadResponse
from app.api.v1.source_writes import SOURCE_SLUG_CONFLICT_DETAIL, _require_name
from app.api.v1.lookups import fetch_content_source_by_id_or_raise
from app.auth.dependencies import require_admin_ops_operator
from app.db import get_our_database_session
from app.models.content_source import ContentSource, ResourceFile
from app.models.enums import ContentSourceKind, ResourceFileMediaType
from app.models.ops_user import OpsUser
from app.sources.editing import (
    RESOURCE_NOT_IN_SLICE_DETAIL,
    allocate_unique_source_slug,
    new_row_id,
    slugify_source_name,
)
from app.sources.resource_files import (
    PreparedResourceFile,
    ResourceFileError,
    prepare_resource_upload,
    require_provenance,
)
from app.sources.resource_store import (
    LocalResourceFileStore,
    configured_resource_file_store,
    resource_body_relative_path,
)
from app.storage.artifacts import ArtifactAssetPathEscapeError


RESOURCE_MEDIA_TYPES: dict[ResourceFileMediaType, str] = {
    ResourceFileMediaType.MARKDOWN: "text/markdown; charset=utf-8",
    ResourceFileMediaType.PLAIN: "text/plain; charset=utf-8",
}


def register_source_resource_routes(sources_router: APIRouter) -> None:
    """Attach resource create, replace, and download."""

    sources_router.add_api_route(
        "/resource",
        create_resource_source_upload,
        methods=["POST"],
        response_model=SourceReadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    sources_router.add_api_route(
        "/{source_id}/resource",
        replace_resource_file,
        methods=["PUT"],
        response_model=SourceReadResponse,
    )
    sources_router.add_api_route(
        "/{source_id}/resource",
        get_resource_file,
        methods=["GET"],
    )


def create_resource_source_upload(
    name: str = Form(...),
    provenance: str = Form(...),
    file: UploadFile = File(...),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SourceReadResponse:
    """Create a resource from one Markdown or TXT upload."""

    _ = current_ops_operator
    payload: bytes = file.file.read()
    created_source: SourceReadResponse = create_resource_source(
        name,
        provenance,
        file.filename or "",
        payload,
        our_database_session,
        configured_resource_file_store(),
    )

    return created_source


def create_resource_source(
    name: str,
    provenance: str,
    filename: str,
    payload: bytes,
    our_database_session: Session,
    file_store: LocalResourceFileStore,
) -> SourceReadResponse:
    """Validate, then write the row and the file. A failure leaves neither.

    Args:
        name: Resource name. The slug is derived from it.
        provenance: Required note about where the text came from.
        filename: Uploaded file name. The suffix selects Markdown or TXT.
        payload: File bytes.
        our_database_session: Open session.
        file_store: Where the bytes go.

    Returns:
        The new resource, including the stored text.
    """

    resource_name: str = _require_name(name)
    cleaned_provenance, prepared_file = _prepared_or_400(provenance, filename, payload)
    source_id: uuid.UUID = new_row_id()
    relative_path: str = resource_body_relative_path(source_id, prepared_file.extension)
    taken_slugs: set[str] = set(
        our_database_session.scalars(select(ContentSource.slug)).all(),
    )
    resource_slug: str = allocate_unique_source_slug(
        slugify_source_name(resource_name),
        taken_slugs,
    )
    created_source: ContentSource = ContentSource(
        id=source_id,
        kind=ContentSourceKind.RESOURCE,
        name=resource_name,
        slug=resource_slug,
    )
    created_source.units = []
    created_file: ResourceFile = ResourceFile(
        source_id=source_id,
        relative_path=relative_path,
        media_type=prepared_file.media_type,
        byte_size=len(prepared_file.payload),
        original_filename=prepared_file.original_filename,
        provenance=cleaned_provenance,
    )
    created_source.resource_file = created_file
    saved_path: str | None = None

    try:
        file_store.save(relative_path, prepared_file.payload)
        saved_path = relative_path
        our_database_session.add(created_source)
        our_database_session.add(created_file)
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail=SOURCE_SLUG_CONFLICT_DETAIL,
        )
    except Exception:
        if saved_path is not None:
            file_store.delete(saved_path)

        raise

    our_database_session.refresh(created_source)

    from app.api.v1.sources import serialize_content_source

    return serialize_content_source(created_source)


def replace_resource_file(
    source_id: uuid.UUID,
    file: UploadFile = File(...),
    our_database_session: Session = Depends(get_our_database_session),
    current_ops_operator: OpsUser | None = Depends(require_admin_ops_operator),
) -> SourceReadResponse:
    """Replace the file. The provenance note stays. A bad file writes nothing."""

    _ = current_ops_operator
    payload: bytes = file.file.read()
    replaced_source: SourceReadResponse = replace_resource_bytes(
        source_id,
        file.filename or "",
        payload,
        our_database_session,
        configured_resource_file_store(),
    )

    return replaced_source


def replace_resource_bytes(
    source_id: uuid.UUID,
    filename: str,
    payload: bytes,
    our_database_session: Session,
    file_store: LocalResourceFileStore,
) -> SourceReadResponse:
    """Swap the stored bytes after the new file has passed the checks."""

    found_source: ContentSource = _fetch_resource_or_raise(source_id, our_database_session)
    found_file: ResourceFile | None = found_source.resource_file

    if found_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This resource has no file.",
        )

    _prepared_name, prepared_file = _prepared_or_400(found_file.provenance, filename, payload)
    next_path: str = resource_body_relative_path(source_id, prepared_file.extension)
    previous_path: str = found_file.relative_path
    previous_payload: bytes = _read_optional(file_store, previous_path)
    wrote_new_path: bool = False

    try:
        file_store.save(next_path, prepared_file.payload)
        wrote_new_path = next_path != previous_path
        found_file.relative_path = next_path
        found_file.media_type = prepared_file.media_type
        found_file.byte_size = len(prepared_file.payload)
        found_file.original_filename = prepared_file.original_filename
        commit_database_session_or_raise_conflict(
            our_database_session,
            conflict_detail="Resource file could not be replaced.",
        )
    except Exception:
        if wrote_new_path:
            file_store.delete(next_path)

        if next_path == previous_path and previous_payload != b"":
            file_store.save(previous_path, previous_payload)

        raise

    if next_path != previous_path:
        file_store.delete(previous_path)

    our_database_session.refresh(found_source)

    from app.api.v1.sources import serialize_content_source

    return serialize_content_source(found_source)


def get_resource_file(
    source_id: uuid.UUID,
    download: bool = Query(default=False),
    our_database_session: Session = Depends(get_our_database_session),
) -> FileResponse:
    """Stream the stored file. Readers may call this.

    ``download=1`` asks the browser to save the file. The bytes are the
    upload, not the rendered HTML.
    """

    found_source: ContentSource = _fetch_resource_or_raise(source_id, our_database_session)
    found_file: ResourceFile | None = found_source.resource_file

    if found_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource file is missing.",
        )

    file_store: LocalResourceFileStore = configured_resource_file_store()

    try:
        stored_path: Path = file_store.open(found_file.relative_path)
    except ArtifactAssetPathEscapeError as escape_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resource path is not allowed.",
        ) from escape_error

    if not stored_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource file is missing.",
        )

    disposition: str = "attachment" if download else "inline"
    safe_filename: str = (
        found_file.original_filename.replace('"', "").replace("\r", "").replace("\n", "")
    )
    file_response: FileResponse = FileResponse(
        path=stored_path,
        media_type=RESOURCE_MEDIA_TYPES[found_file.media_type],
        filename=safe_filename,
        content_disposition_type=disposition,
    )

    return file_response


def _prepared_or_400(
    provenance: str,
    filename: str,
    payload: bytes,
) -> tuple[str, PreparedResourceFile]:
    """Return the note and the prepared file, or 400. Does not write."""

    try:
        cleaned_provenance: str = require_provenance(provenance)
        prepared_file: PreparedResourceFile = prepare_resource_upload(filename, payload)
    except ResourceFileError as resource_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resource_error.detail,
        ) from resource_error

    return cleaned_provenance, prepared_file


def _fetch_resource_or_raise(
    source_id: uuid.UUID,
    our_database_session: Session,
) -> ContentSource:
    """Return a resource source. An album is 400."""

    found_source: ContentSource = fetch_content_source_by_id_or_raise(
        source_id,
        our_database_session,
    )

    if found_source.kind != ContentSourceKind.RESOURCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=RESOURCE_NOT_IN_SLICE_DETAIL,
        )

    return found_source


def _read_optional(file_store: LocalResourceFileStore, relative_path: str) -> bytes:
    """Return the current bytes, or empty when the file is already gone."""

    try:
        stored_path: Path = file_store.open(relative_path)
    except ArtifactAssetPathEscapeError:

        return b""

    if not stored_path.is_file():

        return b""

    previous_payload: bytes = stored_path.read_bytes()

    return previous_payload
