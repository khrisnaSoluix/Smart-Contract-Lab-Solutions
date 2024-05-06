from abc import abstractmethod
from datetime import datetime
from functools import lru_cache

from . import types as supervisor_contract_types
from ....utils import symbols, types_utils
from ..common import lib as common_lib

types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(types_utils.StrictInterface):
    @abstractmethod
    def get_last_execution_time(self, *, event_type):
        pass

    @abstractmethod
    def localize_datetime(self, dt: datetime) -> datetime:
        pass

    @abstractmethod
    def get_plan_creation_date(self):
        pass

    @abstractmethod
    def get_hook_execution_id(self):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = types_utils.ClassSpec(
            name="VaultFunctions",
            docstring="""
                The Vault object is present during the execution of every hook and is accessible
                via the `vault` variable.

                Apart from hook-specific arguments and return values, it is the sole method of
                fetching information from Vault or communicating "hook directives" back to Vault.

                All information fetched from the `vault` object must have been statically declared
                at the top of a hook using the `@requires` decorator, and is fetched in a batch
                before the hook starts executing.

                All hook directives are batched until the hook finishes executing, and then
                implemented in Vault at the same time.
            """,
            public_methods=[
                types_utils.MethodSpec(
                    name="get_last_execution_time",
                    docstring="""
                    Gets the most recent time that the `scheduled_code` hook was called for
                    the given `event_type`.
                """,
                    args=[
                        types_utils.ValueSpec(
                            name="event_type",
                            type="str",
                            docstring="The `scheduled_code` hook's `event_type` string.",
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        docstring="The last execution time.", type="datetime"
                    ),
                    examples=[
                        types_utils.Example(
                            title="A simple example",
                            code="vault.get_last_execution_time(event_type='SERVICE_CHARGE')",
                        )
                    ],
                )
            ],
        )
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
        spec.public_attributes["plan_id"] = types_utils.ValueSpec(
            name="plan_id", type="str", docstring="The ID of the Plan currently being executed."
        )
        spec.public_attributes["supervisees"] = types_utils.ValueSpec(
            name="supervisees",
            type="Dict[str, Vault]",
            docstring="""
                A dictionary which maps the supervised Account IDs to their
                [Vault](../../smart_contracts_api_reference3XX/vault) objects. These objects can
                be used to retrieve account data, and to retrieve or commit
                [HookDirectives](../types/#classes-HookDirectives). The allowed API functions of
                the Supervisee Vault objects per hook can be found
                [here](../hooks/).
            """,
        )
        spec.public_methods["get_hook_execution_id"] = types_utils.MethodSpec(
            name="get_hook_execution_id",
            docstring="""
                Returns a unique-enough string that can be used in generating unique IDs for
                attaching to [HookDirectives](../types/#classes-HookDirectives) objects. The string
                returned is a combination of `plan_id`, `hook_id`, `event_type` and
                `effective_date`. Note: this string is unique for the Plan hook execution and it
                should not be used for multiple Supervisee
                [HookDirectives](../types/#classes-HookDirectives), unless modified.
            """,
            args=[],
            return_value=types_utils.ReturnValueSpec(docstring="The unique-enough ID.", type="str"),
        )
        spec.public_methods["get_plan_creation_date"] = types_utils.MethodSpec(
            name="get_plan_creation_date",
            docstring="Returns the creation date of the Plan currently being executed.",
            args=[],
            return_value=types_utils.ReturnValueSpec(
                docstring="The date the Plan was created.", type="datetime"
            ),
        )
        return spec
