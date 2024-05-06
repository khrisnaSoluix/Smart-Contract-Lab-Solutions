from functools import lru_cache

from .....utils import exceptions, symbols, types_utils


class BalancesFilter:
    def __init__(self, *, addresses=None, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "addresses": addresses,
                },
            )
        if len(addresses) < 1:
            raise exceptions.InvalidSmartContractError(
                "BalancesFilter addresses must contain at least one address."
            )

        if len(set(addresses)) != len(addresses):
            raise exceptions.InvalidSmartContractError(
                "BalancesFilter addresses must not contain any duplicate addresses."
            )

        self.addresses = addresses

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="BalancesFilter",
            docstring="A filter for refining the balances data retrieved by a fetcher.",
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
                name="addresses", type="List[str]", docstring="A list of balance addresses."
            ),
        ]
