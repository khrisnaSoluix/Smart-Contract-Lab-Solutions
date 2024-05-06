# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.deposit.fees.unarranged_overdraft_fee as unarranged_overdraft_fee
import library.features.v4.deposit.transaction_limits.overdraft.overdraft_limit as overdraft_limit
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)

DENOMINATION = "GBP"

default_parameters = {
    "denomination": DENOMINATION,
    unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE: Decimal("5"),
    unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: Decimal("30"),
    unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: (
        "OVERDRAFT_FEE_INCOME_ACCOUNT"
    ),
    unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: (
        "OVERDRAFT_FEE_RECEIVABLE_ACCOUNT"
    ),
    overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: Decimal("100"),
    overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: Decimal("300"),
}


class EventTest(FeatureTest):
    def test_accrual_event_types(self):
        event_types = unarranged_overdraft_fee.accrual_event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=unarranged_overdraft_fee.ACCRUAL_EVENT,
                    scheduler_tag_ids=[f"PRODUCT_A_{unarranged_overdraft_fee.ACCRUAL_EVENT}_AST"],
                ),
            ],
        )

    def test_application_event_types(self):
        event_types = unarranged_overdraft_fee.application_event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=unarranged_overdraft_fee.APPLICATION_EVENT,
                    scheduler_tag_ids=[
                        f"PRODUCT_A_{unarranged_overdraft_fee.APPLICATION_EVENT}_AST"
                    ],
                ),
            ],
        )

    @patch.object(unarranged_overdraft_fee.utils, "daily_scheduled_event")
    def test_accrual_scheduled_events(
        self,
        mock_daily_scheduled_event: MagicMock,
    ):
        mock_vault = sentinel.vault
        mock_daily_scheduled_event.return_value = sentinel.daily_scheduled_event
        start_datetime = datetime(
            year=2023, month=1, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        scheduled_events = unarranged_overdraft_fee.accrual_scheduled_events(
            vault=mock_vault, start_datetime=start_datetime
        )

        self.assertDictEqual(
            scheduled_events,
            {
                unarranged_overdraft_fee.ACCRUAL_EVENT: sentinel.daily_scheduled_event,
            },
        )
        mock_daily_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=start_datetime + relativedelta(days=1),
            parameter_prefix=unarranged_overdraft_fee.FEE_ACCRUAL_PREFIX,
        )

    @patch.object(unarranged_overdraft_fee.utils, "monthly_scheduled_event")
    def test_application_scheduled_events(
        self,
        mock_monthly_scheduled_event: MagicMock,
    ):
        mock_vault = sentinel.vault
        mock_monthly_scheduled_event.return_value = sentinel.monthly_scheduled_event
        start_datetime = datetime(
            year=2023, month=1, day=1, hour=0, minute=0, second=0, tzinfo=ZoneInfo("UTC")
        )
        scheduled_events = unarranged_overdraft_fee.application_scheduled_events(
            vault=mock_vault, start_datetime=start_datetime
        )

        self.assertDictEqual(
            scheduled_events,
            {
                unarranged_overdraft_fee.APPLICATION_EVENT: sentinel.monthly_scheduled_event,
            },
        )
        mock_monthly_scheduled_event.assert_called_once_with(
            vault=mock_vault,
            start_datetime=start_datetime + relativedelta(months=1),
            parameter_prefix=unarranged_overdraft_fee.FEE_APPLICATION_PREFIX,
        )


