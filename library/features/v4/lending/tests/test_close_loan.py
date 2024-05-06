# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call, patch, sentinel

# features
import library.features.v4.lending.close_loan as close_loan

# contracts api
from contracts_api import Posting

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ASSET,
    AccountNotificationDirective,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    Rejection,
    RejectionReason,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class CloseLoanTestCommon(FeatureTest):
    default_denomination = "AUD"
    tside = Tside.ASSET


class TestDoesRepaymentFullyRepayLoan(CloseLoanTestCommon):
    account_id = sentinel.account_id

    def test_loan_paid_off_notification_type(
        self,
    ):
        # expected values
        product_name = "PRODUCT_A"
        # construct expected result
        expected_notification_type = f"{product_name}{close_loan.LOAN_PAID_OFF_NOTIFICATION_SUFFIX}"
        # run function
        notification_type = close_loan.notification_type(product_name=product_name)
        # validate results
        self.assertEqual(notification_type, expected_notification_type)

    @patch.object(close_loan, "notification_type")
    def test_send_loan_paid_off_notification(self, mock_notification_type: MagicMock):
        # expected values
        product_name = "PRODUCT_A"

        # construct expected result
        expected_notification_type = f"{product_name}{close_loan.LOAN_PAID_OFF_NOTIFICATION_SUFFIX}"
        expected_notification_details = {
            "account_id": sentinel.account_id,
        }
        expected_notification: AccountNotificationDirective = AccountNotificationDirective(
            notification_type=expected_notification_type,
            notification_details=expected_notification_details,
        )
        # construct mocks
        mock_notification_type.return_value = expected_notification_type
        # run function
        result_notification = close_loan.send_loan_paid_off_notification(
            account_id=sentinel.account_id,
            product_name=product_name,
        )
        # validate results
        self.assertEqual(result_notification, expected_notification)

    @patch.object(close_loan.utils, "sum_balances")
    def test_param_defaults_are_applied_correctly(self, mock_sum_balances: MagicMock):
        # Outstanding debt amt, followed by the repayment amt
        mock_sum_balances.side_effect = [Decimal("0"), Decimal("0")]

        close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

        # assertions
        mock_sum_balances.assert_has_calls(
            [
                call(
                    balances=BalanceDefaultDict(),
                    # This list should be the default debt addresses
                    addresses=[
                        "PRINCIPAL_OVERDUE",
                        "INTEREST_OVERDUE",
                        "PENALTIES",
                        "PRINCIPAL_DUE",
                        "INTEREST_DUE",
                        "PRINCIPAL",
                    ],
                    denomination=self.default_denomination,
                ),
                call(
                    balances=BalanceDefaultDict(),
                    # This list should be the default payment addresses
                    addresses=[
                        "PRINCIPAL_OVERDUE",
                        "INTEREST_OVERDUE",
                        "PENALTIES",
                        "PRINCIPAL_DUE",
                        "INTEREST_DUE",
                    ],
                    denomination=self.default_denomination,
                ),
            ]
        )

    @patch.object(close_loan.utils, "sum_balances")
    def test_balance_address_inputs_are_correctly_used(self, mock_sum_balances: MagicMock):
        # Outstanding debt amt, followed by the repayment amt
        mock_sum_balances.side_effect = [Decimal("0"), Decimal("0")]
        debt_addresses = ["DEBT_ADDRESS_1", "DEBT_ADDRESS_2"]
        payment_addresses = ["PAYMENT_ADDRESS_1", "PAYMENT_ADDRESS_2"]

        close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            denomination=self.default_denomination,
            account_id=self.account_id,
            debt_addresses=debt_addresses,
            payment_addresses=payment_addresses,
        )

        # assertions
        mock_sum_balances.assert_has_calls(
            [
                call(
                    balances=BalanceDefaultDict(),
                    addresses=debt_addresses,
                    denomination=self.default_denomination,
                ),
                call(
                    balances=BalanceDefaultDict(),
                    addresses=payment_addresses,
                    denomination=self.default_denomination,
                ),
            ]
        )

    @patch.object(close_loan.utils, "sum_balances")
    def test_balances_are_merged_correctly(self, mock_sum_balances: MagicMock):
        # Outstanding debt amt, followed by the repayment amt
        mock_sum_balances.side_effect = [Decimal("0"), Decimal("0")]
        postings_for_instruction_1 = [
            Posting(
                credit=True,
                amount=Decimal("10"),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address="INTEREST_DUE",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("10"),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address="DEFAULT",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        postings_for_instruction_2 = [
            Posting(
                credit=True,
                amount=Decimal("13.25"),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address="PRINCIPAL_DUE",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("13.25"),
                denomination=self.default_denomination,
                account_id=self.account_id,
                account_address="DEFAULT",
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_instructions = [
            self.custom_instruction(postings=postings_for_instruction_1),
            self.custom_instruction(postings=postings_for_instruction_2),
        ]

        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(denomination=self.default_denomination): self.balance(
                    net=Decimal("30")
                )
            }
        )

        close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=posting_instructions,
            balances=balances,
            denomination=self.default_denomination,
            account_id=self.account_id,
            debt_addresses=[],
            payment_addresses=[],
        )

        # assertions
        expected_merged_balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(denomination=self.default_denomination): self.balance(
                    net=Decimal("23.25")
                ),
                self.balance_coordinate(
                    account_address="PRINCIPAL_DUE", denomination=self.default_denomination
                ): self.balance(net=Decimal("-13.25")),
                self.balance_coordinate(
                    account_address="INTEREST_DUE", denomination=self.default_denomination
                ): self.balance(net=Decimal("-10")),
            }
        )
        mock_sum_balances.assert_has_calls(
            [
                call(
                    balances=balances,
                    addresses=[],
                    denomination=self.default_denomination,
                ),
                call(
                    # the balances here should be the merged balances from the repayment
                    # postings
                    balances=expected_merged_balances,
                    addresses=[],
                    denomination=self.default_denomination,
                ),
            ]
        )

    @patch.object(close_loan.utils, "sum_balances")
    def test_outstanding_debt_greater_than_repayment_amount_returns_false(
        self, mock_sum_balances: MagicMock
    ):
        # Outstanding debt amt, followed by the repayment amt
        # (there are no excess funds in this scenario)
        mock_sum_balances.side_effect = [Decimal("100"), Decimal("0")]

        result = close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

        # assertions
        self.assertFalse(result)

    @patch.object(close_loan.utils, "sum_balances")
    def test_outstanding_debt_equal_to_the_repayment_amount_returns_true(
        self, mock_sum_balances: MagicMock
    ):
        # Outstanding debt amt, followed by the repayment amt
        mock_sum_balances.side_effect = [Decimal("100"), Decimal("100")]

        result = close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

        # assertions
        self.assertTrue(result)

    @patch.object(close_loan.utils, "sum_balances")
    def test_outstanding_debt_less_than_the_repayment_amount_returns_true(
        self, mock_sum_balances: MagicMock
    ):
        # Outstanding debt, followed by the repayment amount
        mock_sum_balances.side_effect = [Decimal("100"), Decimal("125")]

        result = close_loan.does_repayment_fully_repay_loan(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            denomination=self.default_denomination,
            account_id=self.account_id,
        )

        # assertions
        self.assertTrue(result)


