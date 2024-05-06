# standard libs
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common import events
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending import emi_in_advance

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
    SentinelPosting,
)


@patch.object(emi_in_advance.emi, "amortise")
@patch.object(emi_in_advance.due_amount_calculation, "transfer_principal_due")
@patch.object(emi_in_advance.utils, "get_parameter")
class ChargeInAdvanceTest(FeatureTest):
    maxDiff = None

    def test_charge_instructions(
        self,
        mock_get_parameter: MagicMock,
        mock_transfer_principal_due: MagicMock,
        mock_amortise: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "principal": sentinel.principal,
            }
        )
        mock_calculate_emi = MagicMock(return_value=sentinel.emi)
        mock_amortisation_feature = MagicMock(calculate_emi=mock_calculate_emi)

        sentinel_emi_instruction = SentinelCustomInstruction("emi")
        sentinel_due_postings = [SentinelPosting("due-credit"), SentinelPosting("due-debit")]
        mock_transfer_principal_due.return_value = sentinel_due_postings
        mock_amortise.return_value = [sentinel_emi_instruction]
        mock_vault = self.create_mock(account_id=sentinel.account_id)

        actual = emi_in_advance.charge(
            mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_amortisation_feature,
        )
        expected = [
            sentinel_emi_instruction,
            CustomInstruction(
                postings=sentinel_due_postings,
                instruction_details={
                    "description": "Principal due on activation",
                    "event": events.ACCOUNT_ACTIVATION,
                },
            ),
        ]
        self.assertEqual(expected, actual)
        mock_amortise.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            amortisation_feature=mock_amortisation_feature,
        )
        mock_calculate_emi.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            principal_amount=sentinel.principal,
        )
        mock_transfer_principal_due.assert_called_once_with(
            customer_account=sentinel.account_id,
            principal_due=sentinel.emi,
            denomination=sentinel.denomination,
        )
