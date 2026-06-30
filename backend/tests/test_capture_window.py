import unittest
from datetime import datetime

from backend.services.capture_window import is_within_window, window_timezone

_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi)


class IsWithinWindowTestCase(unittest.TestCase):
    def test_no_window_or_empty_ranges_always_true(self):
        dt = _at(2026, 6, 30, 3, 0)
        self.assertTrue(is_within_window(dt, None))
        self.assertTrue(is_within_window(dt, {}))
        self.assertTrue(is_within_window(dt, {"ranges": []}))

    def test_same_day_range_inclusive_start_exclusive_end(self):
        win = {"ranges": [["06:00", "18:00"]]}
        self.assertTrue(is_within_window(_at(2026, 6, 30, 6, 0), win))    # start inclusive
        self.assertTrue(is_within_window(_at(2026, 6, 30, 12, 0), win))
        self.assertFalse(is_within_window(_at(2026, 6, 30, 18, 0), win))  # end exclusive
        self.assertFalse(is_within_window(_at(2026, 6, 30, 5, 59), win))
        self.assertFalse(is_within_window(_at(2026, 6, 30, 20, 0), win))

    def test_multiple_ranges(self):
        win = {"ranges": [["06:00", "10:00"], ["14:00", "18:00"]]}
        self.assertTrue(is_within_window(_at(2026, 6, 30, 8, 0), win))
        self.assertFalse(is_within_window(_at(2026, 6, 30, 12, 0), win))  # gap
        self.assertTrue(is_within_window(_at(2026, 6, 30, 16, 0), win))

    def test_overnight_range(self):
        win = {"ranges": [["22:00", "02:00"]]}
        self.assertTrue(is_within_window(_at(2026, 6, 30, 23, 0), win))   # evening
        self.assertTrue(is_within_window(_at(2026, 6, 30, 1, 0), win))    # after midnight
        self.assertFalse(is_within_window(_at(2026, 6, 30, 2, 0), win))   # end exclusive
        self.assertFalse(is_within_window(_at(2026, 6, 30, 12, 0), win))

    def test_days_filter_same_day(self):
        dt = _at(2026, 6, 30, 9, 0)
        today = _NAMES[dt.weekday()]
        other = _NAMES[(dt.weekday() + 1) % 7]
        self.assertTrue(is_within_window(dt, {"ranges": [["06:00", "18:00"]], "days": [today]}))
        self.assertFalse(is_within_window(dt, {"ranges": [["06:00", "18:00"]], "days": [other]}))

    def test_days_filter_overnight_morning_uses_start_day(self):
        # 01:00 belongs to the previous day's window.
        dt = _at(2026, 6, 30, 1, 0)
        start_day = _NAMES[(dt.weekday() - 1) % 7]
        self.assertTrue(is_within_window(dt, {"ranges": [["22:00", "02:00"]], "days": [start_day]}))
        self.assertFalse(is_within_window(dt, {"ranges": [["22:00", "02:00"]], "days": [_NAMES[dt.weekday()]]}))


class WindowTimezoneTestCase(unittest.TestCase):
    def test_defaults_to_taipei(self):
        self.assertEqual("Asia/Taipei", str(window_timezone(None)))
        self.assertEqual("Asia/Taipei", str(window_timezone({})))

    def test_explicit_timezone(self):
        self.assertEqual("UTC", str(window_timezone({"timezone": "UTC"})))


if __name__ == "__main__":
    unittest.main()
