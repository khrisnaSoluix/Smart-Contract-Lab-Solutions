# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import call

# common
from inception_sdk.test_framework.contracts.unit.common import (
    balance_dimensions,
    ContractFeatureTest,
)
from inception_sdk.vault.contracts.types_extension import (
    Balance,
    BalanceDefaultDict,
    Phase,
    DEFAULT_ASSET,
)

from library.features.deposits.fees.early_closure_fee import (
    get_fees,
    DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
)

DEFAULT_DATE = datetime(2019, 1, 1)
DENOMINATION = "MYR"
EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "EARLY_CLOSURE_FEE_INCOME"


class EarlyClosureFeeTest(ContractFeatureTest):
    target_test_file = "library/features/deposits/fees/early_closure_fee.py"

    def create_mock(
        self,
        balance_ts=None,
        creation_date=DEFAULT_DATE,
        early_closure_fee_income_account=EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        **kwargs,
    ):
        return super().create_mock(
            balance_ts=balance_ts,
            creation_date=creation_date,
            early_closure_fee_income_account=early_closure_fee_income_account,
            **kwargs,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        early_closure_fee_debit=Decimal("0"),
        early_closure_fee_credit=Decimal("0"),
    ):
        """
        Creates balances for the relevant addresses
        !!!!!WARNING!!!!! the early_closure_fee_x parameters explicitly let you set the credit and
        debit attributes as the contract behaviour needs the tester to be able to have net 0 value
        but non-zero debit and credit

        :param early_closure_fee_debit: the debit amount for the early_closure_fee address
        :param early_closure_fee_credit: the credit amount for the early_closure_fee address
        """

        balance_dict = {
            balance_dimensions(
                denomination=DENOMINATION,
                address=DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
                phase=Phase.COMMITTED,
            ): Balance(debit=early_closure_fee_debit, credit=early_closure_fee_credit)
        }
        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)

        return [(dt, balance_default_dict)]

    def test_close_code_early_closure_fee_not_applied_if_closed_after_closure_days(self):
        effective_time = datetime(2019, 1, 9)

        balance_ts = self.account_balances(
            effective_time,
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            early_closure_fee="10",
            early_closure_days="7",
        )

        posting_instructions = get_fees(mock_vault, DENOMINATION, effective_date=effective_time)

        self.assertEqual(len(posting_instructions), 0)

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_close_code_early_closure_fee_applied_if_closed_within_closure_days(self):
        effective_time = datetime(2019, 1, 8)

        balance_ts = self.account_balances(
            effective_time,
        )

        early_closure_fee = "10"
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            early_closure_fee=early_closure_fee,
            early_closure_days="7",
        )

        posting_instructions = get_fees(mock_vault, DENOMINATION, effective_date=effective_time)

        self.assertEqual(len(posting_instructions), 2)

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(early_closure_fee),
                    client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE" f"_MOCK_HOOK_{DENOMINATION}",
                    denomination=DENOMINATION,
                    from_account_id="Main account",
                    from_account_address="DEFAULT",
                    to_account_id=EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
                    to_account_address="DEFAULT",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "EARLY CLOSURE FEE",
                        "event": "CLOSE_ACCOUNT",
                        "account_type": "MURABAHAH",
                    },
                ),
                call(
                    amount=Decimal(early_closure_fee),
                    client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE"
                    f"_MOCK_HOOK_{DENOMINATION}_TRACKER",
                    denomination=DENOMINATION,
                    from_account_id="Main account",
                    from_account_address=DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
                    to_account_id="Main account",
                    to_account_address=DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "EARLY CLOSURE FEE",
                        "event": "CLOSE_ACCOUNT",
                        "account_type": "MURABAHAH",
                    },
                ),
            ]
        )

    def test_close_code_early_closure_fee_not_applied_if_already_applied(self):
        effective_time = datetime(2019, 1, 8)

        balance_ts = self.account_balances(
            effective_time,
            early_closure_fee_debit=Decimal("10"),
            early_closure_fee_credit=Decimal("10"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            early_closure_fee="10",
            early_closure_days="7",
        )

        posting_instructions = get_fees(mock_vault, DENOMINATION, effective_date=effective_time)

        self.assertEqual(len(posting_instructions), 0)

        mock_vault.make_internal_transfer_instructions.assert_not_called()
