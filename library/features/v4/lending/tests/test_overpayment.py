# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.lending.overpayment as overpayment
from library.features.v4.common.test.mocks import (
    mock_utils_get_parameter,
    mock_utils_get_parameter_for_multiple_vaults,
)

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Phase,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ACCOUNT_ID, FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    Rejection,
    RejectionReason,
    ScheduledEventHookArguments,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelBalancesObservation,
    SentinelPosting,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)

DEFAULT_DATE = datetime(2020, 1, 2, 3, tzinfo=ZoneInfo("UTC"))


class OverpaymentTest(FeatureTest):
    maxDiff = None


@patch.object(overpayment, "get_total_outstanding_debt")
@patch.object(overpayment, "get_max_overpayment_fee")
@patch.object(overpayment.utils, "get_parameter")
class ValidateOverpaymentTest(OverpaymentTest):
    def test_validate_rejects_if_repayment_over_outstanding_plus_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={overpayment.PARAM_OVERPAYMENT_FEE_RATE: Decimal("0.1")}
        )
        mock_get_max_overpayment_fee.return_value = Decimal("1")
        mock_get_total_outstanding_debt.return_value = Decimal("1")
        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.validate_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-3"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(
            result,
            Rejection(
                message="Cannot pay more than is owed.", reason_code=RejectionReason.AGAINST_TNC
            ),
        )
        mock_get_total_outstanding_debt.assert_called_once_with(
            balances=live_balance_obs.balances, denomination=sentinel.denomination
        )
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=Decimal("0.1"),
            balances=live_balance_obs.balances,
            denomination=sentinel.denomination,
        )

    def test_validate_accepts_if_repayment_equal_outstanding_plus_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.1"}
        )
        mock_get_max_overpayment_fee.return_value = Decimal("1")
        mock_get_total_outstanding_debt.return_value = Decimal("1")
        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.validate_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-2"),
            denomination=sentinel.denomination,
        )

        self.assertIsNone(result)

    def test_validate_accepts_if_repayment_less_than_outstanding_plus_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.1"}
        )
        mock_get_max_overpayment_fee.return_value = Decimal("1")
        mock_get_total_outstanding_debt.return_value = Decimal("1")
        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.validate_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-1"),
            denomination=sentinel.denomination,
        )

        self.assertIsNone(result)

    def test_validate_accepts_if_repayment_equal_to_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        self.assertIsNone(
            overpayment.validate_overpayment(
                vault=sentinel.vault,
                repayment_amount=Decimal("0"),
                denomination=sentinel.denomination,
            )
        )

    def test_validate_accepts_if_repayment_greater_than_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_total_outstanding_debt: MagicMock,
    ):
        self.assertIsNone(
            overpayment.validate_overpayment(
                vault=sentinel.vault,
                repayment_amount=Decimal("1"),
                denomination=sentinel.denomination,
            )
        )


@patch.object(overpayment, "get_overpayment_fee_rate_parameter")
@patch.object(overpayment, "get_max_overpayment_fee")
@patch.object(overpayment.utils, "sum_balances")
@patch.object(overpayment.utils, "round_decimal")
class ValidateOverpaymentAcrossSuperviseesTest(OverpaymentTest):
    supervisee_1_balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("10"), debit=Decimal("0"), net=Decimal("-10"))
        }
    )

    supervisee_2_balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("0"), debit=Decimal("50"), net=Decimal("50"))
        }
    )

    combined_supervisee_balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                denomination="GBP",
                phase=Phase.COMMITTED,
            ): Balance(credit=Decimal("10"), debit=Decimal("50"), net=Decimal("40"))
        }
    )

    def test_validate_repayment_is_rejected_if_over_outstanding_amount_plus_fee(
        self,
        mock_round_decimal: MagicMock,
        mock_sum_balances: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_rate_parameter: MagicMock,
    ):
        mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        mock_get_max_overpayment_fee.return_value = Decimal("10")
        # total outstanding amount
        mock_sum_balances.return_value = Decimal("150")
        mock_round_decimal.return_value = Decimal("160.00")

        result = overpayment.validate_overpayment_across_supervisees(
            main_vault=sentinel.main_vault,
            repayment_amount=Decimal("200"),
            denomination=sentinel.denomination,
            all_supervisee_balances=[self.supervisee_1_balances, self.supervisee_2_balances],
        )

        expected_result = Rejection(
            message="The repayment amount 200 sentinel.denomination "
            "exceeds the total maximum repayment amount of "
            "160.00 sentinel.denomination.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(result, expected_result)

        mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=sentinel.main_vault)
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
        )
        mock_sum_balances.assert_called_once_with(
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
            addresses=overpayment.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
            decimal_places=2,
        )
        mock_round_decimal.assert_called_once_with(amount=Decimal("160"), decimal_places=2)

    def test_returns_none_if_repayment_equals_outstanding_amount_plus_fee(
        self,
        mock_round_decimal: MagicMock,
        mock_sum_balances: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_rate_parameter: MagicMock,
    ):
        mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        mock_get_max_overpayment_fee.return_value = Decimal("50")
        # total outstanding amount
        mock_sum_balances.return_value = Decimal("150")
        mock_round_decimal.return_value = Decimal("200")

        result = overpayment.validate_overpayment_across_supervisees(
            main_vault=sentinel.main_vault,
            repayment_amount=Decimal("200"),
            denomination=sentinel.denomination,
            all_supervisee_balances=[self.supervisee_1_balances, self.supervisee_2_balances],
            rounding_precision=0,
        )

        self.assertIsNone(result)

        mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=sentinel.main_vault)
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
        )
        mock_sum_balances.assert_called_once_with(
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
            addresses=overpayment.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
            decimal_places=0,
        )
        mock_round_decimal.assert_called_once_with(amount=Decimal("200"), decimal_places=0)

    def test_returns_none_if_repayment_is_less_than_outstanding_amount_plus_fee(
        self,
        mock_round_decimal: MagicMock,
        mock_sum_balances: MagicMock,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_rate_parameter: MagicMock,
    ):
        mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        mock_get_max_overpayment_fee.return_value = Decimal("50")
        # total outstanding amount
        mock_sum_balances.return_value = Decimal("150")
        mock_round_decimal.return_value = Decimal("200.00")

        result = overpayment.validate_overpayment_across_supervisees(
            main_vault=sentinel.main_vault,
            repayment_amount=Decimal("190"),
            denomination=sentinel.denomination,
            all_supervisee_balances=[self.supervisee_1_balances, self.supervisee_2_balances],
            rounding_precision=sentinel.rounding_precision,
        )

        self.assertIsNone(result)

        mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=sentinel.main_vault)
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
        )
        mock_sum_balances.assert_called_once_with(
            balances=self.combined_supervisee_balances,
            denomination=sentinel.denomination,
            addresses=overpayment.lending_addresses.ALL_OUTSTANDING_SUPERVISOR,
            decimal_places=sentinel.rounding_precision,
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("200"), decimal_places=sentinel.rounding_precision
        )


