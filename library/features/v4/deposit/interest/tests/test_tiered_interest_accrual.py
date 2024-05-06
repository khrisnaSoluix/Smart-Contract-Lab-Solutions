# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.interest.tiered_interest_accrual as tiered_interest_accrual
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)

ACCRUED_INTEREST_PAYABLE_ACCOUNT = (
    tiered_interest_accrual.interest_accrual_common.PARAM_ACCRUED_INTEREST_PAYABLE_ACCOUNT
)
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = (
    tiered_interest_accrual.interest_accrual_common.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT  # noqa: E501
)
ACCRUED_INTEREST_RECEIVABLE = tiered_interest_accrual.ACCRUED_INTEREST_RECEIVABLE
ACCRUED_INTEREST_PAYABLE = tiered_interest_accrual.ACCRUED_INTEREST_PAYABLE


@patch.object(tiered_interest_accrual, "get_tiered_accrual_amount")
@patch.object(tiered_interest_accrual, "get_accrual_capital")
@patch.object(tiered_interest_accrual.accruals, "accrual_custom_instruction")
@patch.object(tiered_interest_accrual.utils, "get_parameter")
class TestInterestAccrual(FeatureTest):
    common_params = {
        "denomination": sentinel.denomination,
        ACCRUED_INTEREST_PAYABLE_ACCOUNT: "payable_acc",
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "receivable_acc",
        tiered_interest_accrual.interest_accrual_common.PARAM_DAYS_IN_YEAR: "365",
        tiered_interest_accrual.interest_accrual_common.PARAM_ACCRUAL_PRECISION: 5,
        tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: sentinel.tiered_rates,
    }

    def test_accrue_interest_with_positive_accrual(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_cis: MagicMock,
        mock_accrual_capital: MagicMock,
        mock_tiered_accrual_amount: MagicMock,
    ):
        mock_tiered_accrual_amount.return_value = Decimal("1"), "some description"
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.common_params)
        mock_accrual_cis.return_value = [sentinel.accrual_cis]
        mock_accrual_capital.return_value = sentinel.accrual_capital
        mock_vault = self.create_mock()

        self.assertListEqual(
            tiered_interest_accrual.accrue_interest(
                vault=mock_vault, effective_datetime=DEFAULT_DATETIME
            ),
            [sentinel.accrual_cis],
        )

        mock_accrual_capital.assert_called_once_with(mock_vault)

        mock_tiered_accrual_amount.assert_called_once_with(
            effective_balance=sentinel.accrual_capital,
            effective_datetime=DEFAULT_DATETIME,
            tiered_interest_rates=sentinel.tiered_rates,
            days_in_year="365",
            precision=5,
        )

        mock_accrual_cis.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_interest_accrual.ACCRUED_INTEREST_PAYABLE,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account="payable_acc",
            payable=True,
            instruction_details={
                "description": "some description",
                "event": tiered_interest_accrual.ACCRUAL_EVENT,
            },
        )

    def test_accrue_interest_with_negative_accrual(
        self,
        mock_get_parameter: MagicMock,
        mock_accrual_cis: MagicMock,
        mock_accrual_capital: MagicMock,
        mock_tiered_accrual_amount: MagicMock,
    ):
        mock_tiered_accrual_amount.return_value = Decimal("-1"), "some description"
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.common_params)
        mock_accrual_cis.return_value = [sentinel.accrual_cis]
        mock_accrual_capital.return_value = sentinel.accrual_capital
        mock_vault = self.create_mock()

        self.assertListEqual(
            tiered_interest_accrual.accrue_interest(
                vault=mock_vault, effective_datetime=DEFAULT_DATETIME
            ),
            [sentinel.accrual_cis],
        )

        mock_accrual_capital.assert_called_once_with(mock_vault)

        mock_tiered_accrual_amount.assert_called_once_with(
            effective_balance=sentinel.accrual_capital,
            effective_datetime=DEFAULT_DATETIME,
            tiered_interest_rates=sentinel.tiered_rates,
            days_in_year="365",
            precision=5,
        )

        mock_accrual_cis.assert_called_once_with(
            customer_account=mock_vault.account_id,
            customer_address=tiered_interest_accrual.ACCRUED_INTEREST_RECEIVABLE,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account="receivable_acc",
            payable=False,
            instruction_details={
                "description": "some description",
                "event": tiered_interest_accrual.ACCRUAL_EVENT,
            },
        )


