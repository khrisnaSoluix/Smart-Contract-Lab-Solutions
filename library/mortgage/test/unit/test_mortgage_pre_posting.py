# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelRejection,
)


@patch.object(mortgage.utils, "get_parameter")
@patch.object(mortgage.utils, "is_force_override")
class PrePostingHookTest(MortgageTestBase):
    default_hook_args = PrePostingHookArguments(
        effective_datetime=DEFAULT_DATETIME,
        posting_instructions=[sentinel.posting],
        client_transactions=sentinel.client_transactions,
    )

    def test_force_override_returns_none(
        self, mock_is_force_override: MagicMock, mock_get_parameter: MagicMock
    ):
        # construct mocks
        mock_is_force_override.return_value = True

        # run function
        hook_args = self.default_hook_args
        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_get_parameter.assert_not_called()

    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_rejects_multiple_postings(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # expected values
        posting_rejection = SentinelRejection("posting")

        # construct mocks
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = posting_rejection

        # construct expected result
        expected_result = PrePostingHookResult(rejection=posting_rejection)

        # run function
        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[sentinel.posting_1, sentinel.posting_2],
            client_transactions=sentinel.client_transactions,
        )
        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_not_called()

    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_rejects_invalid_denominations(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # expected values
        denomination_rejection = SentinelRejection("denomination")

        # construct mocks
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
            }
        )
        mock_validate_denomination.return_value = denomination_rejection

        # construct expected result
        expected_result = PrePostingHookResult(rejection=denomination_rejection)

        # run function
        hook_args = self.default_hook_args
        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected_result)

    @patch.object(
        mortgage.overpayment_allowance, "get_overpayment_allowance_fee_for_early_repayment"
    )
    @patch.object(mortgage, "_get_early_repayment_fee")
    @patch.object(mortgage.derived_params, "get_total_outstanding_debt")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_credits_greater_than_total_debt_return_rejection(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "application_precision": 2}
        )
        mock_validate_denomination.return_value = None
        mock_is_flag_in_list_applied.return_value = False

        mock_get_total_outstanding_debt.return_value = Decimal("1")
        mock_get_overpayment_allowance_fee_for_early_repayment.return_value = Decimal("0")
        mock_get_early_repayment_fee.return_value = Decimal("0")
        mock_balance_at_coordinates.return_value = Decimal("1")  # principal balance

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Cannot pay more than is owed. To repay the full "
                "amount of the mortgage - including fees - a posting for "
                "1 GBP must be made.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(
        mortgage.overpayment_allowance, "get_overpayment_allowance_fee_for_early_repayment"
    )
    @patch.object(mortgage, "_get_early_repayment_fee")
    @patch.object(mortgage.derived_params, "get_total_outstanding_debt")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_early_full_repayment_with_fees_returns_none(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "application_precision": 2}
        )
        mock_validate_denomination.return_value = None
        mock_is_flag_in_list_applied.return_value = False

        mock_get_total_outstanding_debt.return_value = Decimal("1")
        mock_get_overpayment_allowance_fee_for_early_repayment.return_value = Decimal("2")
        mock_get_early_repayment_fee.return_value = Decimal("10")
        mock_balance_at_coordinates.return_value = Decimal("1")  # principal balance

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("13"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)
        mock_get_early_repayment_fee.assert_called_once_with(
            vault=mock_vault, balances=sentinel.balances_live_balances, denomination="GBP"
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_live_balances,
            address=mortgage.lending_addresses.PRINCIPAL,
            denomination="GBP",
        )

    @patch.object(
        mortgage.overpayment_allowance, "get_overpayment_allowance_fee_for_early_repayment"
    )
    @patch.object(mortgage, "_get_early_repayment_fee")
    @patch.object(mortgage.derived_params, "get_total_outstanding_debt")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_credits_equal_to_total_debt_no_principal_return_none(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "application_precision": 2}
        )
        mock_validate_denomination.return_value = None
        mock_is_flag_in_list_applied.return_value = False

        mock_get_total_outstanding_debt.return_value = Decimal("1")
        mock_get_early_repayment_fee.return_value = Decimal("0")
        mock_balance_at_coordinates.return_value = Decimal("0")  # principal balance

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("1"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(
        mortgage.overpayment_allowance, "get_overpayment_allowance_fee_for_early_repayment"
    )
    @patch.object(mortgage, "_get_early_repayment_fee")
    @patch.object(mortgage.derived_params, "get_total_outstanding_debt")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_credits_less_than_total_debt_return_none(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
        mock_get_early_repayment_fee: MagicMock,
        mock_get_overpayment_allowance_fee_for_early_repayment: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "application_precision": 2}
        )
        mock_validate_denomination.return_value = None
        mock_is_flag_in_list_applied.return_value = False
        mock_get_total_outstanding_debt.return_value = Decimal("2")
        mock_get_early_repayment_fee.return_value = Decimal("0")
        mock_balance_at_coordinates.return_value = Decimal("2")  # principal balance

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("1"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_credit_when_repayments_blocked_return_rejection(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP", "application_precision": 2}
        )
        mock_validate_denomination.return_value = None
        mock_is_flag_in_list_applied.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Repayments are blocked for this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_debits_return_rejection(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_denomination.return_value = None

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("1"))],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Debiting is not allowed from this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(mortgage.utils, "str_to_bool")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_debits_with_fee_metadata_return_none(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_denomination.return_value = None
        mock_str_to_bool.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), instruction_details={"fee": "true"}
                )
            ],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(mortgage.utils, "str_to_bool")
    @patch.object(mortgage.utils, "validate_denomination")
    @patch.object(mortgage.utils, "validate_single_hard_settlement_or_transfer")
    def test_debits_with_interest_adjustment_metadata_return_none(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_denomination.return_value = None
        mock_str_to_bool.return_value = [False, True]

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), instruction_details={"interest_adjustment": "true"}
                )
            ],
            client_transactions={},
        )

        result = mortgage.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
