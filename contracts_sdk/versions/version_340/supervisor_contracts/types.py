from functools import lru_cache

from ..common.types import (
    Balance,
    BalanceDefaultDict,
    BalanceTimeseries,
    defaultAddress,
    defaultAsset,
    Level,
    Features,
    NoteType,
    NumberKind,
    Phase,
    PostingInstructionType,
    RejectedReason,
    Tside,
    UpdatePermission,
    InvalidContractParameter,
    Rejected,
    FlagTimeseries,
    calendarObject,
    datetimeObject,
    decimalObject,
    defaultDict,
    mathObject,
    jsonDumpsObject,
    jsonLoadsObject,
    parseToDatetimeObject,
    roundFloorObject,
    roundHalfDownObject,
    roundHalfUpObject,
    timedeltaObject,
    OptionalValue,
    ParameterTimeseries,
    UnionItem,
    UnionItemValue,
    ClientTransaction,
    ClientTransactionEffects,
    ClientTransactionEffectsDefaultDict,
    AddressDetails,
    AccountIdShape,
    DateShape,
    DenominationShape,
    NumberShape,
    OptionalShape,
    StringShape,
    UnionShape,
    Parameter,
    PostingInstruction,
    PostingInstructionBatch,
    transaction_reference_field_name,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_05UP,
    EventTypesGroup,
    AddAccountNoteDirective,
    AmendScheduleDirective,
    HookDirectives,
    PostingInstructionBatchDirective,
    RemoveSchedulesDirective,
    WorkflowStartDirective,
)

from ....utils import types_utils
from ....utils import symbols


class EventType:
    def __init__(self, *, name, scheduler_tag_ids=None, overrides_event_types=None):
        self._spec().assert_constructor_args(
            self._registry,
            {
                "name": name,
                "scheduler_tag_ids": scheduler_tag_ids,
                "overrides_event_types": overrides_event_types,
            },
        )

        self.name = name
        self.scheduler_tag_ids = scheduler_tag_ids
        self.overrides_event_types = overrides_event_types

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="EventType",
            docstring="""
                    Each scheduled event in a Supervisor Contract has an
                    [EventType](#classes-EventType) associated with it. Each
                    [EventType](#classes-EventType) must have a unique name within the Supervisor
                    Contract and can have optional Scheduler Tags and overridden Schedules
                    attributes. Each Supervisor Contract must include all
                    [EventTypes](#classes-EventType) returned by the
                    [execution_schedules](../../smart_contracts_api_reference3XX/hooks/#execution_schedules)
                    hook in the `event_types` list. **Only available in version 3.4.0+**.
                """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new EventType", args=cls._public_attributes(language_code)
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="name",
                type="str",
                docstring="""
                    The name of the [EventType](#classes-EventType). This name will be the same as
                    the name defined in the
                    [execution_schedules](../../smart_contracts_api_reference3XX/hooks/#execution_schedules)
                    hook.
                """,
            ),
            types_utils.ValueSpec(
                name="scheduler_tag_ids",
                type="Optional[List[str]]",
                docstring="""
                    An optional list of string IDs for the
                    [Scheduler Tags](/api/core_api/#Scheduler-ScheduleTag) of an
                    [EventType](#classes-EventType). The Tags must be created in the Scheduler
                    before they are referenced in a Supervisor Contract. The Tag IDs are global in
                    Vault and must exactly match the Tag IDs created in the Scheduler.
                    [EventTypes](#classes-EventType) in different Contracts with the same Tag will
                    be linked together. This defaults to no Tags if a Tag ID is not provided.
                """,
            ),
            types_utils.ValueSpec(
                name="overrides_event_types",
                type="Optional[List[Tuple[str, str]]]",
                docstring="""
                    A list of (Smart Contract `alias`, `event_type`) tuples specifying which are
                    the overridden Schedules for each [EventType](#classes-EventType). If not
                    provided, this [EventType](#classes-EventType) does not override any of the
                    Supervisee Schedules. The Smart Contract alias is the alias defined in the
                    [SmartContractDescriptor](#classes-SmartContractDescriptor).
                    Note that each Supervisor EventType can only override one Schedule
                    per Supervisee. If multiple Supervisee Schedules need to be overridden,
                    this has to be done using multiple Supervisee EventTypes.
                """,
            ),
        ]


