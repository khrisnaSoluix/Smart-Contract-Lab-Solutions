# standard libs
from decimal import Decimal


def is_credit(amount: Decimal) -> bool:
    return amount < Decimal("0")


def is_debit(amount: Decimal) -> bool:
    return amount > Decimal("0")
