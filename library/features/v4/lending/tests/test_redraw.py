# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.lending.redraw as redraw

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class RedrawTestCommon(FeatureTest):
    default_denomination = "AUD"
    tside = Tside.ASSET


@patch.object(redraw.utils, "balance_at_coordinates")
class AutoRepaymentTest(RedrawTestCommon):
    default_balances = sentinel.balances
    default_account_id = "default_account"
    default_due_posting_instructions = [
        RedrawTestCommon().custom_instruction(
            postings=[
                Posting(
                    credit=False,
                    amount=Decimal("50"),
                    denomination=RedrawTestCommon().default_denomination,
                    account_id=default_account_id,
                    account_address="PRINCIPAL_DUE",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=Decimal("50"),
                    denomination=RedrawTestCommon().default_denomination,
                    account_id=sentinel.internal_account_id,
                    account_address="INTERNAL",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("10"),
                    denomination=RedrawTestCommon().default_denomination,
                    account_id=default_account_id,
                    account_address="INTEREST_DUE",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=True,
                    amount=Decimal("10"),
                    denomination=RedrawTestCommon().default_denomination,
                    account_id=sentinel.internal_account_id,
                    account_address="INTERNAL",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
    ]
    default_repayment_hierarchy = ["PRINCIPAL_DUE", "INTEREST_DUE"]

    def test_no_redraw_balance_returns_no_postings(self, mock_balance_at_coordinates: MagicMock):

        mock_balance_at_coordinates.return_value = Decimal("0")

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=self.default_due_posting_instructions,
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertEqual(auto_repayment_result, [])

    def test_no_due_amount_balances_returns_no_postings(
        self, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=[],
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertEqual(auto_repayment_result, [])

    def test_no_repayment_hierarchy_returns_no_postings(
        self, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=self.default_due_posting_instructions,
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=[],
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertEqual(auto_repayment_result, [])

    @patch.object(redraw.payments, "redistribute_postings")
    def test_redraw_balance_pays_off_part_of_first_due_balance(
        self, mock_redistribute_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")
        auto_repay_due_postings = [SentinelPosting("auto_repay_principal_due_balance")] * 2
        mock_redistribute_postings.return_value = auto_repay_due_postings

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=[
                self.custom_instruction(
                    postings=[
                        Posting(
                            credit=False,
                            amount=Decimal("60"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=self.default_account_id,
                            account_address="PRINCIPAL_DUE",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                        Posting(
                            credit=True,
                            amount=Decimal("60"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id="1",
                            account_address="INTERNAL",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                    ]
                )
            ],
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        mock_redistribute_postings.assert_called_with(
            debit_account=self.default_account_id,
            denomination=self.default_denomination,
            amount=Decimal("55"),
            credit_account=self.default_account_id,
            credit_address="PRINCIPAL_DUE",
            debit_address="REDRAW",
        )
        self.assertEqual(
            auto_repayment_result,
            [
                CustomInstruction(
                    postings=auto_repay_due_postings,  # type: ignore
                    instruction_details={
                        "description": "Auto repay due balances from the redraw balance",
                        "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                    },
                    override_all_restrictions=True,
                )
            ],
        )

    @patch.object(redraw.payments, "redistribute_postings")
    def test_redraw_balance_pays_off_all_of_first_due_balance_and_part_of_second_due_balance(
        self, mock_redistribute_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")
        auto_repay_due_postings = [
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
        ]
        mock_redistribute_postings.side_effect = [
            [auto_repay_due_postings[0], auto_repay_due_postings[1]],
            [auto_repay_due_postings[2], auto_repay_due_postings[3]],
        ]

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=self.default_due_posting_instructions,
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        mock_redistribute_postings.assert_has_calls(
            [
                call(
                    debit_account=self.default_account_id,
                    denomination=self.default_denomination,
                    amount=Decimal("50"),
                    credit_account=self.default_account_id,
                    credit_address="PRINCIPAL_DUE",
                    debit_address="REDRAW",
                ),
                call(
                    debit_account=self.default_account_id,
                    denomination=self.default_denomination,
                    amount=Decimal("5"),
                    credit_account=self.default_account_id,
                    credit_address="INTEREST_DUE",
                    debit_address="REDRAW",
                ),
            ]
        )
        self.assertEqual(
            auto_repayment_result,
            [
                CustomInstruction(
                    postings=auto_repay_due_postings,  # type: ignore
                    instruction_details={
                        "description": "Auto repay due balances from the redraw balance",
                        "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                    },
                    override_all_restrictions=True,
                )
            ],
        )

    @patch.object(redraw.payments, "redistribute_postings")
    def test_redraw_balance_pays_off_all_due_balances(
        self, mock_redistribute_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")
        auto_repay_due_postings = [
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
        ]
        mock_redistribute_postings.side_effect = [
            [auto_repay_due_postings[0], auto_repay_due_postings[1]],
            [auto_repay_due_postings[2], auto_repay_due_postings[3]],
        ]

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=[
                self.custom_instruction(
                    postings=[
                        Posting(
                            credit=False,
                            amount=Decimal("30"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=self.default_account_id,
                            account_address="PRINCIPAL_DUE",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                        Posting(
                            credit=True,
                            amount=Decimal("30"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=sentinel.internal_account_id,
                            account_address="INTERNAL",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                        Posting(
                            credit=False,
                            amount=Decimal("25"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=self.default_account_id,
                            account_address="INTEREST_DUE",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                        Posting(
                            credit=True,
                            amount=Decimal("25"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=sentinel.internal_account_id,
                            account_address="INTERNAL",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                    ]
                )
            ],
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        mock_redistribute_postings.assert_has_calls(
            [
                call(
                    debit_account=self.default_account_id,
                    denomination=self.default_denomination,
                    amount=Decimal("30"),
                    credit_account=self.default_account_id,
                    credit_address="PRINCIPAL_DUE",
                    debit_address="REDRAW",
                ),
                call(
                    debit_account=self.default_account_id,
                    denomination=self.default_denomination,
                    amount=Decimal("25"),
                    credit_account=self.default_account_id,
                    credit_address="INTEREST_DUE",
                    debit_address="REDRAW",
                ),
            ]
        )
        self.assertEqual(
            auto_repayment_result,
            [
                CustomInstruction(
                    postings=auto_repay_due_postings,  # type: ignore
                    instruction_details={
                        "description": "Auto repay due balances from the redraw balance",
                        "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                    },
                    override_all_restrictions=True,
                )
            ],
        )

    @patch.object(redraw.payments, "redistribute_postings")
    def test_redraw_balance_pays_off_all_due_balances_with_leftover_redraw(
        self, mock_redistribute_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("-55.00")
        auto_repay_due_postings = [
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_principal_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
            SentinelPosting("auto_repay_interest_due_balance"),
        ]
        mock_redistribute_postings.side_effect = [
            [auto_repay_due_postings[0], auto_repay_due_postings[1]],
            [auto_repay_due_postings[2], auto_repay_due_postings[3]],
        ]

        auto_repayment_result = redraw.auto_repayment(
            balances=self.default_balances,
            due_amount_posting_instructions=[
                self.custom_instruction(
                    postings=[
                        Posting(
                            credit=False,
                            amount=Decimal("30"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=self.default_account_id,
                            account_address="PRINCIPAL_DUE",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                        Posting(
                            credit=True,
                            amount=Decimal("30"),
                            denomination=RedrawTestCommon().default_denomination,
                            account_id=sentinel.internal_account_id,
                            account_address="INTERNAL",
                            asset=DEFAULT_ASSET,
                            phase=Phase.COMMITTED,
                        ),
                    ]
                )
            ],
            denomination=self.default_denomination,
            account_id=self.default_account_id,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        mock_redistribute_postings.assert_called_once_with(
            debit_account=self.default_account_id,
            denomination=self.default_denomination,
            amount=Decimal("30"),
            credit_account=self.default_account_id,
            credit_address="PRINCIPAL_DUE",
            debit_address="REDRAW",
        )
        self.assertEqual(
            auto_repayment_result,
            [
                CustomInstruction(
                    postings=auto_repay_due_postings,  # type: ignore
                    instruction_details={
                        "description": "Auto repay due balances from the redraw balance",
                        "event": "PROCESS_AUTO_REPAYMENT_FROM_REDRAW_BALANCE",
                    },
                    override_all_restrictions=True,
                )
            ],
        )


class HandleOverpaymentTest(RedrawTestCommon):
    @patch.object(redraw.utils, "create_postings")
    def test_handle_overpayment_rebalances_to_redraw(self, mock_create_postings: MagicMock):
        mock_vault = self.create_mock()
        mock_create_postings.return_value = [sentinel.redraw_postings]

        result = redraw.handle_overpayment(
            vault=mock_vault,
            overpayment_amount=sentinel.overpayment_amount,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual(result, [sentinel.redraw_postings])
        mock_create_postings.assert_called_once_with(
            debit_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            amount=sentinel.overpayment_amount,
            credit_account=mock_vault.account_id,
            credit_address=redraw.REDRAW_ADDRESS,
        )


@patch.object(redraw.utils, "balance_at_coordinates")
class GetAvailableRedrawFundsTest(RedrawTestCommon):
    def test_returns_redraw_balance(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal("-10")
        redraw_funds = redraw.get_available_redraw_funds(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address="REDRAW",
            denomination=sentinel.denomination,
            decimal_places=2,
        )
        self.assertEqual(redraw_funds, Decimal("10"))


@patch.object(redraw.utils, "balance_at_coordinates")
class RejectClosureWhenOutstandingRedrawFundsTest(RedrawTestCommon):
    default_balances = sentinel.balances

    def test_rejects_when_redraw_has_positive_balance(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal("10")
        outstanding_redraw_funds_rejection = redraw.reject_closure_when_outstanding_redraw_funds(
            balances=self.default_balances, denomination=self.default_denomination
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertEqual(
            outstanding_redraw_funds_rejection,
            Rejection(
                message="The loan cannot be closed until all remaining redraw funds are cleared.",
                reason_code=RejectionReason.AGAINST_TNC,
            ),
        )

    def test_rejects_when_redraw_has_negative_balance(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal("-10")
        outstanding_redraw_funds_rejection = redraw.reject_closure_when_outstanding_redraw_funds(
            balances=self.default_balances, denomination=self.default_denomination
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertEqual(
            outstanding_redraw_funds_rejection,
            Rejection(
                message="The loan cannot be closed until all remaining redraw funds are cleared.",
                reason_code=RejectionReason.AGAINST_TNC,
            ),
        )

    def test_does_not_reject_when_redraw_has_zero_balance(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")
        outstanding_redraw_funds_rejection = redraw.reject_closure_when_outstanding_redraw_funds(
            balances=self.default_balances, denomination=self.default_denomination
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertIsNone(outstanding_redraw_funds_rejection)


@patch.object(redraw.utils, "balance_at_coordinates")
class ValidateRedrawFundsTest(RedrawTestCommon):
    default_balances = sentinel.balances

    def test_posting_amount_of_0_is_accepted(self, mock_balance_at_coordinates: MagicMock):

        mock_balance_at_coordinates.return_value = Decimal("10.00")
        validate_redraw_funds_result = redraw.validate_redraw_funds(
            balances=self.default_balances,
            posting_amount=Decimal("0"),
            denomination=self.default_denomination,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertIsNone(validate_redraw_funds_result)

    def test_posting_amount_below_the_redraw_balance_is_accepted(
        self, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("10.00")
        validate_redraw_funds_result = redraw.validate_redraw_funds(
            balances=self.default_balances,
            posting_amount=Decimal("5.25"),
            denomination=self.default_denomination,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertIsNone(validate_redraw_funds_result)

    def test_posting_amount_equal_to_the_redraw_balance_is_accepted(
        self, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("10.00")
        validate_redraw_funds_result = redraw.validate_redraw_funds(
            balances=self.default_balances,
            posting_amount=Decimal("10"),
            denomination=self.default_denomination,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        self.assertIsNone(validate_redraw_funds_result)

    def test_posting_amount_above_redraw_balance_is_rejected(
        self, mock_balance_at_coordinates: MagicMock
    ):

        mock_balance_at_coordinates.return_value = Decimal("10.00")
        validate_redraw_funds_result = redraw.validate_redraw_funds(
            balances=self.default_balances,
            posting_amount=Decimal("10.01"),
            denomination=self.default_denomination,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=self.default_balances, address="REDRAW", denomination=self.default_denomination
        )
        expected_rejection = Rejection(
            message=f"Transaction amount 10.01 {self.default_denomination} is greater than "
            f"the available redraw funds of 10.00 {self.default_denomination}.",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )
        self.assertEqual(expected_rejection, validate_redraw_funds_result)
