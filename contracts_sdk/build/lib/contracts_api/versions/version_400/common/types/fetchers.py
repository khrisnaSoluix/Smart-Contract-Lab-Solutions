from functools import lru_cache, wraps
from typing import Optional, Union

from .enums import DefinedDateTime
from .time_operations import RelativeDateTime
from .....utils import exceptions, symbols, types_utils
from .filters import (
    BalancesFilter,
    
)


def _requires(
    *,
    balances: Optional[str] = None,
    calendar: Optional[list[str]] = None,
    data_scope: Optional[str] = None,
    event_type: Optional[str] = None,
    flags: Optional[bool] = None,
    last_execution_datetime: Optional[list[str]] = None,
    parameters: Optional[bool] = None,
    postings: Optional[bool] = None,
    supervisee_hook_directives: Optional[str] = None,
):
    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return wrapper


requires = types_utils.DecoratorSpec(
    name="requires",
    object=_requires,
    docstring="`@requires(*, balances, calendar, data_scope, event_type, flags, "
    "last_execution_datetime, parameters, postings, supervisee_hook_directives)`\n\n"
    "See full requirements reference for [Smart Contracts](/reference/contracts/apis_4XX/"
    "smart_contracts_api_reference4XX/hook_requirements) and [Supervisors](/reference/contracts/"
    "apis_4XX/supervisor_contracts_api_reference4XX/hook_requirements)\n\n"
    "__Note:__ the `scheduled_event_hook` can be decorated with multiple `@requires` decorators to "
    "define requirements per event_type",
    args=[
        types_utils.ValueSpec(
            name="balances",
            type="str",
            docstring="""
                A [Range Specifier](/reference/contracts/concepts_4xx/#requirements-range_specifiers)
                for example "1 day live"
            """,  # noqa: E501
        ),
        types_utils.ValueSpec(
            name="calendar",
            type="List[str]",
            docstring="A list of Calendar IDs of the required Calendar Events",
        ),
        types_utils.ValueSpec(
            name="data_scope",
            type="str",
            docstring="See [supervisor data scope](../../supervisor_contracts_api_reference4XX/"
            "hook_requirements/#data_scope)<br>  \n(**Supervisor Only**)",
        ),
        types_utils.ValueSpec(
            name="event_type",
            type="str",
            docstring="The defined [metadata event_type](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/metadata/#event_types) that the requirements will "
            'fetch, for example: `@requires(event_type="ACCRUE_INTEREST", ...)`\n(only applies '
            "to `scheduled_event_hook`)",
        ),
        types_utils.ValueSpec(
            name="flags",
            type="bool",
            docstring="Defaults to False",
        ),
        types_utils.ValueSpec(
            name="last_execution_datetime",
            type="List[str]",
            docstring="A list of [`event_types`](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/metadata/#event_types) to retrieve last execution "
            "datetimes for",
        ),
        types_utils.ValueSpec(
            name="parameters",
            type="bool",
            docstring="Defaults to False",
        ),
        types_utils.ValueSpec(
            name="postings",
            type="str",
            docstring="""
                A [Range Specifier](/reference/contracts/concepts_4xx/#requirements-range_specifiers)
                for example "1 day live"
            """,  # noqa: E501
        ),
        types_utils.ValueSpec(
            name="supervisee_hook_directives",
            type="str",
            docstring="""
                One of `none`, `all` or `invoked` that defaults to `none`
                <br>  \n(**Supervisor Only**)
            """,
        ),
    ],
)


def _fetch_account_data(
    *,
    balances: Optional[Union[list[str], dict[str, list[str]]]] = None,
    event_type: Optional[str] = None,
    
    postings: Optional[list[str]] = None,
):
    def wrapper(func):
        @wraps(func)
        def decorator(*args, **kwargs):
            return func(*args, **kwargs)

        return decorator

    return wrapper


