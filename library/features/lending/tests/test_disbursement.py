# standard library
from datetime import datetime
from unittest.mock import call
from decimal import Decimal

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ASSET,
    DEFAULT_ADDRESS,
)

from library.features.lending.disbursement import get_posting_instructions

DEFAULT_DATE = datetime(2019, 1, 1)
PRINCIPAL_ADDRESS = "PRINCIPAL"
DEFAULT_PRINCIPAL_AMOUNT = Decimal("456000")
DEFAULT_DEPOSIT_ACCOUNT = "deposit_account"
DISBURSEMENT_EVENT = "PRINCIPAL_PAYMENT"


class TestDisbursement(ContractFeatureTest):
    target_test_file = "library/features/lending/disbursement.py"

    def create_mock(
        self,
        creation_date=DEFAULT_DATE,
        deposit_account=DEFAULT_DEPOSIT_ACCOUNT,
        principal=DEFAULT_PRINCIPAL_AMOUNT,
        **kwargs,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            **kwargs,
        )

    @classmethod
    def setupClass(cls):
        cls.maxDiff = None
        super().setUpClass()

    def test_get_posting_instructions(self):
        mock_vault = self.create_mock()

        results = get_posting_instructions(mock_vault, "GBP")

        # should contain only disbursement posting instruction with full disbursal amount
        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=DEFAULT_PRINCIPAL_AMOUNT,
                    denomination="GBP",
                    client_transaction_id="MOCK_HOOK_PRINCIPAL_DISBURSEMENT",
                    from_account_id=mock_vault.account_id,
                    from_account_address=PRINCIPAL_ADDRESS,
                    to_account_id=DEFAULT_DEPOSIT_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Principal disbursement of {DEFAULT_PRINCIPAL_AMOUNT}",
                        "event": DISBURSEMENT_EVENT,
                    },
                    asset=DEFAULT_ASSET,
                )
            ]
        )

    def test_get_posting_instructions_principal_address_override(self):
        mock_vault = self.create_mock()
        NEW_PRINCIPAL_ADDRESS = "NEW_PRINCIPAL_ADDRESS"

        results = get_posting_instructions(
            mock_vault, "GBP", principal_address=NEW_PRINCIPAL_ADDRESS
        )

        self.assertEqual(len(results), 1)
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=DEFAULT_PRINCIPAL_AMOUNT,
            denomination="GBP",
            client_transaction_id="MOCK_HOOK_PRINCIPAL_DISBURSEMENT",
            from_account_id=mock_vault.account_id,
            from_account_address=NEW_PRINCIPAL_ADDRESS,
            to_account_id=DEFAULT_DEPOSIT_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": f"Principal disbursement of {DEFAULT_PRINCIPAL_AMOUNT}",
                "event": DISBURSEMENT_EVENT,
            },
            asset=DEFAULT_ASSET,
        )
