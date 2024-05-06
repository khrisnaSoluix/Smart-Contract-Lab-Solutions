from ...version_310.smart_contracts.types import *  # noqa: F401, F403
from ..common.types.parameters import Parameter
from ..common.types.postings import PostingInstruction, PostingInstructionBatch
from ..common.types.constants import transaction_reference_field_name
from ...version_310.smart_contracts import types as types310


def types_registry():
    TYPES = types310.types_registry()
    TYPES["Parameter"] = Parameter
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["PostingInstruction"] = PostingInstruction
    TYPES["TRANSACTION_REFERENCE_FIELD_NAME"] = transaction_reference_field_name
    return TYPES
