from ...version_350.smart_contracts.types import *  # noqa: F403, F401
from ...version_350.smart_contracts import types as types350
from ..common.types import (
    Balance,
    BalanceDefaultDict,
    BalanceTimeseries,
    HookDirectives,
    anyObject,
    callableObject,
    defaultDictObject,
    dictObject,
    iterableObject,
    iteratorObject,
    listObject,
    mappingObject,
    namedTupleObject,
    newTypeObject,
    noReturnObject,
    optionalObject,
    setObject,
    typeObject,
    tupleObject,
    unionObject,
    PostingInstruction,
    PostingInstructionBatch,
    ClientTransaction,
    PostingInstructionBatchDirective,
)


def types_registry():
    TYPES = types350.types_registry()
    TYPES["Balance"] = Balance
    TYPES["BalanceDefaultDict"] = BalanceDefaultDict
    TYPES["BalanceTimeseries"] = BalanceTimeseries
    TYPES["PostingInstruction"] = PostingInstruction
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["ClientTransaction"] = ClientTransaction
    TYPES["HookDirectives"] = HookDirectives
    TYPES["PostingInstructionBatchDirective"] = PostingInstructionBatchDirective
    TYPES["Any"] = anyObject
    TYPES["Callable"] = callableObject
    TYPES["DefaultDict"] = defaultDictObject
    TYPES["Dict"] = dictObject
    TYPES["Iterable"] = iterableObject
    TYPES["Iterator"] = iteratorObject
    TYPES["List"] = listObject
    TYPES["Mapping"] = mappingObject
    TYPES["NamedTuple"] = namedTupleObject
    TYPES["NewType"] = newTypeObject
    TYPES["NoReturn"] = noReturnObject
    TYPES["Optional"] = optionalObject
    TYPES["Set"] = setObject
    TYPES["Tuple"] = tupleObject
    TYPES["Type"] = typeObject
    TYPES["Union"] = unionObject
    return TYPES