fetch_account_data = types_utils.DecoratorSpec(
    name="fetch_account_data",
    object=_fetch_account_data,
    docstring="`@fetch_account_data(*, balances, event_type, parameters, postings)`\n\nSee full "
    "account fetcher requirements for [Smart Contracts](/reference/contracts/apis_4XX/"
    "smart_contracts_api_reference4XX/account_fetcher_requirements) and [Supervisors](/reference/"
    "contracts/apis_4XX/supervisor_contracts_api_reference4XX/account_fetcher_requirements)",
    smart_contract_args=[
        types_utils.ValueSpec(
            name="balances",
            type="List[str]",
            docstring="A list of [BalancesIntervalFetcher](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/types/#classes-BalancesIntervalFetcher) or "
            "[BalancesObservationFetcher](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/types/#classes-BalancesObservationFetcher) "
            "Fetcher IDs",
        ),
        types_utils.ValueSpec(
            name="postings",
            type="List[str]",
            docstring="A list of [PostingsIntervalFetcher](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/types/#classes-PostingsIntervalFetcher) Fetcher IDs",
        ),
    ],
    supervisor_args=[
        types_utils.ValueSpec(
            name="balances",
            type="Dict[str, List[str]]",
            docstring="A dictionary where the key is Supervisee [SmartContractDescriptor]"
            "(/reference/contracts/apis_4XX/supervisor_contracts_api_reference4XX/types/"
            "#classes-SmartContractDescriptor) alias and value is a list of "
            "[BalancesIntervalFetcher](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/types/#classes-BalancesIntervalFetcher) or "
            "[BalancesObservationFetcher](/reference/contracts/apis_4XX/"
            "smart_contracts_api_reference4XX/types/#classes-BalancesObservationFetcher) "
            "Fetcher IDs.<br>  \n*Note: Currently only available in `pre_posting_hook`*",
        ),
    ],
)


class IntervalFetcher:
    def __init__(
        self,
        *,
        fetcher_id: str = None,
        start: Union[RelativeDateTime, DefinedDateTime] = None,
        end: Optional[Union[RelativeDateTime, DefinedDateTime]] = DefinedDateTime.LIVE,
    ):
        self.fetcher_id = fetcher_id
        self.start = start
        self.end = end
        self._validate_attributes()

    def __repr__(self):
        return "IntervalFetcher"

    def _validate_attributes(self):
        if not self.fetcher_id:
            raise exceptions.InvalidSmartContractError(f"{self} 'fetcher_id' must be populated")

        types_utils.validate_type(
            self.start,
            (DefinedDateTime, RelativeDateTime),
            hint="Union[RelativeDateTime, DefinedDateTime]",
            prefix=f"{repr(self)}.start",
        )
        if (
            isinstance(self.start, RelativeDateTime)
            and self.start.origin != DefinedDateTime.EFFECTIVE_DATETIME
        ):
            raise exceptions.InvalidSmartContractError(
                f"{self} 'start' origin value must be set to 'DefinedDateTime.EFFECTIVE_DATETIME'"
            )

        if self.start == DefinedDateTime.LIVE:
            raise exceptions.InvalidSmartContractError(
                f"{self} 'start' cannot be set to 'DefinedDateTime.LIVE'"
            )

        if self.start == DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                f"{self} 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

        types_utils.validate_type(
            self.end,
            (DefinedDateTime, RelativeDateTime),
            hint="Union[RelativeDateTime, DefinedDateTime]",
            is_optional=True,
            prefix=f"{repr(self)}.end",
        )
        if self.end == DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                f"{self} 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="fetcher_id",
                type="str",
                docstring="""
                    The ID for this fetcher. This can be used in the
                    [@fetch_account_data decorator](#decorators)
                    to request the data window defined in this fetcher.
                """,
            ),
            types_utils.ValueSpec(
                name="start",
                type="Union[RelativeDateTime, DefinedDateTime]",
                docstring="""
                    The start time of the interval window. This can either be a
                    [RelativeDateTime](#classes-RelativeDateTime)
                    or a [DefinedDateTime](#enums-DefinedDateTime).
                    The values `DefinedDateTime.INTERVAL_START` and `DefinedDateTime.LIVE` are
                    **not** allowed. If the value is of type `RelativeDateTime`, its origin must
                    be set to `DefinedDateTime.EFFECTIVE_DATETIME`.
                """,
            ),
            types_utils.ValueSpec(
                name="end",
                type="Optional[Union[RelativeDateTime, DefinedDateTime]]",
                docstring="""
                    The end time of the interval window. Can either be defined relative to the
                    effective time or the interval start time, or as a time defined in Vault. By
                    default this will be open ended, returning unbounded results. Note:
                    care must be taken to ensure the `end` time is after the `start` time when the
                    contract code is executed; this is validated at execution time since it relies
                    on the hook `effective_time` and will result in an error during execution if
                    `start` is after `end`. The value `DefinedDateTime.INTERVAL_START` is **not**
                    allowed.
                """,
            ),
        ]


