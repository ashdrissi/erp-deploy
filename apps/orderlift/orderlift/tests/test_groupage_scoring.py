import unittest

from orderlift.orderlift_logistics.services.capacity_math import candidate_pressure


class TestGroupageScoring(unittest.TestCase):
    def test_pressure_prefers_stronger_constraint(self):
        score = candidate_pressure(
            total_weight_kg=2000,
            total_volume_m3=10,
            remaining_weight_kg=20000,
            remaining_volume_m3=12,
        )
        self.assertAlmostEqual(score, 0.8333333333, places=6)

    def test_pressure_handles_zero_capacity(self):
        score = candidate_pressure(
            total_weight_kg=100,
            total_volume_m3=0.3,
            remaining_weight_kg=0,
            remaining_volume_m3=1,
        )
        self.assertAlmostEqual(score, 0.3, places=6)


if __name__ == "__main__":
    unittest.main()
