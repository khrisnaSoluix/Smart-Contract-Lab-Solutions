# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
Amortisation Module
"""

api = "3.9.0"
display_name = "Amortisation Module"
description = "Functions required for calculating amortisation methods within loan type products"

ROUNDING_TYPES = Union[
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_05UP,
]

EmiRecalculationCondition = NamedTuple(
    "EmiRecalculationCondition",
    [
        ("holiday_impact_preference", str),
        ("previous_due_amount_blocked", bool),
        ("overpayment_impact_preference", str),
        ("previous_overpayment_amount", Decimal),
        ("was_previous_interest_rate_fixed", bool),
        ("is_current_interest_rate_fixed", bool),
        ("previous_repayment_day_schedule_date", Optional[datetime]),
        ("last_rate_change_date", datetime),
    ],
)

DecliningPrincipalCalculationInput = NamedTuple(
    "DecliningPrincipalCalculationInput",
    [
        ("precision", int),
        ("actual_principal", Decimal),
        ("principal_with_capitalised_interest", Decimal),
        ("remaining_term", Decimal),
        ("monthly_interest_rate", Decimal),
        ("emi", Decimal),
        ("current_overpayment_amount", Decimal),
        ("is_last_payment_date", bool),
        ("principal_excess", Decimal),
        ("interest_accrued", Decimal),
        ("accrued_interest_excluding_overpayment", Decimal),
        ("accrued_additional_interest", Decimal),
        ("emi_recalculation_condition", EmiRecalculationCondition),
        ("lump_sum_amount", Decimal),
        ("predefined_emi", bool),
    ],
)

InterestOnlyAmortisationInput = NamedTuple(
    "InterestOnlyAmortisationInput",
    [
        ("remaining_principal", Decimal),
        ("accrued_interest", Decimal),
        ("accrued_interest_excluding_overpayment", Decimal),
        ("precision", int),
        ("is_last_repayment_date", bool),
    ],
)

FlatInterestAmortisationInput = NamedTuple(
    "FlatInterestAmortisationInput",
    [
        ("remaining_principal", Decimal),
        ("original_principal", Decimal),
        ("annual_interest_rate", Decimal),
        ("precision", int),
        ("total_term", int),
        ("remaining_term", int),
        ("use_rule_of_78", bool),
    ],
)


def construct_flat_interest_amortisation_input(
    remaining_principal: Decimal,
    original_principal: Decimal,
    annual_interest_rate: Decimal,
    precision: int,
    total_term: int,
    remaining_term: int,
    use_rule_of_78: bool,
) -> FlatInterestAmortisationInput:
    return FlatInterestAmortisationInput(
        remaining_principal=remaining_principal,
        original_principal=original_principal,
        annual_interest_rate=annual_interest_rate,
        precision=precision,
        total_term=total_term,
        remaining_term=remaining_term,
        use_rule_of_78=use_rule_of_78,
    )


def construct_emi_recalculation_condition_input(
    holiday_impact_preference: str,
    overpayment_impact_preference: str,
    previous_due_amount_blocked: bool,
    previous_overpayment_amount: Decimal,
    was_previous_interest_rate_fixed: bool,
    is_current_interest_rate_fixed: bool,
    previous_repayment_day_schedule_date: Optional[datetime],
    last_rate_change_date: datetime,
) -> EmiRecalculationCondition:
    """
    Construction of NamedTuple required to determine if the Estimated Monthly Installment (EMI)
    needs to be recalculated for a declining principal amortised loan type product.

    :param holiday_impact_preference: how to handle a repayment holiday,
        either increase the emi or the term.
    :param overpayment_impact_preference: how to handle an overpayment,
        either reduce the emi or the term.
    :param previous_due_amount_blocked: if True, previous repayment was blocked (repayment holiday).
    :param previous_overpayment_amount: total amount that has been overpaid at the last repayment
        schedule date. Used to determine if a new overpayment has occured.
    :param was_previous_interest_rate_fixed: declares if the interest rate was fixed at the
        last repayment schedule date. Used to determine if a change of rate has occured.
    :param is_current_interest_rate_fixed: declares if the current interest rate is fixed.
    :param previous_repayment_day_schedule_date: the last REPAYMENT_DAY_SCHEDULE event date.
    :param last_rate_change_date: the last datetime that the interest rate was changed.
    :return: EmiRecalculationCondition NamedTuple
    """
    return EmiRecalculationCondition(
        holiday_impact_preference=holiday_impact_preference,
        overpayment_impact_preference=overpayment_impact_preference,
        previous_due_amount_blocked=previous_due_amount_blocked,
        previous_overpayment_amount=previous_overpayment_amount,
        was_previous_interest_rate_fixed=was_previous_interest_rate_fixed,
        is_current_interest_rate_fixed=is_current_interest_rate_fixed,
        previous_repayment_day_schedule_date=previous_repayment_day_schedule_date,
        last_rate_change_date=last_rate_change_date,
    )


def construct_declining_principal_amortisation_input(
    precision: int,
    actual_principal: Decimal,
    principal_with_capitalised_interest: Decimal,
    remaining_term: Decimal,
    monthly_interest_rate: Decimal,
    emi: Decimal,
    current_overpayment_amount: Decimal,
    is_last_payment_date: bool,
    principal_excess: Decimal,
    interest_accrued: Decimal,
    accrued_interest_excluding_overpayment: Decimal,
    accrued_additional_interest: Decimal,
    emi_recalculation_condition: EmiRecalculationCondition,
    lump_sum_amount: Optional[Decimal] = None,
    predefined_emi: bool = False,
) -> DecliningPrincipalCalculationInput:
    """
    Construction of NamedTuple for input into a declining principal amortised loan type product

    :param precision: number of decimal places to round to.
    :param actual_principal: total remaining principal (including overpayments).
    :param principal_with_capitalised_interest: total remaining principal including any
        capitalised interest (excluding overpayments).
    :param remaining_term: remaining term of the loan in months.
    :param monthly_interest_rate: monthly interest rate.
    :param emi: equated monthly installment amount.
    :param current_overpayment_amount: total amount that has been overpaid
    :param is_last_payment_date: if True, the effective date is the last due repayment.
    :param principal_excess: tracks the additional principal being paid off. (If an overpayment
        occurs, the principal reduces resulting in a reduced interest and therefore a higher
        proportion of the principal is paid off).
    :param interest_accrued: amount of actual interest accrued for this current repayment cycle.
    :param accrued_interest_excluding_overpayment: the expected interest accrual for the current
        repayment cycle (excluding principal reduction due to overpayments).
    :param accrued_additional_interest: any additional interest due to the account opening. As the
        repayment date must be at least 1 month after the account opening date, there can be a
        longer period before the first repayment date and therefore additional interest has been
        accrued (compared to the expected interest for first repayment cycle).
    :param emi_recalculation_condition: NamedTuple used to determine if emi needs to be
        recalculated in declining principal amortisation method.
    :param lump_sum_amount: an optional one-off repayment amount agreed to be paid at the
                            end of the term.
    :param predefined_emi: bool used to define whether EMI has been previously agreed. Default False

    :return: DecliningPrincipalCalculationInput NamedTuple
    """
    return DecliningPrincipalCalculationInput(
        precision=precision,
        actual_principal=actual_principal,
        principal_with_capitalised_interest=principal_with_capitalised_interest,
        remaining_term=remaining_term,
        monthly_interest_rate=monthly_interest_rate,
        emi=emi,
        current_overpayment_amount=current_overpayment_amount,
        is_last_payment_date=is_last_payment_date,
        principal_excess=principal_excess,
        interest_accrued=interest_accrued,
        accrued_interest_excluding_overpayment=accrued_interest_excluding_overpayment,
        accrued_additional_interest=accrued_additional_interest,
        emi_recalculation_condition=emi_recalculation_condition,
        lump_sum_amount=lump_sum_amount,
        predefined_emi=predefined_emi,
    )


def construct_interest_only_amortisation_input(
    remaining_principal: Decimal,
    accrued_interest: Decimal,
    accrued_interest_excluding_overpayment: Decimal,
    precision: int,
    is_last_repayment_date: bool,
) -> InterestOnlyAmortisationInput:
    """
    :param remaining_principal: total remaining principal (including overpayments).
    :param accrued_interest: amount of actual interest accrued for this current repayment cycle.
    :param accrued_interest_excluding_overpayment: the expected interest accrual for the current
        repayment cycle (excluding principal reduction due to overpayments).
    :param precision: number of decimal places to round to.
    :param is_last_payment_date: if True, the effective date is the last due repayment.

    """
    return InterestOnlyAmortisationInput(
        remaining_principal=remaining_principal,
        accrued_interest=accrued_interest,
        accrued_interest_excluding_overpayment=accrued_interest_excluding_overpayment,
        precision=precision,
        is_last_repayment_date=is_last_repayment_date,
    )


def calculate_declining_principal_repayment(
    amortisation_input: DecliningPrincipalCalculationInput,
) -> Dict[str, Decimal]:
    remaining_principal = _get_remaining_principal(
        amortisation_input.actual_principal,
        amortisation_input.principal_with_capitalised_interest,
        amortisation_input.emi_recalculation_condition.overpayment_impact_preference,
        amortisation_input.current_overpayment_amount,
    )
    emi = amortisation_input.emi
    principal_excess = amortisation_input.principal_excess
    predefined_emi = amortisation_input.predefined_emi
    accrued_interest_excl_overpayment = amortisation_input.accrued_interest_excluding_overpayment
    interest_due = _round_decimal(amortisation_input.interest_accrued, amortisation_input.precision)
    # In this case, this is where we have exceeded our term for the loan
    # but there is still principal that has not been repayed
    # as a placeholder, emi = principal_due
    if amortisation_input.remaining_term <= 0:
        principal_due = amortisation_input.actual_principal
        emi = principal_due

    elif amortisation_input.monthly_interest_rate == 0:
        principal_due = _round_decimal(
            amortisation_input.actual_principal / amortisation_input.remaining_term,
            amortisation_input.precision,
        )
        emi = principal_due
    else:
        if _does_emi_need_recalculation(
            amortisation_input.emi_recalculation_condition,
            amortisation_input.emi,
            amortisation_input.current_overpayment_amount,
            amortisation_input.predefined_emi,
        ):
            emi = _calculate_declining_principal_emi(
                amortisation_input.precision,
                remaining_principal,
                amortisation_input.monthly_interest_rate,
                amortisation_input.remaining_term,
                amortisation_input.lump_sum_amount,
            )

        additional_interest = _round_decimal(
            amortisation_input.accrued_additional_interest,
            amortisation_input.precision,
        )
        expected_interest = _round_decimal(
            amortisation_input.accrued_interest_excluding_overpayment,
            amortisation_input.precision,
        )

        if predefined_emi and emi < interest_due:
            interest_due = emi
            accrued_interest_excl_overpayment = emi

            # If the repayments being made do not cover the full accrued interest amount, then
            # principal due amounts must be explicitly zeroed to prevent unwanted penalties.
            principal_due = Decimal("0.00")
            principal_excess = Decimal("0.00")
        else:
            # if there is more than a month between repayment dates (e.g. date change resulting in a
            # gap of 1 month 5 days between events) then the principal due for the month needs to
            # deduct the interest accrued over those additional days to ensure the interest is
            # covered first by the emi. (In the case of no gap, the principal is: emi - interest
            # as expected)
            principal_due = emi - (expected_interest - additional_interest)

            # if an overpayment has occurred, the principal amount has reduced and therefore the
            # actual interest accrued on that is less than expected. A larger amount of the emi
            # will be distributed to the principal. Principal excess tracks this additional sum.
            principal_excess = expected_interest - interest_due

        if (
            amortisation_input.is_last_payment_date
            or principal_due > amortisation_input.actual_principal
        ):
            principal_due = amortisation_input.actual_principal
            principal_excess = Decimal("0.00")

    return {
        "emi": emi,
        "interest_due": interest_due,
        "accrued_interest": amortisation_input.interest_accrued,
        "accrued_interest_excluding_overpayment": accrued_interest_excl_overpayment,
        "principal_due_excluding_overpayment": principal_due,
        "principal_excess": principal_excess,
    }


def _does_emi_need_recalculation(
    emi_calc_input: EmiRecalculationCondition,
    emi: Decimal,
    current_overpayment_amount: Decimal,
    predefined_emi: bool,
) -> bool:

    return not predefined_emi and (
        emi == 0
        or (
            emi_calc_input.is_current_interest_rate_fixed is False
            and emi_calc_input.previous_repayment_day_schedule_date is not None
            and _has_rate_changed_since_last_repayment_date(
                emi_calc_input.was_previous_interest_rate_fixed,
                emi_calc_input.is_current_interest_rate_fixed,
                emi_calc_input.previous_repayment_day_schedule_date,
                emi_calc_input.last_rate_change_date,
            )
        )
        or (
            emi_calc_input.previous_due_amount_blocked
            and emi_calc_input.holiday_impact_preference.upper() == "INCREASE_EMI"
        )
        or (
            emi_calc_input.overpayment_impact_preference.upper() == "REDUCE_EMI"
            and _does_account_have_new_overpayment(
                emi_calc_input.previous_overpayment_amount,
                current_overpayment_amount,
            )
        )
    )


def _does_account_have_new_overpayment(
    previous_overpayment_amount: Decimal,
    current_overpayment_amount: Decimal,
) -> bool:

    return current_overpayment_amount != previous_overpayment_amount


def _calculate_declining_principal_emi(
    precision: int,
    remaining_principal: Decimal,
    monthly_interest_rate: Decimal,
    remaining_term: int,
    lump_sum_amount: Optional[Decimal],
) -> Decimal:
    """
    EMI = (P-(L/(1+R)^(N)))*R*(((1+R)^N)/((1+R)^N-1))

    P is principal remaining
    R is the monthly interest rate
    N is term remaining
    L is the lump sum

    Formula can be used for a standard declining principal loan or a
    minimum repayment loan which includes a lump_sum_amount to be paid at the
    end of the term that is > 0
    """

    lump_sum_amount = lump_sum_amount or Decimal("0")
    return _round_decimal(
        (remaining_principal - (lump_sum_amount / (1 + monthly_interest_rate) ** (remaining_term)))
        * monthly_interest_rate
        * ((1 + monthly_interest_rate) ** remaining_term)
        / ((1 + monthly_interest_rate) ** remaining_term - 1),
        precision,
    )


def _get_remaining_principal(
    actual_principal: Decimal,
    principal_with_capitalised_interest: Decimal,
    overpayment_impact_preference: str,
    current_overpayment_amount: Decimal,
) -> Decimal:

    return (
        actual_principal
        if (
            overpayment_impact_preference.upper() == "REDUCE_EMI"
            and current_overpayment_amount != 0
        )
        # if there has been a repayment holiday with INCREASE_TERM,
        # the EMI recalculation will not be triggered
        else principal_with_capitalised_interest
    )


def _has_rate_changed_since_last_repayment_date(
    was_previous_interest_rate_fixed: bool,
    is_current_interest_rate_fixed: bool,
    previous_repayment_day_schedule_date: datetime,
    last_rate_change_date: datetime,
) -> bool:
    return (
        last_rate_change_date > previous_repayment_day_schedule_date
        or was_previous_interest_rate_fixed != is_current_interest_rate_fixed
    )


def calculate_interest_only_repayment(
    amortisation_input: InterestOnlyAmortisationInput,
) -> Dict[str, Decimal]:

    principal_due = _round_decimal(
        amortisation_input.remaining_principal
        if amortisation_input.is_last_repayment_date
        else Decimal("0"),
        amortisation_input.precision,
    )

    interest_due = _round_decimal(
        amortisation_input.accrued_interest,
        amortisation_input.precision,
    )

    return {
        # emi is not applicable for interest only amortisation, defaults to 0
        "emi": Decimal("0"),
        "interest_due": interest_due,
        "accrued_interest": amortisation_input.accrued_interest,
        "accrued_interest_excluding_overpayment": (
            amortisation_input.accrued_interest_excluding_overpayment
        ),
        "principal_due_excluding_overpayment": principal_due,
        "principal_excess": Decimal("0"),
    }


def calculate_flat_interest_repayment(
    flat_interest_amortisation_input: FlatInterestAmortisationInput,
) -> Dict[str, Decimal]:

    total_interest = _get_total_loan_interest(
        flat_interest_amortisation_input.original_principal,
        flat_interest_amortisation_input.annual_interest_rate,
        flat_interest_amortisation_input.total_term,
        flat_interest_amortisation_input.precision,
    )

    emi = _get_flat_interest_amortised_loan_emi(
        flat_interest_amortisation_input.original_principal,
        flat_interest_amortisation_input.total_term,
        total_interest,
        flat_interest_amortisation_input.precision,
    )

    if flat_interest_amortisation_input.use_rule_of_78:
        remaining_term = flat_interest_amortisation_input.remaining_term

        sum_to_N = _get_sum_to_total_term(flat_interest_amortisation_input.total_term)

        interest_due = _round_decimal(
            total_interest * remaining_term / sum_to_N,
            flat_interest_amortisation_input.precision,
        )
    else:
        interest_due = _round_decimal(
            total_interest / flat_interest_amortisation_input.total_term,
            flat_interest_amortisation_input.precision,
        )

    principal_due = min(emi - interest_due, flat_interest_amortisation_input.remaining_principal)

    return {
        "emi": emi,
        "interest_due": interest_due,
        "accrued_interest": interest_due,
        "accrued_interest_excluding_overpayment": interest_due,
        "principal_due_excluding_overpayment": principal_due,
        "principal_excess": Decimal("0"),
    }


def _get_total_loan_interest(
    original_principal: Decimal,
    annual_interest_rate: Decimal,
    total_term: int,
    precision: int,
) -> Decimal:
    """
    Return the total loan interest for a flat interest or
    rule of 78 amortised loan
    """
    return _round_decimal(
        original_principal * annual_interest_rate * Decimal(total_term) / Decimal("12"),
        precision,
    )


def _get_flat_interest_amortised_loan_emi(
    original_principal: Decimal,
    total_term: int,
    total_interest: Decimal,
    precision: int,
) -> Decimal:
    return _round_decimal((original_principal + total_interest) / total_term, precision)


def _get_sum_to_total_term(term: int) -> Decimal:
    """
    Return the sum to N where N is the total loan term
    this is used for rule of 78 interest distribution only
    """
    return Decimal(term * (term + 1) / 2)


def _round_decimal(
    amount: Decimal,
    decimal_places: int,
    rounding: ROUNDING_TYPES = ROUND_HALF_UP,
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -decimal_places)), rounding=rounding)
