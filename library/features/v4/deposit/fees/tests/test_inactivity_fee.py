# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.deposit.fees.inactivity_fee as inactivity_fee
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
    OptionalValue,
    ParameterTimeseries,
    UnionItemValue,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelScheduledEvent,
)

INACTIVITY_FEE_INCOME = "INACTIVITY_FEE_INCOME"


@patch.object(inactivity_fee.fees, "fee_custom_instruction")
@patch.object(inactivity_fee.utils, "get_parameter")
class TestApplication(FeatureTest):
    def test_monthly_inactivity_fee_applied(
        self, mock_get_parameter: MagicMock, mock_fee_custom_instruction: MagicMock
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "inactivity_fee": Decimal("5"),
                "inactivity_fee_income_account": INACTIVITY_FEE_INCOME,
                "denomination": DEFAULT_DENOMINATION,
                "partial_inactivity_fee_enabled": False,
            }
        )
        mock_vault = self.create_mock()
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee_postings")]

        # run function
        result = inactivity_fee.apply(vault=mock_vault, effective_datetime=DEFAULT_DATETIME)

        # call assertions
        self.assertEqual(result, [SentinelCustomInstruction("fee_postings")])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination="GBP",
            amount=Decimal("5"),
            internal_account=INACTIVITY_FEE_INCOME,
            instruction_details={
                "description": "Monthly Inactivity Fee Application",
                "event": "APPLY_INACTIVITY_FEE",
            },
        )

    def test_monthly_inactivity_fee_not_applied(
        self, mock_get_parameter: MagicMock, mock_fee_custom_instruction: MagicMock
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "inactivity_fee": Decimal("0"),
                "inactivity_fee_income_account": INACTIVITY_FEE_INCOME,
                "denomination": DEFAULT_DENOMINATION,
                "partial_inactivity_fee_enabled": False,
            }
        )

        # run function
        fee_postings_result = inactivity_fee.apply(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )

        # call assertions
        self.assertEqual(len(fee_postings_result), 0)
        mock_get_parameter.assert_called_with(
            vault=sentinel.vault, name="inactivity_fee", at_datetime=DEFAULT_DATETIME
        )
        mock_fee_custom_instruction.assert_not_called()

    @patch.object(inactivity_fee.partial_fee, "charge_partial_fee")
    def test_monthly_inactivity_fee_applied_partially_optional_args_provided(
        self,
        mock_charge_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "inactivity_fee": Decimal("5"),
                "inactivity_fee_income_account": INACTIVITY_FEE_INCOME,
                "partial_inactivity_fee_enabled": True,
            }
        )
        mock_vault = self.create_mock()
        mock_charge_partial_fee.return_value = [SentinelCustomInstruction("partial_fee_postings")]
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee_postings")]

        # run function
        result = inactivity_fee.apply(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            available_balance_feature=sentinel.available_balance,
        )

        # call assertions
        self.assertEqual(result, [SentinelCustomInstruction("partial_fee_postings")])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            amount=Decimal("5"),
            internal_account=INACTIVITY_FEE_INCOME,
            instruction_details={
                "description": "Monthly Inactivity Fee Application",
                "event": "APPLY_INACTIVITY_FEE",
            },
        )

        mock_charge_partial_fee.assert_called_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=SentinelCustomInstruction("fee_postings"),
            fee_details=inactivity_fee.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            available_balance_feature=sentinel.available_balance,
        )

    @patch.object(inactivity_fee.partial_fee, "charge_partial_fee")
    def test_monthly_inactivity_fee_applied_partially_optional_args_not_provided(
        self,
        mock_charge_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "inactivity_fee": Decimal("5"),
                "inactivity_fee_income_account": INACTIVITY_FEE_INCOME,
                "partial_inactivity_fee_enabled": True,
                "denomination": "GBP",
            }
        )
        balance_map = {
            inactivity_fee.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                "effective"
            )
        }
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=balance_map)
        mock_charge_partial_fee.return_value = [SentinelCustomInstruction("partial_fee_postings")]
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee_postings")]

        # run function
        result = inactivity_fee.apply(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            available_balance_feature=sentinel.available_balance,
        )

        # call assertions
        self.assertEqual(result, [SentinelCustomInstruction("partial_fee_postings")])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination="GBP",
            amount=Decimal("5"),
            internal_account=INACTIVITY_FEE_INCOME,
            instruction_details={
                "description": "Monthly Inactivity Fee Application",
                "event": "APPLY_INACTIVITY_FEE",
            },
        )

        mock_charge_partial_fee.assert_called_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=SentinelCustomInstruction("fee_postings"),
            fee_details=inactivity_fee.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances_effective,
            denomination="GBP",
            available_balance_feature=sentinel.available_balance,
        )


class TestEventDefinition(FeatureTest):
    def test_event_types(self):
        expected = SmartContractEventType(
            name=inactivity_fee.APPLICATION_EVENT,
            scheduler_tag_ids=[f"PRODUCT_{inactivity_fee.APPLICATION_EVENT}_AST"],
        )
        # function call
        result = inactivity_fee.event_types("PRODUCT")
        # assertion
        self.assertListEqual(result, [expected])

    @patch.object(inactivity_fee.utils, "monthly_scheduled_event")
    def test_scheduled_event(self, mock_monthly_scheduled_event: MagicMock):
        expected = {
            inactivity_fee.APPLICATION_EVENT: SentinelScheduledEvent("inactivity_fee_event")
        }
        # function call
        mock_monthly_scheduled_event.return_value = SentinelScheduledEvent("inactivity_fee_event")
        result = inactivity_fee.scheduled_events(
            vault=sentinel.vault, start_datetime=sentinel.datetime
        )
        # assertion
        self.assertDictEqual(result, expected)
        mock_monthly_scheduled_event.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=sentinel.datetime,
            parameter_prefix=inactivity_fee.INACTIVITY_FEE_APPLICATION_PREFIX,
        )


class TestGetterFunctions(FeatureTest):
    def test_are_inactivity_partial_payments_enabled(self):
        # construct mocks
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                {"partial_inactivity_fee_enabled": OptionalValue(UnionItemValue("True"))},
                DEFAULT_DATETIME,
            ),
        )
        # call assertions
        res = inactivity_fee._are_inactivity_partial_payments_enabled(mock_vault, DEFAULT_DATETIME)
        self.assertTrue(res)

    def test_get_inactivity_internal_income_account(self):
        # construct mocks
        mock_vault = self.create_mock(
            parameter_ts={
                "inactivity_fee_income_account": ParameterTimeseries(
                    [
                        (DEFAULT_DATETIME, sentinel.income_account),
                    ]
                ),
            }
        )
        # call assertions
        res = inactivity_fee._get_inactivity_internal_income_account(mock_vault, DEFAULT_DATETIME)

        self.assertEqual(res, sentinel.income_account)

    @patch.object(inactivity_fee.utils, "is_flag_in_list_applied")
    def test_is_account_inactive(self, mock_is_flag_in_list_applied: MagicMock):
        mock_is_flag_in_list_applied.return_value = sentinel.boolean

        result = inactivity_fee.is_account_inactive(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        self.assertEqual(result, sentinel.boolean)

        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="inactivity_flags",
            effective_datetime=sentinel.datetime,
        )
