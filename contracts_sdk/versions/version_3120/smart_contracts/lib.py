from abc import abstractmethod
from functools import lru_cache
from typing import Dict

from . import types as smart_contract_types
from ...version_3110.smart_contracts import lib as v3110_lib
from ..common import lib as common_lib
from ....utils import symbols, types_utils, feature_flags


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v3110_lib.VaultFunctionsABC):
    @abstractmethod
    def instruct_notification(
        self,
        notification_type: str,
        notification_details: Dict[str, str],
    ):
        pass

    @abstractmethod
    def get_hook_return_data(self):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        if feature_flags.is_fflag_enabled(feature_flags.PRE_POSTING_SUPERVISION):
            spec.public_methods["get_hook_return_data"] = types_utils.MethodSpec(
                name="get_hook_return_data",
                docstring="""
                    Returns a [Rejected](../types/#exceptions-Rejected) Exception object from the
                    supervisee, or None if either no Rejections were raised, or the hook was not
                    invoked.
                    In order to retrieve hook return data from a supervisee, this must be called
                    from within the Supervisor hook, and the supervisee must be associated with a
                    [SupervisionExecutionMode](../../supervisor_contracts_api_reference3XX/types/#enums-SupervisionExecutionMode)
                    of INVOKED to trigger execution of the supervisee hook.
                    **Only available in version 3.12+**
                """,
                args=[],
                return_value=types_utils.ReturnValueSpec(
                    docstring="""
                        The [Rejected](../types/#exceptions-Rejected) Exception type,
                        raised by the supervisee's hook execution, or None.
                    """,
                    type="Union[Rejected, None]",
                ),
            )

            existing_get_balances_observation = spec.public_methods["get_balances_observation"]
            existing_get_balances_observation.examples.append(
                types_utils.Example(
                    title="Supervisor example with no decorator",
                    code="""
                        def pre_posting_code(postings, effective_date):
                            # Iterate through supervisees
                            for account_id, supervisee in vault.supervisees.items():
                                # Raises InvalidSmartContractError
                                supervisee.get_balances_observation()
                                # Raises InvalidSmartContractError
                                supervisee.get_balances_observation(fetcher_id="fetcher_id")
                    """,
                ),
            )
            existing_get_balances_observation.examples.append(
                types_utils.Example(
                    title="Supervisor example with `@fetch_account_data` decorator",
                    code="""
                        @fetch_account_data(balances={"supervisee_alias": ["fetcher_id"]})
                        def pre_posting_code(postings, effective_date):
                            # Iterate through supervisees
                            for account_id, supervisee in vault.supervisees.items():
                                # Raises InvalidSmartContractError
                                supervisee.get_balances_observation()
                                # Returns BalancesObservation at the timestamp defined in the
                                # fetcher
                                supervisee.get_balances_observation(fetcher_id="fetcher_id")
                                # Raises InvalidSmartContractError
                                supervisee.get_balances_observation(fetcher_id="fetcher_not_in_decorator")
                    """,
                ),
            )
            spec.public_methods["get_balances_observation"] = existing_get_balances_observation

            existing_get_balance_timeseries = spec.public_methods["get_balance_timeseries"]
            existing_get_balance_timeseries.examples.append(
                types_utils.Example(
                    title="Supervisor example with no decorator",
                    code="""
                        def pre_posting_code(postings, effective_date):
                            # Iterate through supervisees
                            for account_id, supervisee in vault.supervisees.items():
                                # Raises InvalidSmartContractError
                                supervisee.get_balance_timeseries()
                                # Raises InvalidSmartContractError
                                supervisee.get_balance_timeseries(fetcher_id="fetcher_id")
                    """,
                ),
            )
            existing_get_balance_timeseries.examples.append(
                types_utils.Example(
                    title="Supervisor example with `@fetch_account_data` decorator",
                    code="""
                        @fetch_account_data(balances={"supervisee_alias": ["fetcher_id"]})
                        def pre_posting_code(postings, effective_date):
                            # Iterate through supervisees
                            for account_id, supervisee in vault.supervisees.items():
                                # Raises InvalidSmartContractError
                                supervisee.get_balance_timeseries()
                                # Returns BalanceTimeseries in range defined in the fetcher
                                supervisee.get_balance_timeseries(fetcher_id="fetcher_id")
                                # Raises InvalidSmartContractError
                                supervisee.get_balance_timeseries(fetcher_id="fetcher_not_in_decorator")
                    """,
                ),
            )
            spec.public_methods["get_balance_timeseries"] = existing_get_balance_timeseries

        if feature_flags.is_fflag_enabled(feature_flags.CONTRACTS_NOTIFICATION_EVENT):
            spec.public_methods["instruct_notification"] = types_utils.MethodSpec(
                name="instruct_notification",
                docstring="""
                    Instructs the publishing of a notification.
                    **Only available in version 3.12+**
                """,
                args=[
                    types_utils.ValueSpec(
                        name="notification_type",
                        type="str",
                        docstring="The `type` of notification to be published.",
                    ),
                    types_utils.ValueSpec(
                        name="notification_details",
                        type="Dict[str, str]",
                        docstring="""
                            The information (key-value pairs of data)
                            to be published with the notification.
                        """,
                    ),
                ],
                examples=[
                    types_utils.Example(
                        title="How to instruct a notification event",
                        code="""
                                notification_types = ['NOTIFICATION_TYPE']

                                def post_posting_code(postings, effective_date):
                                    vault.instruct_notification(
                                        notification_type='NOTIFICATION_TYPE',
                                        notification_details={
                                            "key": "value",
                                        }
                                    )
                            """,
                    )
                ],
            )
        return spec
