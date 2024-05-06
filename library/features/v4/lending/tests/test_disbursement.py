# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending import disbursement

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ACCOUNT_ID, FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
)

DEFAULT_DENOMINATION = "GBP"
DEFAULT_PRINCIPAL_AMOUNT = Decimal("456000")
DEFAULT_DEPOSIT_ACCOUNT = "deposit_account"


class TestDisbursement(FeatureTest):
    def test_get_posting_instructions(self):
        expected = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=False,
                        amount=DEFAULT_PRINCIPAL_AMOUNT,
                        denomination=DEFAULT_DENOMINATION,
                        account_id=ACCOUNT_ID,
                        account_address=disbursement.lending_addresses.PRINCIPAL,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=True,
                        amount=DEFAULT_PRINCIPAL_AMOUNT,
                        denomination=DEFAULT_DENOMINATION,
                        account_id=DEFAULT_DEPOSIT_ACCOUNT,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                override_all_restrictions=True,
                instruction_details={
                    "description": f"Principal disbursement of {DEFAULT_PRINCIPAL_AMOUNT}",
                    "event": disbursement.DISBURSEMENT_EVENT,
                },
            )
        ]

        result = disbursement.get_disbursement_custom_instruction(
            account_id=ACCOUNT_ID,
            deposit_account_id=DEFAULT_DEPOSIT_ACCOUNT,
            principal=DEFAULT_PRINCIPAL_AMOUNT,
            denomination=DEFAULT_DENOMINATION,
            principal_address=disbursement.lending_addresses.PRINCIPAL,
        )
        self.assertEqual(expected, result)

    def test_get_posting_instructions_principal_address_override(self):
        NEW_PRINCIPAL_ADDRESS = "NEW_PRINCIPAL_ADDRESS"
        expected = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=False,
                        amount=DEFAULT_PRINCIPAL_AMOUNT,
                        denomination=DEFAULT_DENOMINATION,
                        account_id=ACCOUNT_ID,
                        account_address=NEW_PRINCIPAL_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=True,
                        amount=DEFAULT_PRINCIPAL_AMOUNT,
                        denomination=DEFAULT_DENOMINATION,
                        account_id=DEFAULT_DEPOSIT_ACCOUNT,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                override_all_restrictions=True,
                instruction_details={
                    "description": f"Principal disbursement of {DEFAULT_PRINCIPAL_AMOUNT}",
                    "event": disbursement.DISBURSEMENT_EVENT,
                },
            )
        ]

        result = disbursement.get_disbursement_custom_instruction(
            account_id=ACCOUNT_ID,
            deposit_account_id=DEFAULT_DEPOSIT_ACCOUNT,
            principal=DEFAULT_PRINCIPAL_AMOUNT,
            denomination=DEFAULT_DENOMINATION,
            principal_address=NEW_PRINCIPAL_ADDRESS,
        )
        self.assertEqual(expected, result)


@patch.object(disbursement.utils, "get_parameter")
class GetParametersTest(FeatureTest):
    def test_get_principal_parameter(self, mock_get_parameter: MagicMock):
        principal_parameter = 1000

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={disbursement.PARAM_PRINCIPAL: principal_parameter},
        )

        result = disbursement.get_principal_parameter(vault=sentinel.vault)

        self.assertEqual(
            principal_parameter,
            result,
        )

    def test_get_deposit_account_parameter(self, mock_get_parameter: MagicMock):
        deposit_account = "dummy_account"

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={disbursement.PARAM_DEPOSIT_ACCOUNT: deposit_account},
        )

        result = disbursement.get_deposit_account_parameter(vault=sentinel.vault)

        self.assertEqual(
            deposit_account,
            result,
        )