class BalancesIntervalFetcher(IntervalFetcher):
    def __init__(
        self,
        *,
        fetcher_id: str = None,
        start: Union[RelativeDateTime, DefinedDateTime] = None,
        end: Optional[Union[RelativeDateTime, DefinedDateTime]] = DefinedDateTime.LIVE,
        filter: Optional[BalancesFilter] = None,
    ):
        self.class_name = self.__class__.__name__
        self.filter = filter
        super().__init__(fetcher_id=fetcher_id, start=start, end=end)

    def __repr__(self):
        return "BalancesIntervalFetcher"

    def _validate_attributes(self):
        super()._validate_attributes()
        types_utils.validate_type(
            self.filter,
            BalancesFilter,
            is_optional=True,
            hint="BalancesFilter",
            prefix="BalancesIntervalFetcher.filter",
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        public_attributes = super()._public_attributes(language_code)
        public_attributes.append(
            types_utils.ValueSpec(
                name="filter",
                type="Optional[BalancesFilter]",
                docstring="An optional filter to refine the results returned by the fetcher.",
            ),
        )
        return public_attributes

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="BalancesIntervalFetcher",
            docstring="A fetcher definition for retrieving a balances interval.",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class BalancesObservationFetcher:
    def __init__(
        self,
        fetcher_id: str = None,
        at: Union[DefinedDateTime, RelativeDateTime] = None,
        filter: Optional[BalancesFilter] = None,
    ):
        self.fetcher_id = fetcher_id
        self.at = at
        self.filter = filter
        self._validate_attributes()

    def __repr__(self):
        return "BalancesObservationFetcher"

    def _validate_attributes(self):
        types_utils.validate_type(
            self.fetcher_id,
            str,
            check_empty=True,
            hint="str",
            prefix="BalancesObservationFetcher.fetcher_id",
        )

        if not self.at:
            raise exceptions.InvalidSmartContractError(
                "BalancesObservationFetcher 'at' must be populated"
            )

        types_utils.validate_type(
            self.at,
            (DefinedDateTime, RelativeDateTime),
            hint="Union[DefinedDateTime, RelativeDateTime]",
            prefix="BalancesObservationFetcher.at",
        )

        if self.at == DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                "BalancesObservationFetcher 'at' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

        types_utils.validate_type(
            self.filter,
            BalancesFilter,
            hint="BalancesFilter",
            is_optional=True,
            prefix="BalancesObservationFetcher.filter",
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="fetcher_id", type="str", docstring="The ID for this fetcher."
            ),
            types_utils.ValueSpec(
                name="at",
                type="Union[DefinedDateTime, RelativeDateTime]",
                docstring="""
                    The time at which the balances will be observed. The value
                    `DefinedDateTime.INTERVAL_START` is **not** allowed
                """,
            ),
            types_utils.ValueSpec(
                name="filter",
                type="Optional[BalancesFilter]",
                docstring="An optional filter to refine the results returned by the fetcher.",
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="BalancesObservationFetcher",
            docstring="A fetcher for observing balances at a given moment in time.",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class PostingsIntervalFetcher(IntervalFetcher):
    def __init__(
        self,
        *,
        fetcher_id: str = None,
        start: Union[RelativeDateTime, DefinedDateTime] = None,
        end: Optional[Union[RelativeDateTime, DefinedDateTime]] = DefinedDateTime.LIVE,
    ):
        self.class_name = self.__class__.__name__
        super().__init__(fetcher_id=fetcher_id, start=start, end=end)

    def __repr__(self):
        return "PostingsIntervalFetcher"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostingsIntervalFetcher",
            docstring="A fetcher for retrieving postings data within a given interval window.",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )



