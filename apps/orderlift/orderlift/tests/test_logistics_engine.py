import unittest

from orderlift.orderlift_logistics.services.capacity_math import compute_utilization, detect_limiting_factor


class TestLogisticsEngine(unittest.TestCase):
    def test_utilization_math(self):
        result = compute_utilization(11200, 26.4, 28000, 33)
        self.assertAlmostEqual(result["weight_utilization_pct"], 40.0, places=3)
        self.assertAlmostEqual(result["volume_utilization_pct"], 80.0, places=3)

    def test_limiting_factor_volume(self):
        self.assertEqual(detect_limiting_factor(40, 80), "volume")

    def test_limiting_factor_weight(self):
        self.assertEqual(detect_limiting_factor(98, 35), "weight")

    def test_limiting_factor_both(self):
        self.assertEqual(detect_limiting_factor(90.4, 90.0), "both")


if __name__ == "__main__":
    unittest.main()
