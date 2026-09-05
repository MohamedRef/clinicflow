import unittest

from clinicflow.interpreter_booking_capacity import (
    InterpreterBookingCapacityDemand,
    InterpreterBookingCapacityResource,
    allocate_interpreter_booking_capacity,
)


class InterpreterBookingCapacityTests(unittest.TestCase):
    def test_protects_priority_and_group_boundaries(self) -> None:
        resources = [
            InterpreterBookingCapacityResource("east-2", "east", 3),
            InterpreterBookingCapacityResource("east-1", " EAST ", 4),
            InterpreterBookingCapacityResource("west-1", "west", 8),
        ]
        demands = [
            InterpreterBookingCapacityDemand("routine", "east", 5, 1),
            InterpreterBookingCapacityDemand("urgent", "east", 6, 9),
            InterpreterBookingCapacityDemand("western", "west", 2, 3),
        ]

        decisions = allocate_interpreter_booking_capacity(resources, demands)
        self.assertEqual(
            [decision.demand_id for decision in decisions],
            ["urgent", "western", "routine"],
        )
        urgent, western, routine = decisions
        self.assertEqual(
            [(item.resource_id, item.units) for item in urgent.allocations],
            [("east-1", 4), ("east-2", 2)],
        )
        self.assertEqual(urgent.shortfall_units, 0)
        self.assertEqual(
            [(item.resource_id, item.units) for item in routine.allocations],
            [("east-2", 1)],
        )
        self.assertEqual(routine.shortfall_units, 4)
        self.assertEqual(
            [(item.resource_id, item.units) for item in western.allocations],
            [("west-1", 2)],
        )

    def test_is_deterministic_across_input_order(self) -> None:
        resources = [
            InterpreterBookingCapacityResource("b", "shared", 2),
            InterpreterBookingCapacityResource("a", "shared", 2),
        ]
        demands = [
            InterpreterBookingCapacityDemand("second", "shared", 2, 1),
            InterpreterBookingCapacityDemand("first", "shared", 3, 2),
        ]
        self.assertEqual(
            allocate_interpreter_booking_capacity(reversed(resources), reversed(demands)),
            allocate_interpreter_booking_capacity(resources, demands),
        )

    def test_rejects_unsafe_capacity(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            allocate_interpreter_booking_capacity(
                [
                    InterpreterBookingCapacityResource("same", "a", 1),
                    InterpreterBookingCapacityResource(" SAME ", "a", 2),
                ],
                [],
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            allocate_interpreter_booking_capacity([InterpreterBookingCapacityResource("resource", "a", 0)], [])
        with self.assertRaisesRegex(ValueError, "positive"):
            allocate_interpreter_booking_capacity([], [InterpreterBookingCapacityDemand("demand", "a", 1, 0)])


if __name__ == "__main__":
    unittest.main()
