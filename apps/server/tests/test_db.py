"""Engine, SessionLocal, and FastAPI session dependency exports."""

import os
import unittest
from collections.abc import Generator, Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


os.environ.setdefault("TWERVA_ENV", "test")

from app.db import (  # noqa: E402
    SessionLocal,
    engine,
    get_our_database_session,
    our_database_engine,
)


class DatabasePlumbingTests(unittest.TestCase):
    """1.2a-iii surface: engine, SessionLocal, Depends-compatible generator."""

    def test_engine_aliases_our_database_engine(self) -> None:
        """Expose both the style-guide name and the conventional `engine` alias."""

        self.assertIsInstance(our_database_engine, Engine)
        self.assertIs(engine, our_database_engine)

    def test_session_local_is_a_sessionmaker(self) -> None:
        """SessionLocal is the SQLAlchemy session factory."""

        self.assertIsInstance(SessionLocal, sessionmaker)

    def test_session_dependency_yields_and_closes_a_session(self) -> None:
        """Generator yields a Session and closes it when the request ends."""

        session_generator: Generator[Session, None, None] = get_our_database_session()
        self.assertIsInstance(session_generator, Iterator)

        our_database_session: Session = next(session_generator)
        self.assertIsInstance(our_database_session, Session)
        self.assertTrue(our_database_session.is_active)

        with self.assertRaises(StopIteration):
            next(session_generator)

        self.assertFalse(our_database_session.is_active)


if __name__ == "__main__":
    unittest.main()
