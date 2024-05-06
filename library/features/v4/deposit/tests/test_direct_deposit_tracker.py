# standard libs
from decimal import Decimal
from json import dumps
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.direct_deposit_tracker as direct_deposit_tracker
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Posting, Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelPosting,
)


class GenerateTrackingInstructionsTest(FeatureTest):
    tside = Tside.LIABILITY

    @patch.object(direct_deposit_tracker.utils, "create_postings")
    @patch.object(direct_deposit_tracker.utils, "balance_at_coordinates")
    @patch.object(direct_deposit_tracker.utils, "get_parameter")
    def test_generate_tracking_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # construct values
        posting_instructions: direct_deposit_tracker.utils.PostingInstructionListAlias = [
            self.inbound_hard_settlement(
                amount=Decimal("1"),
                instruction_details={"type": "dummy"},
            ),
            self.inbound_hard_settlement(
                amount=Decimal("2"),
                instruction_details={"type": "direct_deposit"},
            ),
        ]
        postings: list[Posting] = [
            SentinelPosting("credit_to_tracking_address"),
            SentinelPosting("debit_to_internal_account"),
        ]
        expected_result = [
            CustomInstruction(
                postings=postings,
                instruction_details=direct_deposit_tracker.utils.standard_instruction_details(
                    description="Updating tracking balance with amount 2 GBP.",
                    event_type="GENERATE_DEPOSIT_TRACKING_INSTRUCTIONS",
                ),
            )
        ]

        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                direct_deposit_tracker.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("2")
        mock_create_postings.return_value = postings

        # run function
        result = direct_deposit_tracker.generate_tracking_instructions(
            vault=mock_vault,
            posting_instructions=posting_instructions,
        )

        # assertions
        self.assertListEqual(expected_result, result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name=direct_deposit_tracker.common_parameters.PARAM_DENOMINATION,
            at_datetime=None,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=posting_instructions[1].balances(),
            denomination=DEFAULT_DENOMINATION,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("2"),
            debit_account=mock_vault.account_id,
            debit_address=direct_deposit_tracker.common_addresses.INTERNAL_CONTRA,
            credit_account=mock_vault.account_id,
            credit_address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )

    def test_generate_tracking_instructions_no_matching_type(self):
        # construct values
        posting_instructions: direct_deposit_tracker.utils.PostingInstructionListAlias = [
            self.inbound_hard_settlement(
                amount=Decimal("1"),
                instruction_details={"type": "dummy"},
            )
        ]

        # construct mocks
        mock_vault = self.create_mock()

        # run function
        result = direct_deposit_tracker.generate_tracking_instructions(
            vault=mock_vault,
            posting_instructions=posting_instructions,
            denomination=DEFAULT_DENOMINATION,
        )

        # assertions
        self.assertListEqual([], result)


class ResetTrackingInstructionsTest(FeatureTest):
    @patch.object(direct_deposit_tracker.utils, "create_postings")
    @patch.object(direct_deposit_tracker.utils, "balance_at_coordinates")
    @patch.object(direct_deposit_tracker.utils, "get_parameter")
    def test_reset_tracking_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_create_postings: MagicMock,
    ):
        # construct values
        postings: list[Posting] = [
            SentinelPosting("credit_to_internal_account"),
            SentinelPosting("debit_to_tracking_address"),
        ]
        expected_result = [
            CustomInstruction(
                postings=postings,
                instruction_details=direct_deposit_tracker.utils.standard_instruction_details(
                    description="Resetting tracking balance to 0.",
                    event_type="RESET_DEPOSIT_TRACKING_INSTRUCTIONS",
                ),
            )
        ]

        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                direct_deposit_tracker.DIRECT_DEPOSIT_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                direct_deposit_tracker.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("1")
        mock_create_postings.return_value = postings

        # run function
        result = direct_deposit_tracker.reset_tracking_instructions(vault=mock_vault)

        # assertions
        self.assertListEqual(expected_result, result)
        mock_get_parameter.assert_called_once_with(
            vault=mock_vault,
            name=direct_deposit_tracker.common_parameters.PARAM_DENOMINATION,
            at_datetime=None,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("eod_balances").balances,
            address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )
        mock_create_postings.assert_called_once_with(
            amount=Decimal("1"),
            credit_account=mock_vault.account_id,
            credit_address=direct_deposit_tracker.common_addresses.INTERNAL_CONTRA,
            debit_account=mock_vault.account_id,
            debit_address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )

    @patch.object(direct_deposit_tracker.utils, "balance_at_coordinates")
    def test_reset_tracking_instructions_no_balance(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                direct_deposit_tracker.DIRECT_DEPOSIT_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod_balances"
                )
            }
        )
        mock_balance_at_coordinates.return_value = Decimal("0")

        # run function
        result = direct_deposit_tracker.reset_tracking_instructions(
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
        )

        # assertions
        self.assertListEqual([], result)
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("eod_balances").balances,
            address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )


