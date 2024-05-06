# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
import library.mortgage.contracts.template.mortgage as mortgage
from library.mortgage.test.unit.test_mortgage_common import MortgageTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Posting,
    ScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountNotificationDirective,
    CustomInstruction,
    InboundHardSettlement,
    Phase,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelPosting,
    SentinelScheduleExpression,
)


class MortgageHelpersTest(MortgageTestBase):
    @patch.object(mortgage.utils, "sum_balances")
    def test_get_late_payment_balance(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("1234.567")

        expected_result = Decimal("1234.567")
        result = mortgage._get_late_payment_balance(balances=sentinel.balances, denomination="GBP")
        self.assertEqual(result, expected_result)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=mortgage.lending_addresses.LATE_REPAYMENT_ADDRESSES,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

    @patch.object(mortgage.utils, "create_postings")
    def test_move_balance_custom_instructions(self, mock_create_postings: MagicMock):
        # expected values
        postings = [SentinelPosting("create_postings")]

        # construct mocks
        mock_create_postings.return_value = postings

        # construct expected result
        expected_result = [
            CustomInstruction(
                postings=postings,  # type: ignore
                instruction_details={
                    "description": "Move 100 of balance into DUMMY_ADDRESS",
                    "event": "MOVE_BALANCE_INTO_DUMMY_ADDRESS",
                },
                override_all_restrictions=True,
            )
        ]

        # run function
        result = mortgage._move_balance_custom_instructions(
            amount=Decimal("100"),
            denomination="GBP",
            vault_account="account_id",
            balance_address="DUMMY_ADDRESS",
        )
        self.assertEqual(result, expected_result)
        mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account="account_id",
            debit_address="DUMMY_ADDRESS",
            credit_account="account_id",
            credit_address=DEFAULT_ADDRESS,
            denomination="GBP",
        )


@patch.object(mortgage.utils, "get_parameter")
@patch.object(mortgage.utils, "balance_at_coordinates")
class UseExpectedTermTest(MortgageTestBase):
    def test_use_expected_term_with_reduce_emi_overpayment_preference(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal(0)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_emi"}
        )
        self.assertTrue(
            mortgage._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )

    def test_use_expected_term_with_reduce_term_overpayment_preference_but_no_overpayments(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal(0)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term"}
        )
        self.assertTrue(
            mortgage._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )

    def test_dont_use_expected_term_with_reduce_term_overpayment_preference_and_overpayments(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal(1)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term"}
        )
        self.assertFalse(
            mortgage._use_expected_term(
                vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
            )
        )


