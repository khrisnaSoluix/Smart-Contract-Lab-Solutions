# standard libs
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.lending.interest_application_supervisor as interest_application_supervisor  # noqa: E501
import library.features.v4.lending.lending_interfaces as lending_interfaces
from library.features.v4.common.test.mocks import mock_utils_get_parameter

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
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)

DEFAULT_DATE = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

ACCRUED_RECEIVABLE_COORDINATE = BalanceCoordinate(
    interest_application_supervisor.ACCRUED_INTEREST_RECEIVABLE,
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)
NON_EMI_ACCRUED_RECEIVABLE_COORDINATE = BalanceCoordinate(
    interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE,
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)
INTEREST_DUE_COORDINATE = BalanceCoordinate(
    interest_application_supervisor.INTEREST_DUE,
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)
PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_application_supervisor.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)
PARAM_INTEREST_RECEIVED_ACCOUNT = interest_application_supervisor.PARAM_INTEREST_RECEIVED_ACCOUNT
PARAM_APPLICATION_PRECISION = interest_application_supervisor.PARAM_APPLICATION_PRECISION


class InterestApplicationTestCommon(SupervisorFeatureTest):
    maxDiff = None


class InterestApplicationTest(InterestApplicationTestCommon):
    balances = BalanceDefaultDict(
        mapping={
            # the emi/non emi accrued amounts are different to highlight that we
            # are rounding the individual amounts, not the sum of the two
            ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("10.12345")),
            NON_EMI_ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("10.45678")),
            INTEREST_DUE_COORDINATE: Balance(net=Decimal("23.45")),
        }
    )

    parameters = {
        interest_application_supervisor.PARAM_APPLICATION_PRECISION: sentinel.application_precision,
        "denomination": sentinel.denomination,
    }

    @patch.object(interest_application_supervisor, "_get_interest_to_apply")
    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    def test_apply_interest_with_non_emi_and_emi_interest(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
        mock_get_interest_to_apply: MagicMock,
    ):
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping={
                fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation("effective")
            },
        )
        mock_get_interest_to_apply.return_value = lending_interfaces.InterestAmounts(
            emi_accrued=Decimal("10.32345"),
            emi_rounded_accrued=Decimal("10.32"),
            non_emi_accrued=Decimal("10.42345"),
            non_emi_rounded_accrued=Decimal("10.42"),
            total_rounded=Decimal("20.75"),
        )
        mock_accrual_application_postings.return_value = [sentinel.application_postings]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.accrued_int_receivable_account,
                PARAM_INTEREST_RECEIVED_ACCOUNT: sentinel.interest_received_account,
                PARAM_APPLICATION_PRECISION: sentinel.application_precision,
                "denomination": sentinel.denomination,
            }
        )

        daily_accrual_ci = interest_application_supervisor.apply_interest(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )

        self.assertListEqual(
            daily_accrual_ci, [sentinel.application_postings, sentinel.application_postings]
        )
        expected_calls = [
            call(
                customer_account=sentinel.account_id,
                denomination=sentinel.denomination,
                application_amount=Decimal("10.32"),
                accrual_amount=Decimal("10.32345"),
                accrual_customer_address=(
                    interest_application_supervisor.ACCRUED_INTEREST_RECEIVABLE
                ),
                accrual_internal_account=sentinel.accrued_int_receivable_account,
                application_customer_address=interest_application_supervisor.INTEREST_DUE,
                application_internal_account=sentinel.interest_received_account,
                payable=False,
            ),
            call(
                customer_account=sentinel.account_id,
                denomination=sentinel.denomination,
                application_amount=Decimal("10.43"),
                accrual_amount=Decimal("10.42345"),
                accrual_customer_address=(
                    interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
                ),
                accrual_internal_account=sentinel.accrued_int_receivable_account,
                application_customer_address=interest_application_supervisor.INTEREST_DUE,
                application_internal_account=sentinel.interest_received_account,
                payable=False,
            ),
        ]
        mock_accrual_application_postings.assert_has_calls(calls=expected_calls)
        mock_get_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )

    def test_get_emi_interest_to_apply(self):
        self.assertTupleEqual(
            interest_application_supervisor._get_emi_interest_to_apply(
                self.balances, sentinel.denomination
            ),
            (Decimal("10.12345"), Decimal("10.12")),
        )

    def test_get_emi_interest_to_apply_non_default_rounding(self):
        self.assertTupleEqual(
            interest_application_supervisor._get_emi_interest_to_apply(
                self.balances, sentinel.denomination, precision=3
            ),
            (Decimal("10.12345"), Decimal("10.123")),
        )

    def test_get_non_emi_interest_to_apply(self):
        self.assertTupleEqual(
            interest_application_supervisor._get_non_emi_interest_to_apply(
                self.balances, sentinel.denomination
            ),
            (Decimal("10.45678"), Decimal("10.46")),
        )

    def test_get_non_emi_interest_to_apply_non_default_rounding(self):
        self.assertTupleEqual(
            interest_application_supervisor._get_non_emi_interest_to_apply(
                self.balances, sentinel.denomination, precision=1
            ),
            (Decimal("10.45678"), Decimal("10.5")),
        )

    @patch.object(interest_application_supervisor.utils, "get_parameter")
    def test_get_application_precision(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={interest_application_supervisor.PARAM_APPLICATION_PRECISION: 2}
        )
        self.assertEqual(interest_application_supervisor.get_application_precision(mock_vault), 2)

    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor.utils, "round_decimal")
    def test_get_interest_to_apply(
        self,
        mock_round_decimal: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_non_emi_interest_to_apply: MagicMock,
    ):
        mock_get_emi_interest_to_apply.return_value = Decimal("10.32345"), Decimal("10.32")
        mock_get_non_emi_interest_to_apply.return_value = Decimal("10.42345"), Decimal("10.42")
        mock_round_decimal.return_value = Decimal("20.75")

        result = interest_application_supervisor._get_interest_to_apply(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )
        self.assertEqual(
            result,
            interest_application_supervisor.lending_interfaces.InterestAmounts(
                emi_accrued=Decimal("10.32345"),
                emi_rounded_accrued=Decimal("10.32"),
                non_emi_accrued=Decimal("10.42345"),
                non_emi_rounded_accrued=Decimal("10.42"),
                total_rounded=Decimal("20.75"),
            ),
        )

        mock_get_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.application_precision,
        )
        mock_get_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            precision=sentinel.application_precision,
        )
        mock_round_decimal.assert_called_once_with(
            amount=Decimal("20.7469"),
            decimal_places=sentinel.application_precision,
            rounding=ROUND_HALF_UP,
        )

    @patch.object(interest_application_supervisor.utils, "get_balance_default_dict_from_mapping")
    @patch.object(interest_application_supervisor, "_get_interest_to_apply")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    def test_get_interest_to_apply_wrapper_without_fetched_args(
        self,
        mock_get_parameter: MagicMock,
        mock_get_interest_to_apply: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
    ):
        mock_get_balance_default_dict_from_mapping.return_value = sentinel.balance_dict
        mock_get_interest_to_apply.return_value = sentinel.interest_amounts
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.parameters)
        mock_vault = self.create_supervisee_mock(
            requires_fetched_balances=sentinel.fetched_balances
        )

        self.assertEqual(
            interest_application_supervisor.get_interest_to_apply(
                vault=mock_vault,
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
            ),
            sentinel.interest_amounts,
        )

        mock_get_balance_default_dict_from_mapping.assert_called_once_with(
            mapping=sentinel.fetched_balances,
            effective_datetime=sentinel.effective_datetime,
        )
        mock_get_interest_to_apply.assert_called_once_with(
            balances=sentinel.balance_dict,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )

    @patch.object(interest_application_supervisor, "_get_interest_to_apply")
    def test_get_interest_to_apply_wrapper_with_fetched_args(
        self,
        mock_get_interest_to_apply: MagicMock,
    ):
        mock_get_interest_to_apply.return_value = sentinel.interest_amounts

        self.assertEqual(
            interest_application_supervisor.get_interest_to_apply(
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
                vault=sentinel.vault,
                balances_at_application=sentinel.balances,
                denomination=sentinel.denomination,
                application_precision=sentinel.application_precision,
            ),
            sentinel.interest_amounts,
        )

        mock_get_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            application_precision=sentinel.application_precision,
        )


