# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.line_of_credit.contracts.template import drawdown_loan
from library.line_of_credit.test.unit.test_drawdown_loan_common import DrawdownLoanTestBase

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class NetAggregateEMITest(DrawdownLoanTestBase):
    @patch.object(drawdown_loan.utils, "balance_at_coordinates")
    @patch.object(drawdown_loan.utils, "create_postings")
    def test_postings_generated_correctly(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = sentinel.emi_amount
        mock_create_postings.return_value = [sentinel.net_aggregate_emi_postings]

        result = drawdown_loan._net_aggregate_emi(
            balances=sentinel.balances,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, [sentinel.net_aggregate_emi_postings])

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=drawdown_loan.lending_addresses.EMI,
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_called_once_with(
            amount=sentinel.emi_amount,
            debit_account=sentinel.loc_account_id,
            credit_account=sentinel.loc_account_id,
            debit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            credit_address=f"TOTAL_{drawdown_loan.lending_addresses.EMI}",
            denomination=sentinel.denomination,
        )


class GetOriginalPrincipalCustomInstructions(DrawdownLoanTestBase):
    def setUp(self) -> None:
        self.postings = [SentinelPosting("postings")]
        self.mock_create_postings = patch.object(drawdown_loan.utils, "create_postings").start()
        self.mock_create_postings.return_value = self.postings

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_not_closing_loan(self):
        expected_result = [
            CustomInstruction(
                postings=self.postings,  # type: ignore
                instruction_details={"force_override": "True"},
            )
        ]
        result = drawdown_loan._get_original_principal_custom_instructions(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
            is_closing_loan=False,
        )

        self.assertListEqual(result, expected_result)

        self.mock_create_postings.assert_called_once_with(
            amount=sentinel.principal,
            debit_account=sentinel.loc_account_id,
            credit_account=sentinel.loc_account_id,
            debit_address=drawdown_loan.line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL,
            credit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_closing_loan(self):
        expected_result = [
            CustomInstruction(
                postings=self.postings,  # type: ignore
                instruction_details={"force_override": "True"},
            )
        ]
        result = drawdown_loan._get_original_principal_custom_instructions(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
            is_closing_loan=True,
        )

        self.assertListEqual(result, expected_result)

        self.mock_create_postings.assert_called_once_with(
            amount=sentinel.principal,
            debit_account=sentinel.loc_account_id,
            credit_account=sentinel.loc_account_id,
            debit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            credit_address=drawdown_loan.line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL,
            denomination=sentinel.denomination,
        )

    def test_no_postings(self):
        self.mock_create_postings.return_value = []
        result = drawdown_loan._get_original_principal_custom_instructions(
            principal=sentinel.principal,
            loc_account_id=sentinel.loc_account_id,
            denomination=sentinel.denomination,
            is_closing_loan=False,
        )

        self.assertListEqual(result, [])

        self.mock_create_postings.assert_called_once_with(
            amount=sentinel.principal,
            debit_account=sentinel.loc_account_id,
            credit_account=sentinel.loc_account_id,
            debit_address=drawdown_loan.line_of_credit_addresses.TOTAL_ORIGINAL_PRINCIPAL,
            credit_address=drawdown_loan.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
