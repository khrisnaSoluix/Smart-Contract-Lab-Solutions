# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
This module exposes easy helper methods for sending each type
of posting instruction and settings flags with minimal effort from the test writer.
However, for posting instruction types these helper methods are kept simple and minimal on purpose,
only exposing a small subset of fields available on each posting instruction
type.
Any more complex Posting Instruction Batches should be constructed by the
test writer out of the base available objects.
"""
# standard libs
from datetime import datetime, timedelta
from random import randrange

# contracts api
from contracts_api import DateShape, DenominationShape, NumberShape, StringShape

# inception sdk
# common
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.contracts.files import EMPTY_LIABILITY_CONTRACT
from inception_sdk.test_framework.contracts.simulation.common.helper import (
    create_auth_adjustment_event as create_auth_adjustment_event_common,
    create_custom_instruction_event as create_custom_instruction_event_common,
    create_inbound_authorisation_event as create_inbound_authorisation_event_common,
    create_inbound_hard_settlement_event as create_inbound_hard_settlement_event_common,
    create_outbound_authorisation_event as create_outbound_authorisation_event_common,
    create_outbound_hard_settlement_event as create_outbound_hard_settlement_event_common,
    create_posting_instruction_batch_event as create_posting_instruction_batch_event_common,
    create_release_event as create_release_event_common,
    create_settlement_event as create_settlement_event_common,
    create_transfer_event as create_transfer_event_common,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationEvent,
    SimulationTestScenario,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.account_events import (
    AccountStatus,
    CreateAccountEvent,
    CreateAccountProductVersionUpdateEvent,
    CreateInstanceParameterUpdateEvent,
    UpdateAccountEvent,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.calendar_events import (
    CreateCalendar,
    CreateCalendarEvent,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.contract_events import (
    CreateSmartContractModuleVersionsLink,
    CreateTemplateParameterUpdateEvent,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.flag_events import (
    CreateFlag,
    CreateFlagDefinition,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.parameter_events import (
    CreateGlobalParameterEvent,
    CreateGlobalParameterValue,
    GlobalParameter,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.plan_events import (
    AccountPlanAssocStatus,
    CreateAccountPlanAssocEvent,
    CreatePlanEvent,
)
from inception_sdk.vault.postings.posting_classes import Instruction


def account_to_simulate(
    timestamp,
    account_id,
    contract_version_id=None,
    instance_params=None,
    template_params=None,
    contract_file_path=EMPTY_LIABILITY_CONTRACT,
    create_account=True,
):
    """
    Returns a dictionary with account details and if create_account is set to True
    dictionary key "event" is populated with account creation details.
    :param timestamp: timestamp, the datetime at which the account creation event should be
                      scheduled, auto-created events this must always be populated with sim
                      start time
    :param account_id: str, A unique ID for an account
    :param contract_version_id: str, An optional parameter, which will generate an ID if value
                      set to None.
    :param instance_params: dict, contract instance parameters
    :param template_params: dict, contract template parameters
    :param contract_file_path: str, path to contract file
    :param create_account: bool, if True, "event" key is populated with account creation
                           SimulationEvent
    :return: dict with account and contract related information.
    """

    if instance_params is None:
        instance_params = {}
    if template_params is None:
        template_params = {}

    # Avoid generated id collision. API accepts 64-bit signed int, use positive ints (INC-4048)
    generated_id = str(randrange(0, 2**63))
    smart_contract_version_id = contract_version_id or generated_id
    account_dict = {
        "timestamp": timestamp,
        "contract_file_contents": load_file_contents(contract_file_path),
        "account_id": str(account_id),
        "smart_contract_version_id": smart_contract_version_id,
        "instance_parameters": instance_params,
        "template_parameters": template_params,
        "create_account": create_account,
        "event": {},
    }

    if create_account:
        account_dict["event"] = create_account_instruction(
            timestamp=account_dict["timestamp"],
            account_id=account_dict["account_id"],
            product_id=account_dict["smart_contract_version_id"],
            instance_param_vals=account_dict["instance_parameters"],
        )

    return account_dict


def create_account_instruction(
    timestamp: datetime,
    account_id: str = "",
    product_id: str = "",
    permitted_denominations: list[str] | None = None,
    status: AccountStatus = AccountStatus.ACCOUNT_STATUS_UNKNOWN,
    stakeholder_ids: list[str] | None = None,
    instance_param_vals: dict[str, str] | None = None,
    derived_instance_param_vals: dict[str, str] | None = None,
    details: dict[str, str] | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that instructs the simulation to create an account.
    The only required and supported fields are: id, product_version_id and instance_param_vals.
    :param timestamp: the datetime at which the Create account will be applied in the simulation.
    :param account_id: a unique ID for an account. Optional for create requests.
    :param product_id: the ID of the product the account is associated with.
                    Can be obtained using the /v1/products endpoint.
                    Required for create requests if product_version_id is not provided.
    :permitted_denominations: Denominations the account can hold balances in.
                    Must be a subset of the denominations supported by the product version.
    :status: The status of the account.
    :stakeholder_ids: The customer IDs that can access the account. Required for create requests.
    :instance_param_vals: The instance-level parameters for the associated product;
                            a map of the parameter name to value.
    :derived_instance_param_vals:
        The derived instance-level parameters for the associated product
        that have been defined in the account's Smart Contract code;
        a map of the parameter name to value.
    :details: A map of unstructured fields that hold instance-specific account details,
            for example, the source of funds.
    :return: SimulationEvent with a create account event
    """
    return SimulationEvent(
        timestamp,
        CreateAccountEvent(
            id=account_id,
            product_version_id=product_id,
            permitted_denominations=permitted_denominations or [],
            status=status.value,
            stakeholder_ids=stakeholder_ids or [],
            instance_param_vals=instance_param_vals or {},
            derived_instance_param_vals=derived_instance_param_vals or {},
            details=details or {},
        ).to_dict(),
    )


