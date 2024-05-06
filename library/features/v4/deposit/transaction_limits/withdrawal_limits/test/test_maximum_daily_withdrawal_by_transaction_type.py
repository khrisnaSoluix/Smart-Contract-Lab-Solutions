# standard libs
from datetime import timedelta
from decimal import Decimal
from json import dumps
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.transaction_limits.withdrawal_limits.maximum_daily_withdrawal_by_transaction_type as feature  # noqa E501
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.transaction_limits.test.test_common_transaction_limit import (
    CTX_ID_1,
    CTX_ID_2,
    CUT_OFF_DATE,
    DEFAULT_ACCOUNT,
    CommonTransactionLimitTest,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ClientTransaction,
    PrePostingHookArguments,
    Rejection,
    RejectionReason,
)

DEFAULT_INSTRUCTION_DETAILS = {feature.INSTRUCTION_DETAILS_KEY: "ATM"}
PARAM_DAILY_LIMIT = feature.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION
PARAM_TIERED_LIMIT = feature.PARAM_TIERED_DAILY_WITHDRAWAL_LIMIT


@patch.object(feature, "_get_limit_per_transaction_type")
@patch.object(feature.client_transaction_utils, "filter_client_transactions")
@patch.object(feature.client_transaction_utils, "sum_client_transactions")
@patch.object(feature.account_tiers, "get_account_tier")
@patch.object(feature.utils, "get_parameter")
class TestLimitValidation(CommonTransactionLimitTest):
    mocked_parameters = {
        "daily_withdrawal_limit_by_transaction_type": {"ATM": "500"},
        "tiered_daily_withdrawal_limits": {
            "UPPER_TIER": {"ATM": "5000"},
            "MIDDLE_TIER": {"ATM": "2000"},
            "LOWER_TIER": {"ATM": "1500"},
        },
    }

    def test_limit_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("501"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                )
            ],
            tside=self.tside,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.mocked_parameters)
        mock_get_limit_per_transaction_type.return_value = {"ATM": "500"}
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_sum_client_transactions.side_effect = [(0, 501), (0, 0)]
        mock_filter_client_transactions.side_effect = [{CTX_ID_1: proposed_ctx}, {}]
        mock_vault = self.create_mock(
            client_transactions_mapping={"EFFECTIVE_DATE_POSTINGS_FETCHER": {}}
        )

        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily ATM withdrawal limit of "
            f"500 {DEFAULT_DENOMINATION} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        # call to function
        result = feature.validate(
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
        )

        # assertions
        self.assertEqual(result, expected_rejection)
        mock_sum_client_transactions.assert_has_calls(
            [
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions={CTX_ID_1: proposed_ctx},
                    denomination="GBP",
                ),
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions={},
                    denomination="GBP",
                ),
            ]
        )
        mock_filter_client_transactions.assert_has_calls(
            [
                call(
                    client_transactions={CTX_ID_1: proposed_ctx},
                    client_transaction_ids_to_ignore=[""],
                    denomination="GBP",
                    key=feature.INSTRUCTION_DETAILS_KEY,
                    value="ATM",
                ),
                call(
                    client_transactions={},
                    client_transaction_ids_to_ignore=[""],
                    denomination="GBP",
                    key=feature.INSTRUCTION_DETAILS_KEY,
                    value="ATM",
                ),
            ]
        )

    def test_limit_met(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("300"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                ),
            ],
            tside=self.tside,
        )

        current_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_2,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("200"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                ),
            ],
            tside=self.tside,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.mocked_parameters)
        mock_get_limit_per_transaction_type.return_value = {"ATM": "500"}
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_sum_client_transactions.side_effect = [(0, 300), (0, 200)]
        mock_filter_client_transactions.side_effect = [
            {CTX_ID_1: proposed_ctx},
            {CTX_ID_2: current_ctx},
        ]

        # call to function
        result = feature.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
            effective_date_client_transactions={CTX_ID_2: current_ctx},
        )

        # assertions
        self.assertIsNone(result)

    def test_limit_not_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("100"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                )
            ],
            tside=self.tside,
        )
        current_ctx_dict = {
            CTX_ID_2: ClientTransaction(
                client_transaction_id=CTX_ID_2,
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("200"),
                        value_datetime=value_datetime,
                        instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                    )
                ],
                tside=self.tside,
            ),
            "CTX_ID_3": ClientTransaction(
                client_transaction_id="CTX_ID_3",
                account_id=DEFAULT_ACCOUNT,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("800"),
                        value_datetime=value_datetime,
                    )
                ],
                tside=self.tside,
            ),
        }

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(self.mocked_parameters)
        mock_get_limit_per_transaction_type.return_value = {"ATM": "500"}
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_sum_client_transactions.side_effect = [(0, 100), (0, 200)]
        mock_filter_client_transactions.side_effect = [{CTX_ID_1: proposed_ctx}, current_ctx_dict]

        # call to function
        result = feature.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
            effective_date_client_transactions=current_ctx_dict,
        )

        # assertions
        self.assertIsNone(result)

    def test_limit_by_tier_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("500"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                )
            ],
            tside=self.tside,
        )
        current_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_2,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1100"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                ),
            ],
            tside=self.tside,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                **self.mocked_parameters,
                "daily_withdrawal_limit_by_transaction_type": {"ATM": "2000"},
            }
        )
        mock_get_limit_per_transaction_type.return_value = {"ATM": "1500"}
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_sum_client_transactions.side_effect = [(0, 500), (0, 1100)]
        mock_filter_client_transactions.side_effect = [
            {CTX_ID_1: proposed_ctx},
            {CTX_ID_2: current_ctx},
        ]

        # call to function
        result = feature.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
            effective_date_client_transactions={CTX_ID_2: current_ctx},
        )

        expected_rejection = Rejection(
            message=f"Transactions would cause the maximum daily ATM withdrawal limit of "
            f"1500 {DEFAULT_DENOMINATION} to be exceeded.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        # assertions
        self.assertEqual(result, expected_rejection)

    def test_no_withdrawal_proposed(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        # mocks
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**self.mocked_parameters, "denomination": "GBP"}
        )
        mock_get_limit_per_transaction_type.return_value = {"ATM": "500"}
        mock_filter_client_transactions.return_value = {}
        mock_vault = MagicMock()
        mock_vault.get_client_transactions.return_value = {}
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("501"),
                    value_datetime=CUT_OFF_DATE + timedelta(hours=1),
                )
            ],
            tside=self.tside,
        )

        # call to function
        feature_result = feature.validate(
            vault=mock_vault,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
        )

        # assertions
        self.assertIsNone(feature_result)
        mock_get_account_tier.assert_called_once()
        mock_get_parameter.assert_has_calls(
            [
                call(mock_vault, name="tiered_daily_withdrawal_limits", is_json=True),
                call(mock_vault, name="daily_withdrawal_limit_by_transaction_type", is_json=True),
            ]
        )

        mock_filter_client_transactions.assert_called_once_with(
            client_transactions={CTX_ID_1: proposed_ctx},
            client_transaction_ids_to_ignore=[""],
            denomination="GBP",
            key=feature.INSTRUCTION_DETAILS_KEY,
            value="ATM",
        )
        mock_sum_client_transactions.assert_not_called()

    def test_transaction_type_not_in_tiered_limits(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("501"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                )
            ],
            tside=self.tside,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {**self.mocked_parameters, "daily_withdrawal_limit_by_transaction_type": {"X": "500"}}
        )
        mock_get_limit_per_transaction_type.return_value = {"ATM": "500", "X": "500"}
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_sum_client_transactions.side_effect = [(501, 0), (0, 0)]
        mock_filter_client_transactions.side_effect = [{CTX_ID_1: proposed_ctx}, {}, {}]
        mock_vault = self.create_mock(
            client_transactions_mapping={"EFFECTIVE_DATE_POSTINGS_FETCHER": {}}
        )

        # call to function
        result = feature.validate(
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
        )

        # assertions
        self.assertIsNone(result)
        mock_filter_client_transactions.assert_has_calls(
            [
                call(
                    client_transactions={CTX_ID_1: proposed_ctx},
                    client_transaction_ids_to_ignore=[""],
                    denomination="GBP",
                    key=feature.INSTRUCTION_DETAILS_KEY,
                    value="ATM",
                ),
                call(
                    client_transactions={CTX_ID_1: proposed_ctx},
                    client_transaction_ids_to_ignore=[""],
                    denomination="GBP",
                    key=feature.INSTRUCTION_DETAILS_KEY,
                    value="X",
                ),
            ]
        )
        mock_sum_client_transactions.assert_has_calls(
            [
                call(
                    cutoff_datetime=CUT_OFF_DATE,
                    client_transactions={CTX_ID_1: proposed_ctx},
                    denomination="GBP",
                )
            ]
        )

    def test_no_limit_set(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_sum_client_transactions: MagicMock,
        mock_filter_client_transactions: MagicMock,
        mock_get_limit_per_transaction_type: MagicMock,
    ):
        value_datetime = CUT_OFF_DATE + timedelta(hours=1)
        proposed_ctx = ClientTransaction(
            client_transaction_id=CTX_ID_1,
            account_id=DEFAULT_ACCOUNT,
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("501"),
                    value_datetime=value_datetime,
                    instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                )
            ],
            tside=self.tside,
        )

        # mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {"tiered_daily_withdrawal_limits": {}, "daily_withdrawal_limit_by_transaction_type": {}}
        )
        mock_get_account_tier.return_value = "LOWER_TIER"
        # call to function
        result = feature.validate(
            vault=sentinel.vault,
            denomination=DEFAULT_DENOMINATION,
            hook_arguments=PrePostingHookArguments(
                effective_datetime=CUT_OFF_DATE,
                posting_instructions=[],
                client_transactions={CTX_ID_1: proposed_ctx},
            ),
        )

        # assertions
        self.assertIsNone(result)
        mock_get_limit_per_transaction_type.assert_not_called()
        mock_filter_client_transactions.assert_not_called()
        mock_sum_client_transactions.assert_not_called()


