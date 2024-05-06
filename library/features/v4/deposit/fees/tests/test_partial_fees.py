# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from typing import Union
from unittest.mock import ANY, MagicMock, _Sentinel, call, patch, sentinel

# features
import library.features.v4.deposit.fees.partial_fee as partial_fee
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
)


def generate_mock_fee_details(
    partial_fee_tracking_address: Union[str, _Sentinel],
    fee_type: Union[str, _Sentinel],
    internal_account_id: Union[str, _Sentinel],
):
    fee_details = MagicMock(partial_fee.deposit_interfaces.PartialFeeCollection)

    fee_details.fee_type = fee_type

    def get_internal_account_parameter(*args, **kwargs):
        return internal_account_id

    fee_details.outstanding_fee_address = partial_fee_tracking_address
    fee_details.get_internal_account_parameter.side_effect = get_internal_account_parameter
    return fee_details


def mock_incoming_fee_custom_instruction():
    incoming_fee_custom_instruction = MagicMock()
    incoming_fee_custom_instruction.balances.return_value = sentinel.incoming_fee_custom_instruction
    incoming_fee_custom_instruction.instruction_details = {"description": "dummy"}
    return incoming_fee_custom_instruction


class PartialFeeTest(FeatureTest):
    def setUp(self) -> None:
        self.effective_datetime = sentinel.effective_datetime
        self.mock_fee_custom_instruction = patch.object(
            partial_fee.fees, "fee_custom_instruction"
        ).start()
        self.mock_tracking_balance_instructions = patch.object(
            partial_fee, "modify_tracking_balance"
        ).start()
        self.mock_get_parameter = patch.object(partial_fee.utils, "get_parameter").start()

        self.mock_fee_custom_instruction.return_value = [sentinel.CustomInstructionIncome]
        self.mock_tracking_balance_instructions.return_value = [sentinel.CustomInstructionPartial]
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
            }
        )
        self.addCleanup(patch.stopall)
        return super().setUp()


