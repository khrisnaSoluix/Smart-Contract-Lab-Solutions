# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.common.utils as utils
import library.features.v4.lending.interest_accrual as interest_accrual
import library.features.v4.lending.interest_rate.fixed_to_variable as fixed_to_variable
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.overpayment as overpayment

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    AccountNotificationDirective,
    Balance,
    BalanceCoordinate,
    CustomInstruction,
    Phase,
    PostingInstructionsDirective,
    ScheduledEvent,
    ScheduleExpression,
    SmartContractDescriptor,
    SupervisorActivationHookArguments,
    SupervisorActivationHookResult,
    SupervisorContractEventType,
    SupervisorScheduledEventHookArguments,
    SupervisorScheduledEventHookResult,
    UpdateAccountEventTypeDirective,
    requires,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SupervisorContractVault,
)
from inception_sdk.vault.contracts.extensions.contracts_api_extensions.vault_types import (
    SuperviseeContractVault,
)

api = "4.0.0"
version = "2.0.2"

# account type
ACCOUNT_TYPE = "OFFSET_MORTGAGE"

# cannot be used in supervised_smart_contracts, see INC-8721
MORTGAGE_ALIAS = "mortgage"
SAVINGS_ACCOUNT_ALIAS = "savings_account"
CURRENT_ACCOUNT_ALIAS = "current_account"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="mortgage",
        smart_contract_version_id="&{mortgage}",
        supervise_post_posting_hook=False,
    ),
    SmartContractDescriptor(
        alias="savings_account",
        smart_contract_version_id="&{savings_account}",
        supervise_post_posting_hook=False,
    ),
    SmartContractDescriptor(
        alias="current_account",
        smart_contract_version_id="&{current_account}",
        supervise_post_posting_hook=False,
    ),
]

ACCRUE_OFFSET_INTEREST_EVENT = "ACCRUE_OFFSET_INTEREST"
event_types = [
    SupervisorContractEventType(
        name=ACCRUE_OFFSET_INTEREST_EVENT,
        overrides_event_types=[
            (MORTGAGE_ALIAS, "ACCRUE_INTEREST"),
            (SAVINGS_ACCOUNT_ALIAS, "ACCRUE_INTEREST"),
            (CURRENT_ACCOUNT_ALIAS, "ACCRUE_INTEREST"),
        ],
        scheduler_tag_ids=["OFFSET_MORTGAGE_ACCRUE_OFFSET_INTEREST_AST"],
    )
]

PARAM_DENOMINATION = "denomination"
PRINCIPAL = "PRINCIPAL"


def activation_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorActivationHookArguments
) -> Optional[SupervisorActivationHookResult]:
    scheduled_events: dict[str, ScheduledEvent] = {}
    plan_opening_datetime = vault.get_plan_opening_datetime()

    scheduled_events[ACCRUE_OFFSET_INTEREST_EVENT] = ScheduledEvent(
        start_datetime=plan_opening_datetime,
        expression=ScheduleExpression(hour=0, minute=0, second=1),
    )

    return SupervisorActivationHookResult(scheduled_events_return_value=scheduled_events)


@requires(
    event_type=ACCRUE_OFFSET_INTEREST_EVENT,
    balances="latest",
    data_scope="all",
    parameters=True,
    supervisee_hook_directives="all",
)
def scheduled_event_hook(
    vault: SupervisorContractVault, hook_arguments: SupervisorScheduledEventHookArguments
) -> Optional[SupervisorScheduledEventHookResult]:
    """
    Executes the logic of the schedules only accrual of offset interest is supported.
    :param vault: the supervisor vault object
    :param hook_arguments: the scheduled event's hook arguments
    :return: SupervisorScheduledEventHookResult containing the generated offset postings and
    preserves the other directives generated by the supervisees.
    """
    event_type = hook_arguments.event_type

    if event_type == ACCRUE_OFFSET_INTEREST_EVENT:
        notifications, postings, update_event_types = _handle_accrue_offset_interest(
            vault=vault, hook_arguments=hook_arguments
        )
        if notifications or postings or update_event_types:
            return SupervisorScheduledEventHookResult(
                supervisee_account_notification_directives=notifications,
                supervisee_posting_instructions_directives=postings,
                supervisee_update_account_event_type_directives=update_event_types,
            )

    return None