@patch.object(overpayment, "get_total_due_amount")
class IsPostingAnOverpaymentTest(OverpaymentTest):
    def test_is_posting_an_overpayment_returns_true_exceeds_due_amount(
        self,
        mock_get_total_due_amount: MagicMock,
    ):
        mock_get_total_due_amount.return_value = Decimal("1")

        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.is_posting_an_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-3"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, True)

    def test_is_posting_an_overpayment_returns_false_if_debit(
        self,
        mock_get_total_due_amount: MagicMock,
    ):
        mock_get_total_due_amount.return_value = Decimal("1")

        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.is_posting_an_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("3"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, False)

    def test_is_posting_an_overpayment_returns_false_less_than_due(
        self,
        mock_get_total_due_amount: MagicMock,
    ):
        mock_get_total_due_amount.return_value = Decimal("5")

        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.is_posting_an_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-3"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, False)

    def test_is_posting_an_overpayment_returns_false_equal_to_due(
        self,
        mock_get_total_due_amount: MagicMock,
    ):
        mock_get_total_due_amount.return_value = Decimal("1")

        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )

        result = overpayment.is_posting_an_overpayment(
            vault=mock_vault,
            repayment_amount=Decimal("-1"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, False)


class GetOverpaymentFeeTest(OverpaymentTest):
    def test_overpayment_fee_amount(self):
        result = overpayment.get_overpayment_fee(
            principal_repaid=Decimal("5"), overpayment_fee_rate=Decimal("0.01"), precision=2
        )
        self.assertEqual(result, Decimal("0.05"))

    def test_overpayment_fee_amount_100_percent_rate(self):
        result = overpayment.get_overpayment_fee(
            principal_repaid=Decimal("5"), overpayment_fee_rate=Decimal("1"), precision=2
        )
        self.assertEqual(result, Decimal("0"))

    def test_overpayment_fee_amount_over_100_percent_rate(self):
        result = overpayment.get_overpayment_fee(
            principal_repaid=Decimal("5"), overpayment_fee_rate=Decimal("1.5"), precision=2
        )
        self.assertEqual(result, Decimal("0"))


class GetMaxOverpaymentFeeTest(OverpaymentTest):
    def setUp(self) -> None:
        self.mock_get_overpayment_fee = patch.object(overpayment, "get_overpayment_fee").start()
        self.mock_balance_at_coordinates = patch.object(
            overpayment.utils, "balance_at_coordinates"
        ).start()
        self.mock_round_decimal = patch.object(overpayment.utils, "round_decimal").start()
        self.mock_balance_at_coordinates.return_value = Decimal("100")
        self.mock_get_overpayment_fee.return_value = sentinel.max_overpayment_fee
        self.mock_round_decimal.return_value = sentinel.maximum_overpayment
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_max_overpayment_fee(self):
        result = overpayment.get_max_overpayment_fee(
            fee_rate=Decimal("0.5"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, sentinel.max_overpayment_fee)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )
        self.mock_round_decimal.assert_called_once_with(amount=Decimal("200"), decimal_places=2)
        self.mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=sentinel.maximum_overpayment,
            overpayment_fee_rate=Decimal("0.5"),
            precision=2,
        )

    def test_max_overpayment_fee_with_principal_address(self):
        result = overpayment.get_max_overpayment_fee(
            fee_rate=Decimal("0.5"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            principal_address=sentinel.principal_address,
        )
        self.assertEqual(result, sentinel.max_overpayment_fee)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=sentinel.principal_address,
            denomination=sentinel.denomination,
        )
        self.mock_round_decimal.assert_called_once_with(amount=Decimal("200"), decimal_places=2)
        self.mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=sentinel.maximum_overpayment,
            overpayment_fee_rate=Decimal("0.5"),
            precision=2,
        )

    def test_max_overpayment_fee_amount_100_percent_rate(self):
        result = overpayment.get_max_overpayment_fee(
            fee_rate=Decimal("1"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, Decimal("0"))
        self.mock_get_overpayment_fee.assert_not_called()
        self.mock_balance_at_coordinates.assert_not_called()
        self.mock_round_decimal.assert_not_called()

    def test_max_overpayment_fee_amount_over_100_percent_rate(self):
        result = overpayment.get_max_overpayment_fee(
            fee_rate=Decimal("1.5"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertEqual(result, Decimal("0"))
        self.mock_get_overpayment_fee.assert_not_called()
        self.mock_balance_at_coordinates.assert_not_called()
        self.mock_round_decimal.assert_not_called()


class GetTotalOutstandingDebtTest(OverpaymentTest):
    @patch.object(overpayment.utils, "sum_balances")
    def test_get_total_outstanding_debt(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_outstanding_debt
        result = overpayment.get_total_outstanding_debt(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, sentinel.total_outstanding_debt)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=overpayment.lending_addresses.ALL_OUTSTANDING,
            denomination=sentinel.denomination,
            decimal_places=2,
        )


class GetTotalDueAmountTest(OverpaymentTest):
    @patch.object(overpayment.utils, "sum_balances")
    def test_get_total_due_amount(self, mock_sum_balances: MagicMock):
        mock_sum_balances.return_value = sentinel.total_due_amount
        result = overpayment.get_total_due_amount(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, sentinel.total_due_amount)
        mock_sum_balances.assert_called_once_with(
            balances=sentinel.balances,
            addresses=overpayment.lending_addresses.REPAYMENT_HIERARCHY,
            denomination=sentinel.denomination,
            decimal_places=2,
        )


class GetOutstandingPrincipalTest(OverpaymentTest):
    @patch.object(overpayment.utils, "balance_at_coordinates")
    def test_get_outstanding_principal(self, mock_balance_at_coordinates: MagicMock):
        mock_balance_at_coordinates.return_value = sentinel.outstanding_principal
        result = overpayment.get_outstanding_principal(
            balances=sentinel.balances, denomination=sentinel.denomination
        )
        self.assertEqual(result, sentinel.outstanding_principal)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment.lending_addresses.PRINCIPAL,
            denomination=sentinel.denomination,
        )


@patch.object(overpayment.interest_application, "repay_accrued_interest")
@patch.object(overpayment.utils, "create_postings")
@patch.object(overpayment, "get_outstanding_principal")
class HandleOverpaymentTest(OverpaymentTest):
    def test_zero_overpayment(
        self,
        mock_outstanding_principal: MagicMock,
        mock_create_postings: MagicMock,
        mock_repay_accrued_interest: MagicMock,
    ):
        result = overpayment.handle_overpayment(
            vault=sentinel.vault,
            overpayment_amount=Decimal("0"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [])

    def test_overpayment_no_outstanding_principal(
        self,
        mock_outstanding_principal: MagicMock,
        mock_create_postings: MagicMock,
        mock_repay_accrued_interest: MagicMock,
    ):
        mock_outstanding_principal.return_value = Decimal("0")
        mock_repay_accrued_interest.return_value = [sentinel.interest_postings]

        result = overpayment.handle_overpayment(
            vault=sentinel.vault,
            overpayment_amount=Decimal("1"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        mock_repay_accrued_interest.assert_called_once_with(
            vault=sentinel.vault,
            repayment_amount=Decimal("1"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, [sentinel.interest_postings])

    def test_overpayment_to_principal(
        self,
        mock_outstanding_principal: MagicMock,
        mock_create_postings: MagicMock,
        mock_repay_accrued_interest: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_outstanding_principal.return_value = Decimal("1")
        mock_create_postings.side_effect = [
            [sentinel.principal_postings],
            [sentinel.overpayment_tracker_postings],
            [sentinel.overpayment_since_prev_due_amount_tracker_postings],
        ]
        mock_repay_accrued_interest.return_value = []

        result = overpayment.handle_overpayment(
            vault=mock_vault,
            overpayment_amount=Decimal("1"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual(
            result,
            [
                sentinel.principal_postings,
                sentinel.overpayment_tracker_postings,
                sentinel.overpayment_since_prev_due_amount_tracker_postings,
            ],
        )

        mock_outstanding_principal.assert_called_once_with(sentinel.balances, sentinel.denomination)

        principal_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account=mock_vault.account_id,
            credit_address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        overpayment_tracker_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=overpayment.OVERPAYMENT,
            credit_account=mock_vault.account_id,
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )
        overpayment_since_prev_due_amount_tracker_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=(overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER),
            credit_account=mock_vault.account_id,
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_has_calls(
            calls=[
                principal_posting_call,
                overpayment_tracker_posting_call,
                overpayment_since_prev_due_amount_tracker_posting_call,
            ]
        )

        mock_repay_accrued_interest.assert_called_once_with(
            vault=mock_vault,
            repayment_amount=Decimal("0"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

    def test_overpayment_to_principal_and_interest(
        self,
        mock_outstanding_principal: MagicMock,
        mock_create_postings: MagicMock,
        mock_repay_accrued_interest: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_outstanding_principal.return_value = Decimal("1")
        mock_create_postings.side_effect = [
            [sentinel.principal_postings],
            [sentinel.overpayment_tracker_postings],
            [sentinel.overpayment_since_prev_due_amount_tracker_postings],
        ]
        mock_repay_accrued_interest.return_value = []

        result = overpayment.handle_overpayment(
            vault=mock_vault,
            overpayment_amount=Decimal("2"),
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )

        self.assertListEqual(
            result,
            [
                sentinel.principal_postings,
                sentinel.overpayment_tracker_postings,
                sentinel.overpayment_since_prev_due_amount_tracker_postings,
            ],
        )

        mock_outstanding_principal.assert_called_once_with(sentinel.balances, sentinel.denomination)

        principal_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account=mock_vault.account_id,
            credit_address="PRINCIPAL",
            denomination=sentinel.denomination,
        )
        overpayment_tracker_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=overpayment.OVERPAYMENT,
            credit_account=mock_vault.account_id,
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )
        overpayment_since_prev_due_amount_tracker_posting_call = call(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=(overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER),
            credit_account=mock_vault.account_id,
            credit_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
        )
        mock_create_postings.assert_has_calls(
            calls=[
                principal_posting_call,
                overpayment_tracker_posting_call,
                overpayment_since_prev_due_amount_tracker_posting_call,
            ]
        )

        mock_repay_accrued_interest.assert_called_once_with(
            vault=mock_vault,
            repayment_amount=Decimal("1"),
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )


@patch.object(overpayment.utils, "reset_tracker_balances")
class GetResidualCleanupPostingsTest(OverpaymentTest):
    def test_get_residual_cleanup_postings_with_postings(
        self, mock_reset_tracker_balances: MagicMock
    ):
        mock_reset_tracker_balances.return_value = [sentinel.postings]

        result = overpayment.get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [sentinel.postings])

        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=[
                "ACCRUED_EXPECTED_INTEREST",
                "EMI_PRINCIPAL_EXCESS",
                "OVERPAYMENT",
                "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )

    def test_get_residual_cleanup_postings_no_postings(
        self, mock_reset_tracker_balances: MagicMock
    ):
        mock_reset_tracker_balances.return_value = []

        result = overpayment.get_residual_cleanup_postings(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            denomination=sentinel.denomination,
        )

        self.assertListEqual(result, [])

        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances,
            account_id=sentinel.account_id,
            tracker_addresses=[
                "ACCRUED_EXPECTED_INTEREST",
                "EMI_PRINCIPAL_EXCESS",
                "OVERPAYMENT",
                "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination=sentinel.denomination,
            tside=Tside.ASSET,
        )


@patch.object(overpayment.fees, "fee_postings")
class GetOverpaymentFeePostingsTest(OverpaymentTest):
    def test_get_overpayment_fee_postings(self, mock_fee_postings: MagicMock):
        mock_fee_postings.return_value = [sentinel.postings]
        result = overpayment.get_overpayment_fee_postings(
            overpayment_fee=sentinel.overpayment_fee,
            denomination=sentinel.denomination,
            customer_account_id=sentinel.customer_account_id,
            customer_account_address=sentinel.customer_account_address,
            internal_account=sentinel.internal_account,
        )

        self.assertListEqual(result, [sentinel.postings])
        mock_fee_postings.assert_called_once_with(
            customer_account_id=sentinel.customer_account_id,
            customer_account_address=sentinel.customer_account_address,
            denomination=sentinel.denomination,
            amount=sentinel.overpayment_fee,
            internal_account=sentinel.internal_account,
        )


@patch.object(overpayment, "get_overpayment_fee_postings")
@patch.object(overpayment, "get_overpayment_fee")
@patch.object(overpayment.utils, "get_parameter")
class ChargeOverpaymentFeeAsPenalty(OverpaymentTest):
    def test_charge_overpayment_fee_as_penalty_no_postings(
        self,
        mock_get_parameter: MagicMock,
        mock_get_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": Decimal("0.1"),
                "overpayment_fee_income_account": sentinel.overpayment_fee_income_account,
            }
        )
        mock_get_overpayment_fee.return_value = sentinel.overpayment_fee
        mock_get_overpayment_fee_postings.return_value = []

        result = overpayment.charge_overpayment_fee_as_penalty(
            vault=self.create_mock(),
            overpayment_amount=sentinel.overpayment_amount,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        self.assertListEqual(result, [])
        mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=sentinel.overpayment_amount,
            overpayment_fee_rate=Decimal("0.1"),
            precision=sentinel.precision,
        )
        mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=sentinel.overpayment_fee,
            denomination=sentinel.denomination,
            customer_account_id=ACCOUNT_ID,
            customer_account_address="PENALTIES",
            internal_account=sentinel.overpayment_fee_income_account,
        )

    @patch.object(overpayment.utils, "standard_instruction_details")
    def test_charge_overpayment_fee_as_penalty_with_postings(
        self,
        mock_standard_instruction_details: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_postings: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_fee_rate": Decimal("0.1"),
                "overpayment_fee_income_account": sentinel.overpayment_fee_income_account,
            }
        )
        expected_posting = SentinelPosting("overpayment")
        mock_get_overpayment_fee.return_value = sentinel.overpayment_fee
        mock_get_overpayment_fee_postings.return_value = [expected_posting]
        mock_standard_instruction_details.return_value = {"key": "value"}

        expected = [
            CustomInstruction(
                postings=[expected_posting],
                instruction_details={"key": "value"},
                override_all_restrictions=True,
            )
        ]

        result = overpayment.charge_overpayment_fee_as_penalty(
            vault=self.create_mock(),
            overpayment_amount=sentinel.overpayment_amount,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        self.assertListEqual(result, expected)
        mock_get_overpayment_fee.assert_called_once_with(
            principal_repaid=sentinel.overpayment_amount,
            overpayment_fee_rate=Decimal("0.1"),
            precision=sentinel.precision,
        )
        mock_get_overpayment_fee_postings.assert_called_once_with(
            overpayment_fee=sentinel.overpayment_fee,
            denomination=sentinel.denomination,
            customer_account_id=ACCOUNT_ID,
            customer_account_address="PENALTIES",
            internal_account=sentinel.overpayment_fee_income_account,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Charge overpayment_fee=sentinel.overpayment_fee on "
            "overpayment_amount=sentinel.overpayment_amount",
            event_type="CHARGE_OVERPAYMENT_FEE",
            gl_impacted=True,
        )


@patch.object(overpayment.utils, "sum_balances")
@patch.object(overpayment.utils, "get_parameter")
@patch.object(overpayment.utils, "create_postings")
@patch.object(overpayment.interest_accrual_common, "calculate_daily_accrual")
class TrackExpectedInterestTest(OverpaymentTest):
    common_parameters = {
        overpayment.interest_accrual_common.PARAM_ACCRUAL_PRECISION: 5,
        overpayment.interest_accrual_common.PARAM_DAYS_IN_YEAR: "365",
        "denomination": sentinel.denomination,
    }
    common_hook_args = ScheduledEventHookArguments(
        effective_datetime=DEFAULT_DATE, event_type=sentinel.event_type
    )

    def test_track_expected_interest(
        self,
        mock_calculate_daily_accrual: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_sum_balances: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod"
                )
            }
        )
        mock_calculate_daily_accrual.return_value = (
            overpayment.interest_accrual_common.accruals.AccrualDetail(
                amount=Decimal("1"), description=""
            )
        )
        mock_create_postings.return_value = DEFAULT_POSTINGS
        mock_sum_balances.return_value = sentinel.expected_principal
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_interest_rate_feature = MagicMock(
            get_annual_interest_rate=MagicMock(return_value=sentinel.annual_rate)
        )

        result = overpayment.track_interest_on_expected_principal(
            vault=mock_vault,
            hook_arguments=self.common_hook_args,
            interest_rate_feature=mock_interest_rate_feature,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=DEFAULT_POSTINGS,
                    instruction_details={
                        "description": "Tracking expected interest at yearly rate "
                        "sentinel.annual_rate on expected principal sentinel.expected_principal"
                    },
                    override_all_restrictions=True,
                )
            ],
        )

        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            debit_account=mock_vault.account_id,
            debit_address=overpayment.ACCRUED_EXPECTED_INTEREST,
            credit_account=mock_vault.account_id,
            credit_address=overpayment.lending_addresses.INTERNAL_CONTRA,
            denomination="sentinel.denomination",
        )

        mock_sum_balances.called_once_with(
            balances=sentinel.balances_eod,
            denomination="sentinel.denomination",
            addresses=overpayment.EXPECTED_PRINCIPAL,
        )

        mock_calculate_daily_accrual.assert_called_once_with(
            effective_balance=sentinel.expected_principal,
            effective_datetime=DEFAULT_DATE,
            yearly_rate=sentinel.annual_rate,
            days_in_year="365",
            precision=5,
        )

    def test_track_expected_interest_with_zero_accrual(
        self,
        mock_calculate_daily_accrual: MagicMock,
        mock_create_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_sum_balances: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod"
                )
            }
        )
        mock_calculate_daily_accrual.return_value = None
        mock_sum_balances.return_value = sentinel.expected_principal
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_interest_rate_feature = MagicMock(
            get_annual_interest_rate=MagicMock(return_value=sentinel.annual_rate)
        )

        result = overpayment.track_interest_on_expected_principal(
            vault=mock_vault,
            hook_arguments=self.common_hook_args,
            interest_rate_feature=mock_interest_rate_feature,
        )

        self.assertListEqual(result, [])

        mock_sum_balances.called_once_with(
            balances=sentinel.balances_eod,
            denomination=sentinel.denomination,
            addresses=overpayment.EXPECTED_PRINCIPAL,
        )

        mock_calculate_daily_accrual.assert_called_once_with(
            effective_balance=sentinel.expected_principal,
            effective_datetime=DEFAULT_DATE,
            yearly_rate=sentinel.annual_rate,
            days_in_year="365",
            precision=5,
        )

        mock_create_postings.assert_not_called()


