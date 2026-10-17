"""Frozen check SQL for Alembic revisions that still import this path.

The live tables are ``carousels`` and ``slides``. These strings keep the
old enum casts and ``source_id`` paths so historical revisions replay
against the types that exist at that point in the chain. This module
does not register ORM tables.
"""

CONTENT_SOURCE_NAME_CHECK_SQL: str = (
    "btrim(name) <> '' AND btrim(slug) <> ''"
)
UNIT_POSITION_CHECK_SQL: str = "position >= 0"
UNIT_NAME_CHECK_SQL: str = "btrim(name) <> ''"
UNIT_FIELD_TEXT_CHECK_SQL: str = "btrim(label) <> '' AND btrim(value) <> ''"
UNIT_IMAGE_SOURCE_CHECK_SQL: str = "btrim(source) <> ''"
UNIT_IMAGE_BYTE_SIZE_CHECK_SQL: str = "byte_size > 0"
UNIT_IMAGE_LICENSE_NOTE_CHECK_SQL: str = (
    "("
    "license <> 'licensed'::unit_image_license"
    " AND license_note = ''"
    ") OR ("
    "license = 'licensed'::unit_image_license"
    " AND btrim(license_note) <> ''"
    ")"
)
UNIT_IMAGE_DIMENSIONS_CHECK_SQL: str = (
    "("
    "media_type = 'svg'::unit_image_media_type"
    " AND width IS NULL"
    " AND height IS NULL"
    " AND thumbnail_path IS NULL"
    ") OR ("
    "media_type <> 'svg'::unit_image_media_type"
    " AND width > 0"
    " AND height > 0"
    ")"
)
RESOURCE_FILE_MAX_BYTES: int = 2 * 1024 * 1024
RESOURCE_FILE_PROVENANCE_CHECK_SQL: str = "btrim(provenance) <> ''"
RESOURCE_FILE_FILENAME_CHECK_SQL: str = (
    "btrim(original_filename) <> ''"
    " AND strpos(original_filename, '/') = 0"
    " AND strpos(original_filename, chr(92)) = 0"
)
RESOURCE_FILE_BYTE_SIZE_CHECK_SQL: str = (
    f"byte_size > 0 AND byte_size <= {RESOURCE_FILE_MAX_BYTES}"
)
RESOURCE_FILE_PATH_CHECK_SQL: str = (
    "("
    "media_type = 'markdown'::resource_file_media_type"
    " AND relative_path = ('resources/' || source_id::text || '/body.md')"
    ") OR ("
    "media_type = 'plain'::resource_file_media_type"
    " AND relative_path = ('resources/' || source_id::text || '/body.txt')"
    ")"
)
UNIT_IMAGE_PATH_CHECK_SQL: str = (
    "btrim(relative_path) = relative_path"
    " AND relative_path <> ''"
    " AND strpos(relative_path, '..') = 0"
    " AND strpos(relative_path, ':') = 0"
    " AND strpos(relative_path, chr(92)) = 0"
    " AND left(relative_path, 1) <> '/'"
    " AND ("
    "lower(right(relative_path, 4)) IN ('.svg', '.png', '.jpg')"
    " OR lower(right(relative_path, 5)) = '.jpeg'"
    ")"
)
