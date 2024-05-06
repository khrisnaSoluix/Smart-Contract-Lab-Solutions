from functools import lru_cache

from .....utils import symbols, types_utils


class BalancesObservation:
    def __init__(self, *, balances, value_datetime=None, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "value_datetime": value_datetime,
                    "balances": balances,
                },
            )

        self.value_datetime = value_datetime
        self.balances = balances

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="BalancesObservation",
            docstring="""
                A snapshot of an Account's balances at a given time. A balances `observation` gives
                a single data point in the timeseries of an Account's balances, allowing for more
                specific data fetching when only a single data point is needed.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="", args=cls._public_attributes(language_code)
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="value_datetime",
                type="Optional[datetime]",
                docstring="""
                    The time at which the balances are observed. This attribute will be None for
                    a live balances observation.
                """,
            ),
            types_utils.ValueSpec(
                name="balances",
                type="BalanceDefaultDict",
                docstring="The balances at the given timestamp.",
            ),
        ]
