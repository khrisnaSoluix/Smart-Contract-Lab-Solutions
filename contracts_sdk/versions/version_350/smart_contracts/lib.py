from abc import abstractmethod
from functools import lru_cache

from . import types as smart_contract_types
from ..common import lib as common_lib
from ...version_340.smart_contracts import lib as v340_lib
from ....utils import symbols, types_utils


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v340_lib.VaultFunctionsABC):
    @abstractmethod
    def get_permitted_denominations(self):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["get_permitted_denominations"] = types_utils.MethodSpec(
            name="get_permitted_denominations",
            docstring="""
                Returns the permitted denominations of the account.
            """,
            args=[],
            return_value=types_utils.ReturnValueSpec(
                docstring="A list of denominations.", type="List[str]"
            ),
        )
        return spec