@patch.object(feature.account_tiers, "get_account_tier")
@patch.object(feature.utils, "get_parameter")
class TestParameterChangeValidation(CommonTransactionLimitTest):
    def test_account_tier_not_in_tiered_daily_limits_returns_none(
        self, mock_get_parameter: MagicMock, mock_get_account_tier: MagicMock
    ):
        # mocks
        mock_get_account_tier.return_value = sentinel.tier
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {PARAM_TIERED_LIMIT: {"OTHER_TIER": {}}}
        )

        # call to function
        result = feature.validate_parameter_change(
            vault=sentinel.vault, proposed_parameter_value=dumps({"ATM": "11"})
        )

        # assertions
        self.assertIsNone(result)

    def test_validate_parameter_change_rejection(
        self, mock_get_parameter: MagicMock, mock_get_account_tier: MagicMock
    ):
        # mocks
        tiered_limit_dict = {"ATM": "10"}
        mock_get_account_tier.return_value = sentinel.tier
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {PARAM_TIERED_LIMIT: {sentinel.tier: tiered_limit_dict}, "denomination": "GBP"}
        )

        # call to function
        result = feature.validate_parameter_change(
            vault=sentinel.vault, proposed_parameter_value=dumps({"X": "1", "ATM": "11"})
        )
        expected_rejection = Rejection(
            message=f"Cannot update ATM transaction type limit for "
            "Maximum Daily Withdrawal Amount because 11 GBP exceeds "
            f"tiered limit of 10 GBP for active {sentinel.tier}.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        # assertions
        self.assertEqual(result, expected_rejection)

    def test_no_tiered_daily_limits_returns_none(
        self, mock_get_parameter: MagicMock, mock_get_account_tier: MagicMock
    ):
        # mocks
        mock_get_account_tier.return_value = sentinel.tier
        mock_get_parameter.side_effect = mock_utils_get_parameter({PARAM_TIERED_LIMIT: {}})
        # call to function
        result = feature.validate_parameter_change(
            vault=sentinel.vault, proposed_parameter_value=dumps({"X": "1", "ATM": "9"})
        )
        # assertions
        self.assertIsNone(result)

    def test_new_parameter_value_is_equal_to_tiered_limit_value(
        self, mock_get_parameter: MagicMock, mock_get_account_tier: MagicMock
    ):
        # mocks
        tiered_limit_dict = {"ATM": "10"}
        mock_get_account_tier.return_value = sentinel.tier
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {PARAM_TIERED_LIMIT: {sentinel.tier: tiered_limit_dict}, "denomination": "GBP"}
        )
        # call to function
        result = feature.validate_parameter_change(
            vault=sentinel.vault, proposed_parameter_value=dumps({"X": "1", "ATM": "10"})
        )
        # assertions
        self.assertIsNone(result)


class TestFeatureHelperFunctions(CommonTransactionLimitTest):
    def test_get_limit_per_transaction_type(self):
        # mocks
        tiered_limit_dict = {"ATM": "500"}
        daily_limit_dict = {"ATM": "501", "X": "1"}

        # call to function
        result = feature._get_limit_per_transaction_type(
            tiered_limit_dict=tiered_limit_dict, daily_limit_dict=daily_limit_dict
        )
        expected_dict = {"ATM": "500", "X": "1"}

        # assertions
        self.assertDictEqual(result, expected_dict)