class IsDepositTrackingAddressAboveThresholdTest(FeatureTest):
    @patch.object(direct_deposit_tracker.utils, "balance_at_coordinates")
    @patch.object(
        direct_deposit_tracker.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(direct_deposit_tracker.account_tiers, "get_account_tier")
    @patch.object(direct_deposit_tracker.utils, "get_parameter")
    def test_is_deposit_tracking_address_above_threshold(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                direct_deposit_tracker.DIRECT_DEPOSIT_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_threshold_by_tier": dumps({"LOWER_TIER": "100"}),
                direct_deposit_tracker.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("100")
        mock_balance_at_coordinates.return_value = Decimal("101")

        # run function
        result = direct_deposit_tracker._is_deposit_tracking_address_above_threshold(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        # assertions
        self.assertTrue(result)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    name="deposit_threshold_by_tier",
                    is_json=True,
                ),
                call(
                    vault=mock_vault,
                    name=direct_deposit_tracker.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
            ]
        )
        mock_get_account_tier.assert_called_once_with(mock_vault, DEFAULT_DATETIME)
        mock_get_tiered_parameter_value_based_on_account_tier.assert_called_once_with(
            tiered_parameter=dumps({"LOWER_TIER": "100"}),
            tier="LOWER_TIER",
            convert=Decimal,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("eod_balances").balances,
            address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )

    @patch.object(direct_deposit_tracker.utils, "balance_at_coordinates")
    @patch.object(
        direct_deposit_tracker.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(direct_deposit_tracker.account_tiers, "get_account_tier")
    @patch.object(direct_deposit_tracker.utils, "get_parameter")
    def test_is_deposit_tracking_address_above_threshold_no_deposits(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                direct_deposit_tracker.DIRECT_DEPOSIT_EOD_FETCHER_ID: SentinelBalancesObservation(
                    "eod_balances"
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_threshold_by_tier": dumps({"LOWER_TIER": "100"}),
                direct_deposit_tracker.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("100")
        mock_balance_at_coordinates.return_value = Decimal("0")

        # run function
        result = direct_deposit_tracker._is_deposit_tracking_address_above_threshold(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        # assertions
        self.assertFalse(result)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    name="deposit_threshold_by_tier",
                    is_json=True,
                ),
                call(
                    vault=mock_vault,
                    name=direct_deposit_tracker.common_parameters.PARAM_DENOMINATION,
                    at_datetime=None,
                ),
            ]
        )
        mock_get_account_tier.assert_called_once_with(mock_vault, DEFAULT_DATETIME)
        mock_get_tiered_parameter_value_based_on_account_tier.assert_called_once_with(
            tiered_parameter=dumps({"LOWER_TIER": "100"}),
            tier="LOWER_TIER",
            convert=Decimal,
        )
        mock_balance_at_coordinates.assert_called_once_with(
            balances=SentinelBalancesObservation("eod_balances").balances,
            address=direct_deposit_tracker.DIRECT_DEPOSIT_TRACKING_ADDRESS,
            denomination=DEFAULT_DENOMINATION,
        )

    @patch.object(direct_deposit_tracker.account_tiers, "get_account_tier")
    @patch.object(direct_deposit_tracker.utils, "get_parameter")
    def test_is_deposit_tracking_address_above_threshold_no_deposit_threshold(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "deposit_threshold_by_tier": dumps({"LOWER_TIER": "100"}),
                direct_deposit_tracker.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
            }
        )
        mock_get_account_tier.return_value = "UPPER_TIER"

        # run function
        result = direct_deposit_tracker._is_deposit_tracking_address_above_threshold(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        # assertions
        self.assertFalse(result)
        mock_get_parameter.assert_called_once_with(
            sentinel.vault,
            name="deposit_threshold_by_tier",
            is_json=True,
        )
        mock_get_account_tier.assert_called_once_with(sentinel.vault, DEFAULT_DATETIME)
