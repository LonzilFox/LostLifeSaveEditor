"""Width-allocation tests; no GUI display server required."""
from __future__ import annotations
import unittest
from table_layout import MAIN_COLUMNS, MIN_WIDTH, fitted_columns


class ResponsiveTableTests(unittest.TestCase):
    def test_fixed_state_width_and_all_columns(self):
        for available in (540, 545, 735, 885, 1500):
            with self.subTest(available=available):
                widths = fitted_columns(available)
                self.assertEqual(tuple(widths), MAIN_COLUMNS)
                self.assertEqual(widths['state'], MIN_WIDTH['state'])
                self.assertTrue(all(widths[k] >= MIN_WIDTH[k] for k in MAIN_COLUMNS))
                self.assertLessEqual(sum(widths.values()), available)

    def test_narrow_uses_horizontal_scroll_without_collapsing_status(self):
        widths = fitted_columns(320)
        self.assertGreater(sum(widths.values()), 320)
        self.assertEqual(widths['state'], 82)

    def test_increasing_width_not_lost(self):
        for size in (540, 560, 720, 1000, 1800):
            self.assertGreaterEqual(size - sum(fitted_columns(size).values()), 4)
