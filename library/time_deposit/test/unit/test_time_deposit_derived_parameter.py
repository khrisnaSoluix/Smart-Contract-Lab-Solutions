# standard libs
from datetime import datetime
from unittest.mock import patch, sentinel
from zoneinfo import ZoneInfo

# library
import library.time_deposit.contracts.template.time_deposit as time_deposit
from library.time_deposit.test.unit.test_time_deposit_common import TimeDepositTest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
)


class CommonDerivedParameterHookTest(TimeDepositTest):
    def setUp(self) -> None:
        self.mock_vault = sentinel.vault

        self.hook_arguments = DerivedParameterHookArguments(
            effective_datetime=DEFAULT_DATETIME,
        )

        patch_get_grace_period_parameter = patch.object(
            time_deposit.grace_period, "get_grace_period_parameter"
        )
        self.mock_get_grace_period_parameter = patch_get_grace_period_parameter.start()
        self.mock_get_grace_period_parameter.return_value = 0

        patch_get_maximum_withdrawal_limit = patch.object(
            time_deposit.withdrawal_fees, "get_maximum_withdrawal_limit_derived_parameter"
        )
        self.mock_get_maximum_withdrawal_limit = patch_get_maximum_withdrawal_limit.start()
        self.mock_get_maximum_withdrawal_limit.return_value = sentinel.maximum_withdrawal_limit

        patch_get_fee_free_withdrawal_limit = patch.object(
            time_deposit.withdrawal_fees, "get_fee_free_withdrawal_limit_derived_parameter"
        )
        self.mock_get_fee_free_withdrawal_limit = patch_get_fee_free_withdrawal_limit.start()
        self.mock_get_fee_free_withdrawal_limit.return_value = sentinel.fee_free_withdrawal_limit

        self.datetime_min = datetime.min.replace(tzinfo=ZoneInfo("UTC"))

        self.addCleanup(patch.stopall)
        return super().setUp()


class NewTimeDepositDerivedParameterHookTest(CommonDerivedParameterHookTest):
    def setUp(self) -> None:
        super().setUp()

        patch_get_deposit_period_end_datetime = patch.object(
            time_deposit.deposit_period, "get_deposit_period_end_datetime"
        )
        self.mock_get_deposit_period_end_datetime = patch_get_deposit_period_end_datetime.start()
        self.mock_get_deposit_period_end_datetime.return_value = sentinel.end_of_deposit

        patch_get_cooling_off_period_end_datetime = patch.object(
            time_deposit.cooling_off_period, "get_cooling_off_period_end_datetime"
        )
        self.mock_get_cooling_off_period_end_datetime = (
            patch_get_cooling_off_period_end_datetime.start()
        )
        self.mock_get_cooling_off_period_end_datetime.return_value = sentinel.end_of_cooling_off

        self.datetime_min = datetime.min.replace(tzinfo=ZoneInfo("UTC"))

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_derived_parameters(self):
        expected_derived_params = {
            "deposit_period_end_date": sentinel.end_of_deposit,
            "cooling_off_period_end_date": sentinel.end_of_cooling_off,
            "grace_period_end_date": self.datetime_min,
            "maximum_withdrawal_limit": sentinel.maximum_withdrawal_limit,
            "fee_free_withdrawal_limit": sentinel.fee_free_withdrawal_limit,
        }

        hook_result = time_deposit.derived_parameter_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(
            hook_result,
            DerivedParameterHookResult(
                parameters_return_value=expected_derived_params  # type: ignore
            ),
        )


class RenewedTimeDepositDerivedParameterHookTest(CommonDerivedParameterHookTest):
    def setUp(self) -> None:
        super().setUp()

        patch_get_grace_period_end_datetime = patch.object(
            time_deposit.grace_period, "get_grace_period_end_datetime"
        )
        self.mock_get_grace_period_end_datetime = patch_get_grace_period_end_datetime.start()
        self.mock_get_grace_period_end_datetime.return_value = sentinel.grace_period_end_datetime
        self.mock_get_grace_period_parameter.return_value = 1

    def test_derived_parameters(self):
        expected_derived_params = {
            "deposit_period_end_date": self.datetime_min,
            "cooling_off_period_end_date": self.datetime_min,
            "grace_period_end_date": sentinel.grace_period_end_datetime,
            "maximum_withdrawal_limit": sentinel.maximum_withdrawal_limit,
            "fee_free_withdrawal_limit": sentinel.fee_free_withdrawal_limit,
        }

        hook_result = time_deposit.derived_parameter_hook(
            vault=self.mock_vault, hook_arguments=self.hook_arguments
        )

        self.assertEqual(
            hook_result,
            DerivedParameterHookResult(
                parameters_return_value=expected_derived_params  # type: ignore
            ),
        )
