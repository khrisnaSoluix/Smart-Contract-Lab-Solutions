# standard libs
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.interest_accrual_supervisor as interest_accrual_supervisor
import library.features.v4.lending.lending_addresses as lending_addresses
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    Posting,
    ScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)

DEFAULT_DATE = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

PRINCIPAL_COORDINATE = BalanceCoordinate(
    lending_addresses.PRINCIPAL, DEFAULT_ASSET, sentinel.denomination, Phase.COMMITTED
)
NOT_PRINCIPAL_COORDINATE = BalanceCoordinate(
    "NOT_PRINCIPAL", DEFAULT_ASSET, sentinel.denomination, Phase.COMMITTED
)


class InterestAccrualTestCommon(SupervisorFeatureTest):
    maxDiff = None


@patch.object(interest_accrual_supervisor.utils, "get_parameter")
@patch.object(interest_accrual_supervisor.utils, "get_balance_default_dict_from_mapping")
@patch.object(interest_accrual_supervisor.interest_accrual_common, "daily_accrual")
class InterestAccrualTest(InterestAccrualTestCommon):
    def setUp(self):
        self.account_balances = BalanceDefaultDict(
            mapping={
                PRINCIPAL_COORDINATE: Balance(net=Decimal("10")),
                NOT_PRINCIPAL_COORDINATE: Balance(net=Decimal("100")),
            }
        )
        self.mock_vault = self.create_supervisee_mock(
            account_id=sentinel.account_id, requires_fetched_balances=sentinel.fetched_balances
        )
        self.mock_parameter_side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_receivable_account": sentinel.accrued_interest_receivable_account,
                "days_in_year": sentinel.days_in_year,
                "denomination": sentinel.denomination,
                "accrual_precision": sentinel.accrual_precision,
            }
        )

        self.mock_interest_rate_feature = MagicMock(
            get_annual_interest_rate=MagicMock(return_value=sentinel.yearly_interest_rate)
        )

    def test_daily_accrual_schedule_logic_over_1_month_before_due_amount_calc(
        self,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 3, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )

    def test_daily_accrual_schedule_logic_1_month_before_due_amount_calc(
        self,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )

    def test_daily_accrual_schedule_logic_exactly_1_month_before_due_amount_calc(
        self,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )

    def test_daily_accrual_schedule_logic_less_than_1_month_before_due_amount_calc(
        self,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 1, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )

    @patch.object(interest_accrual_supervisor.utils, "update_inflight_balances")
    def test_daily_accrual_schedule_logic_empty_inflight_postings(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 1, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
            inflight_postings=[],
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )
        mock_update_inflight_balances.assert_not_called()

    @patch.object(interest_accrual_supervisor.utils, "update_inflight_balances")
    def test_daily_accrual_schedule_logic_non_empty_inflight_postings(
        self,
        mock_update_inflight_balances: MagicMock,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_update_inflight_balances.return_value = BalanceDefaultDict(
            mapping={
                PRINCIPAL_COORDINATE: Balance(net=Decimal("15")),
                NOT_PRINCIPAL_COORDINATE: Balance(net=Decimal("100")),
            }
        )
        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        inflight_postings = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("3"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address="ANOTHER_ADDRESS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("3"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address="PRINCIPAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("2"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address="ANOTHER_ADDRESS_2",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("2"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address="PRINCIPAL",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
        ]

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 1, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
            inflight_postings=inflight_postings,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("15"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=interest_accrual_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.accrued_interest_receivable_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )

    def test_daily_accrual_schedule_logic_with_custom_accrual_address_and_internal_account(
        self,
        mock_daily_accrual: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_daily_accrual.return_value = sentinel.daily_accrual_ci
        mock_get_balance_default_dict_from_mapping.return_value = self.account_balances
        mock_get_parameter.side_effect = self.mock_parameter_side_effect

        hook_args = ScheduledEventHookArguments(
            effective_datetime=datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC")),
            event_type=sentinel.event_type,
        )

        daily_accrual_ci = interest_accrual_supervisor.daily_accrual_logic(
            vault=self.mock_vault,
            hook_arguments=hook_args,
            next_due_amount_calculation_datetime=datetime(
                2020, 2, 3, 3, 4, 5, tzinfo=ZoneInfo("UTC")
            ),
            interest_rate_feature=self.mock_interest_rate_feature,
            account_type=sentinel.account_type,
            customer_accrual_address=sentinel.custom_accrual_address,
            accrual_internal_account=sentinel.custom_internal_account,
        )

        self.assertEqual(daily_accrual_ci, sentinel.daily_accrual_ci)

        mock_daily_accrual.assert_called_once_with(
            effective_balance=Decimal("10"),
            effective_datetime=datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
            customer_address=sentinel.custom_accrual_address,
            customer_account=sentinel.account_id,
            denomination=sentinel.denomination,
            internal_account=sentinel.custom_internal_account,
            days_in_year=sentinel.days_in_year,
            yearly_rate=sentinel.yearly_interest_rate,
            account_type=sentinel.account_type,
            event_type=sentinel.event_type,
            payable=False,
            precision=sentinel.accrual_precision,
            rounding=ROUND_HALF_UP,
        )
