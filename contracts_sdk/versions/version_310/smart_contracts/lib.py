from abc import abstractmethod
from functools import lru_cache

from . import types as smart_contract_types
from ..common import lib as common_lib
from ...version_300.smart_contracts import lib as v300_lib
from ....utils import symbols, types_utils


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v300_lib.VaultFunctionsABC):
    @abstractmethod
    def make_internal_transfer_instructions(
        self,
        *,
        amount,
        denomination,
        client_transaction_id,
        from_account_id,
        from_account_address=None,
        to_account_id,
        to_account_address=None,
        pics=None,
        override_all_restrictions=False,
        instruction_details=None,
        asset=symbols.DEFAULT_ASSET,
        custom_instruction_grouping_key=None
    ):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        key = "make_internal_transfer_instructions"
        arg = "override_all_restrictions"
        spec.public_methods[key].args[arg] = types_utils.ValueSpec(
            name="override_all_restrictions",
            type="Optional[bool]",
            docstring="""Specifies whether to ignore all restrictions. Available on
            versions 3.1.0+.""",
        )

        return spec