@patch.object(partial_fee.utils, "balance_at_coordinates")
@patch.object(partial_fee.utils, "get_available_balance")
class TestPartialFeeCharging(PartialFeeTest):
    def test_charge_partial_fee_generates_postings(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("15")
        fee_amount = Decimal("20")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_charged_fee = Decimal("15")
        expected_remaining_fee = Decimal("5")

        # setup mocks
        incoming_fee_custom_instruction = mock_incoming_fee_custom_instruction()
        mock_balance_at_coordinates.return_value = -fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_vault = self.create_mock()

        # Execute test

        response = partial_fee.charge_partial_fee(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_details=mock_fee_details,
            fee_custom_instruction=incoming_fee_custom_instruction,
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_called_once_with(
            amount=expected_charged_fee,
            internal_account=internal_address,
            denomination=DEFAULT_DENOMINATION,
            customer_account_id=mock_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            instruction_details=ANY,
        )

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_remaining_fee,
            account_id=mock_vault.account_id,
        )

        # Assert results
        self.assertEqual(
            response, [sentinel.CustomInstructionIncome, sentinel.CustomInstructionPartial]
        )

    def test_charge_partial_fee_generates_postings_more_debt(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("10")
        fee_amount = Decimal("50")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_charged_fee = Decimal("10")
        expected_remaining_fee = Decimal("40")

        # setup mocks
        incoming_fee_custom_instruction = mock_incoming_fee_custom_instruction()
        mock_balance_at_coordinates.return_value = -fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_vault = self.create_mock()
        # Execute test

        response = partial_fee.charge_partial_fee(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_details=mock_fee_details,
            fee_custom_instruction=incoming_fee_custom_instruction,
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_called_once_with(
            amount=expected_charged_fee,
            internal_account=internal_address,
            denomination=DEFAULT_DENOMINATION,
            customer_account_id=mock_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            instruction_details=ANY,
        )

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_remaining_fee,
            account_id=mock_vault.account_id,
        )

        # Assert results
        self.assertEqual(
            response, [sentinel.CustomInstructionIncome, sentinel.CustomInstructionPartial]
        )

    def test_charge_partial_fee_generates_postings_no_balance(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("0")
        fee_amount = Decimal("50")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_remaining_fee = Decimal("50")

        # setup mocks
        incoming_fee_custom_instruction = mock_incoming_fee_custom_instruction()
        mock_balance_at_coordinates.return_value = -fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_vault = self.create_mock()
        # Execute test

        response = partial_fee.charge_partial_fee(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_details=mock_fee_details,
            fee_custom_instruction=incoming_fee_custom_instruction,
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_not_called()

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_remaining_fee,
            account_id=mock_vault.account_id,
        )

        # Assert results
        self.assertEqual(response, [sentinel.CustomInstructionPartial])

    def test_charge_partial_fee_generates_postings_base_balance_enough(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("50")
        fee_amount = Decimal("20")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        # Not used as no custom instructions created
        # expected_charged_fee = Decimal("20")

        # setup mocks
        incoming_fee_custom_instruction = mock_incoming_fee_custom_instruction()

        mock_balance_at_coordinates.return_value = -fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_vault = self.create_mock()

        # Execute test

        response = partial_fee.charge_partial_fee(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_details=mock_fee_details,
            fee_custom_instruction=incoming_fee_custom_instruction,
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_not_called()

        self.mock_tracking_balance_instructions.assert_not_called()

        # Assert results
        self.assertEqual(response, [incoming_fee_custom_instruction])

    def test_charge_partial_fee_fetches_balances_and_denom_with_available_balance_callable(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("15")
        fee_amount = Decimal("20")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_charged_fee = Decimal("15")
        expected_remaining_fee = Decimal("5")

        # setup mocks
        incoming_fee_custom_instruction = mock_incoming_fee_custom_instruction()
        del incoming_fee_custom_instruction.instruction_details["description"]

        mock_balance_at_coordinates.return_value = -fee_amount

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_balance_observation = MagicMock()
        mock_balance_observation.balances = sentinel.balances
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: mock_balance_observation
            }
        )
        mock_available_balance = MagicMock()
        mock_calculate_available_balance = MagicMock(return_value=available_balance)
        mock_available_balance.calculate = mock_calculate_available_balance

        # Execute test

        response = partial_fee.charge_partial_fee(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            fee_details=mock_fee_details,
            fee_custom_instruction=incoming_fee_custom_instruction,
            available_balance_feature=mock_available_balance,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_called_once_with(
            amount=expected_charged_fee,
            internal_account=internal_address,
            denomination=DEFAULT_DENOMINATION,
            customer_account_id=mock_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            instruction_details=ANY,
        )

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_remaining_fee,
            account_id=mock_vault.account_id,
        )

        # Assert results
        self.assertEqual(
            response, [sentinel.CustomInstructionIncome, sentinel.CustomInstructionPartial]
        )
        mock_get_available_balance.assert_not_called()
        mock_calculate_available_balance.assert_called_once_with(
            vault=mock_vault, balances=sentinel.balances, denomination=DEFAULT_DENOMINATION
        )


@patch.object(partial_fee.utils, "balance_at_coordinates")
@patch.object(partial_fee.utils, "get_available_balance")
class TestPartialOutstandingFeeCharging(PartialFeeTest):
    def test_charge_outstanding_fee_generates_postings(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("15")
        fee_amount = Decimal("20")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_charged_fee = Decimal("15")

        # setup mocks

        mock_balance_at_coordinates.return_value = fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )

        mock_balance_observation = MagicMock()
        mock_balance_observation.balances = sentinel.balances
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.LIVE_BALANCES_BOF_ID: mock_balance_observation
            }
        )

        # Execute test

        response = partial_fee.charge_outstanding_fees(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            fee_collection=[mock_fee_details],
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_called_once_with(
            amount=expected_charged_fee,
            internal_account=internal_address,
            denomination=DEFAULT_DENOMINATION,
            customer_account_id=mock_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            instruction_details=ANY,
        )

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_charged_fee,
            account_id=mock_vault.account_id,
            payment_deduction=True,
        )

        # Assert results
        self.assertEqual(
            response, [sentinel.CustomInstructionIncome, sentinel.CustomInstructionPartial]
        )

    def test_charge_partial_fee_generates_postings_sufficient_funds(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("400")
        fee_amount = Decimal("20")
        partial_fee_address = "PARTIAL_FEE"
        internal_address = "INTERNAL_ADDRESS"
        fee_type = "FEE_TYPE"

        expected_charged_fee = Decimal("20")

        mock_balance_at_coordinates.return_value = fee_amount
        mock_get_available_balance.return_value = available_balance

        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address,
            fee_type=fee_type,
            internal_account_id=internal_address,
        )
        mock_vault = self.create_mock()

        # Execute test

        response = partial_fee.charge_outstanding_fees(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_collection=[mock_fee_details],
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_called_once_with(
            amount=expected_charged_fee,
            internal_account=internal_address,
            denomination=DEFAULT_DENOMINATION,
            customer_account_id=mock_vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            instruction_details=ANY,
        )

        self.mock_tracking_balance_instructions.assert_called_once_with(
            tracking_address=partial_fee_address,
            fee_type=fee_type,
            denomination=DEFAULT_DENOMINATION,
            value=expected_charged_fee,
            account_id=mock_vault.account_id,
            payment_deduction=True,
        )

        # Assert results
        self.assertEqual(
            response, [sentinel.CustomInstructionIncome, sentinel.CustomInstructionPartial]
        )

    def test_charge_multiple_outstanding_fee_generates_postings_sufficient_funds(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("40")
        # fee 1
        fee_amount_1 = Decimal("10")
        partial_fee_address_1 = "PARTIAL_FEE_1"
        internal_address_1 = "INTERNAL_ADDRESS_1"
        fee_type_1 = "FEE_TYPE"
        expected_charged_fee_1 = Decimal("10")

        # fee 2
        fee_amount_2 = Decimal("30")
        partial_fee_address_2 = "PARTIAL_FEE_2"
        internal_address_2 = "INTERNAL_ADDRESS_2"
        fee_type_2 = "FEE_TYPE"
        expected_charged_fee_2 = Decimal("30")

        # setup mocks
        mock_balance_at_coordinates.side_effect = [fee_amount_1, fee_amount_2]
        mock_get_available_balance.return_value = available_balance

        mock_fee_details_1 = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address_1,
            fee_type=fee_type_1,
            internal_account_id=internal_address_1,
        )
        mock_fee_details_2 = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address_2,
            fee_type=fee_type_2,
            internal_account_id=internal_address_2,
        )

        mock_balance_observation = MagicMock()
        mock_balance_observation.balances = sentinel.balances
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.LIVE_BALANCES_BOF_ID: mock_balance_observation
            }
        )

        # Execute test

        response = partial_fee.charge_outstanding_fees(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            balances=sentinel.balances,
            fee_collection=[mock_fee_details_1, mock_fee_details_2],
            denomination=DEFAULT_DENOMINATION,
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_has_calls(
            [
                call(
                    amount=expected_charged_fee_1,
                    internal_account=internal_address_1,
                    denomination=DEFAULT_DENOMINATION,
                    customer_account_id=mock_vault.account_id,
                    customer_account_address=DEFAULT_ADDRESS,
                    instruction_details=ANY,
                ),
                call(
                    amount=expected_charged_fee_2,
                    internal_account=internal_address_2,
                    denomination=DEFAULT_DENOMINATION,
                    customer_account_id=mock_vault.account_id,
                    customer_account_address=DEFAULT_ADDRESS,
                    instruction_details=ANY,
                ),
            ]
        )

        self.mock_tracking_balance_instructions.assert_has_calls(
            [
                call(
                    tracking_address=partial_fee_address_1,
                    fee_type=fee_type_1,
                    denomination=DEFAULT_DENOMINATION,
                    value=expected_charged_fee_1,
                    account_id=mock_vault.account_id,
                    payment_deduction=True,
                ),
                call(
                    tracking_address=partial_fee_address_2,
                    fee_type=fee_type_2,
                    denomination=DEFAULT_DENOMINATION,
                    value=expected_charged_fee_2,
                    account_id=mock_vault.account_id,
                    payment_deduction=True,
                ),
            ]
        )

        # Assert results
        self.assertEqual(
            response,
            [
                sentinel.CustomInstructionIncome,
                sentinel.CustomInstructionPartial,
                sentinel.CustomInstructionIncome,
                sentinel.CustomInstructionPartial,
            ],
        )

    def test_charge_multiple_outstanding_fee_generates_postings_insufficient_funds(
        self,
        mock_get_available_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
    ):
        # test parameters
        available_balance = Decimal("30")
        # fee 1
        fee_amount_1 = Decimal("20")
        partial_fee_address_1 = "PARTIAL_FEE_1"
        internal_address_1 = "INTERNAL_ADDRESS_1"
        fee_type_1 = "FEE_TYPE"
        expected_charged_fee_1 = Decimal("20")

        # fee 2
        fee_amount_2 = Decimal("20")
        partial_fee_address_2 = "PARTIAL_FEE_2"
        internal_address_2 = "INTERNAL_ADDRESS_2"
        fee_type_2 = "FEE_TYPE"
        expected_charged_fee_2 = Decimal("10")

        # fee 3
        fee_amount_3 = Decimal("20")
        partial_fee_address_3 = "PARTIAL_FEE_3"
        internal_address_3 = "INTERNAL_ADDRESS_3"
        fee_type_3 = "FEE_TYPE"
        # below unused as no expected posting
        # expected_charged_fee_3 = Decimal("0")

        # setup mocks
        mock_balance_at_coordinates.side_effect = [fee_amount_1, fee_amount_2, fee_amount_3]
        mock_get_available_balance.return_value = available_balance

        mock_fee_details_1 = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address_1,
            fee_type=fee_type_1,
            internal_account_id=internal_address_1,
        )
        mock_fee_details_2 = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address_2,
            fee_type=fee_type_2,
            internal_account_id=internal_address_2,
        )
        mock_fee_details_3 = generate_mock_fee_details(
            partial_fee_tracking_address=partial_fee_address_3,
            fee_type=fee_type_3,
            internal_account_id=internal_address_3,
        )

        mock_balance_observation = MagicMock()
        mock_balance_observation.balances = sentinel.balances
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.LIVE_BALANCES_BOF_ID: mock_balance_observation
            }
        )

        # Execute test

        response = partial_fee.charge_outstanding_fees(
            vault=mock_vault,
            effective_datetime=self.effective_datetime,
            fee_collection=[mock_fee_details_1, mock_fee_details_2, mock_fee_details_3],
        )

        # Assert Relevant Mocks
        self.mock_fee_custom_instruction.assert_has_calls(
            [
                call(
                    amount=expected_charged_fee_1,
                    internal_account=internal_address_1,
                    denomination=DEFAULT_DENOMINATION,
                    customer_account_id=mock_vault.account_id,
                    customer_account_address=DEFAULT_ADDRESS,
                    instruction_details=ANY,
                ),
                call(
                    amount=expected_charged_fee_2,
                    internal_account=internal_address_2,
                    denomination=DEFAULT_DENOMINATION,
                    customer_account_id=mock_vault.account_id,
                    customer_account_address=DEFAULT_ADDRESS,
                    instruction_details=ANY,
                ),
            ]
        )

        self.mock_tracking_balance_instructions.assert_has_calls(
            [
                call(
                    tracking_address=partial_fee_address_1,
                    fee_type=fee_type_1,
                    denomination=DEFAULT_DENOMINATION,
                    value=expected_charged_fee_1,
                    account_id=mock_vault.account_id,
                    payment_deduction=True,
                ),
                call(
                    tracking_address=partial_fee_address_2,
                    fee_type=fee_type_2,
                    denomination=DEFAULT_DENOMINATION,
                    value=expected_charged_fee_2,
                    account_id=mock_vault.account_id,
                    payment_deduction=True,
                ),
            ]
        )

        # Assert results
        self.assertEqual(
            response,
            [
                sentinel.CustomInstructionIncome,
                sentinel.CustomInstructionPartial,
                sentinel.CustomInstructionIncome,
                sentinel.CustomInstructionPartial,
            ],
        )


