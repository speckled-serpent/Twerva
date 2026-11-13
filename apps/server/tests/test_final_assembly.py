"""Final assembly groups live slides under a cap and keeps exclusions."""

import unittest
import uuid

from app.campaigns.assemble import assemble_carousels
from app.carousels.final_assembly import plan_final_groups


SLIDE_A: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01")
SLIDE_B: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02")
SLIDE_C: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa03")
SLIDE_D: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa04")
SLIDE_E: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa05")
SLIDE_F: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa06")
SIX_SLIDES: list[uuid.UUID] = [SLIDE_A, SLIDE_B, SLIDE_C, SLIDE_D, SLIDE_E, SLIDE_F]


class PlanFinalGroupsTests(unittest.TestCase):
    """The cap splits a legal pick. An excluded pair still splits a group."""

    def test_a_cap_of_five_splits_six_slides_in_order(self) -> None:
        """Six slides with no exclusions become five, then the sixth."""

        groups: list[list[uuid.UUID]] = plan_final_groups(SIX_SLIDES, [], 5)

        self.assertEqual(groups, [SIX_SLIDES[:5], [SLIDE_F]])

    def test_three_slides_under_the_cap_stay_one_group(self) -> None:
        """A cap of 8 does not split three slides that can be shown together."""

        groups: list[list[uuid.UUID]] = plan_final_groups(
            [SLIDE_A, SLIDE_B, SLIDE_C],
            [],
            8,
        )

        self.assertEqual(groups, [[SLIDE_A, SLIDE_B, SLIDE_C]])

    def test_a_cap_of_one_returns_one_group_per_slide(self) -> None:
        """Each slide is its own group when the cap is 1."""

        groups: list[list[uuid.UUID]] = plan_final_groups(
            [SLIDE_A, SLIDE_B, SLIDE_C],
            [],
            1,
        )

        self.assertEqual(groups, [[SLIDE_A], [SLIDE_B], [SLIDE_C]])

    def test_an_exclusion_splits_before_the_cap_does(self) -> None:
        """A cannot sit with B, so C joins A and B starts the next group."""

        groups: list[list[uuid.UUID]] = plan_final_groups(
            [SLIDE_A, SLIDE_B, SLIDE_C],
            [(SLIDE_A, SLIDE_B), (SLIDE_B, SLIDE_A)],
            8,
        )

        self.assertEqual(groups, [[SLIDE_A, SLIDE_C], [SLIDE_B]])

    def test_an_empty_list_returns_no_groups(self) -> None:
        """Nothing live is nothing assembled."""

        groups: list[list[uuid.UUID]] = plan_final_groups([], [(SLIDE_A, SLIDE_B)], 5)

        self.assertEqual(groups, [])

    def test_assemble_carousels_still_packs_six_slides_into_one_group(self) -> None:
        """The campaign run has no size cap."""

        carousels: list[list[uuid.UUID]] = assemble_carousels(SIX_SLIDES, [])

        self.assertEqual(carousels, [SIX_SLIDES])


if __name__ == "__main__":
    unittest.main()
