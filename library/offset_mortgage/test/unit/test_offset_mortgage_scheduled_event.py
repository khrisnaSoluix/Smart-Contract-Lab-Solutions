# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# library
import library.offset_mortgage.supervisors.template.offset_mortgage as offset_mortgage
from library.offset_mortgage.test.unit.test_offset_mortgage_common import OffsetMortgageTestBase

# features
from library.features.v4.common.test.mocks import (
    mock_supervisor_get_supervisees_for_alias,
    mock_utils_get_parameter,
)

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Phase,
    SupervisorScheduledEventHookArguments,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    CustomInstruction,
    PostingInstructionsDirective,
    ScheduledEventHookResult,
    SupervisorScheduledEventHookResult,
    UpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelCustomInstruction,
    SentinelPostingInstructionsDirective,
    SentinelUpdateAccountEventTypeDirective,
)

OFFSET_HOOK_ARGUMENTS = SupervisorScheduledEventHookArguments(
    effective_datetime=DEFAULT_DATETIME,
    event_type=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
    supervisee_pause_at_datetime={},
)


class DummyEventTest(OffsetMortgageTestBase):
    def test_blank_hook_returns_none(self):
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type="dummy_event",
            supervisee_pause_at_datetime={},
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)


class InterestAccrualTest(OffsetMortgageTestBase):
    event_type = offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT

    @patch.object(offset_mortgage, "_handle_accrue_offset_interest")
    def test_none_returned_when_no_directives(self, mock_handle_accrue_offset_interest: MagicMock):
        mock_handle_accrue_offset_interest.return_value = ({}, {}, {})
        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertIsNone(result)

    @patch.object(offset_mortgage, "_handle_accrue_offset_interest")
    def test_hook_result_returned_when_only_pi_directives(
        self, mock_handle_accrue_offset_interest: MagicMock
    ):
        # construct mocks
        mock_handle_accrue_offset_interest.return_value = (
            {},
            {"supervisee": [SentinelPostingInstructionsDirective("posting")]},
            {},
        )

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        # construct expected result
        expected_result = SupervisorScheduledEventHookResult(
            supervisee_posting_instructions_directives={
                "supervisee": [SentinelPostingInstructionsDirective("posting")]
            }
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)

    @patch.object(offset_mortgage, "_handle_accrue_offset_interest")
    def test_hook_result_returned_when_only_notification_directives(
        self, mock_handle_accrue_offset_interest: MagicMock
    ):
        # construct mocks
        mock_handle_accrue_offset_interest.return_value = (
            {"supervisee": [SentinelAccountNotificationDirective("notification")]},
            {},
            {},
        )

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        # construct expected result
        expected_result = SupervisorScheduledEventHookResult(
            supervisee_account_notification_directives={
                "supervisee": [SentinelAccountNotificationDirective("notification")]
            }
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)

    @patch.object(offset_mortgage, "_handle_accrue_offset_interest")
    def test_hook_result_returned_when_only_update_event_type_directives(
        self, mock_handle_accrue_offset_interest: MagicMock
    ):
        # construct mocks
        mock_handle_accrue_offset_interest.return_value = (
            {},
            {},
            {"supervisee": [SentinelUpdateAccountEventTypeDirective("update_account_event_type")]},
        )

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        # construct expected result
        expected_result = SupervisorScheduledEventHookResult(
            supervisee_update_account_event_type_directives={
                "supervisee": [SentinelUpdateAccountEventTypeDirective("update_account_event_type")]
            }
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)

    @patch.object(offset_mortgage, "_handle_accrue_offset_interest")
    def test_hook_result_returned_when_all_directives_present(
        self, mock_handle_accrue_offset_interest: MagicMock
    ):
        # construct mocks
        mock_handle_accrue_offset_interest.return_value = (
            {"supervisee": [SentinelAccountNotificationDirective("notification")]},
            {"supervisee": [SentinelPostingInstructionsDirective("posting")]},
            {"supervisee": [SentinelUpdateAccountEventTypeDirective("update_account_event_type")]},
        )

        hook_arguments = SupervisorScheduledEventHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            event_type=self.event_type,
            supervisee_pause_at_datetime={},
        )

        # construct expected result
        expected_result = SupervisorScheduledEventHookResult(
            supervisee_account_notification_directives={
                "supervisee": [SentinelAccountNotificationDirective("notification")]
            },
            supervisee_posting_instructions_directives={
                "supervisee": [SentinelPostingInstructionsDirective("posting")]
            },
            supervisee_update_account_event_type_directives={
                "supervisee": [SentinelUpdateAccountEventTypeDirective("update_account_event_type")]
            },
        )

        # run function
        result = offset_mortgage.scheduled_event_hook(sentinel.vault, hook_arguments)
        self.assertEqual(result, expected_result)


