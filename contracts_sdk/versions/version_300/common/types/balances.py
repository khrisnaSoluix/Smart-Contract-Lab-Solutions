from functools import lru_cache
from decimal import Decimal

from .....utils import symbols
from .....utils import types_utils


class Balance:
    def __init__(self, credit=Decimal(0), debit=Decimal(0), net=Decimal(0), _from_proto=False):
        super().__setattr__("_from_proto", _from_proto)
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {"credit": credit, "debit": debit, "net": net}
            )
        self.credit = credit
        self.debit = debit
        self.net = net

    def _adjust(self, tside, credit=None, debit=None):
        if credit:
            self.credit += credit
        if debit:
            self.debit += debit
        self.net = (self.credit - self.debit) * symbols.TSIDE_NET_BALANCE_MAP[tside]

    def __setattr__(self, name, value):
        if not self._from_proto:
            self._spec().assert_attribute_value(self._registry, name, value)
        super().__setattr__(name, value)

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self.credit == other.credit
            and self.debit == other.debit
            and self.net == other.net
        )

    def __str__(self):
        return "Balance(credit=%s, debit=%s, net=%s)" % (self.credit, self.debit, self.net)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Balance",
            docstring=(
                "The credit, debit, and net balances (credit - debit) for a given balance phase."
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="credit", type="Decimal", docstring="The total credit balance"
            ),
            types_utils.ValueSpec(
                name="debit", type="Decimal", docstring="The total debit balance"
            ),
            types_utils.ValueSpec(
                name="net",
                type="Decimal",
                docstring="""
                    The total net balance.
                    If the contract specifies Tside.LIABILITY, this will equal (credit - debit).
                    If the contract specifies Tside.ASSET, this will equal (debit - credit).
                """,
            ),
        ]


BALANCE_ITEM_TYPE = "Dict[Tuple[str, str, str, Phase], Balance]"


class BalanceDefaultDict(types_utils.TypedDefaultDict(BALANCE_ITEM_TYPE)):
    _balance = Balance

    def __init__(self, default_factory=None, mapping=None, _from_proto=False):
        balance_dict_default_factory = lambda *_: self._balance(_from_proto=True)
        if default_factory is not None:
            balance_dict_default_factory = default_factory
        super(BalanceDefaultDict, self).__init__(
            default_factory=balance_dict_default_factory, mapping=mapping, _from_proto=_from_proto
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="BalanceDefaultDict",
            docstring="""
                The key is (account_address, asset, denomination, phase) and the value is a
                Balance object which contains the debit, credit and net balance changes.
                Returns defaultdict object, type - `Dict[Tuple[str, str, str, Phase], Balance]`.
                If non-existing key is accessed, value with zero debit, credit and net balance
                changes returned.
            """,
        )


class BalanceTimeseries(types_utils.Timeseries(BALANCE_ITEM_TYPE, "Balance dictionary")):
    return_on_empty = lambda *_: BalanceDefaultDict(
        lambda *_: Balance(_from_proto=True), _from_proto=True
    )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.merge_class_specs(
            derived_spec=types_utils.ClassSpec(
                name="BalanceTimeseries",
                docstring="""
                    The time series of historic balances for the Account.

                    The 'at', 'before', and 'latest' methods (and the second field of each tuple
                    returned via 'all') return a dictionary, where the key is a 4-tuple containing:
                    (account_address, asset, denomination, phase), and the value is a Balance
                    object.

                    To find the "total" balance for the Account, or a given address inside the
                    Account, the dictionary at the relevant timestamp will need to be fetched,
                    filtered by applying the appropriate criteria when matching the key, and have
                    Balance objects summed.
                """,
            ),
            base_spec=super()._spec(language_code),
        )
