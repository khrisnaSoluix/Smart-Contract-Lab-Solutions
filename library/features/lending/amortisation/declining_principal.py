from decimal import Decimal
from typing import Optional

# inception library
import library.features.common.utils as utils


def calculate_emi(
    remaining_principal: Decimal,
    interest_rate: Decimal,
    remaining_term: int,
    fulfillment_precision: int = 2,
    lump_sum_amount: Optional[Decimal] = None,
) -> Decimal:
    """
    EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))

    P is principal remaining
    R is the interest rate, can be adjusted to whichever unit
    N is term remaining
    L is the lump sum

    Formula can be used for a standard declining principal loan or a
    minimum repayment loan which includes a lump_sum_amount to be paid at the
    end of the term that is > 0

    when the lump sum amount L is 0, the formula is reduced to

    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    """

    lump_sum_amount = lump_sum_amount or Decimal("0")

    return utils.round_decimal(
        (remaining_principal - (lump_sum_amount / (1 + interest_rate) ** (remaining_term)))
        * interest_rate
        * ((1 + interest_rate) ** remaining_term)
        / ((1 + interest_rate) ** remaining_term - 1),
        fulfillment_precision,
    )