@patch.object(offset_mortgage.supervisor_utils, "get_supervisees_for_alias")
class HandleAccrueOffsetInterestTest(OffsetMortgageTestBase):
    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_no_associated_accounts_returns_empty_dict(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [],
            }
        )

        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, ({}, {}, {}))
        mock_get_supervisee_directives_mapping.assert_not_called()

    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_mortgage_associated_returns_mortgage_nids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = sentinel.mortgage
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [],
            }
        )
        mock_get_supervisee_directives_mapping.return_value = (
            {"mortgage": sentinel.mortgage_nids},
            {},
            {},
        )

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = ({"mortgage": sentinel.mortgage_nids}, {}, {})
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_called_once_with(vault=mortgage)

    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_mortgage_associated_returns_mortgage_uetids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = sentinel.mortgage
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [],
            }
        )
        mock_get_supervisee_directives_mapping.return_value = (
            {},
            {},
            {"mortgage": sentinel.mortgage_uatids},
        )

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = ({}, {}, {"mortgage": sentinel.mortgage_uatids})
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_called_once_with(vault=mortgage)

    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_mortgage_associated_returns_mortgage_all_directive_ids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = sentinel.mortgage
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [],
            }
        )
        mock_get_supervisee_directives_mapping.return_value = (
            {"mortgage": sentinel.mortgage_nids},
            {"mortgage": sentinel.mortgage_pids},
            {"mortgage": sentinel.mortgage_uetids},
        )

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = (
            {"mortgage": sentinel.mortgage_nids},
            {"mortgage": sentinel.mortgage_pids},
            {"mortgage": sentinel.mortgage_uetids},
        )
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_called_once_with(vault=mortgage)

    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_mortgage_associated_returns_mortgage_pids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = sentinel.mortgage
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [],
            }
        )
        mock_get_supervisee_directives_mapping.return_value = (
            {},
            {"mortgage": sentinel.mortgage_pids},
            {},
        )

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = ({}, {"mortgage": sentinel.mortgage_pids}, {})
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_called_once_with(vault=mortgage)

    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_casa_accounts_associated_returns_casa_pids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        ca = sentinel.ca
        sa = sentinel.sa
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [ca],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [sa],
            }
        )
        mock_get_supervisee_directives_mapping.side_effect = [
            ({}, {"sa": sentinel.sa_pids}, {}),
            ({}, {"ca": sentinel.ca_pids}, {}),
        ]

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = ({}, {"sa": sentinel.sa_pids, "ca": sentinel.ca_pids}, {})
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_has_calls(
            calls=[call(vault=sa), call(vault=ca)]
        )

    @patch.object(offset_mortgage, "_split_supervisees_by_eligibility")
    @patch.object(offset_mortgage.utils, "get_parameter")
    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_only_ineligible_returns_ineligible_casa_and_mortgage_pids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_parameter: MagicMock,
        mock_split_supervisees_by_eligibility: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = sentinel.mortgage
        ineligible_ca = sentinel.ineligible_ca
        ineligible_sa = sentinel.ineligible_sa
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [ineligible_ca],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [ineligible_sa],
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_split_supervisees_by_eligibility.return_value = [], [ineligible_ca, ineligible_sa]

        mock_get_supervisee_directives_mapping.side_effect = [
            ({}, {"ca": sentinel.ineligible_ca_pids}, {}),
            ({}, {"sa": sentinel.ineligible_sa_pids}, {}),
            ({}, {"mortgage": sentinel.mortgage_pids}, {}),
        ]

        # construct expected result
        supervisee_directives_id: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = (
            {},
            {
                "ca": sentinel.ineligible_ca_pids,
                "sa": sentinel.ineligible_sa_pids,
                "mortgage": sentinel.mortgage_pids,
            },
            {},
        )
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )
        self.assertTupleEqual(result, supervisee_directives_id)
        mock_get_supervisee_directives_mapping.assert_has_calls(
            calls=[call(vault=ineligible_ca), call(vault=ineligible_sa), call(vault=mortgage)]
        )

    @patch.object(offset_mortgage, "_split_supervisees_by_eligibility")
    @patch.object(offset_mortgage.utils, "get_parameter")
    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_mortgage_and_casas_associated_but_no_mortgage_pids_preserves_and_returns_casa_pids(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_parameter: MagicMock,
        mock_split_supervisees_by_eligibility: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(posting_instructions_directives=[])
        )
        ineligible_ca = sentinel.ineligible_ca
        eligible_sa = sentinel.eligible_sa
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [ineligible_ca],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [eligible_sa],
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_split_supervisees_by_eligibility.return_value = [eligible_sa], [ineligible_ca]

        mock_get_supervisee_directives_mapping.side_effect = [
            ({}, {"ca": sentinel.ineligible_ca_pids}, {}),
            ({}, {"sa": sentinel.eligible_sa_pids}, {}),
        ]

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = (
            {},
            {"ca": sentinel.ineligible_ca_pids, "sa": sentinel.eligible_sa_pids},
            {},
        )

        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault, sentinel.hook_arguments
        )

        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_has_calls(
            calls=[call(vault=ineligible_ca), call(vault=eligible_sa)]
        )

    @patch.object(offset_mortgage, "_generate_offset_accrual_posting_directives_mapping")
    @patch.object(offset_mortgage, "_split_supervisees_by_eligibility")
    @patch.object(offset_mortgage.utils, "get_parameter")
    @patch.object(offset_mortgage.supervisor_utils, "get_supervisee_directives_mapping")
    def test_mortgage_offset_pids_returned_and_ineligible_casas_are_preserved(
        self,
        mock_get_supervisee_directives_mapping: MagicMock,
        mock_get_parameter: MagicMock,
        mock_split_supervisees_by_eligibility: MagicMock,
        mock_generate_offset_accrual_posting_directives_mapping: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        # construct mocks
        mortgage = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(
                posting_instructions_directives=[SentinelPostingInstructionsDirective("mortgage")]
            )
        )
        ineligible_ca = sentinel.ineligible_ca
        sa = sentinel.sa
        mock_get_supervisees_for_alias.side_effect = mock_supervisor_get_supervisees_for_alias(
            supervisees={
                offset_mortgage.MORTGAGE_ALIAS: [mortgage],
                offset_mortgage.CURRENT_ACCOUNT_ALIAS: [ineligible_ca],
                offset_mortgage.SAVINGS_ACCOUNT_ALIAS: [sa],
            }
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": sentinel.denomination}
        )
        mock_split_supervisees_by_eligibility.return_value = [sa], [ineligible_ca]

        mock_get_supervisee_directives_mapping.side_effect = [
            ({}, {"ca": sentinel.ineligible_ca_pids}, {})
        ]
        mock_generate_offset_accrual_posting_directives_mapping.return_value = {
            "mortgage": sentinel.mortgage_accrual_pids
        }

        # construct expected result
        supervisee_directives_ids: tuple[
            dict[str, list[AccountNotificationDirective]],
            dict[str, list[PostingInstructionsDirective]],
            dict[str, list[UpdateAccountEventTypeDirective]],
        ] = (
            {},
            {
                "ca": sentinel.ineligible_ca_pids,
                "mortgage": sentinel.mortgage_accrual_pids,
            },
            {},
        )
        # run function
        result = offset_mortgage._handle_accrue_offset_interest(
            sentinel.vault,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=offset_mortgage.ACCRUE_OFFSET_INTEREST_EVENT,
                supervisee_pause_at_datetime={},
            ),
        )
        self.assertTupleEqual(result, supervisee_directives_ids)
        mock_get_supervisee_directives_mapping.assert_called_once_with(vault=ineligible_ca)


