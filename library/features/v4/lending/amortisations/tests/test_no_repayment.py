# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.amortisations.no_repayment as no_repayment
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)


class NoRepaymentCommon(FeatureTest):
    default_denomination = "GBP"
    tside = Tside.ASSET


@patch.object(no_repayment.utils, "get_parameter")
class TermDetailsTest(NoRepaymentCommon):
    common_params = {"total_repayment_count": "10", "denomination": sentinel.denomination}

    def test_term_details(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        mock_vault = self.create_mock()
        result = no_repayment.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(months=4),
            use_expected_term=sentinel.use_expected_term,
        )

        self.assertEqual(result, (4, 6))

    def test_historical_effective_datetime(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        mock_vault = self.create_mock()
        result = no_repayment.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME - relativedelta(months=4),
            use_expected_term=sentinel.use_expected_term,
        )

        self.assertEqual(result, (0, 10))

    def test_effective_datetime_after_set_term(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(TermDetailsTest.common_params)

        mock_vault = self.create_mock()
        result = no_repayment.term_details(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME + relativedelta(years=1),
            use_expected_term=sentinel.use_expected_term,
        )

        self.assertEqual(result, (10, 0))


class CalculateEmi(FeatureTest):
    def test_calculate_emi(
        self,
    ):
        result = no_repayment.calculate_emi(
            vault=sentinel.MockVault,
            effective_datetime=sentinel.effective_datetime,
            principal_amount=Decimal("1234"),
            principal_adjustments=None,
        )

        self.assertEqual(result, Decimal("0"))


class IsNoRepaymentLoanTest(FeatureTest):
    def test_is_no_repayment_loan_true(self):
        self.assertEqual(no_repayment.is_no_repayment_loan("NO_REPAYMENT"), True)

    def test_is_no_repayment_lower_case_true(self):
        self.assertEqual(no_repayment.is_no_repayment_loan("no_repayment"), True)

    def test_is_no_repayment_loan_false(self):
        self.assertEqual(no_repayment.is_no_repayment_loan("other"), False)


@patch.object(no_repayment.utils, "get_parameter")
class GetBalloonPaymentDatetimeTest(FeatureTest):
    test_date = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))

    def test_zero_offset_days(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                no_repayment.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                "balloon_payment_days_delta": 0,
            }
        )
        mock_vault = self.create_mock(creation_date=self.test_date)
        expected_result = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))

        result = no_repayment.get_balloon_payment_datetime(vault=mock_vault)

        self.assertEqual(result, expected_result)

    def test_non_zero_offset_days(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                no_repayment.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: "12",
                "balloon_payment_days_delta": 10,
            }
        )
        mock_vault = self.create_mock(creation_date=self.test_date)
        expected_result = datetime(2020, 1, 11, tzinfo=ZoneInfo("UTC"))

        result = no_repayment.get_balloon_payment_datetime(vault=mock_vault)

        self.assertEqual(result, expected_result)