@patch.object(overpayment.utils, "balance_at_coordinates")
@patch.object(overpayment.utils, "create_postings")
class TrackEmiPrincipalExcessTest(OverpaymentTest):
    interest_amounts = overpayment.lending_interfaces.InterestAmounts(
        emi_accrued=Decimal("1.12345"),
        emi_rounded_accrued=Decimal("1.12"),
        non_emi_accrued=Decimal("1.42345"),
        non_emi_rounded_accrued=Decimal("1.42"),
        total_rounded=Decimal("2.55"),
    )

    def test_track_emi_principal_excess_with_new_excess_returns_a_ci(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_interest_application_feature = MagicMock(
            get_interest_to_apply=MagicMock(side_effect=[self.interest_amounts]),
            get_application_precision=MagicMock(side_effect=[sentinel.application_precision]),
        )
        mock_create_postings.return_value = DEFAULT_POSTINGS
        mock_balance_at_coordinates.return_value = Decimal("5")
        mock_vault = self.create_mock()
        expected = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Increase principal excess due to "
                    "expected_interest_to_apply=Decimal('5') being larger than "
                    "actual_interest_to_apply=Decimal('2.55')"
                },
            )
        ]

        result = overpayment.track_emi_principal_excess(
            vault=mock_vault,
            interest_application_feature=mock_interest_application_feature,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, expected)

        # import to check that we're rounding correctly
        mock_interest_application_feature.get_interest_to_apply.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment.ACCRUED_EXPECTED_INTEREST,
            denomination=sentinel.denomination,
            decimal_places=sentinel.application_precision,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("2.45"),
            debit_account=mock_vault.account_id,
            debit_address=overpayment.EMI_PRINCIPAL_EXCESS,
            credit_account=mock_vault.account_id,
            credit_address=overpayment.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )

    def test_track_emi_principal_excess_with_no_new_excess_returns_empty_list(
        self,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_interest_application_feature = MagicMock(
            get_interest_to_apply=MagicMock(side_effect=[self.interest_amounts]),
            get_application_precision=MagicMock(side_effect=[sentinel.application_precision]),
        )
        mock_create_postings.return_value = []
        mock_balance_at_coordinates.return_value = Decimal("5")
        mock_vault = self.create_mock()
        expected: list[CustomInstruction] = []

        result = overpayment.track_emi_principal_excess(
            vault=mock_vault,
            interest_application_feature=mock_interest_application_feature,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertListEqual(result, expected)
        mock_interest_application_feature.get_interest_to_apply.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )

    @patch.object(overpayment.utils, "get_parameter")
    def test_track_emi_principal_excess_without_fetched_args(
        self,
        mock_get_parameter: MagicMock,
        mock_create_postings: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"denomination": sentinel.denomination}
        )
        mock_interest_application_feature = MagicMock(
            get_interest_to_apply=MagicMock(side_effect=[self.interest_amounts]),
            get_application_precision=MagicMock(side_effect=[sentinel.application_precision]),
        )
        mock_create_postings.return_value = DEFAULT_POSTINGS
        mock_balance_at_coordinates.return_value = Decimal("5")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "accrued_expected_effective_datetime"
                )
            }
        )
        expected = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Increase principal excess due to "
                    "expected_interest_to_apply=Decimal('5') being larger than "
                    "actual_interest_to_apply=Decimal('2.55')"
                },
            )
        ]

        result = overpayment.track_emi_principal_excess(
            vault=mock_vault,
            interest_application_feature=mock_interest_application_feature,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )
        self.assertListEqual(result, expected)

        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_accrued_expected_effective_datetime,
            address=overpayment.ACCRUED_EXPECTED_INTEREST,
            denomination=sentinel.denomination,
            decimal_places=sentinel.application_precision,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("2.45"),
            debit_account=mock_vault.account_id,
            debit_address=overpayment.EMI_PRINCIPAL_EXCESS,
            credit_account=mock_vault.account_id,
            credit_address=overpayment.lending_addresses.INTERNAL_CONTRA,
            denomination=sentinel.denomination,
        )
        mock_interest_application_feature.get_interest_to_apply.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )


