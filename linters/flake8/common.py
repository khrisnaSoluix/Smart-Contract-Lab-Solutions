"""Flake8 plugin that warns of Contract anti-patterns"""

# standard libs
from typing import NamedTuple

ErrorType = tuple[int, int, str]

HookSignature = NamedTuple(
    "HookSignature",
    [("argument_types", str), ("return_type", str)],
)

HOOK_V3_FUNCTIONS = {
    "close_code",
    "derived_parameters",
    "execution_schedules",
    "post_activate_code",
    "post_parameter_change_code",
    "post_posting_code",
    "pre_parameter_change_code",
    "pre_posting_code",
    "scheduled_code",
    "upgrade_code",
}

SUPERVISOR_HOOK_V3_FUNCTIONS = {
    "execution_schedules",
    "post_posting_code",
    "pre_posting_code",
    "scheduled_code",
}

HOOK_V3_TYPEHINT_MAPPING = {
    "close_code": HookSignature("effective_date: datetime", "None"),
    "derived_parameters": HookSignature("effective_date: datetime", "dict[str, Any]"),
    # execution schedules can also return EOMSchedules so typehint to Any
    "execution_schedules": HookSignature("", "list[tuple[str, dict[str, Any]]]"),
    "post_activate_code": HookSignature("", "None"),
    "post_parameter_change_code": HookSignature(
        (
            "old_parameter_values: dict[str, Parameter], "
            "updated_parameter_values: dict[str, Parameter], effective_date: datetime"
        ),
        "None",
    ),
    "post_posting_code": HookSignature(
        "postings: PostingInstructionBatch, effective_date: datetime", "None"
    ),
    "pre_parameter_change_code": HookSignature(
        "parameters: dict[str, Parameter], effective_date: datetime",
        "Union[dict[str, Parameter], None]",
    ),
    "pre_posting_code": HookSignature(
        "postings: PostingInstructionBatch, effective_date: datetime", "None"
    ),
    "scheduled_code": HookSignature("event_type: str, effective_date: datetime", "None"),
    "upgrade_code": HookSignature("", "None"),
}

SUPERVISOR_HOOK_V3_TYPEHINT_MAPPING = {
    "execution_schedules": HookSignature("", "list[tuple[str, dict[str, Any]]]"),
    "post_posting_code": HookSignature(
        "postings: PostingInstructionBatch, effective_date: datetime", "None"
    ),
    "pre_posting_code": HookSignature(
        "postings: PostingInstructionBatch, effective_date: datetime", "None"
    ),
    "scheduled_code": HookSignature("event_type: str, effective_date: datetime", "None"),
}


## V4
HOOK_V4_FUNCTIONS = {
    "post_parameter_change_hook",
    "pre_posting_hook",
    "derived_parameter_hook",
    "post_posting_hook",
    "activation_hook",
    "deactivation_hook",
    "pre_parameter_change_hook",
    "scheduled_event_hook",
    "conversion_hook",
}

SUPERVISOR_HOOK_V4_FUNCTIONS = {
    "pre_posting_hook",
    "post_posting_hook",
    "activation_hook",
    "scheduled_event_hook",
    "conversion_hook",
}

HOOK_V4_TYPEHINT_MAPPING = {
    "activation_hook": HookSignature(
        "vault, hook_arguments: ActivationHookArguments", "Optional[ActivationHookResult]"
    ),
    "conversion_hook": HookSignature(
        "vault, hook_arguments: ConversionHookArguments", "Optional[ConversionHookResult]"
    ),
    "deactivation_hook": HookSignature(
        "vault, hook_arguments: DeactivationHookArguments", "Optional[DeactivationHookResult]"
    ),
    "derived_parameter_hook": HookSignature(
        "vault, hook_arguments: DerivedParameterHookArguments",
        "DerivedParameterHookResult",
    ),
    "post_parameter_change_hook": HookSignature(
        "vault, hook_arguments: PostParameterChangeHookArguments",
        "Optional[PostParameterChangeHookResult]",
    ),
    "post_posting_hook": HookSignature(
        "vault, hook_arguments: PostPostingHookArguments", "Optional[PostPostingHookResult]"
    ),
    "pre_parameter_change_hook": HookSignature(
        "vault, hook_arguments: PreParameterChangeHookArguments",
        "Optional[PreParameterChangeHookResult]",
    ),
    "pre_posting_hook": HookSignature(
        "vault, hook_arguments: PrePostingHookArguments", "Optional[PrePostingHookResult]"
    ),
    "scheduled_event_hook": HookSignature(
        "vault, hook_arguments: ScheduledEventHookArguments", "Optional[ScheduledEventHookResult]"
    ),
}

