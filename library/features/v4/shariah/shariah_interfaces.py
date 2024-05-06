# standard libs
from decimal import Decimal
from typing import Callable, NamedTuple

ProfitAccrual = NamedTuple(
    "ProfitAccrual",
    [
        (
            "get_accrual_amount",
            Callable[
                # [Decimal, datetime, dict[str, str], str, int=5],
                ...,
                tuple[Decimal, str],
            ],
        ),
    ],
)
