# standard libs
from collections import namedtuple
from datetime import datetime
from decimal import Decimal
from typing import DefaultDict

# contracts api
from contracts_api import DEFAULT_ADDRESS, DEFAULT_ASSET

# inception sdk
from inception_sdk.test_framework.common.constants import (
    DEFAULT_DENOMINATION,
    DEFAULT_POSTING_PHASE,
)

# This is for sim and e2e tests only
BalanceDimensions = namedtuple(
    "BalanceDimensions",
    ["address", "asset", "denomination", "phase"],
    defaults=[DEFAULT_ADDRESS, DEFAULT_ASSET, DEFAULT_DENOMINATION, DEFAULT_POSTING_PHASE],
)


class Balance(object):
    net = Decimal("0")
    credit = Decimal("0")
    debit = Decimal("0")
    value_timestamp = None

    def __init__(
        self,
        credit: Decimal = Decimal("0"),
        debit: Decimal = Decimal("0"),
        net: Decimal = Decimal("0"),
        value_timestamp: datetime | None = None,
    ):
        self.credit = Decimal(credit)
        self.debit = Decimal(debit)
        self.net = Decimal(net)
        self.value_timestamp = value_timestamp

    def __repr__(self):
        return f"{self.net}"

    def __str__(self):
        return f"{self.net}"

    def __eq__(self, other):
        return (
            isinstance(other, Balance)
            and self.net == other.net
            and self.credit == other.credit
            and self.debit == other.debit
        )


def compare_balances(
    expected_balances: list[tuple[BalanceDimensions, str]],
    actual_balances: DefaultDict[BalanceDimensions, Balance],
) -> dict[BalanceDimensions, dict[str, Decimal]]:
    """
    Compare two sets of balances, returning a dictionary with dimensions for which the two did not
    match as keys, and a dictionary containing the expected and actual balances for those
    dimensions as the values. For example:
    {
        BalanceDimensions('DEFAULT', 'COMMERCIAL_BANK_MONEY', 'GBP', 'POSTING_PHASE_COMMITTED'):{
            'expected': Decimal('10'),
            'actual': Decimal('5')
        }
    }

    Able to compare credits and debits of a balance if compare_debits_and_credits is True
    - Note that to be able to do this the expected balances must be
    dict[BalanceDimensions, ExpectedBalanceComparison]
    """
    return {
        dimensions: {
            "expected": Decimal(net),
            "actual": actual_balances[dimensions].net,
        }
        for dimensions, net in expected_balances
        if Decimal(net) != actual_balances[dimensions].net
    }
