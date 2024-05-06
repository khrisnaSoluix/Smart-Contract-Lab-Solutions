# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# contracts api
from contracts_api import PreParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PreParameterChangeHookResult,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelRejection,
)


class NewTimeDepositPreParameterChangeHookTest(TimeDepositTest):
    def test_term_not_in_updated_parameters_returns_none(self):
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={sentinel.parameter: sentinel.value},
        )
        self.assertIsNone(
            time_deposit.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        )

    @patch.object(time_deposit.grace_period, "get_grace_period_parameter")
    def test_term_in_updated_parameters_for_new_time_deposit_raises_rejection(
        self, mock_get_grace_period_parameter: MagicMock
    ):
        mock_get_grace_period_parameter.return_value = 0
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={time_deposit.deposit_parameters.PARAM_TERM: 5},
        )
        expected_result = PreParameterChangeHookResult(
            rejection=Rejection(
                message="Term length can only be changed on Renewed Time Deposit accounts",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        self.assertEqual(
            time_deposit.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args),
            expected_result,
        )


class RenewedTimeDepositPreParameterChangeHookTest(TimeDepositTest):
    def setUp(self) -> None:
        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()
        self.mock_get_grace_period_parameter.return_value = 1

        patch_grace_period_validate_term = patch.object(
            time_deposit.grace_period, "validate_term_parameter_change"
        )
        self.mock_grace_period_validate_term = patch_grace_period_validate_term.start()
        self.mock_grace_period_validate_term.return_value = None

        patch_deposit_maturity_validate_term = patch.object(
            time_deposit.deposit_maturity, "validate_term_parameter_change"
        )
        self.mock_deposit_maturity_validate_term = patch_deposit_maturity_validate_term.start()
        self.mock_deposit_maturity_validate_term.return_value = None

        self.hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={time_deposit.deposit_parameters.PARAM_TERM: 5},
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_valid_term_change_returns_none(self):
        self.assertIsNone(
            time_deposit.pre_parameter_change_hook(
                vault=sentinel.vault, hook_arguments=self.hook_args
            )
        )
        self.mock_get_grace_period_parameter.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_deposit_maturity_validate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            proposed_term_value=5,
        )

    def test_term_change_violating_grace_period_validation_raises_rejection(self):
        self.mock_grace_period_validate_term.return_value = SentinelRejection(
            "grace_period_rejection"
        )
        expected_result = PreParameterChangeHookResult(
            rejection=SentinelRejection("grace_period_rejection")
        )
        self.assertEqual(
            time_deposit.pre_parameter_change_hook(
                vault=sentinel.vault, hook_arguments=self.hook_args
            ),
            expected_result,
        )

        self.mock_get_grace_period_parameter.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_deposit_maturity_validate_term.assert_not_called()

    def test_term_change_violating_deposit_maturity_validation_raises_rejection(self):
        self.mock_deposit_maturity_validate_term.return_value = SentinelRejection(
            "deposit_maturity_rejection"
        )
        expected_result = PreParameterChangeHookResult(
            rejection=SentinelRejection("deposit_maturity_rejection")
        )
        self.assertEqual(
            time_deposit.pre_parameter_change_hook(
                vault=sentinel.vault, hook_arguments=self.hook_args
            ),
            expected_result,
        )

        self.mock_get_grace_period_parameter.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=DEFAULT_DATETIME
        )
        self.mock_deposit_maturity_validate_term.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            proposed_term_value=5,
        )