@patch.object(unarranged_overdraft_fee.utils, "are_optional_parameters_set")
@patch.object(unarranged_overdraft_fee.utils, "balance_at_coordinates")
@patch.object(unarranged_overdraft_fee.utils, "get_parameter")
class AccrueFeeTest(FeatureTest):
    def test_overdraft_fee_not_accrued_param_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = False
        self.assertEquals(unarranged_overdraft_fee.accrue_fee(vault=sentinel.vault), [])

    def test_overdraft_fee_not_accrued_positive_balance(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        mock_balance_at_coordinates.side_effect = [Decimal("100")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )

        self.assertEquals(unarranged_overdraft_fee.accrue_fee(vault=mock_vault), [])
        mock_are_optional_parameters_set.assert_called_once()
        mock_get_parameter.assert_called_with(vault=mock_vault, name="denomination")
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_eod_balance_observation, denomination=DENOMINATION
        )

    @patch.object(unarranged_overdraft_fee.accruals, "accrual_custom_instruction")
    def test_overdraft_fee_accrued(
        self,
        mock_accrual_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        # Mock returns the Default address EOD balance and OVERDRAFT_FEE address balance
        mock_balance_at_coordinates.side_effect = [Decimal("-150"), Decimal("10")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )
        mock_accrual_custom_instruction_response = [sentinel.custom_instruction]
        mock_accrual_custom_instruction.side_effect = [mock_accrual_custom_instruction_response]
        postings = unarranged_overdraft_fee.accrue_fee(vault=mock_vault)
        self.assertEquals(postings, mock_accrual_custom_instruction_response)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            customer_address=unarranged_overdraft_fee.OVERDRAFT_FEE,
            amount=Decimal("5"),
            internal_account="OVERDRAFT_FEE_RECEIVABLE_ACCOUNT",
            payable=False,
            denomination=DENOMINATION,
            instruction_details={
                "description": "Daily unarranged overdraft fee of 5 GBP",
                "event": unarranged_overdraft_fee.ACCRUAL_EVENT,
            },
        )

    @patch.object(unarranged_overdraft_fee.accruals, "accrual_custom_instruction")
    def test_overdraft_fee_accrued_no_cap(
        self,
        mock_accrual_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        parameters = default_parameters.copy()
        parameters[unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP] = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=parameters)
        # Mock returns the Default address EOD balance and OVERDRAFT_FEE address balance
        mock_balance_at_coordinates.side_effect = [Decimal("-150"), Decimal("50")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )
        mock_accrual_custom_instruction_response = [sentinel.custom_instruction]
        mock_accrual_custom_instruction.side_effect = [mock_accrual_custom_instruction_response]
        postings = unarranged_overdraft_fee.accrue_fee(vault=mock_vault)
        self.assertEquals(postings, mock_accrual_custom_instruction_response)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            customer_address=unarranged_overdraft_fee.OVERDRAFT_FEE,
            amount=Decimal("5"),
            internal_account="OVERDRAFT_FEE_RECEIVABLE_ACCOUNT",
            payable=False,
            denomination=DENOMINATION,
            instruction_details={
                "description": "Daily unarranged overdraft fee of 5 GBP",
                "event": unarranged_overdraft_fee.ACCRUAL_EVENT,
            },
        )

    def test_overdraft_fee_not_accrued_balance_above_overdraft_limit(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        mock_balance_at_coordinates.side_effect = [Decimal("-100")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )

        self.assertEquals(unarranged_overdraft_fee.accrue_fee(vault=mock_vault), [])

    def test_overdraft_fee_not_accrued_cap_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        # Mock returns the Default address EOD balance and OVERDRAFT_FEE address balance
        mock_balance_at_coordinates.side_effect = [Decimal("-150"), Decimal("30")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )

        self.assertEquals(unarranged_overdraft_fee.accrue_fee(vault=mock_vault), [])

    @patch.object(unarranged_overdraft_fee.accruals, "accrual_custom_instruction")
    def test_overdraft_fee_partially_accrued_cap_exceeded(
        self,
        mock_accrual_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        # Mock returns the Default address EOD balance and OVERDRAFT_FEE address balance
        mock_balance_at_coordinates.side_effect = [Decimal("-150"), Decimal("26")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EOD_FETCHER_ID: SentinelBalancesObservation("eod_balance_observation")
            }
        )
        mock_accrual_custom_instruction_response = [sentinel.custom_instruction]
        mock_accrual_custom_instruction.side_effect = [mock_accrual_custom_instruction_response]
        postings = unarranged_overdraft_fee.accrue_fee(vault=mock_vault)
        self.assertEquals(postings, mock_accrual_custom_instruction_response)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            customer_address=unarranged_overdraft_fee.OVERDRAFT_FEE,
            amount=Decimal("4"),
            internal_account="OVERDRAFT_FEE_RECEIVABLE_ACCOUNT",
            payable=False,
            denomination=DENOMINATION,
            instruction_details={
                "description": "Daily unarranged overdraft fee of 4 GBP",
                "event": unarranged_overdraft_fee.ACCRUAL_EVENT,
            },
        )


