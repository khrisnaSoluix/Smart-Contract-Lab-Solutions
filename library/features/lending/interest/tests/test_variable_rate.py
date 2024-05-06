# standard
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, PropertyMock

# third party
from dateutil.relativedelta import relativedelta

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import UnionItemValue
from library.features.lending.interest.variable_rate import (
    calculate_daily_accrual_amount,
    should_trigger_reamortisation,
)

DEFAULT_DATE = datetime(2019, 1, 1, tzinfo=timezone.utc)
DEFAULT_VARIABLE_INTEREST_RATE = Decimal("0.129971")
DEFAULT_VARIABLE_RATE_ADJUSTMENT = Decimal("0.00")


class TestVariableRateCalculationBase(ContractFeatureTest):
    target_test_file = "library/features/lending/interest/variable_rate.py"

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        days_in_year=UnionItemValue("365"),
        loan_start_date=DEFAULT_DATE,
        variable_interest_rate=DEFAULT_VARIABLE_INTEREST_RATE,
        variable_rate_adjustment=DEFAULT_VARIABLE_RATE_ADJUSTMENT,
        **kwargs,
    ):
        client_transaction = client_transaction or {}
        balance_ts = balance_ts or []
        postings = postings or []
        flags = flags or []
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
            **kwargs,
        )

    def test_calculate_daily_accrual_amount(self):
        test_cases = [
            # 365
            {
                "description": "365 days, no adjustment. (2388.12 * (0.0125+0)/365 ~ 0.08178)",
                "days_in_year": UnionItemValue("365"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08178"),
            },
            {
                "description": "365 days, positive adjustment. "
                "(2388.12 * (0.0125+0.25)/365 ~ 1.71748)",
                "days_in_year": UnionItemValue("365"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.71748"),
            },
            {
                "description": "365 days, negative adjustment. "
                "(2388.12 * (0.0125-0.002)/365 ~ 0.06869)",
                "days_in_year": UnionItemValue("365"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06870"),
            },
            # 366
            {
                "description": "366 days, no adjustment. (2388.12 * (0.0125+0)/366 ~ 0.08156)",
                "days_in_year": UnionItemValue("366"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08156"),
            },
            {
                "description": "366 days, positive adjustment. "
                "(2388.12 * (0.0125+0.25)/366 ~ 1.71279)",
                "days_in_year": UnionItemValue("366"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.71279"),
            },
            {
                "description": "366 days, negative adjustment. "
                "(2388.12 * (0.0125-0.002)/366 ~ 0.06851)",
                "days_in_year": UnionItemValue("366"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06851"),
            },
            # 360
            {
                "description": "360 days, no adjustment. (2388.12 * (0.0125+0)/360 ~ 0.08292)",
                "days_in_year": UnionItemValue("360"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.00"),
                "expected_result": Decimal("0.08292"),
            },
            {
                "description": "360 days, positive adjustment. "
                "(2388.12 * (0.0125+0.25)/360 ~ 1.74133)",
                "days_in_year": UnionItemValue("360"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("0.25"),
                "expected_result": Decimal("1.74134"),
            },
            {
                "description": "366 days, negative adjustment. "
                "(2388.12 * (0.0125-0.002)/360 ~ 0.06965)",
                "days_in_year": UnionItemValue("360"),
                "variable_interest_rate": Decimal("0.0125"),
                "variable_rate_adjustment": Decimal("-0.002"),
                "expected_result": Decimal("0.06965"),
            },
            {
                "description": "365 days (2388.12 * -0.0126/365 ~ 0.08244)",
                "days_in_year": UnionItemValue("365"),
                "variable_interest_rate": Decimal("0.0126"),
                "variable_rate_adjustment": Decimal("0"),
                "expected_result": Decimal("0.08244"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock(
                days_in_year=test_case["days_in_year"],
                variable_interest_rate=test_case["variable_interest_rate"],
                variable_rate_adjustment=test_case["variable_rate_adjustment"],
            )
            result = calculate_daily_accrual_amount(mock_vault, Decimal("2388.12"), DEFAULT_DATE)
            self.assertEqual(result, test_case["expected_result"], msg=test_case["description"])

    def test_should_trigger_reamortisation(self):
        test_cases = [
            {
                "description": "event has not occurred yet",
                "last_application_execution_event": None,
                "variable_rate_adjustment": DEFAULT_VARIABLE_RATE_ADJUSTMENT,
                "variable_interest_rate": DEFAULT_VARIABLE_INTEREST_RATE,
                "expected_result": True,
            },
            {
                "description": "variable_rate_adjustment changed after last application",
                "last_application_execution_event": DEFAULT_DATE,
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": DEFAULT_VARIABLE_INTEREST_RATE,
                "expected_result": True,
            },
            {
                "description": "variable_interest_rate changed after last application",
                "last_application_execution_event": DEFAULT_DATE,
                "variable_rate_adjustment": DEFAULT_VARIABLE_RATE_ADJUSTMENT,
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": True,
            },
            {
                "description": "variable_interest_rate & variable_rate_adjustment changed "
                "after last application",
                "last_application_execution_event": DEFAULT_DATE,
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(days=10), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(days=12), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": True,
            },
            {
                "description": "event has occurred since last variable_rate_adjustment change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(days=10), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": DEFAULT_VARIABLE_INTEREST_RATE,
                "expected_result": False,
            },
            {
                "description": "event has occurred since last variable_interest_rate change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": DEFAULT_VARIABLE_RATE_ADJUSTMENT,
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(days=10), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": False,
            },
            {
                "description": "event has occurred since last variable_rate_adjustment "
                "& variable_interest_rate change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(days=10), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(days=12), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": False,
            },
            {
                "description": "event occured same day as variable_rate_adjustment change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": DEFAULT_VARIABLE_INTEREST_RATE,
                "expected_result": False,
            },
            {
                "description": "event occured same day as variable_interest_rate change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": DEFAULT_VARIABLE_RATE_ADJUSTMENT,
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": False,
            },
            {
                "description": "event occurred same day as last variable_rate_adjustment "
                "& variable_interest_rate change",
                "last_application_execution_event": DEFAULT_DATE + relativedelta(months=1),
                "variable_rate_adjustment": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_RATE_ADJUSTMENT)
                ],
                "variable_interest_rate": [
                    (DEFAULT_DATE + relativedelta(months=1), DEFAULT_VARIABLE_INTEREST_RATE)
                ],
                "expected_result": False,
            },
        ]
        for test_case in test_cases:
            mock_schedule_details = Mock()
            type(mock_schedule_details).last_execution_time = PropertyMock(
                return_value=test_case["last_application_execution_event"]
            )
            mock_vault = self.create_mock(
                variable_rate_adjustment=test_case["variable_rate_adjustment"],
                variable_interest_rate=test_case["variable_interest_rate"],
            )
            result = should_trigger_reamortisation(
                mock_vault,
                elapsed_term_in_months=None,
                due_amount_schedule_details=mock_schedule_details,
            )
            self.assertEqual(result, test_case["expected_result"], msg=test_case["description"])
