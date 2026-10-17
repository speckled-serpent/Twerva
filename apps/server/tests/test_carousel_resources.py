"""Resource routes are gone. Carousels are one kind."""

import os
import unittest

os.environ.setdefault("TWERVA_ENV", "test")

from app.api.v1.carousels import carousels_router


class ResourceRoutesRemovedTests(unittest.TestCase):
    """Album and resource are one carousel. The resource routes are unregistered."""

    def test_resource_paths_are_absent(self) -> None:
        """Create, read, and replace of a resource file are not on the router."""

        paths: set[str] = set()

        for route in carousels_router.routes:
            path: str = getattr(route, "path", "")
            paths.add(path)

        self.assertNotIn("/carousels/resource", paths)
        self.assertNotIn("/carousels/{carousel_id}/resource", paths)


if __name__ == "__main__":
    unittest.main()
