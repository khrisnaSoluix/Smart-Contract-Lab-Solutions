from abc import abstractmethod
from functools import lru_cache

from . import types as smart_contract_types
from ..common import lib as common_lib
from ...version_330.smart_contracts import lib as v330_lib
from ....utils import symbols, types_utils


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v330_lib.VaultFunctionsABC):
    @abstractmethod
    def get_hook_directives(self):
        pass

    @abstractmethod
    def get_alias(self):
        pass

    @abstractmethod
    def get_flag_timeseries(self, *, flag):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_attributes["tside"] = types_utils.ValueSpec(
            name="tside",
            type="Tside",
            docstring="""
                The treasury side of the Account. It determines the Account
                [Balance](../types/#classes-Balance) net sign. Available on versions 3.4.0+.
            """,
        )

        spec.public_methods["get_hook_directives"] = types_utils.MethodSpec(
            name="get_hook_directives",
            docstring="""
                Returns the uncommitted Supervisee
                [HookDirectives](/reference/contracts/apis_3XX/supervisor_contracts_api_reference3XX/types/#classes-HookDirectives).
                Available on Supervisor Contract versions 3.4.0+ for use on the Supervisees
                [Vault](/reference/contracts/apis_3XX/smart_contracts_api_reference3XX/vault/)
                object only. It cannot be used on a non-supervised Vault object.
            """,
            args=[],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The Supervisee uncommitted
                    [HookDirectives](/reference/contracts/apis_3XX/supervisor_contracts_api_reference3XX/types/#classes-HookDirectives).
                """,
                type="HookDirectives",
            ),
        )
        spec.public_methods["get_alias"] = types_utils.MethodSpec(
            name="get_alias",
            docstring="""
                Returns the alias value set for the Smart Contract Version in the Supervisor
                [SmartContractDescriptor](/reference/contracts/apis_3XX/supervisor_contracts_api_reference3XX/types/#classes-SmartContractDescriptor)
                object. Available on Supervisor Contract versions 3.4.0+ for use on the Supervisees
                [Vault](/reference/contracts/apis_3XX/smart_contracts_api_reference3XX/vault/)
                object only. It cannot be used on a non-supervised Vault object.
            """,
            args=[],
            return_value=types_utils.ReturnValueSpec(
                docstring="The Supervisee Smart Contract Version alias.", type="str"
            ),
        )

        return spec