def create_account_product_version_update_instruction(
    timestamp: datetime,
    account_id: str,
    product_version_id: str,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing an instruction to update an account's product version.
    :param timestamp: the datetime at which the account will be updated.
    :param account_id: the unique ID for an account.
    :param product_version_id: the product version ID we're updating the account to.
    Note that the product version with the updated ID will need to be uploaded
    as part of the test set up.
    """
    return SimulationEvent(
        timestamp,
        CreateAccountProductVersionUpdateEvent(
            account_id=account_id, product_version_id=product_version_id
        ).to_dict(),
    )


def update_account_status_pending_closure(timestamp: datetime, account_id: str):
    """
    Returns a SimulationEvent containing instruction to change account status to pending closure.
    :param timestamp: the datetime at which the account pending closure will be applied.
    :param account_id: str, A unique ID for an account
    """
    return SimulationEvent(
        timestamp,
        UpdateAccountEvent(
            account_id=account_id, status=AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE
        ).to_dict(),
    )


def create_auth_adjustment_instruction(
    amount: str,
    event_datetime: datetime,
    client_transaction_id: str,
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing an Inbound Authorisation
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the Posting Instruction Batch
                           will be applied in the simulation.
    :param target_account_id: Target customer account id for posting instruction
    :param internal_account_id: internal account id for posting instruction
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a InboundAuthorisation Posting Instruction Batch
    """
    return _transform_posting_key(
        create_auth_adjustment_event_common(
            amount,
            event_datetime,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            value_timestamp,
        )
    )


def create_custom_instruction(
    amount: str,
    debtor_target_account_id: str,
    creditor_target_account_id: str,
    debtor_target_account_address: str,
    creditor_target_account_address: str,
    event_datetime: datetime,
    client_transaction_id: str = "",
    denomination: str | None = None,
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing a Custom Instruction
    :param amount string representation of the amount to be sent
    :param debtor_target_account_id account from which the money should be debited
    :param creditor_target_account_id account to which the money should be credited to
    :param debtor_target_account_address address from which the money should be debited
    :param creditor_target_account_address address to which the money should be credited to
    :param event_datetime the datetime at which the Posting Instruction Batch
           will be applied in the simulation
    :param denomination: the denomination the posting instruction will be in.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                            will be applied in the simulation. If "None" defaults to event_datetime.
    :return SimulationEvent with a InboundHardSettlement Posting Instruction Batch
    """
    return _transform_posting_key(
        create_custom_instruction_event_common(
            amount,
            debtor_target_account_id,
            creditor_target_account_id,
            debtor_target_account_address,
            creditor_target_account_address,
            event_datetime,
            client_transaction_id,
            denomination,
            instruction_details,
            batch_details,
            client_batch_id,
            value_timestamp,
        )
    )


def create_inbound_authorisation_instruction(
    amount: str,
    event_datetime: datetime,
    target_account_id: str | None = None,
    internal_account_id: str | None = None,
    denomination: str | None = None,
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing an Inbound Authorisation
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the event will be applied in the simulation
    :param target_account_id: Target customer account id for posting instruction
    :param internal_account_id: internal account id for posting instruction
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a InboundAuthorisation Posting Instruction Batch
    """
    return _transform_posting_key(
        create_inbound_authorisation_event_common(
            amount,
            event_datetime,
            denomination,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            target_account_id,
            internal_account_id,
            value_timestamp,
        )
    )


def create_inbound_hard_settlement_instruction(
    amount: str,
    event_datetime: datetime,
    target_account_id: str | None = None,
    internal_account_id: str | None = None,
    denomination: str | None = None,
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing an Inbound Hard Settlement.
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param target_account_id: Target customer account id for posting instruction
    :param internal_account_id: internal account id for posting instruction
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a InboundHardSettlement Posting Instruction Batch
    """
    return _transform_posting_key(
        create_inbound_hard_settlement_event_common(
            amount,
            event_datetime,
            denomination,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            target_account_id,
            internal_account_id,
            value_timestamp,
        )
    )


def create_outbound_authorisation_instruction(
    amount: str,
    event_datetime: datetime,
    target_account_id: str | None = None,
    internal_account_id: str | None = None,
    denomination: str | None = None,
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing an Outbound Authorisation
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param target_account_id: Target customer account id for posting instruction
    :param internal_account_id: internal account id for posting instruction
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a OutboundAuthorisation Posting Instruction Batch
    """
    return _transform_posting_key(
        create_outbound_authorisation_event_common(
            amount,
            event_datetime,
            denomination,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            target_account_id,
            internal_account_id,
            value_timestamp,
        )
    )


def create_outbound_hard_settlement_instruction(
    amount: str,
    event_datetime: datetime,
    target_account_id: str | None = None,
    internal_account_id: str | None = None,
    denomination: str | None = None,
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
    advice: bool | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing an Outbound Hard Settlement
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param target_account_id: Target customer account id for posting instruction
    :param internal_account_id: internal account id for posting instruction
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :param advice: if true, the amount will be authorised regardless of balance check
    :return: SimulationEvent with a OutboundHardSettlement Posting Instruction Batch
    """
    return _transform_posting_key(
        create_outbound_hard_settlement_event_common(
            amount,
            event_datetime,
            denomination,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            target_account_id,
            internal_account_id,
            value_timestamp,
            advice,
        )
    )


def create_release_event(
    client_transaction_id: str,
    event_datetime: datetime,
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
    require_pre_posting_hook_execution: bool = False,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing a Release
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :param require_pre_posting_hook_execution: A boolean that can ensure the pre-posting hook
                                            is executed when the settlement is processed
    :return SimulationEvent with a Release Posting Instruction Batch
    """
    return _transform_posting_key(
        create_release_event_common(
            client_transaction_id,
            event_datetime,
            instruction_details,
            batch_details,
            client_batch_id,
            value_timestamp,
            require_pre_posting_hook_execution,
        )
    )


def create_settlement_event(
    amount: str,
    client_transaction_id: str,
    event_datetime: datetime,
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    final: bool = False,
    value_timestamp: datetime | None = None,
    require_pre_posting_hook_execution: bool = False,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing a Settlement
    :param amount: string representation of the amount to be sent.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param final: A boolean allowing further (True) or no more (False) settlements associated with
                 the client_transaction_id.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :param require_pre_posting_hook_execution: A boolean that can ensure the pre-posting hook
                                            is executed when the settlement is processed
    :return SimulationEvent with a Settlement Posting Instruction Batch
    """
    return _transform_posting_key(
        create_settlement_event_common(
            amount,
            client_transaction_id,
            event_datetime,
            instruction_details,
            batch_details,
            client_batch_id,
            final,
            value_timestamp,
            require_pre_posting_hook_execution,
        )
    )


def create_transfer_instruction(
    amount: str,
    event_datetime: datetime,
    creditor_target_account_id: str,
    debtor_target_account_id: str,
    denomination: str = "",
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing a Transfer
    :param amount: string representation of the amount to be sent.
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param creditor_target_account_id: account to credit for Transfer.
    :param debtor_target_account_id: account to debit for Transfer.
    :param denomination: the denomination the posting instruction will be in.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a OutboundHardSettlement Posting Instruction Batch
    """
    return _transform_posting_key(
        create_transfer_event_common(
            amount,
            event_datetime,
            creditor_target_account_id,
            debtor_target_account_id,
            denomination,
            client_transaction_id,
            instruction_details,
            batch_details,
            client_batch_id,
            value_timestamp,
        )
    )


def create_posting_instruction_batch(
    instructions: list[Instruction],
    event_datetime: datetime,
    client_transaction_id: str = "",
    instruction_details: dict[str, str] | None = None,
    batch_details: dict[str, str] | None = None,
    client_batch_id: str = "",
    value_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing a Posting Instruction Batch
    instructing any number of instructions passed in as an argument
    :param instructions: list of instructions to be included in the pib
    :param event_datetime: the datetime at which the event will be applied in the simulation.
    :param client_transaction_id: the ID of the client transaction this posting
                                  instruction is creating or mutating.
    :param instruction_details: An optional mapping containing instruction-level metadata.
    :param batch_details: A dictionary containing batch level metadata.
    :param client_batch_id: An id which allows related PostingInstructions
                            to be associated with each other.
    :param value_timestamp: Optional value timestamp at which the Posting Instruction Batch
                          will be applied in the simulation. If "None" defaults to event_datetime.
    :return: SimulationEvent with a Posting Instruction Batch
    """
    return _transform_posting_key(
        create_posting_instruction_batch_event_common(
            instructions,
            event_datetime,
            client_transaction_id=client_transaction_id,
            instruction_details=instruction_details,
            batch_details=batch_details,
            client_batch_id=client_batch_id,
            pib_timestamp=value_timestamp,
        )
    )


def create_instance_parameter_change_event(
    timestamp: datetime, account_id: str, **kwargs: str
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing an account update to update instance parameter values.
    :param timestamp: the datetime will be applied in the simulation.
    :param account_id: the account that the update should act on.
    :param **kwargs: keyword arguments of parameters to update, in form of parameter_name=value.
    :return: SimulationEvent with an account update to update instance parameter values.
    """
    return SimulationEvent(
        timestamp,
        CreateInstanceParameterUpdateEvent(account_id, dict(**kwargs)).to_dict(),
    )


def create_template_parameter_change_event(
    timestamp: datetime, smart_contract_version_id: str = "0", **kwargs: str
) -> SimulationEvent:
    """
    The platform implementation for this can only handle one update per
    instruction, therefore, we are mirroring that constraint and preserve
    the the input and output signatures as instance param update events
    """
    if len(kwargs) > 1:
        raise ValueError("template param update can only take in one parameter per event")

    parameter_name, new_parameter_value = next(iter(kwargs.items()))

    return SimulationEvent(
        timestamp,
        CreateTemplateParameterUpdateEvent(
            smart_contract_version_id, parameter_name, new_parameter_value
        ).to_dict(),
    )


def create_global_parameter_instruction(
    timestamp: datetime,
    global_parameter_id: str,
    display_name: str,
    description: str,
    initial_value: str,
    number: NumberShape | None = None,
    str: StringShape | None = None,  # noqa: A002
    denomination: DenominationShape | None = None,
    date: DateShape | None = None,
) -> SimulationEvent:
    """
    Instructs the simulation to create a new global parameter.
    Only one of the number, str, denomination, date parameters needs to be set.
    :param timestamp: the datetime will be applied in the simulation.
    :param global_parameter_id: The GlobalParameter ID.
        Used by Smart Contracts to retrieve values for this parameter.
    :param display_name: A human-readable name.
    :param description: A description of the parameter.
    :param number: used for parameters representing numerical values.
    :param str: used for parameters representing string values.
    :param denomination used for parameters representing denominations.
    :param date: used for parameters representing date values.
    :param initial_value: used to create a GlobalParameterValue
        associated with the newly created GlobalParameter.
    :return: SimulationEvent with a create global parameter
    """
    return SimulationEvent(
        timestamp,
        CreateGlobalParameterEvent(
            GlobalParameter(
                id=global_parameter_id,
                display_name=display_name,
                description=description,
                number=number,
                str=str,
                denomination=denomination,
                date=date,
            ),
            initial_value=initial_value,
        ).to_dict(),
    )


def create_global_parameter_value_instruction(
    timestamp: datetime,
    global_parameter_id: str,
    value: str,
    effective_timestamp: datetime,
) -> SimulationEvent:
    """
    Instructs the simulation to create a new global parameter value.
    :param timestamp: the datetime will be applied in the simulation.
    :param global_parameter_id: The GlobalParameter ID this value belongs to.
    :param value: the new parameter value that we want to create.
    :param effective_timestamp: A timestamp indicating
        when the GlobalParameterValue is effective from.
    :return: SimulationEvent with a create global parameter value
    """
    return SimulationEvent(
        timestamp,
        CreateGlobalParameterValue(
            global_parameter_id=global_parameter_id,
            value=value,
            effective_timestamp=effective_timestamp,
        ).to_dict(),
    )


def create_plan_instruction(
    timestamp: datetime, plan_id: str, supervisor_contract_version_id: str
) -> SimulationEvent:
    """
    Instructs the simulation to create a plan.
    :param timestamp: the datetime at which the create plan will be applied in the simulation.
    :param id: A unique ID for a plan. Optional for create requests. Max length: 36 characters.
    :param supervisor_contract_version_id: The ID of the supervisor contract version.
                                            Required for create requests.
    :return: SimulationEvent with a create account event
    """
    return SimulationEvent(
        timestamp,
        CreatePlanEvent(
            id=plan_id,
            supervisor_contract_version_id=supervisor_contract_version_id,
        ).to_dict(),
    )


def create_account_plan_assoc_instruction(
    timestamp: datetime,
    assoc_id: str,
    account_id: str,
    plan_id: str,
    status: AccountPlanAssocStatus = AccountPlanAssocStatus.ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE,
) -> SimulationEvent:
    """
    Instructs the simulation to add an account to a plan for the specified duration.
    :param timestamp: The datetime at which the plan association will be created
    :param assoc_id: A unique ID for the account plan association to create
    :param account_id: The account ID to associate
    :param plan_id: The plan ID to associate to
    :param status: The status of the account plan association.
    :return: SimulationEvent with a create account plan associate event
    """
    return SimulationEvent(
        timestamp,
        CreateAccountPlanAssocEvent(
            id=assoc_id,
            account_id=account_id,
            plan_id=plan_id,
            status=status.value,
        ).to_dict(),
    )


def create_flag_definition_event(
    timestamp: datetime,
    flag_definition_id: str,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that
    instructs the simulation to create flag definition.
    """
    return SimulationEvent(timestamp, CreateFlagDefinition(flag_definition_id).to_dict())


def create_flag_event(
    timestamp: datetime,
    flag_definition_id: str,
    account_id: str,
    expiry_timestamp: datetime | None = None,
    effective_timestamp: datetime | None = None,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that
    instructs the simulation to create flag for an account.
    """
    return SimulationEvent(
        timestamp,
        CreateFlag(
            flag_definition_id,
            (effective_timestamp or timestamp).isoformat(),
            expiry_timestamp.isoformat() if expiry_timestamp else "",
            account_id,
        ).to_dict(),
    )


def create_calendar(
    timestamp: datetime,
    calendar_id: str,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that
    instructs the simulation to create a calendar.
    """
    return SimulationEvent(
        timestamp,
        CreateCalendar(
            calendar_id,
        ).to_dict(),
    )


def create_calendar_event(
    timestamp: datetime,
    calendar_event_id: str,
    calendar_id: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that
    instructs the simulation to create a Calendar Event.
    """
    return SimulationEvent(
        timestamp,
        CreateCalendarEvent(
            calendar_event_id,
            calendar_id,
            start_timestamp.isoformat(),
            end_timestamp.isoformat(),
        ).to_dict(),
    )


def _transform_posting_key(event):
    """
    Returns a SimulationEvent that rename the posting key
    from posting_instruction_batch to create_posting_instruction_batch
    """
    batch = event.event["posting_instruction_batch"]
    event.event["create_posting_instruction_batch"] = batch
    del event.event["posting_instruction_batch"]
    return event


def create_derived_parameters_instructions(account_ids, timestamps):
    """
    Helper that support simulation of derived parameters
    :param timestamp: The timestamp used to calculate the output.
    :param account_id: The account ID that derived parameters are to be retrieved for.
    :return: a list of requests for data that is to be returned.
    """

    outputs = []

    if timestamps is not None:
        for i in range(len(timestamps)):
            outputs.append(
                {
                    "timestamp": _datetime_to_rfc_3339(timestamps[i]),
                    "derived_params": {"account_id": account_ids[i]},
                }
            )

    return outputs


def get_supervisor_setup_events(
    test_scenario: SimulationTestScenario,
) -> list[SimulationEvent]:
    """
        Helper that takes in test scenario config and:
        1. setup events to create supervisor contract
        2. setup events to create the number of supervisee contracts as specified
        3. setup events to create supervisor plan
        4. if configured to be true, link supervisees to plan
    Note:
        supervisee account creation events for the same contract are 1 ms apart
        to make them chronologically distinct
    """

    setup_events = []

    if test_scenario.supervisor_config is None:
        raise ValueError(
            "get_supervisor_setup_events called on test scenario with no supervisor_config"
        )

    # Set up global parameters
    if test_scenario.supervisor_config.global_params:
        setup_events.extend(
            [
                SimulationEvent(time=test_scenario.start, event=g.to_dict())
                for g in test_scenario.supervisor_config.global_params
            ]
        )

    event_time_offset = 0
    supervisee_account_creation_events = {}
    for supervisee_contract in test_scenario.supervisor_config.supervisee_contracts:
        for account_config in supervisee_contract.account_configs:
            for i in range(account_config.number_of_accounts):
                if account_config.account_id_base + str(i) in supervisee_account_creation_events:
                    raise ValueError(
                        "account_id_base must be different for each contract and account type"
                    )

                supervisee_account_creation_events[
                    account_config.account_id_base + str(i)
                ] = create_account_instruction(
                    timestamp=test_scenario.start + timedelta(milliseconds=event_time_offset + i),
                    account_id=account_config.account_id_base + str(i),
                    product_id=supervisee_contract.smart_contract_version_id,
                    instance_param_vals=account_config.instance_params,
                )
            event_time_offset += account_config.number_of_accounts

    setup_events.extend(supervisee_account_creation_events.values())

    # Create plan
    event_time_offset += 1
    setup_events.append(
        create_plan_instruction(
            timestamp=test_scenario.start + timedelta(milliseconds=event_time_offset),
            plan_id=test_scenario.supervisor_config.plan_id,
            supervisor_contract_version_id=(
                test_scenario.supervisor_config.supervisor_contract_version_id
            ),
        )
    )
    # Create plan assoc
    if test_scenario.supervisor_config.associate_supervisees_to_plan:
        event_time_offset += 1
        setup_events.extend(
            create_account_plan_assoc_instruction(
                timestamp=test_scenario.start + timedelta(milliseconds=event_time_offset),
                assoc_id="Supervised " + account_id,
                account_id=account_id,
                plan_id=test_scenario.supervisor_config.plan_id,
            )
            for account_id in supervisee_account_creation_events.keys()
        )

    return setup_events


def get_contract_setup_events(
    test_scenario: SimulationTestScenario,
) -> list[SimulationEvent]:
    contract_setup_events = []

    if test_scenario.contract_config is None:
        raise ValueError(
            "get_contract_setup_events called on test scenario with no contract_config"
        )

    # Set up global parameters
    if test_scenario.contract_config and test_scenario.contract_config.global_params:
        contract_setup_events.extend(
            [
                SimulationEvent(time=test_scenario.start, event=g.to_dict())
                for g in test_scenario.contract_config.global_params
            ]
        )

    contract_setup_events.append(
        create_account_instruction(
            timestamp=test_scenario.start,
            account_id=test_scenario.contract_config.account_configs[0].account_id_base,
            product_id=test_scenario.contract_config.smart_contract_version_id,
            instance_param_vals=test_scenario.contract_config.account_configs[0].instance_params,
        )
    )
    return contract_setup_events


def create_smart_contract_module_versions_link(
    timestamp: datetime,
    link_id: str,
    smart_contract_version_id: str,
    alias_to_contract_module_version_id: dict[str, str],
) -> SimulationEvent:
    """
    Returns a SimulationEvent containing that
    instructs the simulation to create a Smart Contract Module Version Link.
    """
    return SimulationEvent(
        timestamp,
        CreateSmartContractModuleVersionsLink(
            link_id,
            smart_contract_version_id,
            alias_to_contract_module_version_id,
        ).to_dict(),
    )


def _datetime_to_rfc_3339(dt):
    timezone_aware = dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None

    if not timezone_aware:
        raise ValueError("The datetime object passed in is not timezone-aware")

    return dt.astimezone().isoformat()
