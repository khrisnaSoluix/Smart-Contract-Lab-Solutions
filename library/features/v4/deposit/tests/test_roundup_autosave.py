# standard libs
from decimal import Decimal
from json import dumps
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.deposit.roundup_autosave as feature
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
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


@patch.object(feature.utils, "get_parameter")
@patch.object(feature.utils, "str_to_bool")
class AutoSaveTest(FeatureTest):
    tside = Tside.LIABILITY
    mocked_parameters = {
        "denomination": DEFAULT_DENOMINATION,
        feature.PARAM_ROUNDUP_AUTOSAVE_ACTIVE: "True",
        feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: 100,
        feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT: "account",
        feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[ATM]"),
    }

    def test_return_no_posting_when_feature_is_disabled(
        self, mock_str_to_bool: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_str_to_bool.return_value = False
        mock_get_parameter.return_value = sentinel.param

        result = feature.apply(
            vault=sentinel.vault,
            postings=sentinel.postings,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertListEqual(result, [])

    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_no_posting_when_params_not_set(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_get_parameter.return_value = sentinel.param
        mock_are_optional_parameters_set.return_value = False

        result = feature.apply(
            vault=sentinel.vault,
            postings=sentinel.postings,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, [])
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=sentinel.vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )

    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_no_posting_when_no_balance(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        mock_get_available_balance.return_value = 0
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.mocked_parameters)

        result = feature.apply(
            vault=sentinel.vault,
            postings=sentinel.postings,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, [])
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=sentinel.vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_no_posting_for_non_matching_transaction_type(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        mock_get_available_balance.return_value = 100
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.mocked_parameters)

        postings = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("1000"),
                instruction_details={"TRANSACTION_TYPE": "DONATION"},
            )
        ]

        result = feature.apply(
            vault=sentinel.vault,
            postings=postings,  # type: ignore
            denomination=sentinel.denomination,
            balances=sentinel.balances,
        )
        self.assertEqual(result, [])
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=sentinel.vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=sentinel.denomination
        )

    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_no_posting_for_inbound_posting(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        mock_get_available_balance.return_value = 100
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[PURCHASE]"),
            }
        )

        postings = [
            self.inbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("1000"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            )
        ]

        result = feature.apply(
            vault=sentinel.vault,
            postings=postings,  # type: ignore
            denomination=DEFAULT_DENOMINATION,
            balances=sentinel.balances,
        )
        self.assertEqual(result, [])
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=sentinel.vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=DEFAULT_DENOMINATION
        )

    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_no_posting_when_balance_below_save_amount(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        # available balance is 5
        mock_get_available_balance.return_value = 5
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: 10,
                feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[PURCHASE]"),
            }
        )

        # Posting is 12 and available balance after posting is 5 and rounding amount is 10
        # the autosave amount for Posting of 12 is 8. 12's nearest multiple of 10 is 20. 20-12 = 8
        # account balance is 5 which is below 8 so no posting would be created.
        postings = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("12"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            )
        ]

        result = feature.apply(
            vault=sentinel.vault,
            postings=postings,  # type: ignore
            denomination=DEFAULT_DENOMINATION,
            balances=sentinel.balances,
        )
        self.assertEqual(result, [])
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=sentinel.vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=DEFAULT_DENOMINATION
        )

    @patch.object(feature.utils, "create_postings")
    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_posting_for_1_transaction_when_low_balance(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_create_postings: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        # available balance is 5
        mock_get_available_balance.return_value = 5
        mock_create_postings.return_value = [SentinelPosting("autosave_posting")]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: 10,
                feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[PURCHASE]"),
            }
        )

        postings = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("6"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("6"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
        ]

        # Posting is 12 and available balance after posting is 5 and rounding amount is 10
        # the autosave amount for Posting of 6 is 4. 6's nearest multiple of 10 is 10. 10-6 = 4
        # account balance is 5 so for first transaction autosave postings should be created
        # 2nd transaction should be ignored.

        mock_vault = self.create_mock()
        result = feature.apply(
            vault=mock_vault,
            postings=postings,  # type: ignore
            denomination=DEFAULT_DENOMINATION,
            balances=sentinel.balances,
        )

        instruction_details = (
            f"Roundup Autosave: {DEFAULT_DENOMINATION} 4 "
            f"using round up to {DEFAULT_DENOMINATION} 10 for transfer of "
            f"{DEFAULT_DENOMINATION} 6\n "
        )

        expected_result = [
            CustomInstruction(
                postings=[SentinelPosting("autosave_posting")],
                instruction_details={
                    "description": instruction_details,
                    "event": "ROUNDUP_AUTOSAVE",
                },
                override_all_restrictions=True,
            )
        ]
        self.assertEqual(result, expected_result)
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=mock_vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances, denomination=DEFAULT_DENOMINATION
        )

    @patch.object(feature.utils, "create_postings")
    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_posting_for_all_transaction(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_create_postings: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        # available balance is 6
        mock_get_available_balance.return_value = 6
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: 10,
                feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[PURCHASE]"),
            }
        )
        mock_create_postings.return_value = [SentinelPosting("autosave_posting")]

        postings = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("6"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("8"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
        ]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                feature.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        result = feature.apply(
            vault=mock_vault,
            postings=postings,  # type: ignore
        )

        instruction_details = (
            f"Roundup Autosave: {DEFAULT_DENOMINATION} 4 "
            f"using round up to {DEFAULT_DENOMINATION} 10 for transfer of "
            f"{DEFAULT_DENOMINATION} 6\n "
            f"Roundup Autosave: {DEFAULT_DENOMINATION} 2 "
            f"using round up to {DEFAULT_DENOMINATION} 10 for transfer of "
            f"{DEFAULT_DENOMINATION} 8\n "
        )
        expected_result = [
            CustomInstruction(
                postings=[SentinelPosting("autosave_posting"), SentinelPosting("autosave_posting")],
                instruction_details={
                    "description": instruction_details,
                    "event": "ROUNDUP_AUTOSAVE",
                },
                override_all_restrictions=True,
            ),
        ]
        self.assertEqual(result, expected_result)
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=mock_vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances_live_balances, denomination=DEFAULT_DENOMINATION
        )

    @patch.object(feature.utils, "create_postings")
    @patch.object(feature.utils, "get_available_balance")
    @patch.object(feature.utils, "are_optional_parameters_set")
    def test_return_posting_for_2_transactions_reject_1_when_low_balance(
        self,
        mock_are_optional_parameters_set: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_create_postings: MagicMock,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_str_to_bool.return_value = True
        mock_are_optional_parameters_set.return_value = True
        # available balance is 6
        mock_get_available_balance.return_value = 6
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT: 10,
                feature.PARAM_ROUNDUP_AUTOSAVE_TRANSACTION_TYPES: dumps("[PURCHASE]"),
            }
        )
        mock_create_postings.return_value = [SentinelPosting("autosave_posting")]

        postings = [
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("6"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("2"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
            self.outbound_hard_settlement(
                denomination=DEFAULT_DENOMINATION,
                amount=Decimal("8"),
                instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
            ),
        ]

        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                feature.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        result = feature.apply(
            vault=mock_vault,
            postings=postings,  # type: ignore
        )

        instruction_details = (
            f"Roundup Autosave: {DEFAULT_DENOMINATION} 4 "
            f"using round up to {DEFAULT_DENOMINATION} 10 for transfer of "
            f"{DEFAULT_DENOMINATION} 6\n "
            f"Roundup Autosave: {DEFAULT_DENOMINATION} 2 "
            f"using round up to {DEFAULT_DENOMINATION} 10 for transfer of "
            f"{DEFAULT_DENOMINATION} 8\n "
        )
        expected_result = [
            CustomInstruction(
                postings=[SentinelPosting("autosave_posting"), SentinelPosting("autosave_posting")],
                instruction_details={
                    "description": instruction_details,
                    "event": "ROUNDUP_AUTOSAVE",
                },
                override_all_restrictions=True,
            ),
        ]
        self.assertEqual(result, expected_result)
        mock_are_optional_parameters_set.assert_called_once_with(
            vault=mock_vault,
            parameters=[
                feature.PARAM_ROUNDUP_AUTOSAVE_ROUNDING_AMOUNT,
                feature.PARAM_ROUNDUP_AUTOSAVE_ACCOUNT,
            ],
        )
        mock_get_available_balance.assert_called_once_with(
            balances=sentinel.balances_live_balances, denomination=DEFAULT_DENOMINATION
        )