class ResetDueAmountCalcOverpaymentTrackerTest(OverpaymentTest):
    @patch.object(overpayment.utils, "get_parameter")
    @patch.object(overpayment.utils, "reset_tracker_balances")
    def test_reset_due_amount_calc_overpayment_trackers(
        self,
        mock_reset_tracker_balances: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        sentinel_postings = [SentinelPosting("reset_overpayment_since")]
        mock_reset_tracker_balances.return_value = sentinel_postings
        expected_result = [
            CustomInstruction(
                postings=sentinel_postings,  # type: ignore
                instruction_details={"description": "Resetting overpayment trackers"},
                override_all_restrictions=True,
            )
        ]

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        balances_observation_fetchers_mapping = {
            overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                "effective_date"
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        result = overpayment.reset_due_amount_calc_overpayment_trackers(vault=mock_vault)
        self.assertListEqual(result, expected_result)

        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances_effective_date,  # type: ignore
            account_id=ACCOUNT_ID,
            tracker_addresses=[
                "ACCRUED_EXPECTED_INTEREST",
                "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination="sentinel.denomination",
            tside=Tside.ASSET,
        )

    @patch.object(overpayment.utils, "get_parameter")
    @patch.object(overpayment.utils, "reset_tracker_balances")
    def test_reset_due_amount_calc_overpayment_trackers_no_postings(
        self,
        mock_reset_tracker_balances: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_reset_tracker_balances.return_value = []
        expected_result: list[CustomInstruction] = []

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        balances_observation_fetchers_mapping = {
            overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                "effective_date"
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        result = overpayment.reset_due_amount_calc_overpayment_trackers(vault=mock_vault)
        self.assertListEqual(result, expected_result)
        mock_reset_tracker_balances.assert_called_once_with(
            balances=sentinel.balances_effective_date,  # type: ignore
            account_id=ACCOUNT_ID,
            tracker_addresses=[
                "ACCRUED_EXPECTED_INTEREST",
                "OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER",
            ],
            contra_address="INTERNAL_CONTRA",
            denomination="sentinel.denomination",
            tside=Tside.ASSET,
        )


@patch.object(overpayment.utils, "get_parameter")
@patch.object(overpayment.utils, "balance_at_coordinates")
class OverpaymentReamortisationCondition(OverpaymentTest):
    def test_reamortisation_required_if_overpayment_and_preference_is_reduce_emi(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_EMI,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("1")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "tracker_obs"
                )
            }
        )
        self.assertTrue(
            overpayment.should_trigger_reamortisation(
                vault=mock_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_tracker_obs,
            address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=sentinel.denomination,
        )

    def test_reamortisation_not_required_if_overpayment_and_preference_is_reduce_term(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("1")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "tracker_obs"
                )
            }
        )
        self.assertFalse(
            overpayment.should_trigger_reamortisation(
                vault=mock_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        mock_balance_at_coordinates.assert_not_called()

    def test_reamortisation_not_required_if_no_overpayment_and_preference_is_reduce_emi(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_EMI,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("0")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "tracker_obs"
                )
            }
        )
        self.assertFalse(
            overpayment.should_trigger_reamortisation(
                vault=mock_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances_tracker_obs,
            address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=sentinel.denomination,
        )

    def test_reamortisation_not_required_if_no_overpayment_and_preference_is_reduce_term(
        self, mock_balance_at_coordinates: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("0")

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.OVERPAYMENT_TRACKER_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "tracker_obs"
                )
            }
        )
        self.assertFalse(
            overpayment.should_trigger_reamortisation(
                vault=mock_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        mock_balance_at_coordinates.assert_not_called()


class SupervisorOverpaymentReamortisationCondition(SupervisorFeatureTest):
    def setUp(self) -> None:
        self.mock_loan_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances
        )
        self.mock_main_vault = sentinel.main_vault

        self.mock_get_balance_default_dict_from_mapping = patch.object(
            overpayment.utils, "get_balance_default_dict_from_mapping"
        ).start()
        self.mock_get_balance_default_dict_from_mapping.return_value = sentinel.balance_default_dict

        self.mock_get_parameter = patch.object(overpayment.utils, "get_parameter").start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_EMI,
            }
        )

        self.mock_balance_at_coordinates = patch.object(
            overpayment.utils, "balance_at_coordinates"
        ).start()
        self.mock_balance_at_coordinates.return_value = Decimal("1")
        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_non_default_arguments(self):
        self.assertTrue(
            overpayment.supervisor_should_trigger_reamortisation(
                loan_vault=self.mock_loan_vault,
                main_vault=self.mock_main_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
                balances=sentinel.balances,
            )
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balances,
            address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=sentinel.denomination,
        )
        self.mock_get_balance_default_dict_from_mapping.assert_not_called()

    def test_reamortisation_required_if_overpayment_and_preference_is_reduce_emi(self):
        self.assertTrue(
            overpayment.supervisor_should_trigger_reamortisation(
                loan_vault=self.mock_loan_vault,
                main_vault=self.mock_main_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balance_default_dict,
            address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=sentinel.denomination,
        )
        self.mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances
        )

    def test_reamortisation_not_required_if_overpayment_and_preference_is_reduce_term(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM,
            }
        )

        self.assertFalse(
            overpayment.supervisor_should_trigger_reamortisation(
                loan_vault=self.mock_loan_vault,
                main_vault=self.mock_main_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        self.mock_balance_at_coordinates.assert_not_called()

    def test_reamortisation_not_required_if_no_overpayment_and_preference_is_reduce_emi(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")

        self.assertFalse(
            overpayment.supervisor_should_trigger_reamortisation(
                loan_vault=self.mock_loan_vault,
                main_vault=self.mock_main_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=sentinel.balance_default_dict,
            address=overpayment.OVERPAYMENT_SINCE_PREV_DUE_AMOUNT_CALC_TRACKER,
            denomination=sentinel.denomination,
        )

    def test_reamortisation_not_required_if_no_overpayment_and_preference_is_reduce_term(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": sentinel.denomination,
                overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM,
            }
        )
        self.mock_balance_at_coordinates.return_value = Decimal("0")

        self.assertFalse(
            overpayment.supervisor_should_trigger_reamortisation(
                loan_vault=self.mock_loan_vault,
                main_vault=self.mock_main_vault,
                period_start_datetime=sentinel.start_datetime,
                period_end_datetime=sentinel.end_datetime,
                elapsed_term=sentinel.elapsed_term,
            )
        )
        self.mock_balance_at_coordinates.assert_not_called()


@patch.object(overpayment.utils, "balance_at_coordinates")
@patch.object(overpayment.utils, "get_parameter")
class PrincipalAdjustmentTest(OverpaymentTest):
    def test_calculate_principal_adjustment_reduce_emi_non_default_args(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"overpayment_impact_preference": overpayment.REDUCE_EMI}
        )

        result = overpayment.calculate_principal_adjustment(
            vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
        )

        self.assertEqual(result, Decimal("0"))

        mock_balance_at_coordinates.assert_not_called()

    def test_calculate_principal_adjustment_reduce_term_non_default_args(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_impact_preference": overpayment.REDUCE_TERM,
            }
        )
        # overpayment, emi_principal_excess
        mock_balance_at_coordinates.side_effect = [Decimal("1"), Decimal("2")]

        result = overpayment.calculate_principal_adjustment(
            vault=sentinel.vault, balances=sentinel.balances, denomination=sentinel.denomination
        )

        self.assertEqual(result, Decimal("3"))

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address=overpayment.OVERPAYMENT,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
                call(
                    balances=sentinel.balances,
                    address=overpayment.EMI_PRINCIPAL_EXCESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
            ]
        )

    def test_calculate_principal_adjustment_reduce_term_default_args(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "overpayment_impact_preference": overpayment.REDUCE_TERM,
                "denomination": sentinel.denomination,
            }
        )
        # overpayment, emi_principal_excess
        mock_balance_at_coordinates.side_effect = [Decimal("1"), Decimal("2")]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                overpayment.EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "expected_eod"
                )
            }
        )

        result = overpayment.calculate_principal_adjustment(vault=mock_vault)

        self.assertEqual(result, Decimal("3"))

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_expected_eod,
                    address=overpayment.OVERPAYMENT,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
                call(
                    balances=sentinel.balances_expected_eod,
                    address=overpayment.EMI_PRINCIPAL_EXCESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
            ]
        )


