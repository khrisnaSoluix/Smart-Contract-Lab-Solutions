from datetime import datetime
from decimal import Decimal
import uuid
from ..types import (
    AddAccountNoteDirective,
    AmendScheduleDirective,
    Balance,
    BalancesFilter,
    BalancesIntervalFetcher,
    BalancesObservation,
    BalancesObservationFetcher,
    BalanceDefaultDict,
    ClientTransaction,
    DefinedDateTime,
    EndOfMonthSchedule,
    EventTypesGroup,
    EventTypeSchedule,
    HookDirectives,
    NoteType,
    ScheduleFailover,
    Next,
    Override,
    PostingsIntervalFetcher,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    PostingInstructionType,
    Previous,
    RelativeDateTime,
    RemoveSchedulesDirective,
    ScheduledJob,
    TransactionCode,
    Shift,
    UpdateAccountEventTypeDirective,
    WorkflowStartDirective,
    defaultAddress,
    defaultAsset,
    Phase,
)
from ....version_390.common.tests.test_types import PublicCommonV390TypesTestCase
from .....utils.exceptions import StrongTypingError, InvalidSmartContractError
from .....utils import symbols


class PublicCommonV3100TypesTestCase(PublicCommonV390TypesTestCase):
    TS_3100 = datetime(year=2021, month=1, day=1)
    request_id_3100 = str(uuid.uuid4())
    account_id_3100 = "test_account_id_3100"

    def test_shift_with_positive_values(self):
        shift = Shift(years=3, months=1, days=12, hours=4, minutes=5, seconds=6)
        self.assertEqual(3, shift.years)
        self.assertEqual(1, shift.months)
        self.assertEqual(12, shift.days)
        self.assertEqual(4, shift.hours)
        self.assertEqual(5, shift.minutes)
        self.assertEqual(6, shift.seconds)

    def test_shift_with_negative_values(self):
        shift = Shift(years=-4, months=-3, days=-2, hours=-10, minutes=-25, seconds=-45)
        self.assertEqual(-4, shift.years)
        self.assertEqual(-3, shift.months)
        self.assertEqual(-2, shift.days)
        self.assertEqual(-10, shift.hours)
        self.assertEqual(-25, shift.minutes)
        self.assertEqual(-45, shift.seconds)

    def test_shift_with_only_time_attribute_values(self):
        shift = Shift(hours=7, minutes=8, seconds=25)
        self.assertEqual(7, shift.hours)
        self.assertEqual(8, shift.minutes)
        self.assertEqual(25, shift.seconds)

    def test_shift_with_optional_values_not_provided(self):
        shift_missing_months = Shift(years=4, days=2, hours=-10, minutes=-25, seconds=-45)
        shift_missing_days = Shift(years=4, months=3, hours=-10, minutes=-25, seconds=-45)
        shift_missing_years = Shift(months=3, days=2, hours=-10, minutes=-25, seconds=-45)
        shift_missing_hours = Shift(years=4, months=3, days=2, minutes=25, seconds=45)
        shift_missing_minutes = Shift(years=2, days=2, months=3, hours=10, seconds=45)
        shift_missing_seconds = Shift(years=2, days=2, months=3, hours=10, minutes=25)

        # Confirm that values are populated with zero if left empty.
        self.assertEqual(None, shift_missing_years.years)
        self.assertEqual(None, shift_missing_months.months)
        self.assertEqual(None, shift_missing_days.days)
        self.assertEqual(None, shift_missing_hours.hours)
        self.assertEqual(None, shift_missing_minutes.minutes)
        self.assertEqual(None, shift_missing_seconds.seconds)

    def test_shift_raises_if_no_values_provided(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            Shift()

        self.assertEqual(
            str(e.exception), "Shift object needs to be populated with at least one attribute."
        )

    def test_shift_raises_if_invalid_argument_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(days="2")
        self.assertEqual(
            str(e.exception), "Shift.__init__ arg 'days' expected Optional[int] but got value '2'"
        )

    def test_defined_date_time_enum(self):
        self.assertEqual(DefinedDateTime.LIVE, -1)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, 1)
        self.assertEqual(DefinedDateTime.INTERVAL_START, 2)
        with self.assertRaises(AttributeError):
            DefinedDateTime.EFFECTIVE_DATETIME

    def test_failover_enum(self):
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE, 1)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_AFTER, 2)

    def test_override_with_valid_values(self):
        override = Override(year=2000, month=1, day=12, hour=4, minute=5, second=6)
        self.assertEqual(2000, override.year)
        self.assertEqual(1, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(4, override.hour)
        self.assertEqual(5, override.minute)
        self.assertEqual(6, override.second)

    def test_override_with_time_attributes_not_populated(self):
        override = Override(year=2000, month=1, day=12)
        self.assertEqual(2000, override.year)
        self.assertEqual(1, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(None, override.hour)
        self.assertEqual(None, override.minute)
        self.assertEqual(None, override.second)

    def test_override_with_optional_date_attribute_not_populated(self):
        override = Override(year=2000, day=12)
        self.assertEqual(2000, override.year)
        self.assertEqual(None, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(None, override.hour)
        self.assertEqual(None, override.minute)
        self.assertEqual(None, override.second)

    def test_override_raises_if_no_values_provided(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            Override()

        self.assertEqual(
            str(e.exception), "Override object needs to be populated with at least one attribute."
        )

    def test_override_raises_if_invalid_argument_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(year="1")
        self.assertEqual(
            str(e.exception),
            "Override.__init__ arg 'year' expected Optional[int] but got value '1'",
        )

    def test_override_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Override(month=13)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Override(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Override(hour=24)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Override(minute=60)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Override(second=60)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Override(year=-1)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Override(month=0)
        with self.assertRaises(InvalidSmartContractError) as ex8:
            Override(day=0)
        with self.assertRaises(InvalidSmartContractError) as ex9:
            Override(hour=-1)
        with self.assertRaises(InvalidSmartContractError) as ex10:
            Override(minute=-1)
        with self.assertRaises(InvalidSmartContractError) as ex11:
            Override(second=-1)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7, ex8, ex9, ex10, ex11]:
            self.assertEqual(str(ex.exception), "Values of Override object are out of range.")

    def test_next_with_all_values_not_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next()
        self.assertEqual(
            str(e.exception), "Next.__init__ arg 'day' expected int but got value None"
        )

    def test_previous_with_all_values_not_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous()
        self.assertEqual(
            str(e.exception), "Previous.__init__ arg 'day' expected int but got value None"
        )

    def test_next_with_all_values_populated(self):
        next_native_type = Next(month=1, day=12, hour=4, minute=5, second=6)
        self.assertEqual(1, next_native_type.month)
        self.assertEqual(12, next_native_type.day)
        self.assertEqual(4, next_native_type.hour)
        self.assertEqual(5, next_native_type.minute)
        self.assertEqual(6, next_native_type.second)

    def test_previous_with_all_values_populated(self):
        previous_native_type = Previous(month=5, day=17, hour=3, minute=45, second=12)
        self.assertEqual(5, previous_native_type.month)
        self.assertEqual(17, previous_native_type.day)
        self.assertEqual(3, previous_native_type.hour)
        self.assertEqual(45, previous_native_type.minute)
        self.assertEqual(12, previous_native_type.second)

    def test_next_raises_error_if_invalid_argument_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(day="2")
        self.assertEqual(str(e.exception), "Next.__init__ arg 'day' expected int but got value '2'")

    def test_previous_raises_error_if_invalid_argument_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(day="2")
        self.assertEqual(
            str(e.exception), "Previous.__init__ arg 'day' expected int but got value '2'"
        )

    def test_next_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Next(month=13, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Next(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Next(hour=24, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Next(minute=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Next(second=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Next(month=0, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Next(day=0)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7]:
            self.assertEqual(str(ex.exception), "Values of Next object are out of range.")

    def test_previous_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Previous(month=13, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Previous(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Previous(hour=24, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Previous(minute=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Previous(second=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Previous(month=0, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Previous(day=0)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7]:
            self.assertEqual(str(ex.exception), "Values of Previous object are out of range.")

    def test_relative_date_time_with_next(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_TIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Next(month=1, day=12, hour=4, minute=5, second=6),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(4, relative_date_time_native_object.find.hour)
        self.assertEqual(5, relative_date_time_native_object.find.minute)
        self.assertEqual(6, relative_date_time_native_object.find.second)

        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, relative_date_time_native_object.origin)

    def test_relative_date_time_with_previous(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_TIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Previous(month=1, day=12, hour=6, minute=7, second=25),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(6, relative_date_time_native_object.find.hour)
        self.assertEqual(7, relative_date_time_native_object.find.minute)
        self.assertEqual(25, relative_date_time_native_object.find.second)

        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, relative_date_time_native_object.origin)

    def test_relative_date_time_origin_not_populated(self):
        with self.assertRaises(StrongTypingError) as ex:
            RelativeDateTime()

        self.assertEqual(
            str(ex.exception),
            "RelativeDateTime.__init__ arg 'origin' expected DefinedDateTime but got value None",
        )

    def test_relative_date_time_with_shift_and_find_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            RelativeDateTime(origin=DefinedDateTime.EFFECTIVE_TIME)

        self.assertEqual(
            str(ex.exception),
            "RelativeDateTime Object requires either shift or find attributes to be populated",
        )

    def test_relative_date_time_with_override(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_TIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(2, relative_date_time_native_object.find.year)
        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(2, relative_date_time_native_object.find.hour)
        self.assertEqual(9, relative_date_time_native_object.find.minute)
        self.assertEqual(53, relative_date_time_native_object.find.second)

        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, relative_date_time_native_object.origin)

    def test_relative_date_time_with_origin_interval_start(self):
        relative_date_time_native_object = RelativeDateTime(
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
            origin=DefinedDateTime.INTERVAL_START,
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(2, relative_date_time_native_object.find.year)
        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(2, relative_date_time_native_object.find.hour)
        self.assertEqual(9, relative_date_time_native_object.find.minute)
        self.assertEqual(53, relative_date_time_native_object.find.second)

        self.assertEqual(DefinedDateTime.INTERVAL_START, relative_date_time_native_object.origin)

    def test_relative_date_time_with_origin_using_illegal_live_value(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            RelativeDateTime(
                shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
                find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
                origin=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(ex.exception),
            'RelativeDateTime origin attribute does not support "DefinedDateTime.LIVE"',
        )

    def test_postings_interval_fetcher_with_relative_datetime_start(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
            ),
            end=DefinedDateTime.EFFECTIVE_TIME,
        )

        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)

        self.assertEqual(-1, postings_interval_fetcher.start.shift.years)
        self.assertEqual(2, postings_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_without_start(self):
        with self.assertRaises(StrongTypingError) as e:
            PostingsIntervalFetcher(fetcher_id="fetcher_id", end=DefinedDateTime.EFFECTIVE_TIME)
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher.__init__ arg 'start' expected "
            "Union[RelativeDateTime, DefinedDateTime] but got value None",
        )

    def test_postings_interval_fetcher_errors_without_id(self):
        with self.assertRaises(StrongTypingError) as e:
            PostingsIntervalFetcher(
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_TIME,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher.__init__ arg 'fetcher_id' expected str but got value None",
        )

    def test_postings_interval_fetcher_errors_with_empty_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="",
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_TIME,
            )
        self.assertEqual(str(e.exception), "PostingsIntervalFetcher 'fetcher_id' cannot be empty")

    def test_postings_interval_fetcher_succeeds_without_end(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
            ),
        )
        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)

        self.assertEqual(-1, postings_interval_fetcher.start.shift.years)
        self.assertEqual(2, postings_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_with_defined_datetime_start(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_TIME
        )
        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, postings_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_with_live_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' cannot be set to 'DefinedDateTime.LIVE'",
        )

    def test_postings_interval_fetcher_between_effective_and_live(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_TIME, end=DefinedDateTime.LIVE
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, postings_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_with_invalid_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_postings_interval_fetcher_errors_with_invalid_end(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_TIME,
                end=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_postings_interval_fetcher_errors_with_invalid_start_origin(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=RelativeDateTime(
                    origin=DefinedDateTime.INTERVAL_START, shift=Shift(years=-1)
                ),
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' origin value must be set to "
            "'DefinedDateTime.EFFECTIVE_TIME'",
        )

    def test_balances_interval_fetcher_with_relative_datetime_start(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
            ),
            end=DefinedDateTime.EFFECTIVE_TIME,
        )

        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)

        self.assertEqual(-1, balances_interval_fetcher.start.shift.years)
        self.assertEqual(2, balances_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_without_start(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(fetcher_id="fetcher_id", end=DefinedDateTime.EFFECTIVE_TIME)
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher.__init__ arg 'start' expected "
            "Union[RelativeDateTime, DefinedDateTime] but got value None",
        )

    def test_balances_interval_fetcher_errors_without_id(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_TIME,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher.__init__ arg 'fetcher_id' expected str but got value None",
        )

    def test_balances_interval_fetcher_errors_with_empty_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="",
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_TIME,
            )
        self.assertEqual(str(e.exception), "BalancesIntervalFetcher 'fetcher_id' cannot be empty")

    def test_balances_interval_fetcher_succeeds_without_end(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_TIME, shift=Shift(years=-1, months=2)
            ),
        )
        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)

        self.assertEqual(-1, balances_interval_fetcher.start.shift.years)
        self.assertEqual(2, balances_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_with_defined_datetime_start(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_TIME
        )
        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_with_live_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' cannot be set to 'DefinedDateTime.LIVE'",
        )

    def test_balances_interval_fetcher_between_effective_and_live(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_TIME, end=DefinedDateTime.LIVE
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_with_invalid_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_balances_interval_fetcher_errors_with_invalid_end(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_TIME,
                end=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_balances_interval_fetcher_errors_with_invalid_start_origin(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=RelativeDateTime(
                    origin=DefinedDateTime.INTERVAL_START, shift=Shift(years=-1)
                ),
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' origin value must be set to "
            "'DefinedDateTime.EFFECTIVE_TIME'",
        )

    def test_balances_interval_fetcher_with_filter(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=DefinedDateTime.EFFECTIVE_TIME,
            end=DefinedDateTime.LIVE,
            filter=filter,
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)
        self.assertEqual(filter, balances_interval_fetcher.filter)

    def test_scheduled_job_with_valid_values(self):
        scheduled_job = ScheduledJob(pause_datetime=self.TS_3100)
        self.assertEqual(self.TS_3100, scheduled_job.pause_datetime)

    def test_scheduled_job_bypass_type_checking_on_init(self):
        scheduled_job = ScheduledJob(pause_datetime="2", _from_proto=True)
        self.assertEqual("2", scheduled_job.pause_datetime)

    def test_scheduled_job_no_values_set(self):
        scheduled_job = ScheduledJob()
        self.assertEqual(None, scheduled_job.pause_datetime)

    def test_scheduled_job_raises_error_if_invalid_argument_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledJob(pause_datetime="2")
        self.assertEqual(
            str(e.exception),
            (
                "ScheduledJob.__init__ arg 'pause_datetime' expected Optional[datetime] "
                "but got value '2'"
            ),
        )

    def test_balances_observation_fetcher_with_defined_datetime(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id", at=DefinedDateTime.EFFECTIVE_TIME, filter=filter
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_TIME, balances_observation_fetcher.at)
        self.assertEqual(filter, balances_observation_fetcher.filter)

    def test_balances_observation_fetcher_with_relative_datetime(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        relative_date_time = RelativeDateTime(
            shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_TIME
        )
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id", at=relative_date_time, filter=filter
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(relative_date_time, balances_observation_fetcher.at)
        self.assertEqual(filter, balances_observation_fetcher.filter)

    def test_balances_observation_fetcher_with_no_filter(self):
        relative_date_time = RelativeDateTime(
            shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_TIME
        )
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id",
            at=relative_date_time,
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(relative_date_time, balances_observation_fetcher.at)

    def test_balances_observation_fetcher_raises_with_empty_fetcher_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservationFetcher(
                fetcher_id="",
                at=RelativeDateTime(shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_TIME),
            )

        self.assertEqual(
            str(e.exception), "BalancesObservationFetcher 'fetcher_id' cannot be empty"
        )

    def test_balances_observation_fetcher_raises_with_fetcher_id_not_populated(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(
                at=RelativeDateTime(shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_TIME)
            )

        self.assertEqual(
            str(e.exception),
            (
                "BalancesObservationFetcher.__init__ arg 'fetcher_id' expected str but got value "
                "None"
            ),
        )

    def test_balances_observation_fetcher_raises_if_at_attribute_not_populated(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(
                fetcher_id="fetcher_id",
            )

        self.assertEqual(
            str(e.exception),
            (
                "BalancesObservationFetcher.__init__ arg 'at' expected Union[DefinedDateTime, "
                "RelativeDateTime] but got value None"
            ),
        )

    def test_balances_observation_fetcher_raises_if_at_populated_with_interval_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservationFetcher(
                fetcher_id="fetcher_id",
                at=DefinedDateTime.INTERVAL_START,
            )

        self.assertEqual(
            str(e.exception),
            "BalancesObservationFetcher 'at' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_end_of_month_schedule_type_default_values(self):
        end_of_month_schedule = EndOfMonthSchedule(day=1)
        self.assertEqual(0, end_of_month_schedule.hour)
        self.assertEqual(0, end_of_month_schedule.minute)
        self.assertEqual(0, end_of_month_schedule.second)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE, end_of_month_schedule.failover)

    def test_end_of_month_schedule_type_can_set_values(self):
        end_of_month_schedule = EndOfMonthSchedule(
            day=15, hour=10, minute=20, second=5, failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE
        )
        self.assertEqual(15, end_of_month_schedule.day)
        self.assertEqual(10, end_of_month_schedule.hour)
        self.assertEqual(20, end_of_month_schedule.minute)
        self.assertEqual(5, end_of_month_schedule.second)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE, end_of_month_schedule.failover)

    def test_end_of_month_schedule_raise_if_values_out_of_range(self):
        values = [
            {"day": 0},
            {"day": 32},
            {"day": 1, "hour": -1},
            {"day": 1, "hour": 25},
            {"day": 1, "minute": -1},
            {"day": 1, "minute": 61},
            {"day": 1, "second": -1},
            {"day": 1, "second": 61},
        ]

        error_parts = [
            ("day", 1, 31),
            ("day", 1, 31),
            ("hour", 0, 23),
            ("hour", 0, 23),
            ("minute", 0, 59),
            ("minute", 0, 59),
            ("second", 0, 59),
            ("second", 0, 59),
        ]

        for i, value in enumerate(values):
            time_component, low, high = error_parts[i]
            with self.assertRaises(InvalidSmartContractError) as e:
                EndOfMonthSchedule(**value)
            self.assertEqual(
                str(e.exception),
                f"Argument {time_component} of EndOfMonthSchedule"
                f" object is out of range({low}-{high}).",
            )

    def test_end_of_month_schedule_raises_strong_typing_error(self):
        with self.assertRaises(Exception) as e:
            EndOfMonthSchedule(hour=5, minute=6)
        self.assertEqual(
            str(e.exception),
            "EndOfMonthSchedule.__init__() missing 1 required keyword-only argument: 'day'",
        )

        with self.assertRaises(StrongTypingError) as e:
            EndOfMonthSchedule(day=1, failover=3)
        self.assertEqual(
            str(e.exception),
            "EndOfMonthSchedule.__init__ arg 'failover' expected "
            "Optional[ScheduleFailover] but got value 3",
        )

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_3100,
                    account_id=self.account_id_3100,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_3100,
                    is_visible_to_customer=True,
                )
            ],
            amend_schedule_directives=[
                AmendScheduleDirective(
                    event_type="event_type_1",
                    new_schedule={
                        "day": "1",
                        "hour": "23",
                        "year": "2020",
                    },
                    request_id=self.request_id_3100,
                    account_id=self.account_id_3100,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_3100,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_3100,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_3100,
                    idempotency_key=self.request_id_3100,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_3100,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_3100,
                        posting_instructions=[
                            PostingInstruction(
                                custom_instruction_grouping_key="some_key",
                                client_transaction_id="the-main-payment-id",
                                pics=["INTERNATIONAL_PAYMENT"],
                                instruction_details={"TYPE": "PURCHASE"},
                                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                                credit=True,
                                amount=Decimal(10),
                                denomination="GBP",
                                account_id=self.account_id_3100,
                                account_address=symbols.DEFAULT_ADDRESS,
                                asset=symbols.DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                    ),
                )
            ],
            update_account_event_type_directives=[
                UpdateAccountEventTypeDirective(
                    account_id=self.account_id_3100,
                    event_type="event_type_1",
                    end_datetime=self.TS_3100,
                    schedule_method=EndOfMonthSchedule(
                        day=5,
                    ),
                )
            ],
        )
        self.assertEqual(
            self.request_id_3100, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_3100, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3100, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3100, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_3100, hook_directives.workflow_start_directives[0].idempotency_key
        )
        self.assertEqual(
            self.account_id_3100, hook_directives.update_account_event_type_directives[0].account_id
        )

    def test_update_account_event_type_directive_can_be_created(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3100,
            event_type="event_type_1",
            end_datetime=self.TS_3100,
        )
        self.assertEqual(update_account_event_type_directive.account_id, self.account_id_3100)
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.end_datetime, self.TS_3100)

    def test_update_account_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=self.account_id_3100,
                event_type="event_type_1",
            )

        self.assertIn(
            "UpdateAccountEventTypeDirective object must have either an end_datetime, a schedule",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_3100,
            )

        self.assertIn("'account_id' expected str but got value 123", str(ex.exception))

    def test_update_account_event_type_directive_with_schedule_method(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            account_id=self.account_id_3100,
            event_type="event_type_1",
            schedule_method=schedule_method,
        )
        self.assertEqual(update_account_event_type_directive.account_id, self.account_id_3100)
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.schedule_method, schedule_method)

    def test_update_account_event_type_directive_validation(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                account_id=self.account_id_3100,
                event_type="event_type_1",
                schedule_method=EndOfMonthSchedule(day=1),
                schedule=EventTypeSchedule(day="1"),
            )
        self.assertEqual(
            "UpdateAccountEventTypeDirective cannot contain both"
            " schedule and schedule_method fields",
            str(ex.exception),
        )

    def test_balances_observation(self):
        value_datetime = datetime(year=2020, month=2, day=20)
        balance_key_1 = (
            defaultAddress.fixed_value,
            defaultAsset.fixed_value,
            "USD",
            Phase.COMMITTED,
        )
        balance_dict = BalanceDefaultDict()
        balance_dict[balance_key_1] = Balance(net=Decimal("20"), credit=Decimal("20"))
        balances_observation = BalancesObservation(
            value_datetime=value_datetime, balances=balance_dict
        )
        self.assertEqual(balance_dict, balances_observation.balances)
        self.assertEqual(value_datetime, balances_observation.value_datetime)

    def test_balances_observation_raises_with_none_balances(self):
        value_datetime = datetime(year=2020, month=2, day=20)
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservation(value_datetime=value_datetime, balances=None)
        self.assertEqual(
            str(e.exception),
            "BalancesObservation.__init__ arg 'balances' expected BalanceDefaultDict but got value"
            " None",
        )

    def test_balances_observation_empty_balances(self):
        value_datetime = datetime(year=2020, month=2, day=20)
        balance_dict = BalanceDefaultDict()
        balances_observation = BalancesObservation(
            value_datetime=value_datetime, balances=balance_dict
        )
        self.assertEqual(value_datetime, balances_observation.value_datetime)
        self.assertEqual(balance_dict, balances_observation.balances)

    def test_balances_observation_no_value_datetime_and_empty_balances(self):
        balance_dict = BalanceDefaultDict()
        balances_observation = BalancesObservation(value_datetime=None, balances=balance_dict)
        self.assertEqual(None, balances_observation.value_datetime)
        self.assertEqual(balance_dict, balances_observation.balances)

    def test_balances_observation_bypass_type_checking_on_init(self):
        balance_dict = "not a BalanceDefaultDict at all"
        balances_observation = BalancesObservation(balances=balance_dict, _from_proto=True)
        self.assertEqual(balances_observation.balances, "not a BalanceDefaultDict at all")
        self.assertEqual(balances_observation.value_datetime, None)

    def test_posting_instruction_types(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        post_two = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="in",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_hook_directives_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            HookDirectives(
                add_account_note_directives=[],
                amend_schedule_directives=[],
                remove_schedules_directives=[],
                workflow_start_directives=[],
                posting_instruction_batch_directives=[],
                update_account_event_type_directives="bad",
            )

        self.assertIn(
            (
                "'update_account_event_type_directives' expected "
                "List[UpdateAccountEventTypeDirective] but got value 'bad'"
            ),
            str(ex.exception),
        )

    def test_hook_directives_errors_with_previous_version_constructor_args(self):
        with self.assertRaises(TypeError) as ex:
            HookDirectives(
                add_account_note_directives=[
                    AddAccountNoteDirective(
                        idempotency_key=self.request_id_380,
                        account_id=self.account_id_380,
                        body="some_body",
                        note_type=NoteType.RAW_TEXT,
                        date=self.TS_380,
                        is_visible_to_customer=True,
                    )
                ],
                amend_schedule_directives=[
                    AmendScheduleDirective(
                        event_type="event_type_1",
                        new_schedule={
                            "day": "1",
                            "hour": "23",
                            "year": "2020",
                        },
                        request_id=self.request_id_380,
                        account_id=self.account_id_380,
                    )
                ],
                remove_schedules_directives=[
                    RemoveSchedulesDirective(
                        account_id=self.account_id_380,
                        event_types=["event_type_1", "event_type_2"],
                        request_id=self.request_id_380,
                    )
                ],
                workflow_start_directives=[
                    WorkflowStartDirective(
                        workflow="test_workflow",
                        context={"key": "value"},
                        account_id=self.account_id_380,
                        idempotency_key=self.request_id_380,
                    )
                ],
                posting_instruction_batch_directives=[
                    PostingInstructionBatchDirective(
                        request_id=self.request_id_380,
                        posting_instruction_batch=PostingInstructionBatch(
                            batch_id="test",
                            batch_details={},
                            client_id="Visa",
                            client_batch_id="international-payment",
                            value_timestamp=self.TS_380,
                            posting_instructions=[
                                PostingInstruction(
                                    custom_instruction_grouping_key="some_key",
                                    client_transaction_id="the-main-payment-id",
                                    pics=["INTERNATIONAL_PAYMENT"],
                                    instruction_details={"TYPE": "PURCHASE"},
                                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                                    credit=True,
                                    amount=Decimal(10),
                                    denomination="GBP",
                                    account_id=self.account_id_380,
                                    account_address=symbols.DEFAULT_ADDRESS,
                                    asset=symbols.DEFAULT_ASSET,
                                    phase=Phase.COMMITTED,
                                ),
                            ],
                        ),
                    )
                ],
            )

        self.assertIn(
            (
                "__init__() missing 1 required keyword-only argument: "
                "'update_account_event_type_directives'"
            ),
            str(ex.exception),
        )

    def test_posting_instruction_advice_field(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_370,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                advice="test",
            )

    def test_posting_instruction_advice_not_set(self):
        common_kwargs = {
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.CUSTOM_INSTRUCTION, phase=Phase.COMMITTED, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(
            type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

    def test_posting_instruction_advice_set(self):
        common_kwargs = {
            "advice": True,
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                phase=Phase.COMMITTED,
                **common_kwargs,
            )

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_370,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
            override_all_restrictions=False,
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_370,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    pics=["INTERNATIONAL_PAYMENT"],
                    instruction_details={"TYPE": "PURCHASE"},
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    credit=True,
                    amount=Decimal(10),
                    denomination="GBP",
                    account_id=self.account_id_370,
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()

    def test_posting_instruction_batch_directive(self):
        posting_instr_batch = PostingInstructionBatch(
            batch_id="test",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_380,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    denomination="GBP",
                    account_id=self.account_id_380,
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    pics=["INTERNATIONAL_PAYMENT"],
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                ),
            ],
        )
        posting_instruction_batch_directive = PostingInstructionBatchDirective(
            request_id=self.request_id_380,
            posting_instruction_batch=posting_instr_batch,
        )
        self.assertEqual(self.request_id_380, posting_instruction_batch_directive.request_id)

    def test_posting_instruction_batch_rejects_invalid_insertion_timestamp(self):
        with self.assertRaises(StrongTypingError):
            PostingInstructionBatch(
                batch_details={},
                client_batch_id="international-payment",
                insertion_timestamp="bananas",
                value_timestamp=self.TS_380,
                posting_instructions=[],
            )

    def test_posting_instruction_missing_kwargs(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(id="101", account_id="1234512", amount=Decimal(10))

    def test_posting_instruction_override_all_restrictions(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_370,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                override_all_restrictions="test",
            )

    def test_posting_instruction_with_transaction_code(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
            override_all_restrictions=False,
            transaction_code=TransactionCode(
                domain="Blossom",
                family="Buttercup",
                subfamily="Bubbles",
            ),
        )
        self.assertTrue(hasattr(pi, "transaction_code"))
        self.assertEqual("Blossom", pi.transaction_code.domain)

    def test_event_types_group_can_be_created(self):
        event_types_group = EventTypesGroup(
            name="TestEvenTypesGroup", event_types_order=["EVENT_TYPE1", "EVENT_TYPE2"]
        )
        self.assertEqual(event_types_group.name, "TestEvenTypesGroup")
        self.assertEqual(event_types_group.event_types_order, ["EVENT_TYPE1", "EVENT_TYPE2"])

    def test_event_types_group_not_enough_event_types(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypesGroup(name="TestEvenTypesGroup", event_types_order=["EVENT_TYPE"])
        self.assertIn("An EventTypesGroup must have at least two event types", str(ex.exception))

    def test_event_types_group_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            EventTypesGroup(name="TestEvenTypesGroup", event_types_order=None)
        self.assertIn(
            "'event_types_order' expected List[str] but got value None", str(ex.exception)
        )

    def test_posting_instruction_batch_validation_is_skipped_if_from_proto(self):
        # This instantiation should not raise an error even though the arguments are
        # invalid, as _from_proto is set to True
        try:
            PostingInstructionBatch(
                batch_id=123,  # Invalid type, str expected
                batch_details={},
                client_id="client_id",
                client_batch_id="client_batch_id",
                value_timestamp=self.TS_300,
                posting_instructions=[
                    PostingInstruction(
                        id="123",
                        type=PostingInstructionType.AUTHORISATION,
                        client_transaction_id="123",
                        instruction_details={"test": "testy"},
                        pics=["test"],
                        custom_instruction_grouping_key="123",
                        account_id="123",
                        account_address=symbols.DEFAULT_ADDRESS,
                        asset=symbols.DEFAULT_ASSET,
                        credit=True,
                        denomination="GBP",
                    )
                ],
                _from_proto=True,  # Bypass validation
            )
        except Exception:
            self.fail("Creating PIB with _from_proto=True should not trigger type checks")