class TestModifyTrackingBalance(FeatureTest):
    def test_modify_tracking_balance(self):
        account_id = sentinel.account_id
        amount = Decimal(123)
        credit_posting = Posting(
            credit=True,
            amount=amount,
            denomination="GBP",
            account_id=account_id,
            account_address="partial_address",
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        )
        debit_posting = Posting(
            credit=False,
            amount=amount,
            denomination="GBP",
            account_id=account_id,
            account_address=partial_fee.lending_addresses.INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        )

        expected_custom_instruction = [
            CustomInstruction(
                postings=[credit_posting, debit_posting],
                instruction_details={
                    "description": "fee_type",
                    "event": "Update fee_type amount owed",
                },
            )
        ]

        actual_custom_instruction = partial_fee.modify_tracking_balance(
            account_id=account_id,
            denomination="GBP",
            tracking_address="partial_address",
            fee_type="fee_type",
            value=amount,
        )

        self.assertEqual(expected_custom_instruction, actual_custom_instruction)

    def test_modify_tracking_balance_reversal(self):
        account_id = sentinel.account_id
        amount = Decimal(123)
        credit_posting = Posting(
            credit=True,
            amount=amount,
            denomination="GBP",
            account_id=account_id,
            account_address=partial_fee.lending_addresses.INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        )
        debit_posting = Posting(
            credit=False,
            amount=amount,
            denomination="GBP",
            account_id=account_id,
            account_address="partial_address",
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        )

        expected_custom_instruction = [
            CustomInstruction(
                postings=[credit_posting, debit_posting],
                instruction_details={
                    "description": "fee_type",
                    "event": "Update fee_type amount owed",
                },
            )
        ]

        actual_custom_instruction = partial_fee.modify_tracking_balance(
            account_id=account_id,
            denomination="GBP",
            tracking_address="partial_address",
            fee_type="fee_type",
            value=amount,
            payment_deduction=True,
        )

        self.assertEqual(expected_custom_instruction, actual_custom_instruction)

    def test_modify_tracking_balance_negative(self):
        account_id = sentinel.account_id
        amount = Decimal(-123)
        expected_custom_instruction = []

        actual_custom_instruction = partial_fee.modify_tracking_balance(
            account_id=account_id,
            denomination="GBP",
            tracking_address="partial_address",
            fee_type="fee_type",
            value=amount,
        )

        self.assertEqual(expected_custom_instruction, actual_custom_instruction)

    def test_modify_tracking_balance_zero(self):
        account_id = sentinel.account_id
        resp = partial_fee.modify_tracking_balance(
            account_id=account_id,
            denomination="GBP",
            tracking_address="partial_address",
            fee_type="fee_type",
            value=Decimal(0),
            payment_deduction=True,
        )

        self.assertEqual(resp, [])


