# standard libs
from unittest.mock import sentinel

# library
from library.bnpl.contracts.template import bnpl
from library.bnpl.test.unit.test_bnpl_common import BNPLTest

# contracts api
from contracts_api import PreParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PreParameterChangeHookResult,
    Rejection,
    RejectionReason,
)


class PreParameterChangeHookTest(BNPLTest):
    def test_restricted_parameter_change_is_rejected(self):
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={bnpl.RESTRICTED_PARAMETERS[0]: "dummy_value"},
        )

        expected = PreParameterChangeHookResult(
            rejection=Rejection(
                message="T&Cs of this loan cannot be changed once opened.",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )
        result = bnpl.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertEqual(result, expected)

    def test_non_restricted_parameter_change_is_not_rejected(self):
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values={"non_restricted_parameter": "dummy_value"},
        )
        result = bnpl.pre_parameter_change_hook(vault=sentinel.vault, hook_arguments=hook_args)
        self.assertIsNone(result)