@patch.object(close_loan.utils, "balance_at_coordinates")
class TestNetBalances(CloseLoanTestCommon):
    @patch.object(close_loan.utils, "create_postings")
    def test_creates_net_postings_for_positive_emi_amount(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("24")
        balances = sentinel.balances
        mock_postings: list[Posting] = [SentinelPosting("dummy_posting")] * 2  # type: ignore
        mock_create_postings.return_value = mock_postings

        net_posting_instructions = close_loan.net_balances(
            balances=balances,
            denomination=self.default_denomination,
            account_id=sentinel.account_id,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=balances, address="EMI", denomination=self.default_denomination
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("24"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address="INTERNAL_CONTRA",
            credit_address="EMI",
            denomination=self.default_denomination,
        )
        expected_posting_instructions = [
            CustomInstruction(
                postings=mock_postings,  # type: ignore
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                },
            )
        ]
        self.assertEqual(net_posting_instructions, expected_posting_instructions)

    @patch.object(close_loan.utils, "create_postings")
    def test_creates_net_postings_for_positive_emi_amount_with_cleanup_feature(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("24")
        balances = sentinel.balances
        mock_emi_postings: list[Posting] = [SentinelPosting("emi_posting")] * 2  # type: ignore
        mock_feature_postings: list[Posting] = [
            SentinelPosting("feature_posting")
        ] * 2  # type: ignore
        mock_create_postings.return_value = mock_emi_postings

        residual_cleanup_feature = Mock(
            get_residual_cleanup_postings=Mock(return_value=mock_feature_postings)
        )

        net_posting_instructions = close_loan.net_balances(
            balances=balances,
            denomination=self.default_denomination,
            account_id=sentinel.account_id,
            residual_cleanup_features=[residual_cleanup_feature],
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=balances, address="EMI", denomination=self.default_denomination
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("24"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address="INTERNAL_CONTRA",
            credit_address="EMI",
            denomination=self.default_denomination,
        )
        expected_posting_instructions = [
            CustomInstruction(
                postings=mock_emi_postings + mock_feature_postings,  # type: ignore
                instruction_details={
                    "description": "Clearing all residual balances",
                    "event": "END_OF_LOAN",
                },
            )
        ]
        self.assertEqual(net_posting_instructions, expected_posting_instructions)

    def test_no_net_balances_returns_empty_list(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = Decimal()
        balances = sentinel.balances
        net_posting_instructions = close_loan.net_balances(
            balances=balances,
            denomination=self.default_denomination,
            account_id=sentinel.account_id,
        )

        # assertions
        mock_balance_at_coordinates.assert_called_once_with(
            balances=balances, address="EMI", denomination=self.default_denomination
        )
        self.assertEqual(net_posting_instructions, [])


@patch.object(close_loan.utils, "sum_balances")
class TestRejectClosureWhenOutstandingDebt(CloseLoanTestCommon):
    default_rejection = Rejection(
        message="The loan cannot be closed until all outstanding debt is repaid",
        reason_code=RejectionReason.AGAINST_TNC,
    )
    default_debt_addresses = [
        "PRINCIPAL_OVERDUE",
        "INTEREST_OVERDUE",
        "PENALTIES",
        "PRINCIPAL_DUE",
        "INTEREST_DUE",
        "PRINCIPAL",
    ]

    def test_rejects_if_sum_of_balances_is_positive(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = Decimal("1.25")

        outstanding_debt_rejection = close_loan.reject_closure_when_outstanding_debt(
            balances=sentinel.balances, denomination=self.default_denomination
        )

        # assertions
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=self.default_debt_addresses,
            denomination=self.default_denomination,
        )
        self.assertEqual(outstanding_debt_rejection, self.default_rejection)

    def test_rejects_if_sum_of_balances_is_negative(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = Decimal("-1.03")

        outstanding_debt_rejection = close_loan.reject_closure_when_outstanding_debt(
            balances=sentinel.balances, denomination=self.default_denomination
        )

        # assertions
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=self.default_debt_addresses,
            denomination=self.default_denomination,
        )
        self.assertEqual(outstanding_debt_rejection, self.default_rejection)

    def test_does_not_reject_if_sum_of_balances_is_zero(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = Decimal("0.00")

        outstanding_debt_rejection = close_loan.reject_closure_when_outstanding_debt(
            balances=sentinel.balances, denomination=self.default_denomination
        )

        # assertions
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=self.default_debt_addresses,
            denomination=self.default_denomination,
        )
        self.assertIsNone(outstanding_debt_rejection)
