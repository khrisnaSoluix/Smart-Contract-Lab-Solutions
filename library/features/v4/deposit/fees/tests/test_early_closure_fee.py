# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.common.fetchers as fetchers
import library.features.v4.deposit.fees.early_closure_fee as early_closure_fee
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    BalancesObservation,
    CustomInstruction,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelPosting,
)

UTC_ZONE = ZoneInfo("UTC")
DEFAULT_DATETIME = datetime(2019, 1, 1, tzinfo=UTC_ZONE)
DENOMINATION = "MYR"
EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "EARLY_CLOSURE_FEE_INCOME"
ACCOUNT_TYPE = sentinel.account_type


class EarlyClosureFeeTest(FeatureTest):
    def account_balances(
        self,
        dt=DEFAULT_DATETIME,
        denomination=DENOMINATION,
        early_closure_fee_debit=Decimal("0"),
        early_closure_fee_credit=Decimal("0"),
    ):
        """
        Creates balances for the relevant addresses to track early closure fee charged
        !!!!!WARNING!!!!! the early_closure_fee_x parameters explicitly let you set the credit and
        debit attributes as the contract behaviour needs the tester to be able to have net 0 value
        but non-zero debit and credit

        :param early_closure_fee_debit: the debit amount for the early_closure_fee address
        :param early_closure_fee_credit: the credit amount for the early_closure_fee address
        """

        balance_dict = {
            self.balance_coordinate(
                denomination=denomination,
                account_address=early_closure_fee.DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
            ): self.balance(
                debit=early_closure_fee_debit,
                credit=early_closure_fee_credit,
            ),
        }

        balances_observation = BalancesObservation(
            balances=BalanceDefaultDict(mapping=balance_dict),
            value_datetime=dt,
        )

        return balances_observation

    @patch.object(early_closure_fee.fees, "fee_postings")
    @patch.object(early_closure_fee.utils, "get_parameter")
    def test_early_closure_fee_not_applied_if_closed_after_closure_days(
        self, mock_get_parameter: MagicMock, mock_fee_postings: MagicMock
    ):
        effective_time = datetime(2019, 1, 9, tzinfo=UTC_ZONE)
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "early_closure_fee": Decimal("10"),
                "early_closure_days": Decimal("7"),
                "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
            }
        )
        balances_observation_fetchers_mapping = {
            fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: self.account_balances(
                dt=effective_time,
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        results = early_closure_fee.apply_fees(
            vault=mock_vault,
            denomination=DENOMINATION,
            effective_datetime=effective_time,
            account_type=ACCOUNT_TYPE,
        )

        self.assertEqual(len(results), 0)
        mock_get_parameter.assert_called_with(mock_vault, "early_closure_fee_income_account")
        mock_fee_postings.assert_not_called()

    @patch.object(early_closure_fee.utils, "standard_instruction_details")
    @patch.object(early_closure_fee, "_update_closure_fee_tracker")
    @patch.object(early_closure_fee.fees, "fee_postings")
    @patch.object(early_closure_fee.utils, "get_parameter")
    def test_early_closure_fee_applied_if_closed_within_closure_days(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_update_closure_fee_tracker: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        effective_time = datetime(2019, 1, 8, tzinfo=UTC_ZONE)
        early_closure_fee_amount = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": DENOMINATION,
                "early_closure_fee": early_closure_fee_amount,
                "early_closure_days": Decimal("7"),
                "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
            }
        )
        balances_observation_fetchers_mapping = {
            fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: self.account_balances(
                dt=effective_time,
            )
        }
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping
        )

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_update_closure_fee_tracker.return_value = [
            SentinelPosting("fee_posting_3"),
            SentinelPosting("fee_posting_4"),
        ]

        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = early_closure_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=effective_time,
            account_type=ACCOUNT_TYPE,
        )

        expected = [
            CustomInstruction(
                postings=[
                    SentinelPosting("fee_posting_1"),
                    SentinelPosting("fee_posting_2"),
                    SentinelPosting("fee_posting_3"),
                    SentinelPosting("fee_posting_4"),
                ],
                instruction_details=mock_standard_instruction_details.return_value,
                override_all_restrictions=True,
            )
        ]

        self.assertListEqual(results, expected)
        mock_fee_postings.assert_called_once()
        mock_update_closure_fee_tracker.assert_called_once()
        mock_standard_instruction_details.assert_called()

    @patch.object(early_closure_fee.utils, "standard_instruction_details")
    @patch.object(early_closure_fee, "_update_closure_fee_tracker")
    @patch.object(early_closure_fee.fees, "fee_postings")
    @patch.object(early_closure_fee.utils, "get_parameter")
    def test_early_closure_fee_no_fetching_applied_if_closed_within_closure_days(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_postings: MagicMock,
        mock_update_closure_fee_tracker: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        effective_time = datetime(2019, 1, 8, tzinfo=UTC_ZONE)
        early_closure_fee_amount = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "early_closure_fee": early_closure_fee_amount,
                "early_closure_days": Decimal("7"),
                "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
            }
        )

        mock_vault = self.create_mock()

        mock_fee_postings.return_value = [
            SentinelPosting("fee_posting_1"),
            SentinelPosting("fee_posting_2"),
        ]
        mock_update_closure_fee_tracker.return_value = [
            SentinelPosting("fee_posting_3"),
            SentinelPosting("fee_posting_4"),
        ]

        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = early_closure_fee.apply_fees(
            vault=mock_vault,
            denomination=DENOMINATION,
            effective_datetime=effective_time,
            account_type=ACCOUNT_TYPE,
            balances=self.account_balances().balances,
        )

        expected = [
            CustomInstruction(
                postings=[
                    SentinelPosting("fee_posting_1"),
                    SentinelPosting("fee_posting_2"),
                    SentinelPosting("fee_posting_3"),
                    SentinelPosting("fee_posting_4"),
                ],
                instruction_details=mock_standard_instruction_details.return_value,
                override_all_restrictions=True,
            )
        ]

        self.assertListEqual(results, expected)
        mock_fee_postings.assert_called_once()
        mock_update_closure_fee_tracker.assert_called_once()
        mock_standard_instruction_details.assert_called()

    @patch.object(early_closure_fee.fees, "fee_postings")
    @patch.object(early_closure_fee.utils, "get_parameter")
    def test_early_closure_fee_not_applied_if_already_applied(
        self, mock_get_parameter: MagicMock, mock_fee_postings: MagicMock
    ):
        effective_time = datetime(2019, 1, 8, tzinfo=UTC_ZONE)
        early_closure_fee_amount = Decimal("10")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "early_closure_fee": early_closure_fee_amount,
                "early_closure_days": Decimal("7"),
                "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
            }
        )

        balances_observation_fetchers_mapping = {
            fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: self.account_balances(
                dt=effective_time,
                early_closure_fee_debit=early_closure_fee_amount,
                early_closure_fee_credit=early_closure_fee_amount,
            )
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
        )

        results = early_closure_fee.apply_fees(
            vault=mock_vault,
            denomination=DENOMINATION,
            effective_datetime=effective_time,
            account_type=ACCOUNT_TYPE,
        )

        self.assertEqual(len(results), 0)
        mock_get_parameter.assert_called_with(mock_vault, "early_closure_fee_income_account")
        mock_fee_postings.assert_not_called()

    @patch.object(early_closure_fee.fees, "fee_postings")
    @patch.object(early_closure_fee.utils, "get_parameter")
    def test_early_closure_fee_not_applied_if_zero_fee(
        self, mock_get_parameter: MagicMock, mock_fee_postings: MagicMock
    ):
        effective_time = datetime(2019, 1, 8, tzinfo=UTC_ZONE)
        early_closure_fee_amount = Decimal("0")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "early_closure_fee": early_closure_fee_amount,
                "early_closure_days": Decimal("7"),
                "early_closure_fee_income_account": EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
            }
        )

        balances_observation_fetchers_mapping = {
            fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: self.account_balances(
                dt=effective_time,
                early_closure_fee_debit=early_closure_fee_amount,
                early_closure_fee_credit=early_closure_fee_amount,
            )
        }

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
        )

        results = early_closure_fee.apply_fees(
            vault=mock_vault,
            denomination=DENOMINATION,
            effective_datetime=effective_time,
            account_type=ACCOUNT_TYPE,
        )

        self.assertEqual(len(results), 0)
        mock_get_parameter.assert_called_with(mock_vault, "early_closure_fee_income_account")
        mock_fee_postings.assert_not_called()


class HelpersTest(FeatureTest):
    @patch.object(early_closure_fee.utils, "create_postings")
    def test_update_closure_fee_tracker(self, mock_tracker_postings: MagicMock):

        mock_tracker_postings.return_value = [SentinelCustomInstruction("create_postings")]
        results = early_closure_fee._update_closure_fee_tracker(
            denomination=sentinel.denomination,
            account_id=sentinel.account_id,
            account_tracker_address=sentinel.account_tracker_address,
        )

        self.assertEqual(results, [SentinelCustomInstruction("create_postings")])
        mock_tracker_postings.assert_called_once()
