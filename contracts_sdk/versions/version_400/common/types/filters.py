from functools import lru_cache

from .....utils import exceptions, symbols, types_utils
from typing import List


class BalancesFilter:
    def __init__(self, *, addresses: List[str] = None):
        self.addresses = addresses or []
        self._validate_attributes()

    def _validate_attributes(self):
        type_hint = "str"
        iterator = types_utils.get_iterator(
            self.addresses, type_hint, "addresses", check_empty=True
        )
        for address in iterator:
            types_utils.validate_type(address, str, hint=f"List[{type_hint}]")
        if len(self.addresses) < 1:
            raise exceptions.InvalidSmartContractError(
                "BalancesFilter addresses must contain at least one address."
            )
        if len(set(self.addresses)) != len(self.addresses):
            raise exceptions.InvalidSmartContractError(
                "BalancesFilter addresses must not contain any duplicate addresses."
            )

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



