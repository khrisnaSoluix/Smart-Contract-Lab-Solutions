import unittest
from datetime import date
from tools.green_days.green_day_calendar_generator import (
    GreenDayDateGenerator,
)
from typing import Set


class TestGreenDayCalendarGenerator(unittest.TestCase):
    def setUp(self):
        # All New South Wales holidays 2022
        self.holidays: Set[date] = set(
            [
                date(2022, 1, 1),
                date(2022, 1, 3),
                date(2022, 1, 26),
                date(2022, 4, 15),
                date(2022, 4, 16),
                date(2022, 4, 17),
                date(2022, 4, 18),
                date(2022, 4, 25),
                date(2022, 6, 13),
                date(2022, 8, 1),
                date(2022, 10, 3),
                date(2022, 12, 25),
                date(2022, 12, 26),
                date(2022, 12, 27),
            ]
        )

    def calculate_num_expected_green_days(self):
        num_days_in_2022 = 365
        num_weekend_days = 105
        num_holidays = len(self.holidays)
        num_holidays_on_weekends = len(set(filter(lambda d: d.weekday() > 4, self.holidays)))
        num_expected_green_days = (
            num_days_in_2022 - num_weekend_days - num_holidays + num_holidays_on_weekends
        )
        return num_expected_green_days

    def test_is_weekday(self):
        weekday = date(2022, 1, 3)
        calendar_generator = GreenDayDateGenerator()
        self.assertTrue(calendar_generator.is_weekday(weekday))

    def test_is_not_weekday(self):
        weekend = date(2022, 1, 1)
        calendar_generator = GreenDayDateGenerator()
        self.assertFalse(calendar_generator.is_weekday(weekend))

    def test_generate_green_days(self):
        calendar_generator = GreenDayDateGenerator()
        green_days = calendar_generator.generate_green_days_for(2022, self.holidays)
        num_expected_green_days = self.calculate_num_expected_green_days()
        self.assertEqual(len(green_days), num_expected_green_days)
        for day in green_days:
            self.assertNotIn(day, self.holidays)
            self.assertLess(day.weekday(), 5)

    def test_generate_green_days_for_invalid_range(self):
        start_year = 2022
        end_year = 2021
        calendar_generator = GreenDayDateGenerator()
        with self.assertRaises(ValueError) as ex:
            calendar_generator.generate_green_days_for_range(start_year, end_year, self.holidays)

        self.assertTrue(
            f"Argument 'end-year' ({end_year}) cannot be before "
            + f"argument 'start-year' ({start_year})."
            in str(ex.exception)
        )

    def test_generate_green_days_for_invalid_start_year(self):
        start_year = None
        end_year = 2022
        calendar_generator = GreenDayDateGenerator()
        with self.assertRaises(ValueError) as ex:
            calendar_generator.generate_green_days_for_range(start_year, end_year, self.holidays)

        self.assertTrue("Argument 'start-year' cannot be None." in str(ex.exception))

    def test_generate_green_days_for_invalid_year(self):
        year = None
        calendar_generator = GreenDayDateGenerator()
        with self.assertRaises(ValueError) as ex:
            calendar_generator.generate_green_days_for(year, self.holidays)

        self.assertTrue("Argument 'year' cannot be None." in str(ex.exception))

    def test_generate_green_days_for_range(self):
        calendar_generator = GreenDayDateGenerator()
        green_days = calendar_generator.generate_green_days_for_range(2022, 2022, self.holidays)
        num_expected_green_days = self.calculate_num_expected_green_days()
        self.assertEqual(len(green_days), num_expected_green_days)
        for day in green_days:
            self.assertNotIn(day, self.holidays)
            self.assertLess(day.weekday(), 5)