@patch.object(partial_fee.utils, "balance_at_coordinates")
class HasOutstandingFeesTest(PartialFeeTest):
    def test_has_no_outstanding_fees(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address="PARTIAL_FEE",
            fee_type="FEE_TYPE",
            internal_account_id="INTERNAL_ADDRESS",
        )
        mock_balance_at_coordinates.return_value = Decimal("0")

        # run function
        result = partial_fee.has_outstanding_fees(
            vault=sentinel.vault,
            fee_collection=[mock_fee_details],
            balances=sentinel.balances,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_has_no_outstanding_fees_balances_and_denomination_not_provided(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )
        mock_fee_details = generate_mock_fee_details(
            partial_fee_tracking_address="PARTIAL_FEE",
            fee_type="FEE_TYPE",
            internal_account_id="INTERNAL_ADDRESS",
        )
        mock_balance_at_coordinates.return_value = Decimal("0")

        # run function
        result = partial_fee.has_outstanding_fees(
            vault=mock_vault,
            fee_collection=[mock_fee_details],
        )
        self.assertFalse(result)

    def test_has_outstanding_fees(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                partial_fee.fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live")
            }
        )
        mock_fee_details_1 = generate_mock_fee_details(
            partial_fee_tracking_address="PARTIAL_FEE",
            fee_type="FEE_TYPE_1",
            internal_account_id="INTERNAL_ADDRESS",
        )
        mock_fee_details_2 = generate_mock_fee_details(
            partial_fee_tracking_address="PARTIAL_FEE",
            fee_type="FEE_TYPE_2",
            internal_account_id="INTERNAL_ADDRESS",
        )
        mock_balance_at_coordinates.side_effect = [Decimal("0"), Decimal("1")]

        # run function
        result = partial_fee.has_outstanding_fees(
            vault=mock_vault,
            fee_collection=[mock_fee_details_1, mock_fee_details_2],
        )
        self.assertTrue(result)