@patch.object(offset_mortgage, "_split_instructions_into_offset_eligible_and_preserved")
class GenerateOffsetAccrualPostingDirectivesMappingTest(OffsetMortgageTestBase):
    def mortgage_posting_directives(self) -> PostingInstructionsDirective:
        return PostingInstructionsDirective(
            posting_instructions=[SentinelCustomInstruction("mortgage")]
        )

    def test_no_offset_eligible_instructions(
        self,
        mock_split_instructions_into_offset_eligible_and_preserved: MagicMock,
    ):
        # expected values
        instructions_to_preserve = [SentinelCustomInstruction("preserve")]

        # construct mocks
        mortgage_account_id = "mortgage"
        mortgage_vault = self.create_supervisee_mock(account_id=mortgage_account_id)
        mock_split_instructions_into_offset_eligible_and_preserved.return_value = (
            [],
            instructions_to_preserve,
        )

        # construct expected result
        expected_result = {
            mortgage_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=instructions_to_preserve,  # type: ignore
                    value_datetime=OFFSET_HOOK_ARGUMENTS.effective_datetime,
                )
            ]
        }

        # run function
        result = offset_mortgage._generate_offset_accrual_posting_directives_mapping(
            mortgage_account=mortgage_vault,
            mortgage_posting_directives=[self.mortgage_posting_directives()],
            eligible_accounts=[],
            mortgage_denomination=sentinel.denomination,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
        )
        self.assertDictEqual(result, expected_result)

    @patch.object(offset_mortgage, "_get_offset_accrual_instructions")
    def test_accrual_instructions_returned(
        self,
        mock_get_offset_accrual_instructions: MagicMock,
        mock_split_instructions_into_offset_eligible_and_preserved: MagicMock,
    ):
        # expected values
        instructions_to_preserve = [SentinelCustomInstruction("preserve")]
        offset_eligible_instructions = [SentinelCustomInstruction("eligible")]
        offset_accrual_instructions = [SentinelCustomInstruction("offset")]

        # construct mocks
        mortgage_account_id = "mortgage"
        mortgage_vault = self.create_supervisee_mock(account_id=mortgage_account_id)
        eligible_ca = self.create_supervisee_mock()
        mock_split_instructions_into_offset_eligible_and_preserved.return_value = (
            offset_eligible_instructions,
            instructions_to_preserve,
        )
        mock_get_offset_accrual_instructions.return_value = offset_accrual_instructions

        # construct expected result
        expected_result = {
            mortgage_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=[*instructions_to_preserve, *offset_accrual_instructions],
                    value_datetime=OFFSET_HOOK_ARGUMENTS.effective_datetime,
                )
            ]
        }

        # run function
        result = offset_mortgage._generate_offset_accrual_posting_directives_mapping(
            mortgage_account=mortgage_vault,
            mortgage_posting_directives=[self.mortgage_posting_directives()],
            eligible_accounts=[eligible_ca],
            mortgage_denomination=sentinel.denomination,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
        )
        self.assertDictEqual(result, expected_result)

    @patch.object(offset_mortgage, "_get_offset_accrual_instructions")
    def test_only_preserved_instructions_when_no_accrual_instructions_returned(
        self,
        mock_get_offset_accrual_instructions: MagicMock,
        mock_split_instructions_into_offset_eligible_and_preserved: MagicMock,
    ):
        # expected values
        instructions_to_preserve = [SentinelCustomInstruction("preserve")]
        offset_eligible_instructions = [SentinelCustomInstruction("eligible")]

        # construct mocks
        mortgage_account_id = "mortgage"
        mortgage_vault = self.create_supervisee_mock(account_id=mortgage_account_id)
        eligible_ca = self.create_supervisee_mock()
        mock_split_instructions_into_offset_eligible_and_preserved.return_value = (
            offset_eligible_instructions,
            instructions_to_preserve,
        )
        mock_get_offset_accrual_instructions.return_value = []

        # construct expected result
        expected_result = {
            mortgage_account_id: [
                PostingInstructionsDirective(
                    posting_instructions=[*instructions_to_preserve],
                    value_datetime=OFFSET_HOOK_ARGUMENTS.effective_datetime,
                )
            ]
        }

        # run function
        result = offset_mortgage._generate_offset_accrual_posting_directives_mapping(
            mortgage_account=mortgage_vault,
            mortgage_posting_directives=[self.mortgage_posting_directives()],
            eligible_accounts=[eligible_ca],
            mortgage_denomination=sentinel.denomination,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
        )
        self.assertDictEqual(result, expected_result)


