from .....utils.symbols import (
    ContractParameterLevel,
    ContractParameterUpdatePermission,
    Features,
    NoteType,
    NumberKind,
    PostingInstructionType,
    Phase,
    VaultRejectionReasonCode,
    Tside,
)
from .....utils import types_utils


PostingInstructionType = types_utils.transform_const_enum(
    name="PostingInstructionType",
    const_enum=PostingInstructionType,
    docstring="The type of the PostingInstruction",
)


Phase = types_utils.transform_const_enum(
    name="Phase",
    const_enum=Phase,
    docstring="The availability of a given Balance",
)


NumberKind = types_utils.transform_const_enum(
    name="NumberKind",
    const_enum=NumberKind,
    docstring="Kinds for NumberShapes. These provide hints on how the number should be displayed.",
)


Tside = types_utils.transform_const_enum(
    name="Tside",
    const_enum=Tside,
    docstring="Account treasury side - determine account [Balance](#classes-Balance) net sign.",
)


Level = types_utils.transform_const_enum(
    name="Level",
    const_enum=ContractParameterLevel,
    docstring="Different levels of visibility for Parameter objects.",
)


Features = types_utils.transform_const_enum(
    name="Features",
    const_enum=Features,
    docstring="Deprecated. This enum is supported in the current Smart Contract API major version "
    "for backwards compatibility reasons but has no effect. It will be removed in the Smart "
    "Contract API 4.0 version.",
)


NoteType = types_utils.transform_const_enum(
    name="NoteType",
    const_enum=NoteType,
    docstring="Indicates the intention when calling "
    "[vault.add_account_note()](/reference/contracts/apis_3XX/smart_contracts_api_reference3XX/vault/#methods-add_account_note).",
)


RejectedReason = types_utils.transform_const_enum(
    name="RejectedReason",
    const_enum=VaultRejectionReasonCode,
    docstring="May optionally be used as the `reason_code` parameter on the "
    "[Rejected](#exceptions-Rejected) exception.",
)


UpdatePermission = types_utils.transform_const_enum(
    name="UpdatePermission",
    const_enum=ContractParameterUpdatePermission,
    docstring="Specifies who can edit a parameter",
)
