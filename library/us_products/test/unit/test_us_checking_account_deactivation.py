# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# features
import library.features.common.fetchers as fetchers

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DeactivationHookArguments,
    DeactivationHookResult,
    PostingInstructionsDirective,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)


class DeactivationHookTest(CheckingAccountTest):
    @patch.object(us_checking_account.dormancy, "is_account_dormant")
    def test_close_account_rejected_when_dormant(
        self,
        mock_is_account_dormant: MagicMock,
    ):
        # construct mocks
        mock_is_account_dormant.return_value = True

        # expected result
        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close a dormant account.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # run hook
        result = us_checking_account.deactivation_hook(
            sentinel.vault, DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(us_checking_account.partial_fee, "has_outstanding_fees")
    @patch.object(us_checking_account.dormancy, "is_account_dormant")
    def test_close_account_rejected_when_has_outstanding_fees(
        self,
        mock_is_account_dormant: MagicMock,
        mock_has_outstanding_fees: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        mock_is_account_dormant.return_value = False
        mock_has_outstanding_fees.return_value = True

        # expected result
        expected_result = DeactivationHookResult(
            rejection=Rejection(
                message="Cannot close account with outstanding fees.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        # run hook
        result = us_checking_account.deactivation_hook(
            mock_vault, DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=SentinelBalancesObservation("live_balances").balances,
        )

    @patch.object(us_checking_account.tiered_interest_accrual, "get_interest_reversal_postings")
    @patch.object(us_checking_account.utils, "get_parameter")
    @patch.object(us_checking_account.partial_fee, "has_outstanding_fees")
    @patch.object(us_checking_account.dormancy, "is_account_dormant")
    def test_close_account_successful_when_not_dormant_and_no_reversal_instructions(
        self,
        mock_is_account_dormant: MagicMock,
        mock_has_outstanding_fees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_interest_reversal_postings: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        mock_is_account_dormant.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.return_value = False
        mock_get_interest_reversal_postings.return_value = []

        # run hook
        result = us_checking_account.deactivation_hook(
            mock_vault, DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertIsNone(result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_get_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name=us_checking_account.CLOSE_ACCOUNT,
            account_type=us_checking_account.PRODUCT_NAME,
            balances=SentinelBalancesObservation("live_balances").balances,
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=SentinelBalancesObservation("live_balances").balances,
        )

    @patch.object(us_checking_account.tiered_interest_accrual, "get_interest_reversal_postings")
    @patch.object(us_checking_account.utils, "get_parameter")
    @patch.object(us_checking_account.partial_fee, "has_outstanding_fees")
    @patch.object(us_checking_account.dormancy, "is_account_dormant")
    def test_close_account_forfeit_accrued_interest(
        self,
        mock_is_account_dormant: MagicMock,
        mock_has_outstanding_fees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_interest_reversal_postings: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        mock_is_account_dormant.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.return_value = False
        mock_get_interest_reversal_postings.return_value = [
            SentinelCustomInstruction("reverse_accrued_interest")
        ]

        # expected result
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("reverse_accrued_interest")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"MOCK_HOOK_{us_checking_account.CLOSE_ACCOUNT}",
                )
            ]
        )

        # run hook
        result = us_checking_account.deactivation_hook(
            mock_vault, DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_get_interest_reversal_postings.assert_called_once_with(
            vault=mock_vault,
            event_name=us_checking_account.CLOSE_ACCOUNT,
            account_type=us_checking_account.PRODUCT_NAME,
            balances=SentinelBalancesObservation("live_balances").balances,
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=SentinelBalancesObservation("live_balances").balances,
        )

    @patch.object(us_checking_account.interest_application, "apply_interest")
    @patch.object(us_checking_account.utils, "get_parameter")
    @patch.object(us_checking_account.partial_fee, "has_outstanding_fees")
    @patch.object(us_checking_account.dormancy, "is_account_dormant")
    def test_close_account_capitalise_accrued_interest(
        self,
        mock_is_account_dormant: MagicMock,
        mock_has_outstanding_fees: MagicMock,
        mock_get_parameter: MagicMock,
        mock_apply_interest: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                fetchers.LIVE_BALANCES_BOF_ID: SentinelBalancesObservation("live_balances")
            }
        )
        mock_is_account_dormant.return_value = False
        mock_has_outstanding_fees.return_value = False
        mock_get_parameter.return_value = True
        mock_apply_interest.return_value = [SentinelCustomInstruction("apply_interest")]

        # expected result
        expected_result = DeactivationHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=[SentinelCustomInstruction("apply_interest")],
                    value_datetime=DEFAULT_DATETIME,
                    client_batch_id=f"MOCK_HOOK_{us_checking_account.CLOSE_ACCOUNT}",
                )
            ]
        )

        # run hook
        result = us_checking_account.deactivation_hook(
            mock_vault, DeactivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        mock_apply_interest.assert_called_once_with(
            vault=mock_vault,
            account_type=us_checking_account.PRODUCT_NAME,
            balances=SentinelBalancesObservation("live_balances").balances,
        )
        mock_has_outstanding_fees.assert_called_once_with(
            vault=mock_vault,
            fee_collection=us_checking_account.FEE_HIERARCHY,
            balances=SentinelBalancesObservation("live_balances").balances,
        )
