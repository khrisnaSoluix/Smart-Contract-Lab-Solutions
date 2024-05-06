# type: ignore
from abc import abstractmethod
from datetime import datetime
from functools import lru_cache
from typing import Optional

from . import types as smart_contract_types
from ..common import lib as common_lib
from ...version_390.smart_contracts import lib as v390_lib
from ....utils import symbols, types_utils


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v390_lib.VaultFunctionsABC):
    @abstractmethod
    def get_balances_observation(self, *, fetcher_id: str = None):
        pass

    @abstractmethod
    def get_balance_timeseries(self, *, fetcher_id: Optional[str] = None):
        pass

    @abstractmethod
    def get_scheduled_job_details(self):
        pass

    @abstractmethod
    def get_posting_batches(self, *, fetcher_id: str = None, include_proposed: bool = None):
        pass

    @abstractmethod
    def get_postings(self, *, fetcher_id: str = None, include_proposed: bool = None):
        pass

    @abstractmethod
    def get_client_transactions(self, *, fetcher_id: str = None, include_proposed=True):
        pass

    @abstractmethod
    def update_event_type(
        self,
        event_type: str,
        schedule: Optional[smart_contract_types.EventTypeSchedule] = None,
        end_datetime: Optional[datetime] = None,
        schedule_method: Optional[smart_contract_types.EndOfMonthSchedule] = None,
    ):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["get_postings"] = types_utils.MethodSpec(
            name="get_postings",
            docstring="""
                Gets a list of [PostingInstruction](../types/#classes-PostingInstruction)
                objects, whose `value_timestamp`s fall within the requested time window. If a
                duration is specified in the `@requires` decorator, the size of the time window
                will fall within
                `[hook_effective_date - requirement_duration, hook_effective_date]`. If a
                `fetcher_id` is specified in the
                [postings](../account_fetcher_requirements/#postings) argument of the
                `@fetch_account_data` decorator and passed as an argument in the `get_postings`
                function call, then the time window is specified in the definition of the
                [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher) with the
                specified `fetcher_id` in the
                [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list
                of the Contract metadata. If no hook decorator is provided and the current hook
                is pre/post_posting_code, this returns any covering postings of the proposed
                batch (plus the proposed postings, if `include_proposed=True`). The default
                ordering of the list is by `value_timestamp`; you can order/filter further
                using the sorted builtin and other builtin mechanisms.
            """,
            args=[
                types_utils.ValueSpec(
                    name="fetcher_id",
                    type="Optional[str]",
                    docstring="""
                        The id of the
                        [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher).
                        1. Define the fetcher in the [Contract Metadata](../metadata/)
                        [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers)
                        list. 2. Define the fetcher id in the postings argument in the
                        `@fetch_account_data` decorator. If this function is called using a
                        supervisee Vault object, the population of this argument will raise an
                        `InvalidSmartContractError`.
                        **Only available in version 3.10.0+**
                    """,
                ),
                types_utils.ValueSpec(
                    name="include_proposed",
                    type="Optional[bool]",
                    docstring="""
                        If True, and the current hook is pre/post_posting_code, the returned
                        list will include the
                        [PostingInstruction](../types/#classes-PostingInstruction) objects
                        from the proposed batch, regardless of the requested time window
                        restrictions. This argument defaults to True, unless the `fetcher_id`
                        argument is populated, in which case setting the argument to True
                        will raise an `InvalidSmartContractError`.
                    """,
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The sorted list of
                    [PostingInstructions](../types/#classes-PostingInstruction).
                """,
                type="List[PostingInstruction]",
            ),
            examples=[
                types_utils.Example(
                    title="An example with no decorator",
                    code="""
                        def post_posting_code(postings, effective_date):
                            # Returns proposed postings
                            vault.get_postings()
                            # Raises InvalidSmartContractError
                            vault.get_postings(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with @requires decorator",
                    code="""
                        @requires(postings="1 month")
                        def post_posting_code(postings, effective_date):
                            # Returns PostingInstructions in required range, including proposed
                            # postings
                            vault.get_postings()
                            # Raises InvalidSmartContractError
                            vault.get_postings(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with @fetch_account_data decorator",
                    code="""
                        @fetch_account_data(postings=["fetcher_id"])
                        def post_posting_code(postings, effective_date):
                            # Raises InvalidSmartContractError
                            vault.get_postings()
                            # Returns PostingInstructions in range defined in the fetcher
                            # excluding proposed postings
                            vault.get_postings(fetcher_id="fetcher_id")
                            # Raises InvalidSmartContractError. Proposed postings can be
                            # accessed from the hook argument.
                            vault.get_postings(fetcher_id="fetcher_id", include_proposed=True)
                            # Raises InvalidSmartContractError
                            vault.get_postings(fetcher_id="fetcher_not_in_decorator")
                    """,
                ),
            ],
        )
        spec.public_methods["get_posting_batches"] = types_utils.MethodSpec(
            name="get_posting_batches",
            docstring="""
                Gets a list of
                [PostingInstructionBatch](../types/#classes-PostingInstructionBatch) objects,
                whose `value_timestamp`s fall within the requested time window. If a duration
                is specified in the `@requires` decorator, the time window size is in the range
                `[hook_effective_date - requirement_duration, hook_effective_date]`. If a
                `fetcher_id` is specified in the
                [postings](../account_fetcher_requirements/#postings) argument of the
                `@fetch_account_data` decorator and passed as an argument in the
                `get_posting_batches` function call, then the time window is specified by the
                definition of the
                [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher) with the
                specified `fetcher_id` in the [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list
                of the Contract metadata. If no hook decorator is provided and the current hook
                is pre/post_posting_code, this returns any covering posting batches of the
                proposed batch (plus the proposed posting batch, if `include_proposed=True`).
                The default ordering of the list is by `value_timestamp`; you can order/filter
                further using the sorted builtin and other builtin mechanisms.
            """,
            args=[
                types_utils.ValueSpec(
                    name="fetcher_id",
                    type="Optional[str]",
                    docstring="""
                        The id of the
                        [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher).
                        1. Define the fetcher in the [Contract Metadata](../metadata/)
                        [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list. 2. Define the fetcher
                        id in the postings argument in the `@fetch_account_data` decorator. If
                        this function is called using a supervisee Vault object, the population
                        of this argument will raise an `InvalidSmartContractError`.
                        **Only available in version 3.10.0+**
                    """,
                ),
                types_utils.ValueSpec(
                    name="include_proposed",
                    type="Optional[bool]",
                    docstring="""
                        If True, and the current hook is pre/post_posting_code, the returned
                        list will include the proposed
                        [PostingInstructionBatch](../types/#classes-PostingInstructionBatch),
                        regardless of the requested time window restrictions. This argument
                        defaults to True, unless the `fetcher_id` argument is populated, in
                        which case setting the argument to True will raise an
                        `InvalidSmartContractError`.
                    """,
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The sorted list of
                    [PostingInstructionBatches](../types/#classes-PostingInstructionBatch).
                """,
                type="List[PostingInstructionBatch]",
            ),
            examples=[],
        )
        spec.public_methods["get_client_transactions"] = types_utils.MethodSpec(
            name="get_client_transactions",
            docstring="""
                Gets a map of `(client_id, client_transaction_id)` to
                [ClientTransaction](../types/#classes-ClientTransaction) objects,
                with the `value_timestamp` of at least one of its
                [PostingInstructions](../types/#classes-PostingInstruction) falling in the
                requested time window. If a duration is specified in the `@requires`
                decorator, the time window size is in the range
                `[hook_effective_date - requirement_duration, hook_effective_date]`. If a
                `fetcher_id` is specified in the
                [postings](../account_fetcher_requirements/#postings) argument of the
                `@fetch_account_data` decorator and passed as an argument in the
                `get_client_transactions`function call, then the time window is specified in
                the definition of the
                [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher) with the
                specified `fetcher_id` in the [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list
                of the Contract metadata. If no hook decorator is provided and the current hook
                is pre/post_posting_code, this returns the client transactions with the
                covering postings of the proposed batch. If `include_proposed=True`, these
                client transactions will include the postings of the proposed posting batch.
                The default ordering of the list of
                [PostingInstructions](../types/#classes-PostingInstruction) in each
                [ClientTransaction](../types/#classes-ClientTransaction), is by
                `value_timestamp`; you can order/filter further using the sorted builtin and
                other builtin mechanisms.
            """,
            args=[
                types_utils.ValueSpec(
                    name="fetcher_id",
                    type="Optional[str]",
                    docstring="""
                        The id of the
                        [PostingsIntervalFetcher](../types/#classes-PostingsIntervalFetcher).
                        1. Define the fetcher in the [Contract Metadata](../metadata/)
                        [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list. 2. Define the fetcher
                        id in the postings argument in the `@fetch_account_data` decorator. If
                        this function is called using a supervisee Vault object, the population
                        of this argument will raise an `InvalidSmartContractError`.
                        **Only available in version 3.10.0+**.
                    """,
                ),
                types_utils.ValueSpec(
                    name="include_proposed",
                    type="Optional[bool]",
                    docstring="""
                        If True, and the current hook is pre/post_posting_code, the returned
                        map will include the
                        [ClientTransactions](../types/#classes-ClientTransaction) from the
                        proposed
                        [PostingInstructionBatch](../types/#classes-PostingInstructionBatch),
                        regardless of the requested time window restrictions. This argument
                        defaults to True, unless the `fetcher_id` argument is populated, in
                        which case setting the argument to True will raise an
                        `InvalidSmartContractError`.
                    """,
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The [ClientTransaction](../types/#classes-ClientTransaction) dictionary,
                    keyed by `(client_id, client_transaction_id)`.
                """,
                type="Dict[Tuple[str, str], ClientTransaction]",
            ),
            examples=[],
        )
        spec.public_methods["get_balances_observation"] = types_utils.MethodSpec(
            name="get_balances_observation",
            docstring="""
                Returns the [BalancesObservation](../types/#classes-BalancesObservation) at the
                timestamp defined by the
                [BalancesObservationFetcher](../types/#classes-BalancesObservationFetcher)
                whose id is provided in the
                [balances](../account_fetcher_requirements/#balances) argument of the
                `@fetch_account_data` decorator. **Only available in version 3.10.0+**.
            """,
            args=[
                types_utils.ValueSpec(
                    name="fetcher_id",
                    type="str",
                    docstring="""
                        The id of the
                        [BalancesObservationFetcher](../types/#classes-BalancesObservationFetcher).
                        1. Define the fetcher in the [Contract Metadata](../metadata/)
                        [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list. 2. Define the fetcher
                        id in the balances argument in the `@fetch_account_data` decorator.
                    """,
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The observation which includes the Balances and the timestamp at which the
                    values apply.
                """,
                type="BalancesObservation",
            ),
            examples=[
                types_utils.Example(
                    title="An example with no decorator",
                    code="""
                        def execution_schedules(hook_arguments):
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation()
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with @requires decorator",
                    code="""
                        @requires(balances="1 month")
                        def execution_schedules(hook_arguments):
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation()
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with `@fetch_account_data` decorator",
                    code="""
                        @fetch_account_data(balances=["fetcher_id"])
                        def execution_schedules(hook_arguments):
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation()
                            # Returns BalancesObservation at the timestamp defined in the
                            # fetcher
                            vault.get_balances_observation(fetcher_id="fetcher_id")
                            # Raises InvalidSmartContractError
                            vault.get_balances_observation(fetcher_id="fetcher_not_in_decorator")
                    """,
                ),
            ],
        )
        spec.public_methods["get_balance_timeseries"] = types_utils.MethodSpec(
            name="get_balance_timeseries",
            docstring="""
                Returns the [BalanceTimeseries](../types/#classes-BalanceTimeseries) covering
                all balances over the time period specified by the hook decorator. If a
                duration is specified in the `@requires` decorator, the time window
                size is in the range
                `[hook_effective_date - requirement_duration, hook_effective_date]`. If a
                `fetcher_id` is specified in the
                [balances](../account_fetcher_requirements/#balances) argument of the
                `@fetch_account_data` decorator and passed as an argument in the function call,
                then the time window is specified in the definition of the
                [BalancesIntervalFetcher](../types/#classes-BalancesIntervalFetcher) with the
                specified `fetcher_id` in the [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list
                of the Contract metadata. If no hook decorator is provided, then an empty
                result is returned if no `fetcher_id` is passed as an argument, otherwise an
                `InvalidSmartContractError` is raised.
            """,
            args=[
                types_utils.ValueSpec(
                    name="fetcher_id",
                    type="Optional[str]",
                    docstring="""
                        The id of the
                        [BalancesIntervalFetcher](../types/#classes-BalancesIntervalFetcher).
                        1. Define the fetcher in the [Contract Metadata](../metadata/)
                        [data_fetchers](../../smart_contracts_api_reference3XX/metadata/#data_fetchers) list. 2. Define the fetcher
                        id in the balances argument in the `@fetch_account_data` decorator. If
                        this function is called using a supervisee Vault object, the population
                        of this argument will raise an `InvalidSmartContractError`.
                        **Only available in version 3.10.0+**.
                    """,
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="The Timeseries of the Balances.", type="BalanceTimeseries"
            ),
            examples=[
                types_utils.Example(
                    title="An example with no decorator",
                    code="""
                        def execution_schedules(hook_arguments):
                            # Returns empty results
                            vault.get_balance_timeseries()
                            # Raises InvalidSmartContractError
                            vault.get_balance_timeseries(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with @requires decorator",
                    code="""
                        @requires(balances="1 month")
                        def execution_schedules(hook_arguments):
                            # Returns BalanceTimeseries in required range
                            vault.get_balance_timeseries()
                            # Raises InvalidSmartContractError
                            vault.get_balance_timeseries(fetcher_id="fetcher_id")
                    """,
                ),
                types_utils.Example(
                    title="An example with @fetch_account_data decorator",
                    code="""
                        @fetch_account_data(balances=["fetcher_id"])
                        def execution_schedules(hook_arguments):
                            # Raises InvalidSmartContractError
                            vault.get_balance_timeseries()
                            # Returns BalanceTimeseries in range defined in the fetcher
                            vault.get_balance_timeseries(fetcher_id="fetcher_id")
                            # Raises InvalidSmartContractError
                            vault.get_balance_timeseries(fetcher_id="fetcher_not_in_decorator")
                    """,
                ),
            ],
        )

        spec.public_methods["get_scheduled_job_details"] = types_utils.MethodSpec(
            name="get_scheduled_job_details",
            docstring=(
                "Retrieves the details of an account [EventType]"
                "(../types/#classes-EventType) scheduled job. "
                "**Only available in version 3.10.0+**."
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
                    """,
                )
            ],
        )

        spec.public_methods["update_event_type"] = types_utils.MethodSpec(
            name="update_event_type",
            docstring="",
            return_value=types_utils.ReturnValueSpec(docstring="", type="None"),
            args=[
                types_utils.ValueSpec(
                    name="event_type",
                    type="str",
                    docstring="The name of the `EventType` that is to be modified.",
                ),
                types_utils.ValueSpec(
                    name="schedule",
                    type="Optional[EventTypeSchedule]",
                    docstring="Optional [EventTypeSchedule](#classes-EventTypeSchedule).",
                ),
                types_utils.ValueSpec(
                    name="end_datetime",
                    type="Optional[datetime]",
                    docstring="""
                        Optional datetime to determine when the schedule needs to stop
                        executing. Must have the same timezone localisation as the Contract
                        based on the [Event Timezone](../../smart_contracts_api_reference3XX/metadata/#events_timezone).

                        NOTE: Once the `end_datetime` has been reached, the schedule can
                        **no longer** be updated or re-enabled.
                    """,  # noqa E501
                ),
                types_utils.ValueSpec(
                    name="schedule_method",
                    type="Optional[EndOfMonthSchedule]",
                    docstring="""
                        Optional schedule_method allows you to specify a monthly recurring
                        schedule that runs at a specific date and time within the month, while
                        specifying rules for handling months where the given day may not exist.
                        You cannot use this method in conjunction with the schedule attribute.
                        **Only available in version 3.10.0+**

                        Note: You can only use EndOfMonthSchedule with the Contract Metadata
                        attribute events_timezone set to its default of UTC.
                    """,
                ),
            ],
            examples=[
                types_utils.Example(
                    title="Vault update_event_type usage example using EventTypeSchedule",
                    code="""
                        vault.update_event_type(
                            event_type='EVENT_NAME',
                            schedule=EventTypeSchedule(
                                minute='*/2', # every 2 minutes
                            ),
                            end_datetime=vault.get_plan_creation_date()
                        )
                    """,
                ),
                types_utils.Example(
                    title="Vault update_event_type usage example using EndOfMonthSchedule",
                    code="""
                        vault.update_event_type(
                            event_type='EVENT_NAME',
                            schedule_method=EndOfMonthSchedule(
                                day=31,
                                hour=0,
                                minute=0,
                                second=0,
                                failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE,
                            ),
                            end_datetime=vault.get_plan_creation_date()
                        )
                    """,
                ),
            ],
        )

        spec.public_methods["get_alias"] = types_utils.MethodSpec(
            name="get_alias",
            docstring="""
                Returns the alias value set for the Smart Contract Version in the Supervisor
                [SmartContractDescriptor](/reference/contracts/apis_3XX/supervisor_contracts_api_reference3XX/types/#classes-SmartContractDescriptor)
                object. Available on Supervisor Contract versions 3.4.0+ for use on the
                Supervisees
                [Vault](/reference/contracts/apis_3XX/smart_contracts_api_reference3XX/vault/)
                object only. If no aliases are defined in the Supervisor Contract metadata, then
                'None' is returned. It cannot be used on a non-supervised Vault object.
            """,
            args=[],
            return_value=types_utils.ReturnValueSpec(
                docstring="The Supervisee Smart Contract Version alias.", type="str"
            ),
        )

        return spec
