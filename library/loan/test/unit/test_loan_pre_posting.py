# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# library
from library.loan.contracts.template import loan
from library.loan.test.unit.test_loan_common import DEFAULT_DATETIME, LoanTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import BalanceDefaultDict, BalancesObservation, PrePostingHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PrePostingHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)


@patch.object(loan.utils, "get_parameter")
class LoanPrePostingTest(LoanTestBase):
    common_hook_args_sentinel_posting = PrePostingHookArguments(
        effective_datetime=DEFAULT_DATETIME,
        posting_instructions=[sentinel.posting_instructions],
        client_transactions={},
    )

    @patch.object(loan.utils, "is_force_override")
    def test_force_override_returns_none(
        self, mock_is_force_override: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_is_force_override.return_value = True

        result = loan.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        self.assertIsNone(result)

        # hook should return before we get any parameter values
        mock_get_parameter.assert_not_called()

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    def test_multiple_postings_return_rejection(
        self,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        posting_rejection = SentinelRejection("denomination_rejection")
        mock_validate_single_hard_settlement.return_value = posting_rejection

        result = loan.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        expected = PrePostingHookResult(rejection=posting_rejection)
        self.assertEqual(result, expected)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    def test_wrong_denomination_returns_rejection(
        self,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )

        denomination_rejection = SentinelRejection("denomination_rejection")
        mock_validate_denomination.return_value = denomination_rejection

        result = loan.pre_posting_hook(
            vault=sentinel.vault, hook_arguments=self.common_hook_args_sentinel_posting
        )

        expected = PrePostingHookResult(rejection=denomination_rejection)

        self.assertEqual(result, expected)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    def test_debits_return_rejection(
        self,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
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

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Debiting is not allowed from this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.utils, "str_to_bool")
    def test_debits_with_fee_metadata_return_none(
        self,
        mock_str_to_bool: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
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

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.outbound_hard_settlement(amount=Decimal("1"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.utils, "str_to_bool")
    def test_debits_with_interest_adjustment_metadata_return_none(
        self,
        mock_str_to_bool: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
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
                    amount=Decimal("1"), instruction_details={"interest_adjustment": "true"}
                )
            ],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.overpayment, "get_max_overpayment_amount")
    @patch.object(loan.overpayment, "validate_overpayment")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_credits_triggering_overpayment_rejection_return_rejection(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_validate_overpayment: MagicMock,
        get_max_overpayment_amount: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "amortisation_method": "declining_principal",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        get_max_overpayment_amount.return_value = Decimal("10")

        overpayment_rejection = SentinelRejection("overpayment")
        mock_validate_overpayment.return_value = overpayment_rejection

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("3"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(result, PrePostingHookResult(rejection=overpayment_rejection))
        mock_validate_overpayment.assert_called_once_with(
            vault=sentinel.vault,
            repayment_amount=Decimal("-3"),
            denomination=self.default_denomination,
        )

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.overpayment, "get_max_overpayment_amount")
    @patch.object(loan.early_repayment, "get_total_early_repayment_amount")
    @patch.object(loan.overpayment, "validate_overpayment")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_credits_triggering_early_repayment_rejection_return_rejection(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_validate_overpayment: MagicMock,
        mock_get_total_early_repayment_amount: MagicMock,
        mock_get_max_overpayment_amount: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "amortisation_method": "declining_principal",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_get_max_overpayment_amount.return_value = Decimal("3")
        mock_get_total_early_repayment_amount.return_value = sentinel.total_early_repayment_amount

        expected = PrePostingHookResult(
            rejection=Rejection(
                message=(
                    "Cannot repay remaining debt without paying early repayment fees, "
                    f"amount required is {sentinel.total_early_repayment_amount}"
                ),
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("3"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertEqual(expected, result)
        mock_validate_overpayment.assert_not_called()

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_credits_triggering_overpayment_rejection_for_flat_interest(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "amortisation_method": "flat_interest",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_flat_interest_loan.return_value = True
        mock_is_rule_of_78_loan.return_value = False

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Overpayments are not allowed for flat interest loans.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_credits_triggering_overpayment_rejection_for_rule_of_78(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "amortisation_method": "rule_of_78",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Overpayments are not allowed for rule of 78 loans.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    @patch.object(loan.minimum_repayment, "is_minimum_repayment_loan")
    def test_credits_triggering_overpayment_rejection_for_minimum_repayment(
        self,
        mock_is_minimum_repayment_loan: MagicMock,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": self.default_denomination,
                "amortisation_method": "minimum_repayment_with_balloon_payment",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_is_minimum_repayment_loan.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Overpayments are not allowed for minimum repayment with balloon "
                "payment loans.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.overpayment, "validate_overpayment")
    @patch.object(loan.overpayment, "get_max_overpayment_amount")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_credits_that_dont_trigger_any_rejections_are_accepted(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_get_max_overpayment_amount: MagicMock,
        mock_validate_overpayment: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
                "amortisation_method": "declining_principal",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = True
        mock_is_posting_an_early_repayment.return_value = False
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_validate_overpayment.return_value = None
        mock_get_max_overpayment_amount.return_value = Decimal("10")

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("3"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    @patch.object(loan.overpayment, "validate_overpayment")
    @patch.object(loan.overpayment, "get_max_overpayment_amount")
    @patch.object(loan.early_repayment, "is_posting_an_early_repayment")
    @patch.object(loan.overpayment, "is_posting_an_overpayment")
    @patch.object(loan.flat_interest, "is_flat_interest_loan")
    @patch.object(loan.rule_of_78, "is_rule_of_78_loan")
    def test_early_repayment_accepted(
        self,
        mock_is_rule_of_78_loan: MagicMock,
        mock_is_flat_interest_loan: MagicMock,
        mock_is_posting_an_overpayment: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
        mock_get_max_overpayment_amount: MagicMock,
        mock_validate_overpayment: MagicMock,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": "GBP",
                "amortisation_method": "declining_principal",
            }
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = False
        mock_is_posting_an_overpayment.return_value = False
        mock_is_posting_an_early_repayment.return_value = True
        mock_is_flat_interest_loan.return_value = False
        mock_is_rule_of_78_loan.return_value = False
        mock_validate_overpayment.return_value = None
        mock_get_max_overpayment_amount.return_value = Decimal("10")

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("3"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=sentinel.vault, hook_arguments=hook_args)

        self.assertIsNone(result)

    @patch.object(loan.utils, "is_force_override")
    @patch.object(loan.utils, "validate_single_hard_settlement_or_transfer")
    @patch.object(loan.utils, "validate_denomination")
    @patch.object(loan.repayment_holiday, "is_repayment_blocked")
    def test_credit_when_repayments_blocked_return_rejection(
        self,
        mock_is_repayment_blocked: MagicMock,
        mock_validate_denomination: MagicMock,
        mock_validate_single_hard_settlement: MagicMock,
        mock_is_force_override: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # BalanceDefaultDict can be empty since _get_total_outstanding_debt is mocked
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                loan.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(
                    balances=BalanceDefaultDict()
                )
            }
        )

        mock_is_force_override.return_value = False
        mock_validate_single_hard_settlement.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": "GBP"}
        )
        mock_validate_denomination.return_value = None
        mock_is_repayment_blocked.return_value = True

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("2"))],
            client_transactions={},
        )

        result = loan.pre_posting_hook(vault=mock_vault, hook_arguments=hook_args)
        expected = PrePostingHookResult(
            rejection=Rejection(
                message="Repayments are blocked for this account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(expected, result)

        mock_is_repayment_blocked.assert_called_once_with(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