def _handle_accrue_offset_interest(
    vault: SupervisorContractVault, hook_arguments: SupervisorScheduledEventHookArguments
) -> (
    tuple[
        dict[str, list[AccountNotificationDirective]],
        dict[str, list[PostingInstructionsDirective]],
        dict[str, list[UpdateAccountEventTypeDirective]],
    ]
):
    supervisee_notification_directives: dict[str, list[AccountNotificationDirective]] = {}
    supervisee_posting_directives: dict[str, list[PostingInstructionsDirective]] = {}
    supervisee_update_account_event_type_directives: dict[
        str, list[UpdateAccountEventTypeDirective]
    ] = {}

    mortgage_accounts = supervisor_utils.get_supervisees_for_alias(
        vault=vault, alias=MORTGAGE_ALIAS
    )
    savings_accounts = supervisor_utils.get_supervisees_for_alias(
        vault=vault, alias=SAVINGS_ACCOUNT_ALIAS
    )
    current_accounts = supervisor_utils.get_supervisees_for_alias(
        vault=vault, alias=CURRENT_ACCOUNT_ALIAS
    )
    all_casa_accounts = savings_accounts + current_accounts

    # If no accounts associated with plan, no accrual needed
    if not mortgage_accounts and not all_casa_accounts:
        return {}, {}, {}
    # If only mortgage and no CA/SAs, preserve and return all mortgage PIDs
    if mortgage_accounts and not all_casa_accounts:
        # we only support 1 mortgage account
        mortgage_account = mortgage_accounts[0]
        directives = supervisor_utils.get_supervisee_directives_mapping(vault=mortgage_account)
        return (
            directives[0],
            directives[1],
            directives[2],
        )

    # If only CA/SA and no mortgage accounts, preserve and return all CA/SAs PIDs
    elif all_casa_accounts and not mortgage_accounts:
        for casa_account in all_casa_accounts:
            directives = supervisor_utils.get_supervisee_directives_mapping(vault=casa_account)
            supervisee_notification_directives.update(directives[0])
            supervisee_posting_directives.update(directives[1])
            supervisee_update_account_event_type_directives.update(directives[2])

        return (
            supervisee_notification_directives,
            supervisee_posting_directives,
            supervisee_update_account_event_type_directives,
        )

    # We only support 1 mortgage account
    mortgage_account = mortgage_accounts[0]
    mortgage_denomination = _get_denomination_parameter(vault=mortgage_account)

    # Filter accounts by eligibility (must have same denomination parameter value
    # as mortgage, must have a positive balance)
    eligible_accounts, ineligible_accounts = _split_supervisees_by_eligibility(
        casa_accounts=all_casa_accounts, mortgage_denomination=mortgage_denomination
    )

    # preserve and extend mapping for all ineligible CA/SAs
    for account in ineligible_accounts:
        directives = supervisor_utils.get_supervisee_directives_mapping(vault=account)
        supervisee_notification_directives.update(directives[0])
        supervisee_posting_directives.update(directives[1])
        supervisee_update_account_event_type_directives.update(directives[2])

    # if there are no eligible CA/SAs, then preserve and return all mortgage PIDs
    if not eligible_accounts:
        directives = supervisor_utils.get_supervisee_directives_mapping(vault=mortgage_account)
        supervisee_notification_directives.update(directives[0])
        supervisee_posting_directives.update(directives[1])
        supervisee_update_account_event_type_directives.update(directives[2])
        return (
            supervisee_notification_directives,
            supervisee_posting_directives,
            supervisee_update_account_event_type_directives,
        )

    mortgage_posting_directives = (
        mortgage_account.get_hook_result().posting_instructions_directives  # type: ignore
    )

    # if there are no accrual PostingInstructionsDirectives on the mortgage account, we have
    # no interest accrual to offset, so preserve all CA/SAs PIDs (all ineligible CA/SAs have
    # already been added to the directives dict)
    if not mortgage_posting_directives:
        for account in eligible_accounts:
            directives = supervisor_utils.get_supervisee_directives_mapping(vault=account)
            supervisee_notification_directives.update(directives[0])
            supervisee_posting_directives.update(directives[1])
            supervisee_update_account_event_type_directives.update(directives[2])
        return (
            supervisee_notification_directives,
            supervisee_posting_directives,
            supervisee_update_account_event_type_directives,
        )

    supervisee_posting_directives.update(
        _generate_offset_accrual_posting_directives_mapping(
            mortgage_account=mortgage_account,
            mortgage_posting_directives=mortgage_posting_directives,
            eligible_accounts=eligible_accounts,
            mortgage_denomination=mortgage_denomination,
            hook_arguments=hook_arguments,
        )
    )

    return (
        supervisee_notification_directives,
        supervisee_posting_directives,
        supervisee_update_account_event_type_directives,
    )


