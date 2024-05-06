from ...version_300.smart_contracts.types import *  # noqa: F401, F403
from ..common.types import (
    AddressDetails,
    AccountIdShape,
    DateShape,
    DenominationShape,
    NumberShape,
    OptionalShape,
    Parameter,
    StringShape,
    UnionShape,
    PostingInstruction,
    PostingInstructionBatch,
)
from ...version_300.smart_contracts import types as types300


def types_registry():
    TYPES = types300.types_registry()
    TYPES["NumberShape"] = NumberShape
    TYPES["StringShape"] = StringShape
    TYPES["AccountIdShape"] = AccountIdShape
    TYPES["DenominationShape"] = DenominationShape
    TYPES["DateShape"] = DateShape
    TYPES["OptionalShape"] = OptionalShape
    TYPES["UnionShape"] = UnionShape
    TYPES["Parameter"] = Parameter
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["PostingInstruction"] = PostingInstruction

    TYPES["AddressDetails"] = AddressDetails
    return TYPES