class TestTieredAccrualAmount(FeatureTest):
    @patch.object(tiered_interest_accrual.utils, "yearly_to_daily_rate")
    @patch.object(tiered_interest_accrual, "determine_tier_balance")
    def test_accrue_interest_with_multiple_tiers(
        self, mock_determine_tier_balance: MagicMock, mock_yearly_to_daily_rate: MagicMock
    ):
        mock_determine_tier_balance.side_effect = [
            Decimal("4"),
            Decimal("6"),
            Decimal("90"),
            Decimal("0"),
        ]
        # last tier has no balance, so no yearly->daily needed
        # made numbers == yearly rate for simplicity
        mock_yearly_to_daily_rate.side_effect = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]

        accrual_amount, description = tiered_interest_accrual.get_tiered_accrual_amount(
            effective_balance=Decimal("100"),
            effective_datetime=sentinel.effective_datetime,
            tiered_interest_rates={"0": "0.01", "4": "0.02", "10": "0.03", "1000": "0.04"},
            days_in_year=sentinel.days_in_year,
        )

        # 0.01 on 4, 0.02 on 6, 90 on 0.03
        self.assertEqual(accrual_amount, Decimal("2.86"))
        self.assertEqual(
            description,
            "Accrual on 4.00 at annual rate of 1.00%. Accrual on 6.00 at annual rate of 2.00%. "
            "Accrual on 90.00 at annual rate of 3.00%. ",
        )

        mock_determine_tier_balance.assert_has_calls(
            [
                call(effective_balance=Decimal(100), tier_min=Decimal("0"), tier_max=Decimal("4")),
                call(effective_balance=Decimal(100), tier_min=Decimal("4"), tier_max=Decimal("10")),
                call(
                    effective_balance=Decimal(100), tier_min=Decimal("10"), tier_max=Decimal("1000")
                ),
                call(effective_balance=Decimal(100), tier_min=Decimal("1000"), tier_max=None),
            ]
        )
        mock_yearly_to_daily_rate.assert_has_calls(
            [
                call(
                    effective_date=sentinel.effective_datetime,
                    yearly_rate=Decimal("0.01"),
                    days_in_year=sentinel.days_in_year,
                ),
                call(
                    effective_date=sentinel.effective_datetime,
                    yearly_rate=Decimal("0.02"),
                    days_in_year=sentinel.days_in_year,
                ),
                call(
                    effective_date=sentinel.effective_datetime,
                    yearly_rate=Decimal("0.03"),
                    days_in_year=sentinel.days_in_year,
                ),
            ]
        )


class DetermineTierBalance(FeatureTest):
    def test_normal_negative_tiers(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-5"), tier_max=Decimal("-4"), tier_min=Decimal("-10")
        )
        self.assertEqual(tier_balance, Decimal("-1"))

    def test_normal_negative_tiers_with_balance_at_max(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-4"), tier_max=Decimal("-4"), tier_min=Decimal("-10")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_normal_negative_tiers_with_balance_at_min(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-10"), tier_max=Decimal("-4"), tier_min=Decimal("-10")
        )
        self.assertEqual(tier_balance, Decimal("-6"))

    def test_normal_positive_tier(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("5"), tier_max=Decimal("10"), tier_min=Decimal("4")
        )
        self.assertEqual(tier_balance, Decimal("1"))

    def test_normal_positive_tier_with_balance_at_min(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("4"), tier_max=Decimal("10"), tier_min=Decimal("4")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_normal_positive_tier_with_balance_at_max(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("10"), tier_max=Decimal("10"), tier_min=Decimal("4")
        )
        self.assertEqual(tier_balance, Decimal("6"))

    def test_no_tiers_yields_zero(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("10")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_different_sign_min_max_tiers_yields_zero(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("10"), tier_min=Decimal("-1"), tier_max=Decimal("1")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_negative_tier_min_gt_negative_tier_max_yields_zero(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-5"), tier_max=Decimal("-10"), tier_min=Decimal("-4")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_positive_tier_min_gt_positive_tier_max_yields_zero(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("5"), tier_max=Decimal("4"), tier_min=Decimal("10")
        )
        self.assertEqual(tier_balance, Decimal("0"))

    def test_no_tier_min_and_negative_tier_max(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-15"), tier_max=Decimal("-10")
        )
        self.assertEqual(tier_balance, Decimal("-5"))

    def test_no_tier_min_and_positive_tier_max(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("4"), tier_max=Decimal("10")
        )
        self.assertEqual(tier_balance, Decimal("4"))

    def test_no_tier_max_and_negative_tier_min(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("-15"), tier_min=Decimal("-10")
        )
        self.assertEqual(tier_balance, Decimal("-10"))

    def test_no_tier_max_and_positive_tier_min(self):
        tier_balance = tiered_interest_accrual.determine_tier_balance(
            effective_balance=Decimal("15"), tier_min=Decimal("10")
        )
        self.assertEqual(tier_balance, Decimal("5"))