def _generate_offset_accrual_posting_directives_mapping(
    mortgage_account: SuperviseeContractVault,
    mortgage_posting_directives: list[PostingInstructionsDirective],
    eligible_accounts: list[SuperviseeContractVault],
    mortgage_denomination: str,
    hook_arguments: SupervisorScheduledEventHookArguments,
) -> dict[str, list[PostingInstructionsDirective]]:
    """
    Generate the offset accrual PostingInstructionsDirective mapping for the mortgage account
    when all the eligibility criteria have been met.
    All non-standard interest accrual instructions are preserved

    :param mortgage_account: vault object for the mortgage account
    :param mortgage_posting_directives: non-empty list of PostingInstructionsDirectives returned
    from the mortgage accrual schedule result
    :param eligible_accounts: list of eligible CA/SA account vault objects
    :param mortgage_denomination: denomination of the mortgage account
    :param effective_datetime: effective datetime of the hook
    :return: PostingInstructionsDirective mapping containing instructions for offset accrual
    """

    posting_instructions: list[CustomInstruction] = [
        instruction
        for directive in mortgage_posting_directives
        for instruction in directive.posting_instructions
    ]

    (
        offset_eligible_instructions,
        instructions_to_preserve,
    ) = _split_instructions_into_offset_eligible_and_preserved(
        posting_instructions=posting_instructions,
        mortgage_account_id=mortgage_account.account_id,
        mortgage_denomination=mortgage_denomination,
    )

    # if there are no instructions eligible for offset, we should return the preserved
    # instructions and not offset any accrual
    if not offset_eligible_instructions:
        # instructions_to_preserve cannot be empty, since mortgage_posting_directives is not empty
        return {
            mortgage_account.account_id: [
                PostingInstructionsDirective(
                    posting_instructions=instructions_to_preserve,
                    value_datetime=hook_arguments.effective_datetime,
                )
            ]
        }

    offset_accrual_instructions = _get_offset_accrual_instructions(
        mortgage_account=mortgage_account,
        eligible_accounts=eligible_accounts,
        mortgage_denomination=mortgage_denomination,
        hook_arguments=hook_arguments,
    )

    return {
        mortgage_account.account_id: [
            PostingInstructionsDirective(
                # instructions_to_preserve cannot be empty, since mortgage_posting_directives
                # is not empty, and offset_accrual_instructions cannot be empty since there are
                # offset_eligible_instructions
                posting_instructions=[*instructions_to_preserve, *offset_accrual_instructions],
                value_datetime=hook_arguments.effective_datetime,
            )
        ]
    }


def _get_offset_accrual_instructions(
    mortgage_account: SuperviseeContractVault,
    eligible_accounts: list[SuperviseeContractVault],
    mortgage_denomination: str,
    hook_arguments: SupervisorScheduledEventHookArguments,
) -> list[CustomInstruction]:

    mortgage_balances = utils.get_balance_default_dict_from_mapping(
        mapping=mortgage_account.get_balances_timeseries()
    )

    # this must be > 0 as we've already filtered out accounts with <= 0 balance
    total_casa_effective_balance = Decimal(
        sum(
            utils.balance_at_coordinates(
                balances=utils.get_balance_default_dict_from_mapping(
                    mapping=account.get_balances_timeseries(),
                ),
                denomination=mortgage_denomination,
            )
            for account in eligible_accounts
        )
    )

    # this effectively offsets the mortgage's PRINCIPAL
    principal_coordinate = BalanceCoordinate(
        account_address=lending_addresses.PRINCIPAL,
        asset=DEFAULT_ASSET,
        denomination=mortgage_denomination,
        phase=Phase.COMMITTED,
    )
    mortgage_balances[principal_coordinate] += Balance(
        # net is negative as the mortgage has TSide ASSET
        credit=total_casa_effective_balance,
        debit=Decimal(0),
        net=-total_casa_effective_balance,
    )

    # we must pass in all optional fetched data to account for offset principal and lack of ODF
    instructions = interest_accrual.daily_accrual_logic(
        vault=mortgage_account,
        hook_arguments=hook_arguments,
        interest_rate_feature=fixed_to_variable.InterestRate,
        account_type=ACCOUNT_TYPE,
        balances=mortgage_balances,
        denomination=mortgage_denomination,
    )

    instructions += overpayment.track_interest_on_expected_principal(
        vault=mortgage_account,
        hook_arguments=hook_arguments,
        balances=mortgage_balances,
        denomination=mortgage_denomination,
        interest_rate_feature=fixed_to_variable.InterestRate,
    )

    for instruction in instructions:
        instruction.instruction_details[
            "description"
        ] += f" offset by balance {mortgage_denomination} {total_casa_effective_balance}"

    return instructions


