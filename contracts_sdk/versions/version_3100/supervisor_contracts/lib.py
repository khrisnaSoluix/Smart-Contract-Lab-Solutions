from abc import abstractmethod
from functools import lru_cache

from . import types as supervisor_contract_types
from ..common import lib as common_lib
from ...version_390.supervisor_contracts import lib as v390_lib
from ....utils import symbols, types_utils


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v390_lib.VaultFunctionsABC):
    @abstractmethod
    def get_scheduled_job_details(self):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["get_scheduled_job_details"] = types_utils.MethodSpec(
            name="get_scheduled_job_details",
            docstring=(
                "Retrieves the details of an account [EventType]"
                "(../types/#classes-EventType) scheduled job. "
                "**Only available in version 3.10.0+**"
            ),
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The [ScheduledJob](../types/#classes-ScheduledJob) details for the current
                    event.
                """,
                type="ScheduledJob",
            ),
            examples=[
                types_utils.Example(
                    title="Access additional details of a scheduled job.",
                    code="""
                        pause_datetime = vault.get_scheduled_job_details().pause_datetime

                        supervisee_vault = vault.supervisees['SUPERVISEE']
                        supervisee_pause_datetime = (
                            supervisee_vault.get_scheduled_job_details().pause_datetime
                        )
                    """,
                )
            ],
        )

        return spec
