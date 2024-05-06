# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.lending.interest_application as interest_application
import library.features.v4.lending.lending_interfaces as lending_interfaces
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesObservation,
    Phase,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)

ACCRUED_RECEIVABLE_COORDINATE = BalanceCoordinate(
    interest_application.ACCRUED_INTEREST_RECEIVABLE,
    DEFAULT_ASSET,
    sentinel.denomination,
    Phase.COMMITTED,
)

PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    interest_application.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
)
PARAM_INTEREST_RECEIVED_ACCOUNT = interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT
PARAM_APPLICATION_PRECISION = interest_application.PARAM_APPLICATION_PRECISION


class InterestApplicationTestCommon(FeatureTest):
    maxDiff = None


class InterestApplicationTest(InterestApplicationTestCommon):
    # These amounts are such that accrued interest at effective datetime (20.4469) rounds
    # differently to the sum of rounded non-emi (10.12345) and emi (20.4469-10.12345)
    # i.e. round(20.4469, 2) -> 20.45 != round(10.12345, 2) + round(10.32345, 2) -> 20.44
    effective_datetime_balances = BalanceDefaultDict(
        mapping={
            ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("20.4469")),
        }
    )
    one_month_ago_balances = BalanceDefaultDict(
        mapping={
            ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("10.12345")),
        }
    )

    parameters = {
        interest_application.PARAM_APPLICATION_PRECISION: 2,
        "denomination": sentinel.denomination,
    }

    @patch.object(interest_application, "_get_interest_to_apply")
    @patch.object(interest_application.accruals, "accrual_application_postings")
    @patch.object(interest_application.utils, "get_parameter")
    def test_apply_interest(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
        mock_get_interest_to_apply: MagicMock,
    ):
        mock_vault = self.create_mock(
            account_id=sentinel.account_id,
            balances_observation_fetchers_mapping={
                interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "effective"
                ),
                interest_application.ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID: (
                    SentinelBalancesObservation("one_month_ago")
                ),
            },
        )
        mock_get_interest_to_apply.return_value = lending_interfaces.InterestAmounts(
            emi_accrued=Decimal("10.32345"),
            emi_rounded_accrued=Decimal("10.32"),
            non_emi_accrued=Decimal("10.42345"),
            non_emi_rounded_accrued=Decimal("10.42"),
            total_rounded=Decimal("20.75"),
        )
        mock_accrual_application_postings.return_value = sentinel.application_postings
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.accrued_int_receivable_account,
                PARAM_INTEREST_RECEIVED_ACCOUNT: sentinel.interest_received_account,
                PARAM_APPLICATION_PRECISION: 2,
                "denomination": sentinel.denomination,
            }
        )

        daily_accrual_ci = interest_application.apply_interest(
            vault=mock_vault,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )

        self.assertEqual(daily_accrual_ci, sentinel.application_postings)
        expected_calls = [
            call(
                customer_account=sentinel.account_id,
                denomination=sentinel.denomination,
                application_amount=Decimal("20.75"),
                accrual_amount=Decimal("20.74690"),
                accrual_customer_address=interest_application.ACCRUED_INTEREST_RECEIVABLE,
                accrual_internal_account=sentinel.accrued_int_receivable_account,
                application_customer_address=interest_application.INTEREST_DUE,
                application_internal_account=sentinel.interest_received_account,
                payable=False,
            ),
        ]
        mock_accrual_application_postings.assert_has_calls(calls=expected_calls)
        mock_get_interest_to_apply.assert_called_once_with(
            balances_at_application=sentinel.balances_effective,
            balances_one_repayment_period_ago=sentinel.balances_one_month_ago,
            denomination=sentinel.denomination,
            application_precision=2,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )

    @patch.object(interest_application.utils, "get_parameter")
    def test_get_application_precision(self, mock_get_parameter: MagicMock):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={interest_application.PARAM_APPLICATION_PRECISION: 2}
        )
        self.assertEqual(interest_application.get_application_precision(mock_vault), 2)

    def test_get_interest_to_apply_effective_effective_datetime_greater_than_1_month_from_previous(
        self,
    ):
        effective_datetime = DEFAULT_DATETIME + relativedelta(months=1, days=1)
        previous_application_datetime = DEFAULT_DATETIME
        result = interest_application._get_interest_to_apply(
            effective_datetime=effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances_at_application=self.effective_datetime_balances,
            balances_one_repayment_period_ago=self.one_month_ago_balances,
            denomination=sentinel.denomination,
            application_precision=2,
        )
        self.assertEqual(
            result,
            interest_application.lending_interfaces.InterestAmounts(
                emi_accrued=Decimal("10.32345"),
                emi_rounded_accrued=Decimal("10.33"),
                non_emi_accrued=Decimal("10.12345"),
                non_emi_rounded_accrued=Decimal("10.12"),
                total_rounded=Decimal("20.45"),
            ),
        )

    def test_get_interest_to_apply_effective_effective_datetime_exactly_1_month_from_previous(
        self,
    ):
        effective_datetime = DEFAULT_DATETIME + relativedelta(months=1)
        previous_application_datetime = DEFAULT_DATETIME
        result = interest_application._get_interest_to_apply(
            effective_datetime=effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances_at_application=self.effective_datetime_balances,
            balances_one_repayment_period_ago=self.one_month_ago_balances,
            denomination=sentinel.denomination,
            application_precision=2,
        )
        self.assertEqual(
            result,
            interest_application.lending_interfaces.InterestAmounts(
                emi_accrued=Decimal("10.32345"),
                emi_rounded_accrued=Decimal("10.33"),
                non_emi_accrued=Decimal("10.12345"),
                non_emi_rounded_accrued=Decimal("10.12"),
                total_rounded=Decimal("20.45"),
            ),
        )

    def test_get_interest_to_apply_effective_effective_datetime_less_than_1_month_from_previous(
        self,
    ):
        effective_datetime = DEFAULT_DATETIME + relativedelta(days=10)
        previous_application_datetime = DEFAULT_DATETIME
        result = interest_application._get_interest_to_apply(
            effective_datetime=effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances_at_application=self.effective_datetime_balances,
            balances_one_repayment_period_ago=self.one_month_ago_balances,
            denomination=sentinel.denomination,
            application_precision=2,
        )
        self.assertEqual(
            result,
            interest_application.lending_interfaces.InterestAmounts(
                emi_accrued=Decimal("20.4469"),
                emi_rounded_accrued=Decimal("20.45"),
                non_emi_accrued=Decimal("0"),
                non_emi_rounded_accrued=Decimal("0"),
                total_rounded=Decimal("20.45"),
            ),
        )

    def test_get_interest_to_apply_effective_effective_datetime_equal_previous(
        self,
    ):
        effective_datetime = DEFAULT_DATETIME
        previous_application_datetime = DEFAULT_DATETIME
        result = interest_application._get_interest_to_apply(
            effective_datetime=effective_datetime,
            previous_application_datetime=previous_application_datetime,
            balances_at_application=self.effective_datetime_balances,
            balances_one_repayment_period_ago=self.one_month_ago_balances,
            denomination=sentinel.denomination,
            application_precision=2,
        )
        self.assertEqual(
            result,
            interest_application.lending_interfaces.InterestAmounts(
                emi_accrued=Decimal("20.4469"),
                emi_rounded_accrued=Decimal("20.45"),
                non_emi_accrued=Decimal("0"),
                non_emi_rounded_accrued=Decimal("0"),
                total_rounded=Decimal("20.45"),
            ),
        )

    @patch.object(interest_application, "_get_interest_to_apply")
    @patch.object(interest_application.utils, "get_parameter")
    def test_get_interest_to_apply_wrapper_without_fetched_args(
        self,
        mock_get_parameter: MagicMock,
        mock_get_interest_to_apply: MagicMock,
    ):
        mock_get_interest_to_apply.return_value = sentinel.interest_amounts
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.parameters)
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID: SentinelBalancesObservation(
                    "effective_datetime_accrual"
                ),
                interest_application.ACCRUED_INTEREST_ONE_MONTH_AGO_FETCHER_ID: (
                    SentinelBalancesObservation("one_month_ago_accrual")
                ),
            }
        )

        self.assertEqual(
            interest_application.get_interest_to_apply(
                vault=mock_vault,
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
            ),
            sentinel.interest_amounts,
        )

        mock_get_interest_to_apply.assert_called_once_with(
            balances_at_application=sentinel.balances_effective_datetime_accrual,
            balances_one_repayment_period_ago=sentinel.balances_one_month_ago_accrual,
            denomination=sentinel.denomination,
            application_precision=2,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )

    @patch.object(interest_application, "_get_interest_to_apply")
    def test_get_interest_to_apply_wrapper_with_fetched_args(
        self,
        mock_get_interest_to_apply: MagicMock,
    ):
        mock_get_interest_to_apply.return_value = sentinel.interest_amounts

        self.assertEqual(
            interest_application.get_interest_to_apply(
                vault=sentinel.vault,
                effective_datetime=sentinel.effective_datetime,
                previous_application_datetime=sentinel.previous_application_datetime,
                balances_at_application=sentinel.balances_at_application,
                balances_one_repayment_period_ago=sentinel.balances_one_repayment_period_ago,
                denomination=sentinel.denomination,
                application_precision=2,
            ),
            sentinel.interest_amounts,
        )

        mock_get_interest_to_apply.assert_called_once_with(
            balances_at_application=sentinel.balances_at_application,
            balances_one_repayment_period_ago=sentinel.balances_one_repayment_period_ago,
            denomination=sentinel.denomination,
            application_precision=2,
            effective_datetime=sentinel.effective_datetime,
            previous_application_datetime=sentinel.previous_application_datetime,
        )


