"""Unit tests for desktop/timetext.py."""

import unittest
from datetime import datetime

from fakes import ROOT  # noqa: F401  (puts desktop/ on sys.path)
from timetext import clock, countdown, days_text, hours_text, minutes_until


def ts(text):
    return datetime.fromisoformat(text).timestamp()


class DaysTextTest(unittest.TestCase):
    def test_names_common_sets(self):
        self.assertEqual(days_text([1, 2, 3, 4, 5, 6, 7]), "Every day")
        self.assertEqual(days_text([5, 4, 3, 2, 1]), "Weekdays")
        self.assertEqual(days_text([7, 6]), "Weekends")
        self.assertEqual(days_text([1, 3, 5]), "Mon, Wed, Fri")


class HoursTextTest(unittest.TestCase):
    def test_window_and_all_day(self):
        self.assertEqual(hours_text("22:30", "07:00"), "22:30–07:00")
        self.assertEqual(hours_text("00:00", "00:00"), "all day")


class ClockTest(unittest.TestCase):
    def test_today_shows_time_only(self):
        now = ts("2026-10-19T12:00")
        self.assertEqual(clock(ts("2026-10-19T18:05") * 1000, now), "18:05")

    def test_other_day_shows_weekday(self):
        now = ts("2026-10-19T23:00")
        self.assertEqual(clock(ts("2026-10-20T07:00") * 1000, now), "Tue 07:00")


class CountdownTest(unittest.TestCase):
    def test_minutes_and_hours(self):
        now = ts("2026-10-19T12:00")
        self.assertEqual(countdown(ts("2026-10-19T12:01") * 1000, now), "in 1 minute")
        self.assertEqual(countdown(ts("2026-10-19T12:45") * 1000, now), "in 45 minutes")
        self.assertEqual(countdown(ts("2026-10-19T14:00") * 1000, now), "in 2 hours")
        self.assertEqual(countdown(ts("2026-10-19T13:20") * 1000, now), "in 1 h 20 min")
        self.assertEqual(countdown(ts("2026-10-19T11:00") * 1000, now), "in 0 minutes")


class MinutesUntilTest(unittest.TestCase):
    def test_later_today(self):
        self.assertEqual(minutes_until(18, 0, ts("2026-10-19T16:30")), 90)

    def test_past_time_means_tomorrow(self):
        self.assertEqual(minutes_until(7, 0, ts("2026-10-19T22:00")), 9 * 60)

    def test_same_minute_means_tomorrow(self):
        self.assertEqual(minutes_until(16, 30, ts("2026-10-19T16:30:20")), 24 * 60)


if __name__ == "__main__":
    unittest.main()
