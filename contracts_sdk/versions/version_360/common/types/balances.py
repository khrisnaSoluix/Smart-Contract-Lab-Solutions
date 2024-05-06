from copy import deepcopy
from functools import lru_cache

from .....utils import symbols
from ....version_350.common import types as types350


class Balance(types350.Balance):
    def __add__(self, other):
        return self.__class__(
            credit=self.credit + other.credit,
            debit=self.debit + other.debit,
            net=self.net + other.net,
        )

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        self.credit += other.credit
        self.debit += other.debit
        self.net += other.net
        return self

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)
        super_spec.docstring += """
            Balance objects support addition operations from version 3.6+.
        """

        return super_spec


class BalanceDefaultDict(types350.BalanceDefaultDict):
    _balance = Balance

    def __add__(self, other):
        aggregated_balance_dict = deepcopy(self)
        for balance_key, balance in other.items():
            if balance_key in aggregated_balance_dict:
                aggregated_balance_dict[balance_key] = (
                    aggregated_balance_dict[balance_key] + balance
                )
            else:
                aggregated_balance_dict[balance_key] = balance

        return aggregated_balance_dict

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        for balance_key, balance in other.items():
            self[balance_key] = self.get(balance_key, self._balance()) + balance
        return self

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)

        super_spec.docstring += """
                BalanceDefaultDict objects support addition operations from 3.6+.
        """

        return super_spec


class BalanceTimeseries(types350.BalanceTimeseries):
    return_on_empty = lambda *_: BalanceDefaultDict(
        lambda *_: Balance(_from_proto=True), _from_proto=True
    )