class BalanceHelpersTest(MortgageTestBase):
    @patch.object(mortgage.utils, "sum_balances")
    def test_get_late_payment_balance(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = Decimal("1234.567")

        expected_result = Decimal("1234.567")
        result = mortgage._get_late_payment_balance(balances=sentinel.balances, denomination="GBP")
        self.assertEqual(result, expected_result)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=mortgage.lending_addresses.LATE_REPAYMENT_ADDRESSES,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_get_outstanding_principal(
        self,
        mock_balances_at_coordinates: MagicMock,
    ):
        mock_balances_at_coordinates.return_value = Decimal("1234.567")

        expected_result = Decimal("1234.567")
        result = mortgage._get_outstanding_principal(balances=sentinel.balances, denomination="GBP")
        self.assertEqual(result, expected_result)

        mock_balances_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=mortgage.lending_addresses.PRINCIPAL,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

    @patch.object(mortgage.utils, "sum_balances")
    def test_get_outstanding_payments_amount(
        self,
        mock_sum_balances: MagicMock,
    ):
        mock_sum_balances.return_value = sentinel.balance_sum

        expected_result = sentinel.balance_sum
        result = mortgage._get_outstanding_payments_amount(
            balances=sentinel.balances, denomination="GBP"
        )
        self.assertEqual(result, expected_result)

        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=mortgage.lending_addresses.REPAYMENT_HIERARCHY,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

    @patch.object(mortgage.utils, "balance_at_coordinates")
    def test_get_interest_to_revert(self, mock_balance_at_coordinates: MagicMock):
        # expected values
        monthly_interest = Decimal("10")

        # construct mocks
        mock_balance_at_coordinates.return_value = monthly_interest

        # run function
        result = mortgage._get_interest_to_revert(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, monthly_interest)

    @patch.object(mortgage.utils, "sum_balances")
    def test_get_overdue_capital_include_overdue_interest(self, mock_sum_balances: MagicMock):
        # construct mocks
        mock_sum_balances.return_value = sentinel.balance_sum

        # run function
        result = mortgage._get_overdue_capital(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=True,
        )

        self.assertEqual(result, sentinel.balance_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=mortgage.lending_addresses.OVERDUE_ADDRESSES,
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(mortgage.utils, "sum_balances")
    def test_get_overdue_capital_do_not_include_overdue_interest(
        self, mock_sum_balances: MagicMock
    ):
        # construct mocks
        mock_sum_balances.return_value = sentinel.balance_sum

        # run function
        result = mortgage._get_overdue_capital(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            include_overdue_interest=False,
        )

        self.assertEqual(result, sentinel.balance_sum)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=[mortgage.lending_addresses.PRINCIPAL_OVERDUE],
            denomination=sentinel.denomination,
            decimal_places=2,
        )

    @patch.object(mortgage.utils, "balance_at_coordinates")
    @patch.object(mortgage.fees, "fee_postings")
    def test_handle_early_repayment_fee_does_not_generate_instructions_when_no_early_repayment_fee(
        self,
        mock_fee_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_balance_at_coordinates.side_effect = [Decimal("0")]

        # run function
        result = mortgage._handle_early_repayment_fee(
            repayment_posting_instructions=[],
            balances=BalanceDefaultDict(),
            account_id=sentinel.account_id,
            early_repayment_fee_account=sentinel.early_repayment_fee_account,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, [])
        mock_balance_at_coordinates.assert_called_once_with(
            balances={},
            denomination=sentinel.denomination,
        )
        mock_fee_postings.assert_not_called()

    @patch.object(mortgage.utils, "balance_at_coordinates")
    @patch.object(mortgage.fees, "fee_postings")
    def test_handle_early_repayment_fee_generates_repayment_fee_posting_instructions(
        self,
        mock_fee_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_balance_at_coordinates.side_effect = [Decimal("-13.25")]
        mock_fee_postings.return_value = [SentinelPosting("dummy_fee_posting")]

        # setup input repayment postings
        posting_for_instruction_1 = [
            Posting(
                credit=True,
                amount=Decimal("10"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_2 = [
            Posting(
                credit=True,
                amount=Decimal("13.25"),
                denomination=sentinel.denomination,
                account_id=sentinel.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        repayment_posting_instructions = [
            self.custom_instruction(postings=posting_for_instruction_1),
            self.custom_instruction(postings=posting_for_instruction_2),
        ]

        # run function
        result = mortgage._handle_early_repayment_fee(
            repayment_posting_instructions=repayment_posting_instructions,
            balances=BalanceDefaultDict(mapping={}),
            account_id=sentinel.account_id,
            early_repayment_fee_account=sentinel.early_repayment_fee_account,
            denomination=sentinel.denomination,
        )

        self.assertEqual(
            result, [CustomInstruction(postings=[SentinelPosting("dummy_fee_posting")])]
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        denomination=sentinel.denomination,
                        phase=Phase.COMMITTED,
                    ): Balance(
                        # 13.25 + 10 = 23.25
                        credit=Decimal("23.25"),
                        debit=Decimal("0"),
                        net=Decimal("-23.25"),
                    )
                }
            ),
            denomination=sentinel.denomination,
        )
        mock_fee_postings.assert_called_once_with(
            customer_account_id=sentinel.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            denomination=sentinel.denomination,
            # abs(10 - 23.25) = 13.25
            amount=Decimal("13.25"),
            internal_account=sentinel.early_repayment_fee_account,
        )


@patch.object(mortgage.utils, "balance_at_coordinates")
@patch.object(mortgage.utils, "create_postings")
class GetResidualCleanupPostingsHelper(MortgageTestBase):
    def test_get_residual_cleanup_postings_returns_no_postings_for_cleared_addresses(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")

        result = mortgage._get_residual_cleanup_postings(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            account_id=sentinel.account_id,
        )
        self.assertListEqual(result, [])

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address="CAPITALISED_INTEREST_TRACKER",
        )
        mock_create_postings.assert_not_called()

    def test_get_residual_cleanup_postings_returns_postings(
        self, mock_create_postings: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_return_postings = [SentinelPosting("dummy_posting")]
        mock_balance_at_coordinates.return_value = Decimal("10")
        mock_create_postings.return_value = mock_return_postings

        result = mortgage._get_residual_cleanup_postings(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            account_id=sentinel.account_id,
        )
        self.assertListEqual(result, mock_return_postings)

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            address="CAPITALISED_INTEREST_TRACKER",
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("10"),
            debit_account=sentinel.account_id,
            credit_account=sentinel.account_id,
            debit_address="INTERNAL_CONTRA",
            credit_address="CAPITALISED_INTEREST_TRACKER",
            denomination=sentinel.denomination,
        )


class PostingsHelpersTest(MortgageTestBase):
    @patch.object(mortgage.utils, "create_postings")
    def test_get_interest_adjustment_custom_instructions(self, mock_create_postings: MagicMock):
        # expected values
        postings = [SentinelPosting("create_postings")]

        # construct mocks
        mock_create_postings.return_value = postings
        # construct expected result
        expected_result = [
            CustomInstruction(
                postings=postings,  # type: ignore
                instruction_details={
                    "description": "Waive monthly interest due: 100",
                    "event": "EARLY_REPAYMENT_INTEREST_ADJUSTMENT",
                },
            )
        ]

        # run function
        result = mortgage._get_interest_adjustment_custom_instructions(
            amount=Decimal("100"),
            denomination="GBP",
            vault_account="account_id",
            interest_received_account="INTEREST_RECEIVED_ACCOUNT",
        )
        self.assertEqual(result, expected_result)
        mock_create_postings.assert_called_once_with(
            amount=Decimal("100"),
            debit_account="INTEREST_RECEIVED_ACCOUNT",
            credit_account="account_id",
            debit_address=DEFAULT_ADDRESS,
            credit_address=mortgage.lending_addresses.INTEREST_DUE,
            denomination="GBP",
        )

    @patch.object(mortgage.utils, "create_postings")
    def test_get_interest_adjustment_custom_instructions_returns_empty_list_with_negative_amount(
        self, mock_create_postings: MagicMock
    ):
        # construct mocks
        mock_create_postings.return_value = []

        # run function
        result = mortgage._get_interest_adjustment_custom_instructions(
            amount=Decimal("-100"),
            denomination="GBP",
            vault_account="account_id",
            interest_received_account="INTEREST_RECEIVED_ACCOUNT",
        )
        self.assertListEqual(result, [])
        mock_create_postings.assert_called_once_with(
            amount=Decimal("-100"),
            debit_account="INTEREST_RECEIVED_ACCOUNT",
            credit_account="account_id",
            debit_address=DEFAULT_ADDRESS,
            credit_address=mortgage.lending_addresses.INTEREST_DUE,
            denomination="GBP",
        )

    @patch.object(mortgage.utils, "create_postings")
    def test_get_interest_adjustment_custom_instructions_returns_empty_list_with_zero_amount(
        self, mock_create_postings: MagicMock
    ):
        # construct mocks
        mock_create_postings.return_value = []

        # run function
        result = mortgage._get_interest_adjustment_custom_instructions(
            amount=Decimal("0"),
            denomination="GBP",
            vault_account="account_id",
            interest_received_account="INTEREST_RECEIVED_ACCOUNT",
        )
        self.assertListEqual(result, [])
        mock_create_postings.assert_called_once_with(
            amount=Decimal("0"),
            debit_account="INTEREST_RECEIVED_ACCOUNT",
            credit_account="account_id",
            debit_address=DEFAULT_ADDRESS,
            credit_address=mortgage.lending_addresses.INTEREST_DUE,
            denomination="GBP",
        )

    def test_is_interest_adjustment_when_false_in_instruction_details(self):
        result = mortgage._is_interest_adjustment(
            posting=InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id="DEFAULT_INTERNAL_ACCOUNT",
                instruction_details={"interest_adjustment": "false"},
            ),
        )
        self.assertFalse(result)

    def test_is_interest_adjustment_when_true_in_instruction_details(self):
        result = mortgage._is_interest_adjustment(
            posting=InboundHardSettlement(
                amount=Decimal("1"),
                denomination="GBP",
                target_account_id="some_account",
                internal_account_id="DEFAULT_INTERNAL_ACCOUNT",
                instruction_details={"interest_adjustment": "true"},
            ),
        )
        self.assertTrue(result)


class TimeCalculationHelpersTest(MortgageTestBase):
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.term_helpers, "calculate_elapsed_term")
    def test_is_within_remaining_term_returns_true_when_elapsed_lt_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 1
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.PARAM_INTEREST_ONLY_TERM: 2}
        )
        self.assertTrue(
            mortgage._is_within_interest_only_term(
                sentinel.vault, sentinel.balances, sentinel.denomination
            )
        )
        mock_elapsed_term.assert_called_once_with(sentinel.balances, sentinel.denomination)

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.term_helpers, "calculate_elapsed_term")
    def test_is_within_remaining_term_returns_false_when_elapsed_gt_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 3
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.PARAM_INTEREST_ONLY_TERM: 2}
        )
        self.assertFalse(
            mortgage._is_within_interest_only_term(
                sentinel.vault, sentinel.balances, sentinel.denomination
            )
        )
        mock_elapsed_term.assert_called_once_with(sentinel.balances, sentinel.denomination)

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.term_helpers, "calculate_elapsed_term")
    def test_is_within_remaining_term_returns_false_when_elapsed_eq_term(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 2
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {mortgage.PARAM_INTEREST_ONLY_TERM: 2}
        )
        self.assertFalse(
            mortgage._is_within_interest_only_term(
                sentinel.vault, sentinel.balances, sentinel.denomination
            )
        )
        mock_elapsed_term.assert_called_once_with(sentinel.balances, sentinel.denomination)

    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.term_helpers, "calculate_elapsed_term")
    def test_is_within_remaining_term_without_optional_params(
        self, mock_elapsed_term: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_elapsed_term.return_value = 2
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                mortgage.PARAM_INTEREST_ONLY_TERM: 2,
                mortgage.PARAM_DENOMINATION: sentinel.denomination,
            }
        )
        bof_mapping = {
            mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                "effective"
            )
        }
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        self.assertFalse(mortgage._is_within_interest_only_term(mock_vault))
        mock_elapsed_term.assert_called_once_with(
            sentinel.balances_effective, sentinel.denomination
        )

    @patch.object(mortgage.utils, "get_parameter")
    def test_is_end_of_interest_only_term_within_term(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_only_term": Decimal("3")}
        )
        self.assertFalse(
            mortgage._is_end_of_interest_only_term(
                vault=sentinel.vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=2,
            )
        )

    @patch.object(mortgage.utils, "get_parameter")
    def test_is_end_of_interest_only_term_end_of_term(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_only_term": Decimal("3")}
        )
        self.assertTrue(
            mortgage._is_end_of_interest_only_term(
                vault=sentinel.vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=3,
            )
        )

    @patch.object(mortgage.utils, "get_parameter")
    def test_is_end_of_interest_only_term_past_end_of_term(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_only_term": Decimal("3")}
        )
        self.assertFalse(
            mortgage._is_end_of_interest_only_term(
                vault=sentinel.vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=4,
            )
        )

    @patch.object(mortgage.utils, "get_parameter")
    def test_is_end_of_interest_only_zero_interest_only_term(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"interest_only_term": Decimal("0")}
        )
        self.assertFalse(
            mortgage._is_end_of_interest_only_term(
                vault=sentinel.vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=0,
            )
        )


