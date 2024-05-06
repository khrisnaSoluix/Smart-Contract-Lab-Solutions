# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
import library.offset_mortgage.supervisors.template.offset_mortgage as offset_mortgage
from library.offset_mortgage.test.unit.test_offset_mortgage_common import OffsetMortgageTestBase

# contracts api
from contracts_api import DEFAULT_ASSET, Phase, Posting


@patch.object(offset_mortgage.utils, "get_balance_default_dict_from_mapping")
@patch.object(offset_mortgage.utils, "balance_at_coordinates")
@patch.object(offset_mortgage, "_get_denomination_parameter")
class SplitAccountsByEligibilityTest(OffsetMortgageTestBase):
    def test_if_condition_short_circuits_if_mismatched_denomination(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        # construct mocks
        ca_1 = self.create_supervisee_mock()
        casa_accounts = [ca_1]
        mock_get_denomination_parameter.return_value = "USD"

        # construct expected result
        expected_result: tuple[list, list] = [], [ca_1]

        # run function
        result = offset_mortgage._split_supervisees_by_eligibility(casa_accounts, "GBP")
        self.assertTupleEqual(result, expected_result)
        # should not call balances condition due to short-circuit evaluation
        # and hence balances are not pulled from Vault if denom doesn't match
        mock_balance_at_coordinates.assert_not_called()
        mock_get_balance_default_dict_from_mapping.assert_not_called()
        ca_1.get_balances_timeseries.assert_not_called()

    def test_all_eligible(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        # construct mocks
        ca_1 = self.create_supervisee_mock(requires_fetched_balances={})
        ca_2 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_1 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_2 = self.create_supervisee_mock(requires_fetched_balances={})
        casa_accounts = [ca_1, ca_2, sa_1, sa_2]
        mock_get_denomination_parameter.side_effect = ["GBP", "GBP", "GBP", "GBP"]
        mock_balance_at_coordinates.side_effect = [
            Decimal("100"),
            Decimal("10"),
            Decimal("50"),
            Decimal("20"),
        ]
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict

        # construct expected result
        expected_result: tuple[list, list] = [ca_1, ca_2, sa_1, sa_2], []
        # run function
        result = offset_mortgage._split_supervisees_by_eligibility(casa_accounts, "GBP")
        self.assertTupleEqual(result, expected_result)

    def test_all_ineligible(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        # construct mocks
        ca_1 = self.create_supervisee_mock(requires_fetched_balances={})
        ca_2 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_1 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_2 = self.create_supervisee_mock(requires_fetched_balances={})
        casa_accounts = [ca_1, ca_2, sa_1, sa_2]
        mock_get_denomination_parameter.side_effect = ["SGD", "AUD", "USD", "AUD"]
        mock_balance_at_coordinates.side_effect = [
            Decimal("-100"),
            Decimal("0"),
            Decimal("-50"),
            Decimal("-20"),
        ]
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict

        # construct expected result
        expected_result: tuple[list, list] = [], [ca_1, ca_2, sa_1, sa_2]
        # run function
        result = offset_mortgage._split_supervisees_by_eligibility(casa_accounts, "GBP")
        self.assertTupleEqual(result, expected_result)

    def test_mix_of_eligible_and_ineligible(
        self,
        mock_get_denomination_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        # construct mocks
        ca_1 = self.create_supervisee_mock(requires_fetched_balances={})
        ca_2 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_1 = self.create_supervisee_mock(requires_fetched_balances={})
        sa_2 = self.create_supervisee_mock(requires_fetched_balances={})
        casa_accounts = [ca_1, ca_2, sa_1, sa_2]
        mock_get_denomination_parameter.side_effect = ["GBP", "AUD", "GBP", "USD"]
        mock_balance_at_coordinates.side_effect = [
            Decimal("-100"),  # return value for ca_1
            Decimal("50"),  # return value for sa_1
        ]
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.default_dict

        # construct expected result
        expected_result: tuple[list, list] = [sa_1], [ca_1, ca_2, sa_2]
        # run function
        result = offset_mortgage._split_supervisees_by_eligibility(casa_accounts, "GBP")
        self.assertTupleEqual(result, expected_result)


class SplitInstructionsIntoOffsetEligibleAndPreservedTest(OffsetMortgageTestBase):
    def test_splits_custom_instructions_for_accrued_interest_receivable(self):
        # expected values
        accrued_interest_receivable_instruction = self.custom_instruction(
            postings=[
                Posting(
                    credit=True,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="ACCRUED_INTEREST_RECEIVABLE",
                    account_address="DEFAULT",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="MORTGAGE_ACCOUNT",
                    account_address=offset_mortgage.interest_accrual.ACCRUED_INTEREST_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        accrued_expected_interest_instruction = self.custom_instruction(
            postings=[
                Posting(
                    credit=True,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="MORTGAGE_ACCOUNT",
                    account_address="INTERNAL_CONTRA",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="MORTGAGE_ACCOUNT",
                    account_address=offset_mortgage.overpayment.ACCRUED_EXPECTED_INTEREST,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        other_instruction = self.custom_instruction(
            postings=[
                Posting(
                    credit=True,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="MORTGAGE_ACCOUNT",
                    account_address="INTERNAL_CONTRA",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("8.21919"),
                    denomination="GBP",
                    account_id="MORTGAGE_ACCOUNT",
                    account_address="SOMETHING_ELSE",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions = [
            accrued_interest_receivable_instruction,
            accrued_expected_interest_instruction,
            other_instruction,
        ]

        # construct expected result
        expected_offset_eligible_instructions = [
            accrued_interest_receivable_instruction,
            accrued_expected_interest_instruction,
        ]
        expected_instructions_to_preserve = [other_instruction]
        expected_result = expected_offset_eligible_instructions, expected_instructions_to_preserve
        # run function
        result = offset_mortgage._split_instructions_into_offset_eligible_and_preserved(
            posting_instructions=posting_instructions,
            mortgage_account_id="MORTGAGE_ACCOUNT",
            mortgage_denomination="GBP",
        )
        self.assertTupleEqual(result, expected_result)
