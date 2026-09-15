"""Health endpoint stays independent of DATABASE_URL."""

import asyncio
import os
import unittest

from app.main import HealthStatusResponse, get_health_status


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


if __name__ == "__main__":
    unittest.main()