class RepayAccruedInterestTest(InterestApplicationTestCommon):
    common_parameters: dict[str, str] = {
        "denomination": sentinel.denomination,
        interest_application.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: sentinel.receivable,
        interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: sentinel.received,
        interest_application.PARAM_APPLICATION_PRECISION: "2",
    }

    effective_datetime_balances = BalanceDefaultDict(
        mapping={
            ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("20.4469")),
        }
    )

    def test_repay_accrued_interest_with_0_repayment_amount(self):
        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=sentinel.vault, repayment_amount=Decimal("0")
            ),
            [],
        )

    def test_repay_accrued_interest_with_negative_repayment_amount(self):
        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=sentinel.vault, repayment_amount=Decimal("-1")
            ),
            [],
        )

    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_no_accrued_interest(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=sentinel.vault,
                repayment_amount=Decimal("10"),
                balances=BalanceDefaultDict(
                    mapping={
                        ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("0")),
                    }
                ),
            ),
            [],
        )

    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_0_rounded_accrued_interest(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=sentinel.vault,
                repayment_amount=Decimal("10"),
                balances=BalanceDefaultDict(
                    mapping={
                        ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("0.001")),
                    }
                ),
            ),
            [],
        )

    @patch.object(interest_application.accruals, "accrual_application_postings")
    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_rounded_interest_equal_to_repayment(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_accrual_application_postings.return_value = [sentinel.apply_posting]

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=mock_vault,
                repayment_amount=Decimal("1.01"),
                balances=BalanceDefaultDict(
                    mapping={
                        ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("1.01234")),
                    }
                ),
            ),
            [sentinel.apply_posting],
        )

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01234"),
            accrual_customer_address=interest_application.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=interest_application.DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application.accruals, "accrual_application_postings")
    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_rounded_interest_less_than_repayment(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_accrual_application_postings.return_value = [sentinel.apply_posting]

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=mock_vault,
                repayment_amount=Decimal("10"),
                balances=BalanceDefaultDict(
                    mapping={
                        ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("1.01234")),
                    }
                ),
            ),
            [sentinel.apply_posting],
        )

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01234"),
            accrual_customer_address=interest_application.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=interest_application.DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application.accruals, "accrual_application_postings")
    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_interest_over_repayment(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_accrual_application_postings.return_value = [sentinel.apply_posting]

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=mock_vault,
                repayment_amount=Decimal("1.00"),
                balances=BalanceDefaultDict(
                    mapping={
                        ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("1.01234")),
                    }
                ),
            ),
            [sentinel.apply_posting],
        )

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.00"),
            accrual_amount=Decimal("1.00"),
            accrual_customer_address=interest_application.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=interest_application.DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )

    @patch.object(interest_application.accruals, "accrual_application_postings")
    @patch.object(interest_application.utils, "get_parameter")
    def test_repay_accrued_interest_with_default_args(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_application_postings: MagicMock,
    ):
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                interest_application.ACCRUED_INTEREST_EFF_FETCHER_ID: BalancesObservation(
                    balances=BalanceDefaultDict(
                        mapping={
                            ACCRUED_RECEIVABLE_COORDINATE: Balance(net=Decimal("1.01234")),
                        }
                    )
                ),
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=self.common_parameters)
        mock_accrual_application_postings.return_value = [sentinel.apply_posting]

        self.assertListEqual(
            interest_application.repay_accrued_interest(
                vault=mock_vault,
                repayment_amount=Decimal("1.01"),
            ),
            [sentinel.apply_posting],
        )

        mock_accrual_application_postings.assert_called_once_with(
            customer_account=mock_vault.account_id,
            denomination=sentinel.denomination,
            application_amount=Decimal("1.01"),
            accrual_amount=Decimal("1.01234"),
            accrual_customer_address=interest_application.ACCRUED_INTEREST_RECEIVABLE,
            accrual_internal_account=sentinel.receivable,
            application_customer_address=interest_application.DEFAULT_ADDRESS,
            application_internal_account=sentinel.received,
            payable=False,
        )