@patch.object(unarranged_overdraft_fee.utils, "are_optional_parameters_set")
@patch.object(unarranged_overdraft_fee.utils, "balance_at_coordinates")
@patch.object(unarranged_overdraft_fee.utils, "get_parameter")
class ApplyFeeTest(FeatureTest):
    def test_overdraft_fee_not_applied_param_not_set(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = False

        self.assertEquals(unarranged_overdraft_fee.apply_fee(vault=sentinel.vault), [])

    @patch.object(unarranged_overdraft_fee.accruals, "accrual_application_custom_instruction")
    def test_overdraft_fee_applied_optional_args_provided(
        self,
        mock_accrual_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        mock_balance_at_coordinates.side_effect = [Decimal("-25.232")]

        mock_vault = self.create_mock()

        mock_accrual_custom_instruction_response = [sentinel.custom_instruction]
        mock_accrual_custom_instruction.side_effect = [mock_accrual_custom_instruction_response]
        postings = unarranged_overdraft_fee.apply_fee(
            vault=mock_vault, balances=sentinel.balances, denomination=sentinel.denomination
        )
        mock_are_optional_parameters_set.assert_called_once()
        self.assertEquals(postings, mock_accrual_custom_instruction_response)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            denomination=sentinel.denomination,
            application_amount=Decimal("25.232"),
            accrual_amount=Decimal("25.232"),
            accrual_customer_address="UNARRANGED_OVERDRAFT_FEE",
            accrual_internal_account="OVERDRAFT_FEE_RECEIVABLE_ACCOUNT",
            application_internal_account="OVERDRAFT_FEE_INCOME_ACCOUNT",
            application_customer_address="DEFAULT",
            payable=False,
            instruction_details={
                "description": "Unarranged overdraft fee of 25.232 sentinel.denomination applied.",
                "event": "APPLY_UNARRANGED_OVERDRAFT_FEE",
            },
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="UNARRANGED_OVERDRAFT_FEE",
            denomination=sentinel.denomination,
        )

    @patch.object(unarranged_overdraft_fee.accruals, "accrual_application_custom_instruction")
    def test_overdraft_fee_applied_optional_args_not_provided(
        self,
        mock_accrual_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        mock_balance_at_coordinates.side_effect = [Decimal("-25.232")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("effective_balance_observation")
                )
            }
        )
        mock_accrual_custom_instruction_response = [sentinel.custom_instruction]
        mock_accrual_custom_instruction.side_effect = [mock_accrual_custom_instruction_response]
        postings = unarranged_overdraft_fee.apply_fee(vault=mock_vault)
        mock_are_optional_parameters_set.assert_called_once()
        self.assertEquals(postings, mock_accrual_custom_instruction_response)
        mock_accrual_custom_instruction.assert_called_once_with(
            customer_account="default_account",
            denomination=DENOMINATION,
            accrual_amount=Decimal("25.232"),
            accrual_customer_address="UNARRANGED_OVERDRAFT_FEE",
            application_amount=Decimal("25.232"),
            accrual_internal_account="OVERDRAFT_FEE_RECEIVABLE_ACCOUNT",
            application_internal_account="OVERDRAFT_FEE_INCOME_ACCOUNT",
            application_customer_address="DEFAULT",
            payable=False,
            instruction_details={
                "description": "Unarranged overdraft fee of 25.232 GBP applied.",
                "event": "APPLY_UNARRANGED_OVERDRAFT_FEE",
            },
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_effective_balance_observation,
            address="UNARRANGED_OVERDRAFT_FEE",
            denomination=DENOMINATION,
        )

    def test_overdraft_fee_not_applied_when_no_accrual(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_are_optional_parameters_set: MagicMock,
    ):
        mock_are_optional_parameters_set.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=default_parameters.copy()
        )
        mock_balance_at_coordinates.side_effect = [Decimal("0")]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: (
                    SentinelBalancesObservation("effective_balance_observation")
                )
            }
        )

        self.assertEquals(unarranged_overdraft_fee.apply_fee(vault=mock_vault), [])
