"""A pick refuses an excluded pair and allows every other set."""

import unittest
import uuid

from app.sources.unit_exclusions import (
    DUPLICATE_EXCLUSION_DETAIL,
    EXCLUDED_PAIR_DETAIL,
    SELF_EXCLUSION_DETAIL,
    UNKNOWN_EXCLUSION_DETAIL,
    assert_unit_pick_allowed,
    normalized_exclusion_ids,
)


class UnitPickTests(unittest.TestCase):
    """Symmetric exclusion, checked without a database."""

    def test_an_excluded_pair_is_refused_from_either_direction(self) -> None:
        """One stored direction blocks a pick that contains both units."""

        harbor: uuid.UUID = uuid.uuid4()
        desert: uuid.UUID = uuid.uuid4()
        dunes: uuid.UUID = uuid.uuid4()
        pairs: list[tuple[uuid.UUID, uuid.UUID]] = [(harbor, desert)]

        with self.assertRaises(ValueError) as forward_error:
            assert_unit_pick_allowed([harbor, desert], pairs)

        with self.assertRaises(ValueError) as reverse_error:
            assert_unit_pick_allowed([desert, harbor], pairs)

        self.assertEqual(str(forward_error.exception), EXCLUDED_PAIR_DETAIL)
        self.assertEqual(str(reverse_error.exception), EXCLUDED_PAIR_DETAIL)
        assert_unit_pick_allowed([harbor, dunes], pairs)
        assert_unit_pick_allowed([desert, dunes], pairs)
        assert_unit_pick_allowed([harbor], pairs)
        assert_unit_pick_allowed([harbor, harbor, dunes], pairs)

    def test_a_pick_without_an_excluded_pair_is_allowed(self) -> None:
        """Units that do not name each other can be shown together."""

        harbor: uuid.UUID = uuid.uuid4()
        desert: uuid.UUID = uuid.uuid4()
        dunes: uuid.UUID = uuid.uuid4()

        assert_unit_pick_allowed([harbor, desert, dunes], [])
        assert_unit_pick_allowed([], [(harbor, desert)])

    def test_normalization_rejects_self_outsiders_and_duplicates(self) -> None:
        """The stored list is other units in this source, once each."""

        harbor: uuid.UUID = uuid.uuid4()
        desert: uuid.UUID = uuid.uuid4()
        outsider: uuid.UUID = uuid.uuid4()
        siblings: set[uuid.UUID] = {desert}

        stored: list[uuid.UUID] = normalized_exclusion_ids(harbor, [desert], siblings)

        self.assertEqual(stored, [desert])

        with self.assertRaises(ValueError) as self_error:
            normalized_exclusion_ids(harbor, [harbor], siblings)

        with self.assertRaises(ValueError) as outside_error:
            normalized_exclusion_ids(harbor, [outsider], siblings)

        with self.assertRaises(ValueError) as duplicate_error:
            normalized_exclusion_ids(harbor, [desert, desert], siblings)

        self.assertEqual(str(self_error.exception), SELF_EXCLUSION_DETAIL)
        self.assertEqual(str(outside_error.exception), UNKNOWN_EXCLUSION_DETAIL)
        self.assertEqual(str(duplicate_error.exception), DUPLICATE_EXCLUSION_DETAIL)
