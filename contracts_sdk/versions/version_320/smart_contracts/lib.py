from . import types as smart_contract_types
from ..common import lib as common_lib
from ...version_310.smart_contracts import lib as v310_lib


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v310_lib.VaultFunctionsABC):
    pass