@patch.object(mortgage.utils, "get_schedule_time_from_parameters")
class CalculateNextDueAmountCalculationDatetimeTest(MortgageTestBase):
    def test_effective_datetime_less_than_repayment_day_1_day_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 2, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_over_1_month_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_1_microsecond_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 2, 4, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_midnight_same_day_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 2, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_same_datetime_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_1_microsecond_after_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 2, 5, 0, 1, 0, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_1_microsecond_before_mid_cycle_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 8, 5, 0, 0, 0, 999999, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 7, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 8, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_repayment_day_changed_from_10_to_5(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 6, 11, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 8, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_less_than_repayment_day_repayment_day_changed_from_1_to_5(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 6, 1, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 7, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_1_day_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 9, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_over_1_month_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 1, 20, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_1_microsecond_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 9, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 10
        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_midnight_same_day_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 10, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 10
        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_same_datetime_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 4, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_1_microsecond_after_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 10, 0, 1, 0, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 3, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 4, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_repayment_day_changed_from_15_to_10(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 6, 16, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 15, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 8, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_greater_than_repayment_day_repayment_day_changed_from_1_to_5(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 6, 2, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 10

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 19, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 7, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_1_day_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 4, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_over_1_month_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 1, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 2, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_1_microsecond_before_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 4, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_midnight_same_day_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_same_datetime_as_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = None
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 4, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_1_microsecond_after_first_schedule(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 3, 5, 0, 1, 0, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 3, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 4, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_repayment_day_changed_from_10_to_5(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        due_amount_calculation_day = 5
        effective_datetime = datetime(2020, 6, 11, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 10, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 8, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)

    def test_effective_datetime_same_as_repayment_day_repayment_day_changed_from_1_to_5(
        self,
        mock_get_schedule_time_from_parameters: MagicMock,
    ):
        # input values
        effective_datetime = datetime(2020, 6, 1, 12, 1, 1, tzinfo=ZoneInfo("UTC"))
        last_execution_datetime = datetime(2020, 6, 1, 0, 1, 0, tzinfo=ZoneInfo("UTC"))
        due_amount_calculation_day = 5

        # construct mocks
        mock_vault = self.create_mock(
            creation_date=datetime(2020, 1, 5, 0, 1, tzinfo=ZoneInfo("UTC")),
        )
        mock_get_schedule_time_from_parameters.return_value = 0, 1, 0

        # construct expected result
        expected_result = datetime(2020, 7, 5, 0, 1, 0, tzinfo=ZoneInfo("UTC"))

        # run function
        result = mortgage._calculate_next_due_amount_calculation_datetime(
            mock_vault, effective_datetime, last_execution_datetime, due_amount_calculation_day
        )
        self.assertEqual(result, expected_result)


class LateRepaymentFeeTest(MortgageTestBase):
    common_params = {
        mortgage.PARAM_DENOMINATION: sentinel.denomination,
        mortgage.PARAM_LATE_REPAYMENT_FEE: Decimal("25"),
        mortgage.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: sentinel.fee_income_account,
    }

    @patch.object(mortgage.utils, "standard_instruction_details")
    @patch.object(mortgage.fees, "fee_postings")
    @patch.object(mortgage.utils, "get_parameter")
    def test_late_repayment_fee_returns_custom_instruction_when_fee_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # expected values
        fee_postings = [SentinelPosting("fee_posting")]

        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        mock_fee_postings.return_value = fee_postings

        # construct expected result
        expected_result = [
            CustomInstruction(
                postings=fee_postings, instruction_details={"sentinel": "dict"}  # type: ignore
            )
        ]
        # run function
        result = mortgage._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(result, expected_result)

        mock_fee_postings.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            customer_account_address=mortgage.lending_addresses.PENALTIES,
            denomination=f"{sentinel.denomination}",
            amount=Decimal("25"),
            internal_account=sentinel.fee_income_account,
        )

    @patch.object(mortgage.utils, "standard_instruction_details")
    @patch.object(mortgage.fees, "fee_postings")
    @patch.object(mortgage.utils, "get_parameter")
    def test_late_repayment_fee_returns_empty_list_when_no_fee_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_params)
        mock_standard_instruction_details.return_value = {"sentinel": "dict"}
        mock_fee_postings.return_value = []

        # run function
        result = mortgage._charge_late_repayment_fee(
            vault=mock_vault,
            event_type=sentinel.event_type,
        )

        self.assertListEqual(result, [])

        mock_fee_postings.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            customer_account_address=mortgage.lending_addresses.PENALTIES,
            denomination=f"{sentinel.denomination}",
            amount=Decimal("25"),
            internal_account=sentinel.fee_income_account,
        )
        mock_standard_instruction_details.assert_not_called()


class HandleDelinquencyTest(MortgageTestBase):
    @patch.object(mortgage, "_mark_account_delinquent")
    @patch.object(mortgage, "_update_delinquency_schedule")
    @patch.object(mortgage.utils, "get_parameter")
    def test_handle_delinquency_with_zero_grace_period_overdue_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 0, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_delinquency_schedule]
        mock_mark_account_delinquent.return_value = [sentinel.delinquent_notification_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.overdue.CHECK_OVERDUE_EVENT
        )

        result = mortgage._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=False
        )

        expected = (
            [sentinel.delinquent_notification_directive],
            [sentinel.update_delinquency_schedule],
        )
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            skip_schedule=True,
        )
        mock_mark_account_delinquent.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME, balances=None
        )

    @patch.object(mortgage, "_mark_account_delinquent")
    @patch.object(mortgage, "_update_delinquency_schedule")
    @patch.object(mortgage.utils, "get_parameter")
    def test_handle_delinquency_with_non_zero_grace_period_overdue_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 5, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_event_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.overdue.CHECK_OVERDUE_EVENT
        )

        result = mortgage._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=False
        )
        expected = [], [sentinel.update_event_directive]  # type: ignore
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(days=5),
            skip_schedule=False,
        )
        mock_mark_account_delinquent.assert_not_called()

    @patch.object(mortgage, "_mark_account_delinquent")
    @patch.object(mortgage, "_update_delinquency_schedule")
    @patch.object(mortgage.utils, "get_parameter")
    def test_handle_delinquency_on_delinquency_event(
        self,
        mock_get_parameter: MagicMock,
        mock_update_delinquency_schedule: MagicMock,
        mock_mark_account_delinquent: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"grace_period": 5, "denomination": sentinel.denomination}
        )
        mock_update_delinquency_schedule.return_value = [sentinel.update_event_directive]
        mock_mark_account_delinquent.return_value = [sentinel.delinquent_notification_directive]

        hook_args = ScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME, event_type=mortgage.CHECK_DELINQUENCY
        )

        result = mortgage._handle_delinquency(
            vault=mock_vault, hook_arguments=hook_args, is_delinquency_schedule_event=True
        )

        expected = (
            [sentinel.delinquent_notification_directive],
            [sentinel.update_event_directive],
        )
        self.assertEqual(result, expected)

        mock_update_delinquency_schedule.assert_called_once_with(
            vault=mock_vault,
            next_schedule_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            skip_schedule=True,
        )
        mock_mark_account_delinquent.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME, balances=None
        )

    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    def test_mark_account_delinquent_blocking_flag_applied(
        self,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_is_flag_in_list_applied.side_effect = [True, False]

        result = mortgage._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        self.assertListEqual(result, [])
        mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="delinquency_blocking_flags",
            effective_datetime=sentinel.datetime,
        )

    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    def test_mark_account_delinquent_already_delinquent(
        self,
        mock_is_flag_in_list_applied: MagicMock,
    ):
        mock_is_flag_in_list_applied.side_effect = [False, True]

        result = mortgage._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )
        self.assertListEqual(result, [])
        mock_is_flag_in_list_applied.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    parameter_name="delinquency_blocking_flags",
                    effective_datetime=sentinel.datetime,
                ),
                call(
                    vault=sentinel.vault,
                    parameter_name="delinquency_flag",
                    effective_datetime=sentinel.datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_flag_in_list_applied.call_count, 2)

    @patch.object(mortgage, "_get_late_payment_balance")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    def test_mark_account_delinquent_with_positive_late_balance_returns_notification_directive(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_flag_in_list_applied.side_effect = [False, False]
        mock_get_late_payment_balance.return_value = Decimal("10")

        expected = [
            AccountNotificationDirective(
                notification_type="MORTGAGE_MARK_DELINQUENT",
                notification_details={"account_id": ACCOUNT_ID},
            )
        ]
        result = mortgage._mark_account_delinquent(
            vault=mock_vault, effective_datetime=sentinel.datetime, balances=sentinel.balances
        )
        self.assertListEqual(result, expected)
        mock_is_flag_in_list_applied.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    parameter_name="delinquency_blocking_flags",
                    effective_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    parameter_name="delinquency_flag",
                    effective_datetime=sentinel.datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_flag_in_list_applied.call_count, 2)

    @patch.object(mortgage, "_get_late_payment_balance")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    def test_mark_account_delinquent_with_zero_late_balance_returns_empty_list(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_flag_in_list_applied.side_effect = [False, False]
        mock_get_late_payment_balance.return_value = Decimal("0")

        result = mortgage._mark_account_delinquent(
            vault=sentinel.vault, effective_datetime=sentinel.datetime, balances=sentinel.balances
        )
        self.assertListEqual(result, [])
        mock_is_flag_in_list_applied.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    parameter_name="delinquency_blocking_flags",
                    effective_datetime=sentinel.datetime,
                ),
                call(
                    vault=sentinel.vault,
                    parameter_name="delinquency_flag",
                    effective_datetime=sentinel.datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_flag_in_list_applied.call_count, 2)

    @patch.object(mortgage, "_get_late_payment_balance")
    @patch.object(mortgage.utils, "get_parameter")
    @patch.object(mortgage.utils, "is_flag_in_list_applied")
    def test_mark_account_delinquent_without_balances_gets_observation(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_late_payment_balance: MagicMock,
    ):
        effective_balances_observation = SentinelBalancesObservation("effective")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                mortgage.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: effective_balances_observation
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_is_flag_in_list_applied.side_effect = [False, False]
        mock_get_late_payment_balance.return_value = Decimal("0")

        result = mortgage._mark_account_delinquent(
            vault=mock_vault, effective_datetime=sentinel.datetime, balances=None
        )
        self.assertListEqual(result, [])
        mock_is_flag_in_list_applied.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    parameter_name="delinquency_blocking_flags",
                    effective_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    parameter_name="delinquency_flag",
                    effective_datetime=sentinel.datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_flag_in_list_applied.call_count, 2)
        mock_get_late_payment_balance.assert_called_once_with(
            balances=sentinel.balances_effective, denomination=sentinel.denomination
        )

    @patch.object(mortgage.utils, "get_schedule_expression_from_parameters")
    def test_update_delinquency_schedule_skip(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):

        schedule_expression = SentinelScheduleExpression("delinquency")

        mock_get_schedule_expression_from_parameters.return_value = schedule_expression

        expected = [
            UpdateAccountEventTypeDirective(
                event_type="CHECK_DELINQUENCY", expression=schedule_expression, skip=True
            )
        ]

        result = mortgage._update_delinquency_schedule(
            vault=sentinel.vault, next_schedule_datetime=DEFAULT_DATETIME, skip_schedule=True
        )

        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix="check_delinquency",
            day=DEFAULT_DATETIME.day,
            month=DEFAULT_DATETIME.month,
            year=DEFAULT_DATETIME.year,
        )

    @patch.object(mortgage.utils, "get_schedule_expression_from_parameters")
    def test_update_delinquency_schedule_skip_is_false(
        self, mock_get_schedule_expression_from_parameters: MagicMock
    ):

        schedule_expression = SentinelScheduleExpression("delinquency")

        mock_get_schedule_expression_from_parameters.return_value = schedule_expression

        expected = [
            UpdateAccountEventTypeDirective(
                event_type="CHECK_DELINQUENCY", expression=schedule_expression, skip=False
            )
        ]

        result = mortgage._update_delinquency_schedule(
            vault=sentinel.vault, next_schedule_datetime=DEFAULT_DATETIME, skip_schedule=False
        )

        self.assertListEqual(result, expected)
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel.vault,
            parameter_prefix="check_delinquency",
            day=DEFAULT_DATETIME.day,
            month=DEFAULT_DATETIME.month,
            year=DEFAULT_DATETIME.year,
        )


