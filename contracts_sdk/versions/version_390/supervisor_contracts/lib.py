from . import types as supervisor_contract_types
from ...version_380.supervisor_contracts import lib as v380_lib
from ..common import lib as common_lib


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v380_lib.VaultFunctionsABC):
    pass
