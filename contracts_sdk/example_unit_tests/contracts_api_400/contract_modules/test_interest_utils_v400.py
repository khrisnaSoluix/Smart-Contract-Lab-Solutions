from datetime import datetime
from zoneinfo import ZoneInfo
from unittest import TestCase

from contracts_api import ParameterTimeseries, OptionalValue  # type: ignore
from contracts_api.utils import timezone_utils  # type: ignore
from . import interest_utils_v400


class InterestUtilsTestCase(TestCase):
    def test_get_selected_interest_payday_with_effective_datetime(self):
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=timezone)
        next_datetime = datetime(2022, 10, 11, 1, 1, tzinfo=timezone)
        later_datetime = datetime(2022, 10, 12, 1, 1, tzinfo=timezone)
        timeseries = ParameterTimeseries(
            [
                (effective_datetime, OptionalValue(20)),
                (next_datetime, OptionalValue(21)),
                (later_datetime, OptionalValue(22)),
            ]
        )
        payday = interest_utils_v400.get_selected_interest_payday(timeseries, effective_datetime)
        self.assertEqual(20, payday)

    def test_get_selected_interest_payday_with_no_effective_datetime(self):
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=timezone)
        next_datetime = datetime(2022, 10, 11, 1, 1, tzinfo=timezone)
        later_datetime = datetime(2022, 10, 12, 1, 1, tzinfo=timezone)
        timeseries = ParameterTimeseries(
            [
                (effective_datetime, OptionalValue(20)),
                (next_datetime, OptionalValue(21)),
                (later_datetime, OptionalValue(22)),
            ]
        )
        payday = interest_utils_v400.get_selected_interest_payday(timeseries)
        self.assertEqual(22, payday)

    def test_get_selected_interest_payday_with_no_set_values(self):
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 10, 10, 1, 1, tzinfo=timezone)
        next_datetime = datetime(2022, 10, 11, 1, 1, tzinfo=timezone)
        later_datetime = datetime(2022, 10, 12, 1, 1, tzinfo=timezone)
        timeseries = ParameterTimeseries(
            [
                (effective_datetime, OptionalValue()),
                (next_datetime, OptionalValue()),
                (later_datetime, OptionalValue()),
            ]
        )
        payday = interest_utils_v400.get_selected_interest_payday(timeseries, effective_datetime)
        self.assertIsNone(payday)
        payday = interest_utils_v400.get_selected_interest_payday(timeseries)
        self.assertIsNone(payday)

    def test_interest_payday_selected_day_earlier_than_effective_day_february(self):
        selected_day = 30
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 1, 31, 1, 1, tzinfo=timezone)
        payday = interest_utils_v400.get_interest_payday(selected_day, effective_datetime)
        self.assertEqual("28", payday)

    def test_interest_payday_selected_day_later_than_effectve_day(self):
        selected_day = 30
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 1, 3, 1, 1, tzinfo=timezone)
        payday = interest_utils_v400.get_interest_payday(selected_day, effective_datetime)
        self.assertEqual("30", payday)

    def test_interest_payday_interest_paid_february(self):
        selected_day = 30
        timezone = ZoneInfo("UTC")
        effective_datetime = datetime(2022, 1, 1, 1, 1, tzinfo=timezone)
        payday = interest_utils_v400.get_interest_payday(selected_day, effective_datetime, True)
        self.assertEqual("28", payday)


class ContractAPIUtilsTestCase(TestCase):
    def test_can_use_utils(self):
        tz_aware_utc = datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(
            timezone_utils.validate_timezone_is_utc(tz_aware_utc, "", ""), tz_aware_utc
        )