@patch.object(mortgage.repayment_holiday, "is_due_amount_calculation_blocked")
class DoHandleInterestCapitalisationTest(MortgageTestBase):
    def test_should_handle_interest_capitalisation_boolean_permutation_1(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = True
        result = mortgage._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_penalty_interest_capitalisation: True, is_due_amount_calculation_blocked: True"
        )
        self.assertEqual(True, result, description)

    def test_should_handle_interest_capitalisation_boolean_permutation_2(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = False
        result = mortgage._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=True,
        )
        description = (
            "is_penalty_interest_capitalisation: True, is_due_amount_calculation_blocked: False"
        )
        self.assertEqual(True, result, description)

    def test_should_handle_interest_capitalisation_boolean_permutation_3(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = True
        result = mortgage._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_penalty_interest_capitalisation: False, is_due_amount_calculation_blocked: True"
        )
        self.assertEqual(False, result, description)

    def test_should_handle_interest_capitalisation_boolean_permutation_4(
        self,
        mock_is_due_amount_calculation_blocked: MagicMock,
    ):
        mock_is_due_amount_calculation_blocked.return_value = False
        result = mortgage._should_handle_interest_capitalisation(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            is_penalty_interest_capitalisation=False,
        )
        description = (
            "is_penalty_interest_capitalisation: False, is_due_amount_calculation_blocked: False"
        )
        self.assertEqual(True, result, description)
