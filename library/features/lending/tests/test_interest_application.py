from datetime import datetime
from decimal import Decimal
from unittest.mock import call, patch, sentinel, Mock

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types import Tside
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    UnionItemValue,
)
from library.features.lending.interest_application import (
    get_residual_cleanup_posting_instructions,
    get_application_posting_instructions,
)

DEFAULT_DATE = datetime(2019, 1, 1)
DEFAULT_PRODUCT = "MORTGAGE"

ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUAL_EVENT = "ACCRUE_INTEREST"
ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "ACCRUED_INTEREST_RECEIVABLE"
NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS = "NON_EMI_ACCRUED_INTEREST_RECEIVABLE"
INTEREST_DUE_ADDRESS = "INTEREST_DUE"
APPLICATION_EVENT = "APPLY_ACCRUED_INTEREST"
PUBLIC_HOLIDAYS = "&{PUBLIC_HOLIDAYS}"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

APPLICATION_EVENT = "APPLY_ACCRUED_INTEREST"


class TestInterestApplicationBase(ContractFeatureTest):
    target_test_file = "library/features/lending/interest_application.py"
    side = Tside.ASSET

    def create_mock(
        self,
        balance_ts=None,
        creation_date=DEFAULT_DATE,
        days_in_year=UnionItemValue("365"),
        interest_accrual_hour=0,
        interest_accrual_minute=0,
        interest_accrual_second=0,
        interest_application_hour=0,
        interest_application_minute=0,
        interest_application_second=0,
        interest_application_frequency=UnionItemValue("monthly"),
        accrued_interest_receivable_account=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
        interest_received_account=INTEREST_RECEIVED_ACCOUNT,
        **kwargs,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts or self.init_balances(balance_defs=[{"net": "98"}]),
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            **kwargs,
        )

    @classmethod
    def setupClass(cls):
        cls.maxDiff = None
        super().setUpClass()


