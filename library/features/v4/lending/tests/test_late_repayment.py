# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.late_repayment as late_repayment
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduledEventHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelScheduleExpression,
)

DEFAULT_DATE = datetime(2020, 1, 2, 3, tzinfo=ZoneInfo("UTC"))


class LateRepaymentTest(FeatureTest):
    maxDiff = None


sentinel_instruction_details = {"sentinel": "details"}  # TODO: sentinel-ize in the future


class ScheduleLogicTest(LateRepaymentTest):
    @patch.object(late_repayment.utils, "get_parameter")
    @patch.object(late_repayment, "get_total_overdue_amount")
    @patch.object(late_repayment.fees, "fee_custom_instruction")
    @patch.object(late_repayment.utils, "standard_instruction_details")
    def test_scheduled_logic_with_late_repayment_fee(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_total_overdue_amount: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        fee_ci = SentinelCustomInstruction("fee")
        mock_fee_custom_instruction.return_value = [fee_ci]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                late_repayment.PARAM_LATE_REPAYMENT_FEE: Decimal("10"),
                late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.income,
                late_repayment.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_total_overdue_amount.return_value = Decimal("0.01")
        result = late_repayment.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATE,
            ),
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )
        self.assertListEqual([fee_ci], result)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("10"),
            internal_account=sentinel.income,
            customer_account_address=late_repayment.lending_addresses.PENALTIES,
            instruction_details=sentinel_instruction_details,
        )

    @patch.object(late_repayment.utils, "get_parameter")
    @patch.object(late_repayment, "get_total_overdue_amount")
    @patch.object(late_repayment.fees, "fee_custom_instruction")
    @patch.object(late_repayment.utils, "standard_instruction_details")
    def test_scheduled_logic_check_total_overdue_amount_false(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_total_overdue_amount: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        fee_ci = SentinelCustomInstruction("fee")
        mock_fee_custom_instruction.return_value = [fee_ci]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                late_repayment.PARAM_LATE_REPAYMENT_FEE: Decimal("10"),
                late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.income,
                late_repayment.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_standard_instruction_details.return_value = sentinel_instruction_details
        mock_get_total_overdue_amount.return_value = Decimal("0")
        result = late_repayment.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATE,
            ),
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
            check_total_overdue_amount=False,
        )
        self.assertListEqual([fee_ci], result)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("10"),
            internal_account=sentinel.income,
            customer_account_address=late_repayment.lending_addresses.PENALTIES,
            instruction_details=sentinel_instruction_details,
        )

    @patch.object(late_repayment.utils, "get_parameter")
    @patch.object(late_repayment, "get_total_overdue_amount")
    @patch.object(late_repayment.fees, "fee_custom_instruction")
    @patch.object(late_repayment.utils, "standard_instruction_details")
    def test_scheduled_logic_without_late_repayment_fee(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_total_overdue_amount: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                late_repayment.PARAM_LATE_REPAYMENT_FEE: Decimal("0"),
                late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.income,
                late_repayment.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_get_total_overdue_amount.return_value = Decimal("0.01")
        result = late_repayment.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATE,
            ),
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )
        self.assertListEqual([], result)
        mock_get_total_overdue_amount.assert_called_once_with(mock_vault)
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    @patch.object(late_repayment.utils, "get_parameter")
    @patch.object(late_repayment, "get_total_overdue_amount")
    @patch.object(late_repayment.fees, "fee_custom_instruction")
    @patch.object(late_repayment.utils, "standard_instruction_details")
    def test_scheduled_logic_with_negative_overdue_amount(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_get_total_overdue_amount: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                late_repayment.PARAM_LATE_REPAYMENT_FEE: Decimal("10"),
                late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.income,
                late_repayment.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_get_total_overdue_amount.return_value = Decimal("-0.01")
        result = late_repayment.schedule_logic(
            vault=mock_vault,
            hook_arguments=ScheduledEventHookArguments(
                event_type=sentinel.event_type,
                effective_datetime=DEFAULT_DATE,
            ),
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )
        self.assertListEqual([], result)
        mock_get_total_overdue_amount.assert_called_once_with(mock_vault)
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    @patch.object(late_repayment.utils, "sum_balances")
    @patch.object(late_repayment.utils, "get_parameter")
    def test_get_total_overdue_amount(
        self,
        mock_get_parameter: MagicMock,
        mock_sum_balances: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                late_repayment.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("effective")
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={late_repayment.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_sum_balances.return_value = Decimal("100")

        # run function
        result = late_repayment.get_total_overdue_amount(mock_vault)
        self.assertEqual(result, Decimal("100"))
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances_effective,
            addresses=late_repayment.lending_addresses.OVERDUE_ADDRESSES,
            denomination=sentinel.denomination,
            decimal_places=2,
        )


class ScheduleEventsTest(LateRepaymentTest):
    def test_late_repayment_event_types(self):
        event_types = late_repayment.event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name="CHECK_LATE_REPAYMENT",
                    scheduler_tag_ids=["PRODUCT_A_CHECK_LATE_REPAYMENT_AST"],
                )
            ],
        )

    @patch.object(late_repayment.utils, "get_schedule_expression_from_parameters")
    def test_late_repayment_check_after_specified_days_after_due_calculation(
        self,
        mock_get_schedule_expression_from_parameters: MagicMock,
    ):
        late_repay_dt = datetime(2020, 1, 2, 3, 4, 5, tzinfo=ZoneInfo("UTC"))
        mock_vault = sentinel.vault
        sched_expr = SentinelScheduleExpression("late_repayment")
        mock_get_schedule_expression_from_parameters.return_value = sched_expr

        scheduled_events = late_repayment.scheduled_events(
            vault=mock_vault,
            start_datetime=late_repay_dt,
        )
        expected = {
            late_repayment.CHECK_LATE_REPAYMENT_EVENT: ScheduledEvent(
                start_datetime=late_repay_dt.replace(hour=0, minute=0, second=0),
                expression=sched_expr,
            )
        }
        self.assertDictEqual(scheduled_events, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=mock_vault,
            parameter_prefix="check_late_repayment",
            day=2,
        )


@patch.object(late_repayment.utils, "get_parameter")
class GetParametersTest(LateRepaymentTest):
    def test_get_late_repayment_fee_parameter(self, mock_get_parameter: MagicMock):
        late_repayment_fee_parameter = 100

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={late_repayment.PARAM_LATE_REPAYMENT_FEE: late_repayment_fee_parameter},
        )

        result = late_repayment.get_late_repayment_fee_parameter(vault=sentinel.vault)

        self.assertEqual(
            late_repayment_fee_parameter,
            result,
        )