class GetOffsetAccrualInstructionsTest(OffsetMortgageTestBase):
    @patch.object(offset_mortgage.overpayment, "track_interest_on_expected_principal")
    @patch.object(offset_mortgage.interest_accrual, "daily_accrual_logic")
    @patch.object(offset_mortgage.utils, "balance_at_coordinates")
    @patch.object(offset_mortgage.utils, "get_balance_default_dict_from_mapping")
    @patch.object(offset_mortgage.utils, "get_parameter")
    def test_offset_accrual_instructions_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_balance_default_dict_from_mapping: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_interest_accrual: MagicMock,
        mock_expected_interest_accrual: MagicMock,
    ):
        # expected values
        mortgage_outstanding_principal = Decimal("300000")
        total_casa_available_balance = Decimal("10000")
        original_mortgage_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=offset_mortgage.lending_addresses.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=mortgage_outstanding_principal, debit=mortgage_outstanding_principal)
            }
        )
        offset_mortgage_balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=offset_mortgage.lending_addresses.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(
                    net=mortgage_outstanding_principal - total_casa_available_balance,
                    debit=mortgage_outstanding_principal,
                    credit=total_casa_available_balance,
                )
            }
        )
        ca_balances = sentinel.ca_balances

        accrual_custom_instructions = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS, instruction_details={"description": "accrual postings"}
            )
        ]
        expected_accrual_custom_instructions = [
            CustomInstruction(
                postings=DEFAULT_POSTINGS,
                instruction_details={"description": "expected accrual postings"},
            )
        ]
        mock_interest_accrual.return_value = accrual_custom_instructions
        mock_expected_interest_accrual.return_value = expected_accrual_custom_instructions

        # construct mocks
        mortgage_account_id = "mortgage"
        mortgage_vault = self.create_supervisee_mock(
            account_id=mortgage_account_id, requires_fetched_balances={}
        )
        eligible_ca = self.create_supervisee_mock(
            requires_fetched_balances={"eligible_ca": sentinel.balances}
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "accrued_interest_receivable_account": sentinel.accrued_interest_receivable_account,
                "accrual_precision": 5,
            }
        )
        mock_get_balance_default_dict_from_mapping.side_effect = [
            original_mortgage_balances,
            ca_balances,
        ]
        mock_balance_at_coordinates.return_value = total_casa_available_balance

        # construct expected result
        expected_result = accrual_custom_instructions + expected_accrual_custom_instructions

        # run function
        result = offset_mortgage._get_offset_accrual_instructions(
            mortgage_account=mortgage_vault,
            eligible_accounts=[eligible_ca],
            mortgage_denomination=sentinel.denomination,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
        )
        self.assertListEqual(result, expected_result)
        # The mock returns are mutated by the function so we need to check the mutations again.
        self.assertDictEqual(
            result[0].instruction_details,
            {"description": "accrual postings offset by balance sentinel.denomination 10000"},
        )
        self.assertDictEqual(
            result[1].instruction_details,
            {
                "description": (
                    "expected accrual postings offset by balance sentinel.denomination 10000"
                )
            },
        )

        mock_balance_at_coordinates.assert_called_once_with(
            balances=ca_balances,
            denomination=sentinel.denomination,
        )
        mock_interest_accrual.assert_called_once_with(
            vault=mortgage_vault,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
            interest_rate_feature=offset_mortgage.fixed_to_variable.InterestRate,
            account_type=offset_mortgage.ACCOUNT_TYPE,
            balances=offset_mortgage_balances,
            denomination=sentinel.denomination,
        )
        mock_expected_interest_accrual.assert_called_once_with(
            vault=mortgage_vault,
            hook_arguments=OFFSET_HOOK_ARGUMENTS,
            balances=offset_mortgage_balances,
            interest_rate_feature=offset_mortgage.fixed_to_variable.InterestRate,
            denomination=sentinel.denomination,
        )