class TestInterestApplication(TestInterestApplicationBase):
    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_regular_interest_only(
        self,
        mock_get_balance_sum: Mock,
        mock_round_decimal: Mock,
        mock_get_residual_cleanup_posting_instructions: Mock,
    ):
        mock_get_balance_sum.side_effect = [Decimal("1.23432"), Decimal("0")]
        mock_round_decimal.return_value = Decimal("1.23")
        mock_get_residual_cleanup_posting_instructions.side_effect = [
            [
                sentinel.accrued_interest_reversal_posting_1,
                sentinel.accrued_interest_reversal_posting_2,
            ],
            [],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", INTEREST_DUE_ADDRESS
        )

        mock_round_decimal.assert_called_once_with(Decimal("1.23432"), decimal_places=2)

        self.assertEqual(len(results), 3)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTEREST_DUE_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Interest Applied",
                        "event": APPLICATION_EVENT,
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }
        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23432"),
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_regular_interest_and_rounded_down_non_emi(
        self,
        mock_get_balance_sum: Mock,
        mock_round_decimal: Mock,
        mock_get_residual_cleanup_posting_instructions: Mock,
    ):
        mock_get_balance_sum.side_effect = [Decimal("1.23432"), Decimal("0.0001")]
        mock_round_decimal.return_value = Decimal("1.23")
        mock_get_residual_cleanup_posting_instructions.side_effect = [
            [
                sentinel.accrued_interest_reversal_posting_1,
                sentinel.accrued_interest_reversal_posting_2,
            ],
            [
                sentinel.non_emi_accrued_interest_reversal_posting_1,
                sentinel.non_emi_accrued_interest_reversal_posting_2,
            ],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", INTEREST_DUE_ADDRESS
        )

        mock_round_decimal.assert_called_once_with(Decimal("1.23442"), decimal_places=2)

        self.assertEqual(len(results), 5)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTEREST_DUE_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Interest Applied",
                        "event": APPLICATION_EVENT,
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }
        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23432"),
                    instruction_details=instruction_details,
                ),
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("0.0001"),
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_non_emi_interest_and_rounded_down_regular(
        self,
        mock_get_balance_sum: Mock,
        mock_round_decimal: Mock,
        mock_get_residual_cleanup_posting_instructions: Mock,
    ):
        mock_get_balance_sum.side_effect = [Decimal("0.0001"), Decimal("1.23432")]
        mock_round_decimal.return_value = Decimal("1.23")
        mock_get_residual_cleanup_posting_instructions.side_effect = [
            [
                sentinel.accrued_interest_reversal_posting_1,
                sentinel.accrued_interest_reversal_posting_2,
            ],
            [
                sentinel.non_emi_accrued_interest_reversal_posting_1,
                sentinel.non_emi_accrued_interest_reversal_posting_2,
            ],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", INTEREST_DUE_ADDRESS
        )

        mock_round_decimal.assert_called_once_with(Decimal("1.23442"), decimal_places=2)

        self.assertEqual(len(results), 5)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTEREST_DUE_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Interest Applied",
                        "event": APPLICATION_EVENT,
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }
        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("0.0001"),
                    instruction_details=instruction_details,
                ),
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23432"),
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_regular_and_non_emi_interest(
        self,
        mock_get_balance_sum: Mock,
        mock_round_decimal: Mock,
        mock_get_residual_cleanup_posting_instructions: Mock,
    ):
        mock_get_balance_sum.side_effect = [Decimal("1.23432"), Decimal("1.23456")]
        mock_round_decimal.return_value = Decimal("2.47")
        mock_get_residual_cleanup_posting_instructions.side_effect = [
            [
                sentinel.accrued_interest_reversal_posting_1,
                sentinel.accrued_interest_reversal_posting_2,
            ],
            [
                sentinel.non_emi_accrued_interest_reversal_posting_1,
                sentinel.non_emi_accrued_interest_reversal_posting_2,
            ],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", INTEREST_DUE_ADDRESS
        )

        mock_round_decimal.assert_called_once_with(Decimal("2.46888"), decimal_places=2)

        self.assertEqual(len(results), 5)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("2.47"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTEREST_DUE_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Interest Applied",
                        "event": APPLICATION_EVENT,
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }
        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23432"),
                    instruction_details=instruction_details,
                ),
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23456"),
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_non_emi_interest_only(
        self,
        mock_get_balance_sum: Mock,
        mock_round_decimal: Mock,
        mock_get_residual_cleanup_posting_instructions: Mock,
    ):
        mock_get_balance_sum.side_effect = [Decimal("0"), Decimal("1.23456")]
        mock_round_decimal.return_value = Decimal("1.23")
        mock_get_residual_cleanup_posting_instructions.side_effect = [
            [],
            [
                sentinel.non_emi_accrued_interest_reversal_posting_1,
                sentinel.non_emi_accrued_interest_reversal_posting_2,
            ],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", INTEREST_DUE_ADDRESS
        )

        mock_round_decimal.assert_called_once_with(Decimal("1.23456"), decimal_places=2)

        self.assertEqual(len(results), 3)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.23"),
                    denomination="GBP",
                    from_account_id=mock_vault.account_id,
                    from_account_address=INTEREST_DUE_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="APPLY_ACCRUED_INTEREST_MOCK_HOOK_GBP_INTERNAL",
                    instruction_details={
                        "description": "Interest Applied",
                        "event": APPLICATION_EVENT,
                    },
                ),
            ]
        )

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }
        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("0"),
                    instruction_details=instruction_details,
                ),
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("1.23456"),
                    instruction_details=instruction_details,
                ),
            ]
        )

    @patch(
        "library.features.lending.interest_application.get_residual_cleanup_posting_instructions"
    )
    @patch("library.features.lending.interest_application.utils.round_decimal")
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_application_posting_instructions_nothing_to_apply(
        self,
        mock_get_balance_sum,
        mock_round_decimal,
        mock_get_residual_cleanup_posting_instructions,
    ):
        mock_get_balance_sum.side_effect = [Decimal("0.00001"), Decimal("0.00001")]
        mock_round_decimal.return_value = Decimal("0")
        mock_get_residual_cleanup_posting_instructions.return_value = [
            [
                sentinel.accrued_interest_reversal_posting_1,
                sentinel.accrued_interest_reversal_posting_2,
            ],
            [
                sentinel.non_emi_accrued_interest_reversal_posting_1,
                sentinel.non_emi_accrued_interest_reversal_posting_2,
            ],
        ]

        mock_vault = self.create_mock()

        results = get_application_posting_instructions(
            mock_vault, DEFAULT_DATE, "GBP", DEFAULT_PRODUCT
        )

        mock_round_decimal.assert_called_once_with(Decimal("0.00002"), decimal_places=2)

        # current logic reverses everything after an application
        # even if application is rounded to 0, the remainder is still flattened out
        self.assertEqual(len(results), 4)
        mock_vault.make_internal_transfer_instructions.assert_not_called()

        instruction_details = {
            "description": "Zeroing remainder accrued interest after application",
            "event": APPLICATION_EVENT,
        }

        mock_get_residual_cleanup_posting_instructions.assert_has_calls(
            [
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("0.00001"),
                    instruction_details=instruction_details,
                ),
                call(
                    mock_vault,
                    "GBP",
                    accrued_at_address=NON_EMI_ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    remainder=Decimal("0.00001"),
                    instruction_details=instruction_details,
                ),
            ]
        )


