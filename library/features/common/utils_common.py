# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
"""
Utils Module
Provides commonly used Contract API agnostic helper methods for use in smart contracts
"""

from decimal import (
    ROUND_HALF_UP,
    Decimal,
)


# yearly_to_daily_rate
VALID_DAYS_IN_YEAR = ["360", "365", "366", "actual"]
DEFAULT_DAYS_IN_YEAR = "actual"


# Value/type manipulation
def str_to_bool(string: str) -> bool:
    """
    Convert a string true to bool True, default value of False.
    :param string:
    :return:
    """
    return str(string).lower() == "true"


def yearly_to_monthly_rate(yearly_rate: Decimal) -> Decimal:
    return yearly_rate / 12


def round_decimal(
    amount: Decimal,
    decimal_places: int,
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -int(decimal_places))), rounding=rounding)


def remove_exponent(d: Decimal) -> Decimal:
    """
    Safely remove trailing zeros when dealing with exponents. This is useful when using a decimal
    value in a string used for informational purposes (e.g. instruction_details or logging).
    E.g: remove_exponent(Decimal("5E+3"))
    Returns: Decimal('5000')
    """
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


# Postings helper functions
def get_transaction_type(
    instruction_details: dict[str, str],
    txn_code_to_type_map: dict[str, str],
    default_txn_type: str,
) -> str:
    """
    Gets the transaction type from Posting instruction metadata.
    :param instruction_details: mapping containing instruction-level metadata for the Posting
    :param txn_code_to_type_map: map of transaction code to transaction type
    :param default_txn_type: transaction type to default to if code not found in the map
    :return: the transaction type of the Posting instruction
    """
    txn_code = instruction_details.get("transaction_code", "None")
    return txn_code_to_type_map.get(txn_code, default_txn_type)