@patch.object(overpayment.utils, "balance_at_coordinates")
@patch.object(overpayment.utils, "get_parameter")
class SupervisorPrincipalAdjustmentTest(SupervisorFeatureTest):
    def test_calculate_principal_adjustment_reduce_emi_non_default_args_supervisor(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_loan_vault = sentinel.loan_vault
        mock_main_vault = sentinel.main_vault

        mock_get_parameter.side_effect = mock_utils_get_parameter_for_multiple_vaults(
            parameters_per_vault={
                mock_main_vault: {
                    overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_EMI
                }
            }
        )

        result = overpayment.supervisor_calculate_principal_adjustment(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, Decimal("0"))

        mock_balance_at_coordinates.assert_not_called()

    def test_calculate_principal_adjustment_reduce_term_non_default_args_supervisor(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_loan_vault = sentinel.loan_vault
        mock_main_vault = sentinel.main_vault

        mock_get_parameter.side_effect = mock_utils_get_parameter_for_multiple_vaults(
            parameters_per_vault={
                mock_main_vault: {
                    overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM
                }
            }
        )
        # overpayment, emi_principal_excess
        mock_balance_at_coordinates.side_effect = [Decimal("1"), Decimal("2")]

        result = overpayment.supervisor_calculate_principal_adjustment(
            loan_vault=mock_loan_vault,
            main_vault=mock_main_vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, Decimal("3"))

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances,
                    address=overpayment.OVERPAYMENT,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
                call(
                    balances=sentinel.balances,
                    address=overpayment.EMI_PRINCIPAL_EXCESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
            ]
        )

    def test_calculate_principal_adjustment_reduce_term_default_args_supervisor(
        self, mock_get_parameter: MagicMock, mock_balance_at_coordinates: MagicMock
    ):
        mock_loan_vault = sentinel.loan_vault
        mock_main_vault = sentinel.main_vault

        # overpayment, emi_principal_excess
        mock_balance_at_coordinates.side_effect = [Decimal("1"), Decimal("2")]
        mock_loan_vault = self.create_supervisee_mock(
            balances_observation_fetchers_mapping={
                overpayment.EXPECTED_INTEREST_ACCRUAL_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "expected_eod"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter_for_multiple_vaults(
            parameters_per_vault={
                mock_main_vault: {
                    overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: overpayment.REDUCE_TERM
                },
                mock_loan_vault: {"denomination": sentinel.denomination},
            }
        )

        result = overpayment.supervisor_calculate_principal_adjustment(
            loan_vault=mock_loan_vault, main_vault=mock_main_vault
        )

        self.assertEqual(result, Decimal("3"))

        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.balances_expected_eod,
                    address=overpayment.OVERPAYMENT,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
                call(
                    balances=sentinel.balances_expected_eod,
                    address=overpayment.EMI_PRINCIPAL_EXCESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ),
            ]
        )


@patch.object(overpayment.utils, "get_parameter")
@patch.object(overpayment, "get_overpayment_fee_rate_parameter")
@patch.object(overpayment, "get_max_overpayment_fee")
class EarlyRepaymentOverpaymentFeeTest(OverpaymentTest):
    def test_get_early_repayment_overpayment_fee_no_optional_args_supplied(
        self,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_rate_parameter: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_max_overpayment_fee.return_value = sentinel.max_overpayment_fee
        mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        mock_get_parameter.return_value = sentinel.denomination
        live_balance_obs = SentinelBalancesObservation("live")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={fetchers.LIVE_BALANCES_BOF_ID: live_balance_obs}
        )
        result = overpayment.get_early_repayment_overpayment_fee(
            vault=mock_vault,
        )
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=sentinel.balances_live,
            denomination=sentinel.denomination,
            precision=2,
        )
        mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=mock_vault)
        mock_get_parameter.assert_called_once_with(vault=mock_vault, name="denomination")
        self.assertEqual(sentinel.max_overpayment_fee, result)

    def test_get_early_repayment_overpayment_fee_with_optional_args_supplied(
        self,
        mock_get_max_overpayment_fee: MagicMock,
        mock_get_overpayment_fee_rate_parameter: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_max_overpayment_fee.return_value = sentinel.max_overpayment_fee
        mock_get_overpayment_fee_rate_parameter.return_value = sentinel.overpayment_fee_rate
        result = overpayment.get_early_repayment_overpayment_fee(
            vault=sentinel.vault,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_max_overpayment_fee.assert_called_once_with(
            fee_rate=sentinel.overpayment_fee_rate,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_overpayment_fee_rate_parameter.assert_called_once_with(vault=sentinel.vault)
        mock_get_parameter.assert_not_called()
        self.assertEqual(sentinel.max_overpayment_fee, result)


class EarlyRepaymentSkipFeeChargeTest(OverpaymentTest):
    def test_skip_charge_early_repayment_fee_for_overpayment_no_optional_args_supplied(self):
        result = overpayment.skip_charge_early_repayment_fee_for_overpayment(
            vault=sentinel.vault,
            account_id=sentinel.account_id,
            amount_to_charge=sentinel.amount_to_charge,
            fee_name=sentinel.fee_name,
        )
        self.assertListEqual([], result)

    def test_skip_charge_early_repayment_fee_for_overpayment_with_optional_args_supplied(self):
        result = overpayment.skip_charge_early_repayment_fee_for_overpayment(
            vault=sentinel.vault,
            account_id=sentinel.account_id,
            amount_to_charge=sentinel.amount_to_charge,
            fee_name=sentinel.fee_name,
            denomination=sentinel.denomination,
        )
        self.assertListEqual([], result)