class TestResidualCleanup(TestInterestApplicationBase):
    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_with_positive_remainder_specified(
        self,
        mock_get_balance_sum,
    ):
        specified_remainder = Decimal("0.00456")
        mock_get_balance_sum.return_value = specified_remainder

        mock_vault = self.create_mock()

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(
            mock_vault, "GBP", instruction_details, specified_remainder
        )

        mock_get_balance_sum.assert_not_called()

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("0.00456"),
            denomination="GBP",
            from_account_id=mock_vault.account_id,
            from_account_address=INTERNAL_CONTRA,
            to_account_id=mock_vault.account_id,
            to_account_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id="REVERSE_RESIDUAL_ACCRUED_INTEREST_RECEIVABLE_MOCK_HOOK_GBP",
            instruction_details=instruction_details,
        )

    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_negative_remainder_specified(
        self,
        mock_get_balance_sum,
    ):
        specified_remainder = Decimal("-0.00456")
        mock_get_balance_sum.return_value = specified_remainder

        mock_vault = self.create_mock()

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(
            mock_vault, "GBP", instruction_details, specified_remainder
        )

        mock_get_balance_sum.assert_not_called()

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("0.00456"),
            denomination="GBP",
            from_account_id=mock_vault.account_id,
            from_account_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            to_account_id=mock_vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id="REVERSE_RESIDUAL_ACCRUED_INTEREST_RECEIVABLE_MOCK_HOOK_GBP",
            instruction_details=instruction_details,
        )

    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_remainder_unspecified(
        self,
        mock_get_balance_sum,
    ):
        remainder = "-0.00456"
        mock_get_balance_sum.return_value = Decimal(remainder)

        mock_vault = self.create_mock(
            balance_ts=self.init_balances(
                balance_defs=[{"address": ACCRUED_INTEREST_RECEIVABLE_ADDRESS, "net": remainder}]
            )
        )

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(mock_vault, "GBP", instruction_details)

        mock_get_balance_sum.assert_called_once_with(
            mock_vault, [ACCRUED_INTEREST_RECEIVABLE_ADDRESS]
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("0.00456"),
            denomination="GBP",
            from_account_id=mock_vault.account_id,
            from_account_address=ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            to_account_id=mock_vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id="REVERSE_RESIDUAL_ACCRUED_INTEREST_RECEIVABLE_MOCK_HOOK_GBP",
            instruction_details=instruction_details,
        )

    @patch("library.features.lending.interest_application.utils.get_balance_sum")
    def test_get_residual_cleanup_posting_instructions_0_remainder(
        self,
        mock_get_balance_sum,
    ):
        remainder = "0"
        mock_get_balance_sum.return_value = Decimal(remainder)

        mock_vault = self.create_mock(
            balance_ts=self.init_balances(
                balance_defs=[{"address": ACCRUED_INTEREST_RECEIVABLE_ADDRESS, "net": remainder}]
            )
        )

        instruction_details = {"some": "details"}

        results = get_residual_cleanup_posting_instructions(mock_vault, "GBP", instruction_details)

        mock_get_balance_sum.assert_called_once_with(
            mock_vault, [ACCRUED_INTEREST_RECEIVABLE_ADDRESS]
        )

        self.assertEqual(len(results), 0)
        mock_vault.make_internal_transfer_instructions.assert_not_called()