class SmartContractDescriptor:
    def __init__(self, *, alias, smart_contract_version_id):
        self._spec().assert_constructor_args(
            self._registry, {"alias": alias, "smart_contract_version_id": smart_contract_version_id}
        )

        self.alias = alias
        self.smart_contract_version_id = smart_contract_version_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SmartContractDescriptor",
            docstring="""
                **Only available in version 3.4+.**
                Each Supervisor Contract must declare the Smart Contracts that it supervises. Using
                the Smart Contract Descriptor object, a Product Version Id is declared with an alias
                that is used throughout the Supervisor Contract to refer to this Smart Contract
                Product Version.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SmartContractDescriptor",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="alias",
                type="str",
                docstring="""
                    An alias for the Product Version to use throughout the Supervisor Contract.
                """,
            ),
            types_utils.ValueSpec(
                name="smart_contract_version_id",
                type="str",
                docstring="""
                    A string ID for the Product Version of a Smart Contract that will be supervised
                    by this Supervisor Contract.
                """,
            ),
        ]


# Master copy for types registry for Supervisor Contracts.
def types_registry():
    return {
        "AccountIdShape": AccountIdShape,
        "AddAccountNoteDirective": AddAccountNoteDirective,
        "AddressDetails": AddressDetails,
        "AmendScheduleDirective": AmendScheduleDirective,
        "Balance": Balance,
        "BalanceDefaultDict": BalanceDefaultDict,
        "BalanceTimeseries": BalanceTimeseries,
        "calendar": calendarObject,
        "ClientTransaction": ClientTransaction,
        "ClientTransactionEffects": ClientTransactionEffects,
        "ClientTransactionEffectsDefaultDict": ClientTransactionEffectsDefaultDict,
        "DateShape": DateShape,
        "datetime": datetimeObject,
        "Decimal": decimalObject,
        "defaultdict": defaultDict,
        "DEFAULT_ADDRESS": defaultAddress,
        "DEFAULT_ASSET": defaultAsset,
        "DenominationShape": DenominationShape,
        "EventType": EventType,
        "EventTypesGroup": EventTypesGroup,
        "FlagTimeseries": FlagTimeseries,
        "HookDirectives": HookDirectives,
        "InvalidContractParameter": InvalidContractParameter,
        "math": mathObject,
        "json_dumps": jsonDumpsObject,
        "json_loads": jsonLoadsObject,
        "Level": Level,
        "Features": Features,
        "NoteType": NoteType,
        "NumberShape": NumberShape,
        "NumberKind": NumberKind,
        "OptionalShape": OptionalShape,
        "OptionalValue": OptionalValue,
        "Parameter": Parameter,
        "ParameterTimeseries": ParameterTimeseries,
        "parse_to_datetime": parseToDatetimeObject,
        "Phase": Phase,
        "PostingInstruction": PostingInstruction,
        "PostingInstructionBatch": PostingInstructionBatch,
        "PostingInstructionBatchDirective": PostingInstructionBatchDirective,
        "PostingInstructionType": PostingInstructionType,
        "Rejected": Rejected,
        "RejectedReason": RejectedReason,
        "RemoveSchedulesDirective": RemoveSchedulesDirective,
        "ROUND_CEILING": ROUND_CEILING,
        "ROUND_DOWN": ROUND_DOWN,
        "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
        "ROUND_05UP": ROUND_05UP,
        "ROUND_FLOOR": roundFloorObject,
        "ROUND_HALF_DOWN": roundHalfDownObject,
        "ROUND_HALF_UP": roundHalfUpObject,
        "SmartContractDescriptor": SmartContractDescriptor,
        "StringShape": StringShape,
        "timedelta": timedeltaObject,
        "Tside": Tside,
        "TRANSACTION_REFERENCE_FIELD_NAME": transaction_reference_field_name,
        "UnionItem": UnionItem,
        "UnionItemValue": UnionItemValue,
        "UnionShape": UnionShape,
        "UpdatePermission": UpdatePermission,
        "WorkflowStartDirective": WorkflowStartDirective,
    }