## Mortgage helpers
def _split_instructions_into_offset_eligible_and_preserved(
    posting_instructions: list[CustomInstruction],
    mortgage_account_id: str,
    mortgage_denomination: str,
) -> tuple[list[CustomInstruction], list[CustomInstruction]]:
    """
    Only CustomInstructions that affect the ACCRUED_INTEREST_RECEIVABLE address
    are eligible for offsetting, and all other instructions should be preserved.

    :param posting_instructions: list of CustomInstructions provided in the
    mortgage account
    :param mortgage_account_id: account id for the mortgage
    :param mortgage_denomination: denomination for the mortgage
    :return: list of offset eligible instructions, list of instructions to preserve
    """
    offset_eligible_instructions: list[CustomInstruction] = []
    instructions_to_preserve: list[CustomInstruction] = []

    accrued_interest_receivable_coordinate = BalanceCoordinate(
        account_address=lending_addresses.ACCRUED_INTEREST_RECEIVABLE,
        asset=DEFAULT_ASSET,
        denomination=mortgage_denomination,
        phase=Phase.COMMITTED,
    )
    accrued_interest_expected_coordinate = BalanceCoordinate(
        account_address=overpayment.ACCRUED_EXPECTED_INTEREST,
        asset=DEFAULT_ASSET,
        denomination=mortgage_denomination,
        phase=Phase.COMMITTED,
    )

    for custom_instruction in posting_instructions:
        balances = custom_instruction.balances(account_id=mortgage_account_id)
        # preserve instructions that do not affect interest addresses. This includes
        # includes accrued expected to ensure offset accruals do not affect overpayment handling
        if balances[accrued_interest_receivable_coordinate].net + balances[
            accrued_interest_expected_coordinate
        ].net == Decimal("0"):
            instructions_to_preserve.append(custom_instruction)
        else:
            offset_eligible_instructions.append(custom_instruction)

    return offset_eligible_instructions, instructions_to_preserve


## CA/SA helpers
def _split_supervisees_by_eligibility(
    casa_accounts: list[SuperviseeContractVault],
    mortgage_denomination: str,
) -> tuple[list[SuperviseeContractVault], list[SuperviseeContractVault]]:
    """
    Eligible accounts have same denomination parameter value as mortgage and have a positive balance
    Constructs two lists of vault objects, one with eligible accounts
    and one with ineligible accounts.

    :param casa_accounts: List of CA/SA vault objects
    :param mortgage_denomination: Denomination of the mortgage account
    :return: list of eligible accounts, list of ineligible accounts
    """
    eligible_accounts: list[SuperviseeContractVault] = []
    ineligible_accounts: list[SuperviseeContractVault] = []

    for account in casa_accounts:
        account_denomination = _get_denomination_parameter(vault=account)
        if account_denomination == mortgage_denomination and utils.balance_at_coordinates(
            balances=utils.get_balance_default_dict_from_mapping(
                mapping=account.get_balances_timeseries(),
            ),
            denomination=mortgage_denomination,
        ) > Decimal("0"):
            eligible_accounts.append(account)
        else:
            ineligible_accounts.append(account)

    return eligible_accounts, ineligible_accounts


## Misc helpers
def _get_denomination_parameter(vault: SuperviseeContractVault) -> str:
    denomination: str = utils.get_parameter(vault=vault, name=PARAM_DENOMINATION)
    return denomination
