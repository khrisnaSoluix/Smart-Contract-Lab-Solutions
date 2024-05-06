from functools import lru_cache

from .enums import DefinedDateTime
from .time_operations import RelativeDateTime
from .....utils import exceptions, symbols, types_utils


class IntervalFetcher:
    def __init__(self, *, fetcher_id=None, start=None, end=DefinedDateTime.LIVE):
        self._spec().assert_constructor_args(
            self._registry,
            {
                "fetcher_id": fetcher_id,
                "start": start,
                "end": end,
            },
        )
        class_name = self.__class__.__name__
        if fetcher_id == "":
            raise exceptions.InvalidSmartContractError(f"{class_name} 'fetcher_id' cannot be empty")

        if isinstance(start, RelativeDateTime) and start.origin != DefinedDateTime.EFFECTIVE_TIME:
            raise exceptions.InvalidSmartContractError(
                f"{class_name} 'start' origin value must be set to "
                "'DefinedDateTime.EFFECTIVE_TIME'"
            )

        if start == DefinedDateTime.LIVE:
            raise exceptions.InvalidSmartContractError(
                f"{class_name} 'start' cannot be set to 'DefinedDateTime.LIVE'"
            )

        if start == DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                f"{class_name} 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

        if end == DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                f"{class_name} 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

        self.fetcher_id = fetcher_id
        self.start = start
        self.end = end

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
                    [@fetch_account_data decorator](../../smart_contracts_api_reference3XX/account_fetcher_requirements/)
                    to request the data window defined in this fetcher.
                """,  # noqa: E501
            ),
            types_utils.ValueSpec(
                name="start",
                type="Union[RelativeDateTime, DefinedDateTime]",
                docstring="""
                    The start time of the interval window. This can either be a
                    [RelativeDateTime](../types/#classes-RelativeDateTime)
                    or a [DefinedDateTime](../types/#enums-DefinedDateTime).
                    The values `DefinedDateTime.INTERVAL_START` and `DefinedDateTime.LIVE` are
                    **not** allowed. If the value is of type `RelativeDateTime`, its origin must be
                    set to `DefinedDateTime.EFFECTIVE_TIME`.
                """,  # noqa: E501
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
    def __init__(self, *, fetcher_id=None, start=None, end=DefinedDateTime.LIVE, filter=None):
        self.class_name = self.__class__.__name__
        super().__init__(fetcher_id=fetcher_id, start=start, end=end)
        self._spec().assert_constructor_args(
            self._registry,
            {
                "filter": filter,
            },
        )

        self.filter = filter

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
    def __init__(self, fetcher_id=None, at=None, filter=None):
        self._spec().assert_constructor_args(
            self._registry,
            {
                "fetcher_id": fetcher_id,
                "at": at,
                "filter": filter,
            },
        )

        if fetcher_id == "":
            raise exceptions.InvalidSmartContractError(
                "BalancesObservationFetcher 'fetcher_id' cannot be empty"
            )

        if at == symbols.DefinedDateTime.INTERVAL_START:
            raise exceptions.InvalidSmartContractError(
                "BalancesObservationFetcher 'at' cannot be set to 'DefinedDateTime.INTERVAL_START'"
            )

        self.fetcher_id = fetcher_id
        self.at = at
        self.filter = filter

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
    def __init__(self, *, fetcher_id=None, start=None, end=DefinedDateTime.LIVE):
        self.class_name = self.__class__.__name__
        super().__init__(fetcher_id=fetcher_id, start=start, end=end)

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
