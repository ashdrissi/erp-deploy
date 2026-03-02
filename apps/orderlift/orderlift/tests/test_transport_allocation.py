import unittest

from orderlift.sales.utils.transport_allocation import compute_transport_allocation


class TestTransportAllocation(unittest.TestCase):
    def test_by_value(self):
        calc = compute_transport_allocation(
            mode="By Value",
            container_price=2000,
            line_base_amount=600,
            totals={"total_merch_value": 3000},
        )
        self.assertAlmostEqual(calc["applied"], 400)

    def test_by_kg(self):
        calc = compute_transport_allocation(
            mode="By Kg",
            container_price=1800,
            line_weight_kg=90,
            totals={"total_weight_kg": 900},
        )
        self.assertAlmostEqual(calc["applied"], 180)

    def test_by_m3(self):
        calc = compute_transport_allocation(
            mode="By M3",
            container_price=1500,
            line_volume_m3=2,
            totals={"total_volume_m3": 10},
        )
        self.assertAlmostEqual(calc["applied"], 300)

    def test_zero_denominator_warns(self):
        calc = compute_transport_allocation(
            mode="By Kg",
            container_price=1500,
            line_weight_kg=10,
            totals={"total_weight_kg": 0},
        )
        self.assertEqual(calc["applied"], 0)
        self.assertTrue(calc["warning"])


if __name__ == "__main__":
    unittest.main()
