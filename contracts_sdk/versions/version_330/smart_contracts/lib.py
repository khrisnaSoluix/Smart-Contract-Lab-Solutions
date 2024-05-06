from abc import abstractmethod
from datetime import datetime
from functools import lru_cache

from . import types as smart_contract_types
from ....utils import symbols, types_utils
from ...version_320.smart_contracts import lib as v320_lib
from ..common import lib as common_lib


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v320_lib.VaultFunctionsABC):
    @abstractmethod
    def localize_datetime(self, dt: datetime) -> datetime:
        pass

    @abstractmethod
    def amend_schedule(self, *, event_type, new_schedule):
        pass

    @abstractmethod
    def remove_schedule(self, *, event_type):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        localize_datetime_spec = types_utils.MethodSpec(
            name="localize_datetime",
            docstring="""
                Localizes a datetime value to the events_timezone specified in the contract.
                If no events_timezone is specified in the contract, the UTC timezone is
                used.
            """,
            args=[
                types_utils.ValueSpec(
                    name="dt", type="datetime", docstring="The datetime to localize"
                )
            ],
            return_value=types_utils.ReturnValueSpec(
                type="datetime", docstring="The localized datetime"
            ),
            examples=[
                types_utils.Example(
                    title="Localizing the account creation date.",
                    code="""
                    def execution_schedules():
                        utc_creation_date = vault.get_account_creation_date()
                        localized_creation_date = vault.localize_datetime(utc_creation_date)
                    """,
                )
            ],
        )
        spec.public_methods[localize_datetime_spec.name] = localize_datetime_spec
        spec.public_methods[
            "amend_schedule"
        ].docstring = """
            Replaces the schedule for *event_type* with *new_schedule*.
            Requires full definition of *new_schedule* as this function
            disables the old schedule and creates a *new_schedule* in Vault.
            See [execution_schedules](../../smart_contracts_api_reference3XX/hooks/#execution_schedules) for information on schedules.
            In versions 3.3+, amending schedules that belong to event type group is not allowed.
        """
        spec.public_methods[
            "remove_schedule"
        ].docstring = """
            Instructs Vault to stop scheduling execution of the `scheduled_code` hook
            for the given `event_type`.
            In versions 3.3+, removing schedules that belong to event type group is not allowed.
        """
        return spec
