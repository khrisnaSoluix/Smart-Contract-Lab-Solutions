from datetime import datetime
from unittest.mock import call, patch, sentinel, Mock

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import (
    Decimal,
    DEFAULT_ADDRESS,
    INTERNAL_CONTRA,
    Tside,
    Vault,
)

import library.features.lending.overpayment as overpayment

# Schedule event names
HANDLE_OVERPAYMENT_ALLOWANCE = "HANDLE_OVERPAYMENT_ALLOWANCE"

# Addresses
ACCRUED_EXPECTED_INTEREST_ADDRESS = "ACCRUED_EXPECTED_INTEREST"
DEFAULT_DENOMINATION = "GBP"
EMI_PRINCIPAL_EXCESS_ADDRESS = "EMI_PRINCIPAL_EXCESS"
PENALTIES_ADDRESS = "PENALTIES"
PRINCIPAL_ADDRESS = "PRINCIPAL"
OVERPAYMENT_ADDRESS = "OVERPAYMENT"
OVERPAYMENT_FEE = "OVERPAYMENT_FEE_INCOME"

DEFAULT_DATE = datetime(2022, 5, 1)


class TestOverpayment(ContractFeatureTest):

    target_test_file = "library/features/lending/overpayment.py"
    side = Tside.ASSET

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_get_cleanup_residual_posting_instructions(
        self,
        mocked_get_balance_sum,
    ):
        test_cases = [
            {
                "description": "should create no postings when the balances are zero",
                "accrued_expected_interest_address_value": Decimal("0.00"),
                "emi_principal_excess_address_value": Decimal("0.00"),
                "overpayment_address_value": Decimal("0.00"),
                "overpayment_tracker_address_value": Decimal("0.00"),
                "expected_postings": [],
            },
            {
                "description": "should create correct postings when the balances are nonzero",
                "accrued_expected_interest_address_value": Decimal("23.00"),
                "emi_principal_excess_address_value": Decimal("31.58"),
                "overpayment_address_value": Decimal("0.02"),
                "overpayment_tracker_address_value": Decimal("1.00"),
                "expected_postings": [
                    {
                        "amount": Decimal("0.02"),
                        "denomination": DEFAULT_DENOMINATION,
                        "client_transaction_id": f"CLEAR_{OVERPAYMENT_ADDRESS}_MOCK_HOOK",
                        "from_account_id": "Main account",
                        "from_account_address": INTERNAL_CONTRA,
                        "to_account_id": "Main account",
                        "to_account_address": OVERPAYMENT_ADDRESS,
                        "instruction_details": {
                            "description": f"Clearing {OVERPAYMENT_ADDRESS} address",
                            "event": "END_OF_LOAN",
                        },
                        "override_all_restrictions": True,
                    },
                    {
                        "amount": Decimal("31.58"),
                        "denomination": DEFAULT_DENOMINATION,
                        "client_transaction_id": f"CLEAR_{EMI_PRINCIPAL_EXCESS_ADDRESS}"
                        "_MOCK_HOOK",
                        "from_account_id": "Main account",
                        "from_account_address": INTERNAL_CONTRA,
                        "to_account_id": "Main account",
                        "to_account_address": EMI_PRINCIPAL_EXCESS_ADDRESS,
                        "instruction_details": {
                            "description": "Clearing principal excess",
                            "event": "END_OF_LOAN",
                        },
                        "override_all_restrictions": True,
                    },
                    {
                        "amount": Decimal("23.00"),
                        "denomination": DEFAULT_DENOMINATION,
                        "client_transaction_id": f"CLEAR_{ACCRUED_EXPECTED_INTEREST_ADDRESS}"
                        "_MOCK_HOOK",
                        "from_account_id": "Main account",
                        "from_account_address": INTERNAL_CONTRA,
                        "to_account_id": "Main account",
                        "to_account_address": ACCRUED_EXPECTED_INTEREST_ADDRESS,
                        "instruction_details": {
                            "description": f"Clearing {ACCRUED_EXPECTED_INTEREST_ADDRESS} balance",
                            "event": "END_OF_LOAN",
                        },
                        "override_all_restrictions": True,
                    },
                    {
                        "amount": Decimal("1.00"),
                        "denomination": DEFAULT_DENOMINATION,
                        "client_transaction_id": "RESET_OVERPAYMENT_TRACKER_MOCK_HOOK",
                        "from_account_id": "Main account",
                        "from_account_address": INTERNAL_CONTRA,
                        "to_account_id": "Main account",
                        "to_account_address": overpayment.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
                        "override_all_restrictions": True,
                    },
                ],
            },
        ]
        for test_case in test_cases:

            def mock_get_balance_sum(vault: Vault, addresses: list[str]) -> Decimal:
                balances = {
                    overpayment.ACCRUED_EXPECTED_INTEREST: test_case[
                        "accrued_expected_interest_address_value"
                    ],
                    overpayment.EMI_PRINCIPAL_EXCESS: test_case[
                        "emi_principal_excess_address_value"
                    ],
                    overpayment.OVERPAYMENT: test_case["overpayment_address_value"],
                    overpayment.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC: test_case[
                        "overpayment_tracker_address_value"
                    ],
                }
                return balances.get(addresses[0]) or Decimal("0")

            mocked_get_balance_sum.side_effect = mock_get_balance_sum
            mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

            expected_postings = [call(**kwargs) for kwargs in test_case["expected_postings"]]
            actual_cleanup_instructions = overpayment.get_cleanup_residual_posting_instructions(
                mock_vault, PRINCIPAL_ADDRESS
            )

            self.assertEqual(len(expected_postings), len(actual_cleanup_instructions))
            mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

    @patch("library.features.lending.overpayment.interest_accrual.get_accrual_capital")
    def test_get_accrual_posting_instructions(self, mocked_get_accrual_capital: Mock):
        accrued_amount = Decimal("0.00273")
        accrual_capital = Decimal("100")
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)
        mocked_accrual_formula = Mock(return_value=accrued_amount)
        mocked_get_accrual_capital.side_effect = [accrual_capital]

        expected_posting = {
            "amount": accrued_amount,
            "denomination": DEFAULT_DENOMINATION,
            "client_transaction_id": f"UPDATE_{ACCRUED_EXPECTED_INTEREST_ADDRESS}_MOCK_HOOK",
            "from_account_id": "Main account",
            "from_account_address": ACCRUED_EXPECTED_INTEREST_ADDRESS,
            "to_account_id": "Main account",
            "to_account_address": INTERNAL_CONTRA,
            "instruction_details": {
                "description": (
                    f"Daily interest excluding overpayment effects accrued on balance of "
                    f"{accrual_capital}"
                )
            },
            "override_all_restrictions": True,
        }

        actual_accrual_posting_instructions = overpayment.get_accrual_posting_instructions(
            mock_vault, DEFAULT_DATE, DEFAULT_DENOMINATION, mocked_accrual_formula
        )

        self.assertEqual(1, len(actual_accrual_posting_instructions))
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(**expected_posting)
        mocked_accrual_formula.assert_called_once_with(mock_vault, accrual_capital, DEFAULT_DATE)

        mocked_get_accrual_capital.assert_called_once_with(
            mock_vault,
            DEFAULT_DATE,
            DEFAULT_DENOMINATION,
            [PRINCIPAL_ADDRESS, EMI_PRINCIPAL_EXCESS_ADDRESS, OVERPAYMENT_ADDRESS],
        )

    @patch("library.features.lending.overpayment.interest_accrual.get_accrual_capital")
    def test_get_accrual_posting_instructions_0_accrual(self, mocked_get_accrual_capital: Mock):
        accrued_amount = Decimal("0")
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)
        mocked_accrual_formula = Mock(return_value=accrued_amount)
        mocked_get_accrual_capital.side_effect = [Decimal("0")]

        actual_accrual_posting_instructions = overpayment.get_accrual_posting_instructions(
            mock_vault, DEFAULT_DATE, DEFAULT_DENOMINATION, mocked_accrual_formula
        )

        self.assertListEqual([], actual_accrual_posting_instructions)
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mocked_accrual_formula.assert_called_once_with(mock_vault, Decimal("0"), DEFAULT_DATE)

        mocked_get_accrual_capital.assert_called_once_with(
            mock_vault,
            DEFAULT_DATE,
            DEFAULT_DENOMINATION,
            [PRINCIPAL_ADDRESS, EMI_PRINCIPAL_EXCESS_ADDRESS, OVERPAYMENT_ADDRESS],
        )

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_get_application_posting_instructions(self, mocked_get_balance_sum: Mock):
        accrued_expected_amount = Decimal("0.00273")
        mock_vault = self.create_mock(
            denomination=DEFAULT_DENOMINATION,
        )
        mocked_get_balance_sum.side_effect = [accrued_expected_amount]

        expected_posting = {
            "amount": accrued_expected_amount,
            "denomination": DEFAULT_DENOMINATION,
            "client_transaction_id": f"UPDATE_{ACCRUED_EXPECTED_INTEREST_ADDRESS}_MOCK_HOOK",
            "from_account_id": "Main account",
            "from_account_address": INTERNAL_CONTRA,
            "to_account_id": "Main account",
            "to_account_address": ACCRUED_EXPECTED_INTEREST_ADDRESS,
            "instruction_details": {"description": (f"Clear {ACCRUED_EXPECTED_INTEREST_ADDRESS}")},
            "override_all_restrictions": True,
        }

        actual_interest_application_postings = overpayment.get_application_posting_instructions(
            mock_vault,
            DEFAULT_DATE,
            DEFAULT_DENOMINATION,
        )

        self.assertEqual(1, len(actual_interest_application_postings))
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(**expected_posting)

        mocked_get_balance_sum.assert_called_once_with(
            mock_vault, addresses=[ACCRUED_EXPECTED_INTEREST_ADDRESS], timestamp=DEFAULT_DATE
        )

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_get_application_posting_instructions_0_accrual(self, mocked_get_balance_sum: Mock):
        accrued_expected_amount = Decimal("0")
        mock_vault = self.create_mock(
            denomination=DEFAULT_DENOMINATION,
        )
        mocked_get_balance_sum.side_effect = [accrued_expected_amount]

        actual_interest_application_postings = overpayment.get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, DEFAULT_DENOMINATION
        )

        self.assertListEqual([], actual_interest_application_postings)
        mock_vault.make_internal_transfer_instructions.assert_not_called()

        mocked_get_balance_sum.assert_called_once_with(
            mock_vault, addresses=[ACCRUED_EXPECTED_INTEREST_ADDRESS], timestamp=DEFAULT_DATE
        )

    def test_get_overpayment_fee_posting_instructions(self):
        test_cases = [
            {
                "description": "no overpayment instructions are returned if fee is 0",
                "overpayment_fee": Decimal("0"),
                "expected_postings": [],
            },
            {
                "description": "no overpayment instructions are returned if fee is < 0",
                "overpayment_fee": Decimal("-1"),
                "expected_postings": [],
            },
            {
                "description": "correct overpayment instructions are returned if fee > 0",
                "overpayment_fee": Decimal("5.00"),
                "expected_postings": [
                    {
                        "amount": Decimal("5.00"),
                        "denomination": DEFAULT_DENOMINATION,
                        "client_transaction_id": "CHARGE_OVERPAYMENT_FEE_MOCK_HOOK",
                        "from_account_id": "Main account",
                        "from_account_address": PENALTIES_ADDRESS,
                        "to_account_id": OVERPAYMENT_FEE,
                        "to_account_address": DEFAULT_ADDRESS,
                        "instruction_details": {
                            "description": "Charging GBP 5.00 overpayment fee",
                            "event": overpayment.REPAYMENT,
                        },
                        "override_all_restrictions": True,
                    }
                ],
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock(
                denomination=DEFAULT_DENOMINATION,
                overpayment_fee_account=OVERPAYMENT_FEE,
            )

            expected_postings = [call(**kwargs) for kwargs in test_case["expected_postings"]]
            actual_transfer_fee_instructions = overpayment.get_overpayment_fee_posting_instructions(
                mock_vault,
                test_case["overpayment_fee"],
            )

            self.assertEqual(
                len(expected_postings),
                len(actual_transfer_fee_instructions),
                test_case["description"],
            )
            mock_vault.make_internal_transfer_instructions.assert_has_calls(
                expected_postings, test_case["description"]
            )

    def test_get_principal_adjustment_amount_returns_0(
        self,
    ):
        mock_vault = self.create_mock()
        self.assertEqual(0, overpayment.get_principal_adjustment_amount(mock_vault))
        mock_vault.assert_not_called()

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    @patch("library.features.lending.overpayment.interest_accrual.get_additional_interest")
    @patch("library.features.lending.overpayment.interest_accrual.get_accrued_interest")
    def test_get_principal_adjustment_posting_instructions(
        self,
        mocked_get_accrued_interest: Mock,
        mocked_get_additional_interest: Mock,
        mocked_get_balance_sum: Mock,
    ):
        # this amount gets rounded
        emi_principal_excess_amount = Decimal("23.32112")
        # ACCRUED_EXPECTED_INTEREST
        mocked_get_balance_sum.return_value = emi_principal_excess_amount * 2
        # ACCRUED_INTEREST_RECEIVABLE and NON_EMI_ACCRUED_INTEREST_RECEIVABLE
        mocked_get_accrued_interest.return_value = emi_principal_excess_amount / 2
        mocked_get_additional_interest.return_value = emi_principal_excess_amount / 2
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        # Expected interest > actual, so adjustment needed
        expected_postings_list = [
            {
                "amount": Decimal("23.32"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": f"UPDATE_{EMI_PRINCIPAL_EXCESS_ADDRESS}_MOCK_HOOK",
                "from_account_id": "Main account",
                "from_account_address": EMI_PRINCIPAL_EXCESS_ADDRESS,
                "to_account_id": "Main account",
                "to_account_address": INTERNAL_CONTRA,
                "instruction_details": {
                    "description": f"Increase {EMI_PRINCIPAL_EXCESS_ADDRESS} by {Decimal('23.32')}"
                },
                "override_all_restrictions": True,
            },
        ]
        expected_postings = [call(**kwargs) for kwargs in expected_postings_list]
        actual_principal_adjustment_posting_instructions = (
            overpayment.get_principal_adjustment_posting_instructions(
                mock_vault, DEFAULT_DENOMINATION
            )
        )

        self.assertEqual(
            len(expected_postings_list), len(actual_principal_adjustment_posting_instructions)
        )
        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)
        mocked_get_balance_sum.assert_called_once_with(
            mock_vault, [ACCRUED_EXPECTED_INTEREST_ADDRESS]
        )
        mocked_get_accrued_interest.assert_called_once_with(mock_vault)

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    @patch("library.features.lending.overpayment.interest_accrual.get_additional_interest")
    @patch("library.features.lending.overpayment.interest_accrual.get_accrued_interest")
    def test_get_principal_adjustment_posting_instructions_no_amount(
        self,
        mocked_get_accrued_interest: Mock,
        mocked_get_additional_interest: Mock,
        mocked_get_balance_sum: Mock,
    ):
        emi_principal_excess_amount = Decimal("23.32")
        # ACCRUED_EXPECTED_INTEREST
        mocked_get_balance_sum.return_value = emi_principal_excess_amount
        # ACCRUED_INTEREST_RECEIVABLE and NON_EMI_ACCRUED_INTEREST_RECEIVABLE
        mocked_get_accrued_interest.return_value = emi_principal_excess_amount / 2
        mocked_get_additional_interest.return_value = emi_principal_excess_amount / 2
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        instructions = overpayment.get_principal_adjustment_posting_instructions(
            mock_vault, DEFAULT_DENOMINATION
        )

        # Expected interest == actual, so no adjustments needed
        self.assertListEqual(instructions, [])
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mocked_get_balance_sum.assert_called_once_with(
            mock_vault, [ACCRUED_EXPECTED_INTEREST_ADDRESS]
        )
        mocked_get_accrued_interest.assert_called_once_with(mock_vault)

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_should_trigger_reamortisation_supervisor(self, mocked_get_balance_sum):
        test_cases = [
            {
                "description": "Do not reamortisate if no overpayments tracked",
                "current_tracker_balance": Decimal("0"),
                "overpayment_preference": "reduce_emi",
                "expected_result": False,
            },
            {
                "description": "Reamortisate if one or more overpayments tracked",
                "current_tracker_balance": Decimal("1"),
                "overpayment_preference": "reduce_emi",
                "expected_result": True,
            },
            {
                "description": (
                    "Do not reamortisate if reduce_term even if one or more overpayments tracked"
                ),
                "current_tracker_balance": Decimal("0"),
                "overpayment_preference": "reduce_term",
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mocked_get_balance_sum.return_value = test_case["current_tracker_balance"]
            mock_vault = self.create_mock()

            is_reamortisation_needed = overpayment.should_trigger_reamortisation_supervisor(
                mock_vault,
                elapsed_term_in_months=None,
                due_amount_schedule_details=None,
                overpayment_impact_preference=test_case["overpayment_preference"],
            )

            self.assertEqual(
                is_reamortisation_needed, test_case["expected_result"], test_case["description"]
            )

    def test_track_overpayment(self):
        mock_vault = self.create_mock(denomination=self.default_denom)
        overpayment.track_overpayment(mock_vault)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("1"),
            denomination=self.default_denom,
            client_transaction_id="TRACK_OVERPAYMENT_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address=overpayment.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
            to_account_id="Main account",
            to_account_address=INTERNAL_CONTRA,
            override_all_restrictions=True,
        )

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_reset_overpayment_tracker_with_overpayments_tracked(self, mocked_get_balance_sum):
        mock_vault = self.create_mock(denomination=self.default_denom)
        mock_vault.make_internal_transfer_instructions.side_effect = [
            sentinel.reset_tracker_postings
        ]
        mocked_get_balance_sum.return_value = Decimal("2")
        postings = overpayment.reset_overpayment_tracker(mock_vault)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("2"),
            denomination=self.default_denom,
            client_transaction_id="RESET_OVERPAYMENT_TRACKER_MOCK_HOOK",
            from_account_id="Main account",
            from_account_address=INTERNAL_CONTRA,
            to_account_id="Main account",
            to_account_address=overpayment.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
            override_all_restrictions=True,
        )
        self.assertEqual(postings, sentinel.reset_tracker_postings)

    @patch("library.features.lending.overpayment.utils.get_balance_sum")
    def test_reset_overpayment_tracker_no_overpayments_tracked(self, mocked_get_balance_sum):
        mock_vault = self.create_mock(denomination=self.default_denom)
        mocked_get_balance_sum.return_value = Decimal("0")
        postings = overpayment.reset_overpayment_tracker(mock_vault)
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        self.assertListEqual(postings, [])
