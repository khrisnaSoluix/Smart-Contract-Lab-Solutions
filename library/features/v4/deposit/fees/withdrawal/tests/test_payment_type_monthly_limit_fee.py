# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.deposit.fees.withdrawal import payment_type_monthly_limit_fee

# contracts api
from contracts_api import CustomInstruction, Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
)

START_OF_MONTH = datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
CURRENT_DATETIME = datetime(2022, 1, 31, tzinfo=ZoneInfo("UTC"))
PAYMENT_TYPE = "PAYMENT_TYPE"
DEFAULT_ACCOUNT = "default_account"


@patch.object(payment_type_monthly_limit_fee.utils, "standard_instruction_details")
@patch.object(payment_type_monthly_limit_fee.fees, "fee_custom_instruction")
@patch.object(
    payment_type_monthly_limit_fee.client_transaction_utils,
    "extract_debits_by_instruction_details_key",
)
@patch.object(payment_type_monthly_limit_fee.utils, "get_parameter")
class TestPaymentTypeMonthlyLimit(FeatureTest):
    tside = Tside.LIABILITY

    payment_type_monthly_limit_fees_map = {
        "ATM_ARBM": {"fee": "0.50", "limit": "3"},
        "ATM_XYZ": {"fee": "3.25", "limit": "1"},
    }

    payment_type_monthly_limit_fees_parameters = {
        "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
        "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
    }

    payment_type_fee_income_account = "PAYMENT_TYPE_FEE_INCOME_ACCOUNT"

    def standard_assertions(self, mock_extract_debits_by_instruction_details_key: MagicMock):
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            calls=[
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.historic_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=START_OF_MONTH,
                    key=PAYMENT_TYPE,
                    value="ATM_ARBM",
                ),
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.updated_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=CURRENT_DATETIME,
                    key=PAYMENT_TYPE,
                    value="ATM_ARBM",
                ),
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.historic_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=START_OF_MONTH,
                    key=PAYMENT_TYPE,
                    value="ATM_XYZ",
                ),
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.updated_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=CURRENT_DATETIME,
                    key=PAYMENT_TYPE,
                    value="ATM_XYZ",
                ),
            ]
        )

    def test_payment_type_monthly_limit_no_matching_historic_or_updated_client_transactions(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock(balances_observation_fetchers_mapping={})
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # no fee charged since no debits for the payment type
        mock_extract_debits_by_instruction_details_key.side_effect = [[], [], [], []]

        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        self.assertListEqual(results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        mock_extract_debits_by_instruction_details_key.assert_has_calls(
            calls=[
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.historic_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=START_OF_MONTH,
                    key=PAYMENT_TYPE,
                    value="ATM_ARBM",
                ),
                call(
                    denomination=DEFAULT_DENOMINATION,
                    client_transactions=sentinel.updated_client_transactions,
                    client_transaction_ids_to_ignore=[],
                    cutoff_datetime=CURRENT_DATETIME,
                    key=PAYMENT_TYPE,
                    value="ATM_ARBM",
                ),
            ]
        )

    def test_payment_type_monthly_limit_not_exceeded_in_historic_or_updated_client_transactions(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # no fee charged since neither historic nor new debits exceed limit
        mock_extract_debits_by_instruction_details_key.side_effect = [[1], [], [1], []]

        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        self.assertListEqual(results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_exceeded_by_1_in_updated_client_transactions(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # Charge 1x fee amount for first payment type since monthly limit 3 exceeded by 1 in
        # updated cts.
        mock_extract_debits_by_instruction_details_key.side_effect = [[1, 2, 3], [1], [], []]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 1x ATM_ARBM 0.50 = 0.50
        total_fee = "0.50"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_historically_exceeded_no_new_excesses(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # No fee charged despite limit previous exceeded as no new withdrawals
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2, 3, 4],
            [],
            [],
            [],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        self.assertListEqual(results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_historically_exceeded_and_1_new_excess(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # Charge 1x fee amount for first payment type since monthly limit 3 already exceeded in
        # historic cts and exceeded by 1 in updated cts
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2, 3, 4],
            [1],
            [],
            [],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 1x ATM_ARBM 0.50 = 0.50
        total_fee = "0.50"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_historically_exceeded_and_2_new_excess(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # Charge 2x fee amount for first payment type since monthly limit 3 already exceeded in
        # historic cts and exceeded by 2 in updated cts
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2, 3, 4],
            [1, 2],
            [],
            [],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 2x ATM_ARBM 0.50 = 1.00
        total_fee = "1.00"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_historically_not_exceeded_and_1_new_excess(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # Charge 1x fee amount for first payment type since monthly limit 1 not previously
        # exceeded in historic cts but exceeded by 1 in updated cts
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1],
            [1, 2, 3],
            [],
            [],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 1x ATM_ARBM 0.50 = 0.50
        total_fee = "0.50"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_historically_not_exceeded_and_2_new_excess(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # Charge 2x fee amount for first payment type since monthly limit 1 not previously
        # exceeded in historic cts but exceeded by 2 in updated cts
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1],
            [1, 2, 3, 4],
            [],
            [],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 2x ATM_ARBM 0.50 = 1.00
        total_fee = "1.00"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )

    def test_payment_type_monthly_limit_exceeded_for_two_payment_types(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )
        # Charge 2x fee amount (0.50) for payment type ATM_ARBM since monthly limit exceeded by 2.
        # Charge 1x fee amount (3.25) for payment type ATM_XYC  since monthly limit exceeded by 1.
        total_fee = "4.25"

        # two calls per type, first is historic, second is new
        # first type charges 2 fees as updated client transactions exceed limit by 2
        # second type charges 1 fees as updated client transactions exceed limit by 1
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2, 3],
            [1, 2],
            [],
            [1, 2],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Total fees charged for limits on payment types: ATM_ARBM 1.00 GBP"
            ",ATM_XYZ 3.25 GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_with_no_optional_args(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock(
            client_transactions_mapping={
                payment_type_monthly_limit_fee.fetchers.MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID: (
                    sentinel.historic_client_transactions
                )
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )

        # two calls per type, first is historic, second is new
        # no fee charged since no debits for the payment type
        mock_extract_debits_by_instruction_details_key.side_effect = [[], [], [], []]

        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
        )

        self.assertListEqual(results, [])
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_with_0_monthly_limit_exceeded(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=self.payment_type_monthly_limit_fees_parameters
        )
        # Charge 2x fee amount (0.50) for payment type ATM_ARBM since monthly limit exceeded by 2.
        # Charge 1x fee amount (3.25) for payment type ATM_XYC  since monthly limit exceeded by 1.
        total_fee = "4.25"

        # two calls per type, first is historic, second is new
        # first type charges 2 fees as updated client transactions exceed limit by 2
        # second type charges 1 fees as updated client transactions exceed limit by 1
        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2, 3],
            [1, 2],
            [],
            [1, 2],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description="Total fees charged for limits on payment types: ATM_ARBM 1.00 GBP"
            ",ATM_XYZ 3.25 GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
        self.standard_assertions(mock_extract_debits_by_instruction_details_key)

    def test_payment_type_monthly_limit_0_fee_no_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # Payment type has invalid fee: 0.

        payment_type_monthly_limit_fees_map = {
            "ATM_DEF": {"fee": "0", "limit": "1"},
        }

        payment_type_monthly_limit_fees_parameters = {
            "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
            "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        }

        # Mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=payment_type_monthly_limit_fees_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = None
        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        # 2. Call the function.
        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # 3. Assert.
        expected: list[CustomInstruction] = []

        self.assertListEqual(results, expected)
        mock_extract_debits_by_instruction_details_key.assert_not_called()
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_monthly_limit_missing_fee_no_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        payment_type_monthly_limit_fees_map = {
            "ATM_DEF": {"feeee": "12.56", "limit": "1"},
        }

        payment_type_monthly_limit_fees_parameters = {
            "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
            "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        }

        # Mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=payment_type_monthly_limit_fees_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = None
        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        # 2. Call the function.

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # 3. Assert.
        expected: list[CustomInstruction] = []

        self.assertListEqual(results, expected)
        mock_extract_debits_by_instruction_details_key.assert_not_called()
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_monthly_limit_invalid_limit_no_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        payment_type_monthly_limit_fees_map = {
            "ATM_DEF": {"fee": "32.56", "limit": "-2"},
        }

        payment_type_monthly_limit_fees_parameters = {
            "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
            "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        }

        # Mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=payment_type_monthly_limit_fees_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = None
        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        # 2. Call the function.

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # 3. Assert.
        expected: list[CustomInstruction] = []

        self.assertListEqual(results, expected)
        mock_extract_debits_by_instruction_details_key.assert_not_called()
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_monthly_limit_missing_limit_no_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        # Payment type has invalid limit: missing "limit"
        payment_type_monthly_limit_fees_map = {
            "ATM_DEF": {"fee": "32.56", "límite": "2"},
        }

        payment_type_monthly_limit_fees_parameters = {
            "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
            "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        }

        # Mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=payment_type_monthly_limit_fees_parameters
        )
        mock_extract_debits_by_instruction_details_key.side_effect = None
        mock_fee_custom_instruction.return_value = []
        mock_standard_instruction_details.return_value = {}

        # 2. Call the function.

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # 3. Assert.
        expected: list[CustomInstruction] = []

        self.assertListEqual(results, expected)
        mock_extract_debits_by_instruction_details_key.assert_not_called()
        mock_fee_custom_instruction.assert_not_called()
        mock_standard_instruction_details.assert_not_called()

    def test_payment_type_monthly_limit_limit_0_fee_charged(
        self,
        mock_get_parameter: MagicMock,
        mock_extract_debits_by_instruction_details_key: MagicMock,
        mock_fee_custom_instruction: MagicMock,
        mock_standard_instruction_details: MagicMock,
    ):
        mock_vault = self.create_mock()

        payment_type_monthly_limit_fees_map = {
            "ATM_ARBM": {"fee": "0.50", "limit": "0"},
        }

        payment_type_monthly_limit_fees_parameters = {
            "maximum_monthly_payment_type_withdrawal_limit": payment_type_monthly_limit_fees_map,
            "payment_type_fee_income_account": "PAYMENT_TYPE_FEE_INCOME_ACCOUNT",
        }

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=payment_type_monthly_limit_fees_parameters
        )
        # Charge 1x fee amount for payment type ATM_ARBM since monthly limit exceeded by 1.

        mock_extract_debits_by_instruction_details_key.side_effect = [
            [1, 2],
            [1, 2],
        ]

        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee")]
        mock_standard_instruction_details.return_value = {"sentinel": "dictionary"}

        results = payment_type_monthly_limit_fee.apply_fees(
            vault=mock_vault,
            effective_datetime=CURRENT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
            updated_client_transactions=sentinel.updated_client_transactions,
            historic_client_transactions=sentinel.historic_client_transactions,
        )

        expected = [SentinelCustomInstruction("fee")]

        # total fee is 2x ATM_ARBM 0.50 = 1.00
        total_fee = "1.00"

        self.assertListEqual(results, expected)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal(total_fee),
            internal_account=self.payment_type_fee_income_account,
            instruction_details={"sentinel": "dictionary"},
        )
        mock_standard_instruction_details.assert_called_once_with(
            description=f"Total fees charged for limits on payment types: ATM_ARBM {total_fee} GBP",
            event_type="APPLY_PAYMENT_TYPE_WITHDRAWAL_LIMIT_FEES",
            gl_impacted=True,
        )
