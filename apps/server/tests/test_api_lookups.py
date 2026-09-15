"""Fetch-or-404 helpers map missing rows to HTTP 404."""

import unittest
import uuid

from fastapi import HTTPException

from app.api.v1.lookups import fetch_brand_by_id_or_raise
from app.models import Brand


class _MissingRowSession:
    """Session stand-in whose `get` always misses."""

    def get(self, model_class: type[object], primary_key: uuid.UUID) -> None:

        return None


class LookupNotFoundTests(unittest.TestCase):
    """Unknown ids become 404 before a handler returns a body."""

    def test_fetch_brand_by_id_or_raise_returns_404(self) -> None:
        """Missing Brand primary key raises HTTP 404."""

        missing_brand_id: uuid.UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")
        fake_session: _MissingRowSession = _MissingRowSession()

        with self.assertRaises(HTTPException) as raised_http_error:
            fetch_brand_by_id_or_raise(missing_brand_id, fake_session)  # type: ignore[arg-type]

        self.assertEqual(raised_http_error.exception.status_code, 404)
        self.assertIn(str(missing_brand_id), raised_http_error.exception.detail)
        self.assertIs(Brand.__tablename__, "brands")


if __name__ == "__main__":
    unittest.main()
