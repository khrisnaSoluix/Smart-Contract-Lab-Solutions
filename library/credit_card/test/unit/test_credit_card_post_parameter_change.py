# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from unittest.mock import MagicMock, patch, sentinel

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# contracts api
from contracts_api import PostParameterChangeHookArguments

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    PostingInstructionsDirective,
    PostParameterChangeHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelCustomInstruction,
)


@patch.object(credit_card, "_handle_credit_limit_change")
class PostParameterChangeHookTest(CreditCardTestBase):
    def test_no_credit_limit_change_posting_instructions_returns_none(
        self,
        mock_handle_credit_limit_change: MagicMock,
    ):
        # construct mocks
        mock_handle_credit_limit_change.return_value = []

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values=sentinel.updated_parameter_values,
        )

        result = credit_card.post_parameter_change_hook(
            vault=sentinel.vault,
            hook_arguments=hook_args,
        )

        self.assertIsNone(result)

        mock_handle_credit_limit_change.assert_called_once_with(
            sentinel.vault,
            sentinel.old_parameter_values,
            sentinel.updated_parameter_values,
        )

    def test_handle_credit_limit_change_directives_returned(
        self,
        mock_handle_credit_limit_change: MagicMock,
    ):
        # construct mocks
        posting_instructions = [SentinelCustomInstruction("credit_limit_change_postings")]

        mock_handle_credit_limit_change.return_value = posting_instructions

        # construct expected result
        expected_result = PostParameterChangeHookResult(
            posting_instructions_directives=[
                PostingInstructionsDirective(
                    posting_instructions=posting_instructions, value_datetime=DEFAULT_DATETIME
                )
            ]
        )

        # run function
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values=sentinel.updated_parameter_values,
        )

        result = credit_card.post_parameter_change_hook(
            vault=sentinel.vault,
            hook_arguments=hook_args,
        )

        self.assertEqual(result, expected_result)

        mock_handle_credit_limit_change.assert_called_once_with(
            sentinel.vault,
            sentinel.old_parameter_values,
            sentinel.updated_parameter_values,
        )