class RepayAccruedInterestTest(InterestApplicationTestCommon):
    common_parameters: dict[str, str] = {
        "denomination": sentinel.denomination,
        interest_application_supervisor.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.receivable,  # noqa: E501
        interest_application_supervisor.PARAM_INTEREST_RECEIVED_ACCOUNT: sentinel.received,
        interest_application_supervisor.PARAM_APPLICATION_PRECISION: sentinel.precision,
    }

    common_bof_mapping = {
        interest_application_supervisor.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
            "effective"
        )
    }

    def test_repay_accrued_interest_with_0_amount(self):
        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=sentinel.vault, repayment_amount=Decimal("0")
            ),
            [],
        )

    def test_repay_accrued_interest_with_negative_amount(self):
        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=sentinel.vault, repayment_amount=Decimal("-1")
            ),
            [],
        )

    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_no_accrued_interest(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (0, 0)
        mock_get_emi_interest_to_apply.return_value = (0, 0)

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("10")
            ),
            [],
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_non_emi_interest_equal_to_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("1.01234"), Decimal("1.01"))
        mock_get_emi_interest_to_apply.return_value = (0, 0)
        mock_accrual_application_postings.side_effect = [[sentinel.non_emi_posting]]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("1.01")
            ),
            [sentinel.non_emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_not_called()

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01234"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_non_emi_interest_less_than_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("1.01234"), Decimal("1.01"))
        mock_get_emi_interest_to_apply.return_value = (0, 0)
        mock_accrual_application_postings.side_effect = [[sentinel.non_emi_posting]]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("100")
            ),
            [sentinel.non_emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01234"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_non_emi_interest_over_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("2.01234"), Decimal("2.01"))
        mock_get_emi_interest_to_apply.return_value = (0, 0)
        mock_accrual_application_postings.side_effect = [[sentinel.non_emi_posting]]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("1.01")
            ),
            [sentinel.non_emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_not_called()

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_emi_and_non_emi_interest_equal_to_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("2.01234"), Decimal("2.01"))
        mock_get_emi_interest_to_apply.return_value = (Decimal("3.01234"), Decimal("3.01"))
        mock_accrual_application_postings.side_effect = [
            [sentinel.non_emi_posting],
            [sentinel.emi_posting],
        ]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("5.02")
            ),
            [sentinel.non_emi_posting, sentinel.emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        non_emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("2.01"),
            accrual_amount=Decimal("2.01234"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )
        emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("3.01"),
            accrual_amount=Decimal("3.01234"),
            accrual_customer_address=interest_application_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

        mock_accrual_application_postings.assert_has_calls(
            [non_emi_application_call, emi_application_call]
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_emi_and_non_emi_interest_over_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("2.01234"), Decimal("2.01"))
        mock_get_emi_interest_to_apply.return_value = (Decimal("3.01234"), Decimal("3.01"))
        mock_accrual_application_postings.side_effect = [
            [sentinel.non_emi_posting],
            [sentinel.emi_posting],
        ]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("4.5")
            ),
            [sentinel.non_emi_posting, sentinel.emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        # non emi is fully repaid, but emi is partially repaid
        non_emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("2.01"),
            accrual_amount=Decimal("2.01234"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )
        emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("2.49"),
            accrual_amount=Decimal("2.49"),
            accrual_customer_address=interest_application_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

        mock_accrual_application_postings.assert_has_calls(
            [non_emi_application_call, emi_application_call]
        )

    @patch.object(interest_application_supervisor.accruals, "accrual_application_postings")
    @patch.object(interest_application_supervisor.utils, "get_parameter")
    @patch.object(interest_application_supervisor, "_get_emi_interest_to_apply")
    @patch.object(interest_application_supervisor, "_get_non_emi_interest_to_apply")
    def test_repay_accrued_interest_with_emi_and_non_emi_interest_less_than_repayment(
        self,
        mock_non_emi_interest_to_apply: MagicMock,
        mock_get_emi_interest_to_apply: MagicMock,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=self.common_bof_mapping  # type: ignore
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        mock_non_emi_interest_to_apply.return_value = (Decimal("2.01234"), Decimal("2.01"))
        mock_get_emi_interest_to_apply.return_value = (Decimal("3.01234"), Decimal("3.01"))
        mock_accrual_application_postings.side_effect = [
            [sentinel.non_emi_posting],
            [sentinel.emi_posting],
        ]

        self.assertListEqual(
            interest_application_supervisor.repay_accrued_interest(
                vault=mock_vault, repayment_amount=Decimal("100")
            ),
            [sentinel.non_emi_posting, sentinel.emi_posting],
        )

        mock_non_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )
        mock_get_emi_interest_to_apply.assert_called_once_with(
            balances=sentinel.balances_effective,
            denomination=sentinel.denomination,
            precision=sentinel.precision,
        )

        # non emi is fully repaid, but emi is partially repaid
        non_emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("2.01"),
            accrual_amount=Decimal("2.01234"),
            accrual_customer_address=(
                interest_application_supervisor.NON_EMI_ACCRUED_INTEREST_RECEIVABLE
            ),
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )
        emi_application_call = call(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("3.01"),
            accrual_amount=Decimal("3.01234"),
            accrual_customer_address=interest_application_supervisor.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

        mock_accrual_application_postings.assert_has_calls(
            [non_emi_application_call, emi_application_call]
        )
