from . import types as supervisor_contract_types
from ..common import lib as common_lib
from ...version_350.supervisor_contracts import lib as v350_lib


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v350_lib.VaultFunctionsABC):
    pass
