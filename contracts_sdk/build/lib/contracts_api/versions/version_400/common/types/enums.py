from enum import Enum
from functools import lru_cache

from .....utils import symbols
from .....utils.types_utils import EnumSpec, EnumRepr, enum_members


class RejectionReason(EnumRepr, Enum):
    UNKNOWN_REASON = symbols.VaultRejectionReasonCode.UNKNOWN_REASON
    INSUFFICIENT_FUNDS = symbols.VaultRejectionReasonCode.INSUFFICIENT_FUNDS
    WRONG_DENOMINATION = symbols.VaultRejectionReasonCode.WRONG_DENOMINATION
    AGAINST_TNC = symbols.VaultRejectionReasonCode.AGAINST_TNC
    CLIENT_CUSTOM_REASON = symbols.VaultRejectionReasonCode.CLIENT_CUSTOM_REASON

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=(
                "May optionally be used as the `reason_code` parameter on the "
                "[Rejection](#classes-Rejection) class."
            ),
            members=enum_members(cls),
            show_values=False,
        )


class Tside(EnumRepr, Enum):
    ASSET = symbols.Tside.ASSET
    LIABILITY = symbols.Tside.LIABILITY

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=(
                "Account treasury side - determine account [Balance](#classes-Balance) " "net sign."
            ),
            members=enum_members(cls),
            show_values=False,
        )


class Phase(EnumRepr, Enum):
    COMMITTED = symbols.Phase.COMMITTED
    PENDING_IN = symbols.Phase.PENDING_IN
    PENDING_OUT = symbols.Phase.PENDING_OUT

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("The availability of a given Balance."),
            members=enum_members(cls),
            show_values=False,
        )


class ParameterLevel(EnumRepr, Enum):
    GLOBAL = symbols.ContractParameterLevel.GLOBAL
    TEMPLATE = symbols.ContractParameterLevel.TEMPLATE
    INSTANCE = symbols.ContractParameterLevel.INSTANCE

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("Different levels of visibility for Parameter objects."),
            members=enum_members(cls),
            show_values=False,
        )


class ParameterUpdatePermission(EnumRepr, Enum):
    PERMISSION_UNKNOWN = symbols.ContractParameterUpdatePermission.PERMISSION_UNKNOWN
    FIXED = symbols.ContractParameterUpdatePermission.FIXED
    OPS_EDITABLE = symbols.ContractParameterUpdatePermission.OPS_EDITABLE
    USER_EDITABLE = symbols.ContractParameterUpdatePermission.USER_EDITABLE
    USER_EDITABLE_WITH_OPS_PERMISSION = (
        symbols.ContractParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION
    )  # noqa: E501

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("Specifies who can edit a parameter."),
            members=enum_members(cls),
            show_values=False,
        )


class DefinedDateTime(EnumRepr, Enum):
    LIVE = symbols.DefinedDateTime.LIVE
    # EFFECTIVE_TIME = 1  Removed in v4
    INTERVAL_START = symbols.DefinedDateTime.INTERVAL_START
    EFFECTIVE_DATETIME = symbols.DefinedDateTime.EFFECTIVE_DATETIME

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("A datetime that is defined within Vault."),
            members=enum_members(cls),
            show_values=False,
        )


class ScheduleFailover(EnumRepr, Enum):
    FIRST_VALID_DAY_BEFORE = symbols.ScheduleFailover.FIRST_VALID_DAY_BEFORE
    FIRST_VALID_DAY_AFTER = symbols.ScheduleFailover.FIRST_VALID_DAY_AFTER

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("Specify the failover strategy for this schedule."),
            members=enum_members(cls),
            show_values=False,
        )


class SupervisionExecutionMode(EnumRepr, Enum):
    OVERRIDE = symbols.SupervisionExecutionMode.OVERRIDE
    INVOKED = symbols.SupervisionExecutionMode.INVOKED

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=(
                "Determines the execution of a supervisee's hook when triggered by an incoming "
                "request. If INVOKED, this executes the supervised account first, triggered by the "
                "incoming request, and provides the results to the supervisor. If OVERRIDE, this "
                "executes the supervisor hook instead of the supervisee's hook."
            ),
            members=enum_members(cls),
            show_values=False,
        )


class PostingInstructionType(EnumRepr, Enum):
    OUTBOUND_AUTHORISATION = symbols.PostingInstructionType.OUTBOUND_AUTHORISATION
    INBOUND_AUTHORISATION = symbols.PostingInstructionType.INBOUND_AUTHORISATION
    AUTHORISATION = symbols.PostingInstructionType.AUTHORISATION
    AUTHORISATION_ADJUSTMENT = symbols.PostingInstructionType.AUTHORISATION_ADJUSTMENT
    CUSTOM_INSTRUCTION = symbols.PostingInstructionType.CUSTOM_INSTRUCTION
    OUTBOUND_HARD_SETTLEMENT = symbols.PostingInstructionType.OUTBOUND_HARD_SETTLEMENT
    INBOUND_HARD_SETTLEMENT = symbols.PostingInstructionType.INBOUND_HARD_SETTLEMENT
    HARD_SETTLEMENT = symbols.PostingInstructionType.HARD_SETTLEMENT
    RELEASE = symbols.PostingInstructionType.RELEASE
    SETTLEMENT = symbols.PostingInstructionType.SETTLEMENT
    TRANSFER = symbols.PostingInstructionType.TRANSFER

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH) -> EnumSpec:
        return EnumSpec(
            name=cls.__name__,
            docstring=("The type of the PostingInstruction."),
            members=enum_members(cls),
            show_values=False,
        )



