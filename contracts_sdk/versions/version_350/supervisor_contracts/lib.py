from . import types as supervisor_contract_types
from ..common import lib as common_lib
from ...version_340.supervisor_contracts import lib as v340_lib


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v340_lib.VaultFunctionsABC):
    pass