HOOK_V4_TEMPLATE_TYPEHINT_MAPPING = {
    "activation_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: ActivationHookArguments",
        "Optional[ActivationHookResult]",
    ),
    "conversion_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: ConversionHookArguments",
        "Optional[ConversionHookResult]",
    ),
    "deactivation_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: DeactivationHookArguments",
        "Optional[DeactivationHookResult]",
    ),
    "derived_parameter_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: DerivedParameterHookArguments",
        "DerivedParameterHookResult",
    ),
    "post_parameter_change_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: PostParameterChangeHookArguments",
        "Optional[PostParameterChangeHookResult]",
    ),
    "post_posting_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: PostPostingHookArguments",
        "Optional[PostPostingHookResult]",
    ),
    "pre_parameter_change_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: PreParameterChangeHookArguments",
        "Optional[PreParameterChangeHookResult]",
    ),
    "pre_posting_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: PrePostingHookArguments",
        "Optional[PrePostingHookResult]",
    ),
    "scheduled_event_hook": HookSignature(
        "vault: SmartContractVault, hook_arguments: ScheduledEventHookArguments",
        "Optional[ScheduledEventHookResult]",
    ),
}


SUPERVISOR_HOOK_V4_TYPEHINT_MAPPING = {
    "activation_hook": HookSignature(
        "vault, hook_arguments: SupervisorActivationHookArguments",
        "Optional[SupervisorActivationHookResult]",
    ),
    "conversion_hook": HookSignature(
        "vault, hook_arguments: SupervisorConversionHookArguments",
        "Optional[SupervisorConversionHookResult]",
    ),
    "post_posting_hook": HookSignature(
        "vault, hook_arguments: SupervisorPostPostingHookArguments",
        "Optional[SupervisorPostPostingHookResult]",
    ),
    "pre_posting_hook": HookSignature(
        "vault, hook_arguments: SupervisorPrePostingHookArguments",
        "Optional[SupervisorPrePostingHookResult]",
    ),
    "scheduled_event_hook": HookSignature(
        "vault, hook_arguments: SupervisorScheduledEventHookArguments",
        "Optional[SupervisorScheduledEventHookResult]",
    ),
}

SUPERVISOR_HOOK_V4_TEMPLATE_TYPEHINT_MAPPING = {
    "activation_hook": HookSignature(
        "vault: SupervisorContractVault, hook_arguments: SupervisorActivationHookArguments",
        "Optional[SupervisorActivationHookResult]",
    ),
    "conversion_hook": HookSignature(
        "vault: SupervisorContractVault, hook_arguments: SupervisorConversionHookArguments",
        "Optional[SupervisorConversionHookResult]",
    ),
    "post_posting_hook": HookSignature(
        "vault: SupervisorContractVault, hook_arguments: SupervisorPostPostingHookArguments",
        "Optional[SupervisorPostPostingHookResult]",
    ),
    "pre_posting_hook": HookSignature(
        "vault: SupervisorContractVault, hook_arguments: SupervisorPrePostingHookArguments",
        "Optional[SupervisorPrePostingHookResult]",
    ),
    "scheduled_event_hook": HookSignature(
        "vault: SupervisorContractVault, hook_arguments: SupervisorScheduledEventHookArguments",
        "Optional[SupervisorScheduledEventHookResult]",
    ),
}


# TODO: create ODF checker V4
