# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.fees.withdrawal.excess_fee as feature
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ClientTransaction,
    Tside,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
)

DEFAULT_INSTRUCTION_DETAILS = {"transaction_type": "ATM"}
POSTING_INTERVAL_FETCHER = {
    "MONTH_TO_EFFECTIVE_POSTINGS_FETCHER": [SentinelCustomInstruction("dummy_ci")]
}


@patch.object(feature.utils, "standard_instruction_details")
@patch.object(feature.fees, "fee_custom_instruction")
@patch.object(feature.client_transaction_utils, "extract_debits_by_instruction_details_key")
@patch.object(feature.utils, "get_parameter")
class TestApplyExcessFee(FeatureTest):
    tside = Tside.LIABILITY
    excess_fee_parameters = {
        "excess_fee": "10",
        "permitted_withdrawals": "1",
        "excess_fee_income_account": "EXCESS_FEE_INCOME_ACCOUNT",
        "excess_fee_monitored_transaction_type": "ATM",
    }

    def test_no_monitored_transaction_type_defined_no_excess_fee_applied(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        proposed_client_transactions = {sentinel.ctx_id_1: sentinel.ct_1}
        monthly_client_transactions = {sentinel.ctx_id_2: sentinel.ct_2}

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                **self.excess_fee_parameters.copy(),
                "excess_fee_monitored_transaction_type": "",
            }
        )
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [],
            [sentinel.ct_id_2_pi],
        ]
        mock_vault = self.create_mock()
        mock_vault.get_client_transactions.return_value = monthly_client_transactions

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_extract_debits_by_instruction_details_key.assert_not_called()

    def test_no_proposed_withdrawals_no_excess_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        proposed_client_transactions = {sentinel.ctx_id_1: sentinel.ct_1}
        monthly_client_transactions = {sentinel.ctx_id_2: sentinel.ct_2}

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.excess_fee_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [],
            [sentinel.ct_id_2_pi],
        ]
        mock_vault = self.create_mock()
        mock_vault.get_client_transactions.return_value = monthly_client_transactions

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            [
                call(
                    denomination="GBP",
                    client_transactions=proposed_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=DEFAULT_DATETIME,
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                )
            ]
        )

    def test_excess_fee_is_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        monthly_client_transactions = {sentinel.ctx_id_1: sentinel.ct_1}
        proposed_client_transactions = {sentinel.ctx_id_2: sentinel.ct_2}
        mock_parameters = {**self.excess_fee_parameters.copy(), "excess_fee": "0"}
        mock_get_parameter.side_effect = mock_utils_get_parameter(parameters=mock_parameters)
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [sentinel.ct_id_2_pi],
            [],
        ]
        mock_vault = self.create_mock()
        mock_vault.get_client_transactions.return_value = monthly_client_transactions

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            [
                call(
                    client_transactions=proposed_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME,
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                )
            ]
        )

    def test_proposed_withdrawals_no_excess_fee(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        monthly_client_transactions = {sentinel.ctx_id: sentinel.ct}
        proposed_client_transactions = {
            "ctx_id_2": ClientTransaction(
                client_transaction_id="ctx_id_2",
                account_id=ACCOUNT_ID,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("50"),
                        value_datetime=DEFAULT_DATETIME,
                        instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                    )
                ],
            )
        }

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.excess_fee_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [sentinel.ct_id_2_pi],
            [],
        ]
        mock_vault = MagicMock()
        mock_vault.get_client_transactions.return_value = {
            **monthly_client_transactions,
            **proposed_client_transactions,
        }

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            [
                call(
                    client_transactions=proposed_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME,
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
                call(
                    client_transactions={
                        **monthly_client_transactions,
                        **proposed_client_transactions,
                    },
                    client_transaction_ids_to_ignore=list(proposed_client_transactions.keys()),
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME
                    + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0),
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
            ]
        )

    def test_proposed_withdrawals_above_permitted_limit(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        monthly_client_transactions = {
            "ctx_id_1": ClientTransaction(
                client_transaction_id="ctx_id_1",
                account_id=ACCOUNT_ID,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("50"),
                        value_datetime=DEFAULT_DATETIME,
                        instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                    )
                ],
            )
        }
        proposed_client_transactions = {
            "ctx_id_2": ClientTransaction(
                client_transaction_id="ctx_id_2",
                account_id=ACCOUNT_ID,
                posting_instructions=[
                    self.outbound_hard_settlement(
                        amount=Decimal("50"),
                        value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
                        instruction_details=DEFAULT_INSTRUCTION_DETAILS,
                    )
                ],
            )
        }

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.excess_fee_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [sentinel.ct_id_2_pi],
            [sentinel.ct_id_1_pi],
        ]
        mock_vault = MagicMock()
        mock_vault.get_client_transactions.return_value = {
            **monthly_client_transactions,
            **proposed_client_transactions,
        }
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("excess_fee")]

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [SentinelCustomInstruction("excess_fee")])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination="GBP",
            amount=Decimal("10"),
            internal_account="EXCESS_FEE_INCOME_ACCOUNT",
            instruction_details=sentinel.instruction_details,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Proposed withdrawals exceeded permitted limit by 1",
            event_type="APPLY_EXCESS_FEES",
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            [
                call(
                    client_transactions=proposed_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME,
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
                call(
                    client_transactions={
                        **monthly_client_transactions,
                        **proposed_client_transactions,
                    },
                    client_transaction_ids_to_ignore=list(proposed_client_transactions.keys()),
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME
                    + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0),
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
            ]
        )

    def test_monthly_withdrawals_above_permitted_limit(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # setup mocks
        monthly_client_transactions = {
            "CTX_ID_1": sentinel.ct_1,
            "CTX_ID_2": sentinel.ct_2,
            "CTX_ID_3": sentinel.ct_3,
            "CTX_ID_4": sentinel.ct_4,
        }
        proposed_client_transactions = {
            "CTX_ID_3": sentinel.ct_3,
            "CTX_ID_4": sentinel.ct_4,
        }

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.excess_fee_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [sentinel.cti_id_3_pi, sentinel.cti_id_4_pi],
            [sentinel.cti_id_1_pi, sentinel.cti_id_2_pi],
        ]
        mock_vault = MagicMock()
        mock_vault.get_client_transactions.return_value = {
            "CTX_ID_1": sentinel.ct_1,
            "CTX_ID_2": sentinel.ct_2,
            "CTX_ID_3": sentinel.ct_3,
            "CTX_ID_4": sentinel.ct_4,
        }
        mock_standard_instruction_details.return_value = sentinel.instruction_details
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("excess_fee")]

        # feature call
        feature_results = feature.apply(
            vault=mock_vault,
            proposed_client_transactions=proposed_client_transactions,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            account_type=sentinel.account_type,
        )

        # assertions
        self.assertListEqual(feature_results, [SentinelCustomInstruction("excess_fee")])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination="GBP",
            amount=Decimal("20"),
            internal_account="EXCESS_FEE_INCOME_ACCOUNT",
            instruction_details=sentinel.instruction_details,
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Proposed withdrawals exceeded permitted limit by 2",
            event_type="APPLY_EXCESS_FEES",
            gl_impacted=True,
            account_type=sentinel.account_type,
        )
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            [
                call(
                    client_transactions=proposed_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME,
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
                call(
                    client_transactions={
                        **monthly_client_transactions,
                        **proposed_client_transactions,
                    },
                    client_transaction_ids_to_ignore=list(proposed_client_transactions.keys()),
                    denomination="GBP",
                    cutoff_datetime=DEFAULT_DATETIME
                    + relativedelta(day=1, hour=0, minute=0, second=0, microsecond=0),
                    key=feature.INSTRUCTION_DETAIL_KEY,
                    value="ATM",
                ),
            ]
        )
