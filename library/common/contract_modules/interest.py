# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
Interest Accrual Module
"""

api = "3.9.0"
display_name = "Interest Module"
description = "Functions required for accruing and applying interest and fees "
"within smart contracts"


ROUNDING_TYPES = Union[
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_05UP,
]

PostingInfo = NamedTuple(
    "PostingInfo",
    [
        ("tier_name", str),
        ("amount", Decimal),
        ("description", str),
    ],
)

PayableReceivableMapping = NamedTuple(
    "PayableReceivableMapping",
    [
        ("payable_address", str),
        ("receivable_address", str),
        ("payable_internal_account", str),
        ("paid_internal_account", str),
        ("receivable_internal_account", str),
        ("received_internal_account", str),
    ],
)

CHARGE_TYPES = Union["INTEREST", "FEES"]

AccrualDetails = NamedTuple(
    "AccrualDetails",
    [
        ("payable_receivable_mapping", PayableReceivableMapping),
        ("denomination", str),
        ("balance", Decimal),
        ("rates", dict[str, dict[str, str]]),
        ("instruction_description", str),
        ("base", str),
        ("precision", int),
        ("rounding_mode", ROUNDING_TYPES),
        ("accrual_is_capitalised", bool),
        ("net_postings", bool),
    ],
)

FeeDetails = NamedTuple(
    "FeeDetails",
    [
        ("payable_receivable_mapping", PayableReceivableMapping),
        ("denomination", str),
        ("fee", dict[str, Decimal]),
        ("instruction_description", str),
    ],
)

ChargeApplicationDetails = NamedTuple(
    "ChargeApplicationDetails",
    [
        ("payable_receivable_mapping", PayableReceivableMapping),
        ("denomination", str),
        ("instruction_description", str),
        ("zero_out_description", str),
        ("precision", int),
        ("rounding_mode", ROUNDING_TYPES),
        ("zero_out_remainder", bool),
        ("apply_address", str),
        ("charge_type", CHARGE_TYPES),
    ],
)


def construct_payable_receivable_mapping(
    payable_address: str = "",
    receivable_address: str = "",
    payable_internal_account: str = "",
    paid_internal_account: str = "",
    receivable_internal_account: str = "",
    received_internal_account: str = "",
) -> PayableReceivableMapping:
    return PayableReceivableMapping(
        payable_address=payable_address,
        receivable_address=receivable_address,
        payable_internal_account=payable_internal_account,
        paid_internal_account=paid_internal_account,
        receivable_internal_account=receivable_internal_account,
        received_internal_account=received_internal_account,
    )


def construct_accrual_details(
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    balance: Decimal,
    rates: dict[str, dict[str, str]],
    base: str = "actual",
    precision: int = 5,
    rounding_mode: ROUNDING_TYPES = ROUND_HALF_UP,
    accrual_is_capitalised: bool = False,
    net_postings: bool = True,
    instruction_description: str = None,
) -> AccrualDetails:
    return AccrualDetails(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        balance=balance,
        rates=rates,
        instruction_description=instruction_description,
        base=base,
        precision=precision,
        rounding_mode=rounding_mode,
        accrual_is_capitalised=accrual_is_capitalised,
        net_postings=net_postings,
    )


def construct_fee_details(
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    fee: dict[str, Decimal],
    instruction_description: str = None,
) -> FeeDetails:
    return FeeDetails(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        fee=fee,
        instruction_description=instruction_description,
    )


def construct_charge_application_details(
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    precision: int = 2,
    rounding_mode: ROUNDING_TYPES = ROUND_HALF_UP,
    zero_out_remainder: bool = False,
    apply_address: str = DEFAULT_ADDRESS,
    instruction_description: str = None,
    zero_out_description: str = None,
    charge_type: CHARGE_TYPES = "INTEREST",
) -> ChargeApplicationDetails:
    return ChargeApplicationDetails(
        payable_receivable_mapping=payable_receivable_mapping,
        denomination=denomination,
        instruction_description=instruction_description,
        zero_out_description=zero_out_description,
        precision=precision,
        rounding_mode=rounding_mode,
        zero_out_remainder=zero_out_remainder,
        apply_address=apply_address,
        charge_type=charge_type,
    )


def accrue_interest(
    vault,
    accrual_details: list[AccrualDetails],
    account_tside: str,
    effective_date: datetime,
    event_type: str,
    number_of_days: int = 1,
    charge_type: CHARGE_TYPES = "INTEREST",
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    :param accrual_details: List of AccrualDetails used to calculate accrual amounts
        for each balance address and then create the postings, see AccrualDetails
    :param account_tside: str used to determine the directions of credits and debits
    :param effective_date: datetime
    :param event_type: String of the event name, such as "ACCRUE_INTEREST"
    :param number_of_days: number of days of interest to be accrued - normally interest accrues on
     daily basis but in certain cases, backdated interest may be required. Defaults to 1
    :return: List of accrual posting instructions
    """
    accrual_postings = []
    for accrual_detail in accrual_details:
        is_capitalised_accrual = accrual_detail.accrual_is_capitalised

        accruals = _calculate_accruals(accrual_detail, effective_date, number_of_days)

        if len(accruals) > 0:
            if is_capitalised_accrual:
                accrual_postings.extend(
                    _create_capitalised_accrual_postings(
                        vault,
                        payable_receivable_mapping=accrual_detail.payable_receivable_mapping,
                        denomination=accrual_detail.denomination,
                        accruals=accruals,
                        account_tside=account_tside,
                        event_type=event_type,
                        instruction_description=accrual_detail.instruction_description,
                        account_type=account_type,
                    )
                )
            else:
                accrual_postings.extend(
                    _create_postings_for_accruals(
                        vault,
                        payable_receivable_mapping=accrual_detail.payable_receivable_mapping,
                        denomination=accrual_detail.denomination,
                        accruals=accruals,
                        tside=account_tside,
                        net_postings=accrual_detail.net_postings,
                        event_type=event_type,
                        instruction_description=accrual_detail.instruction_description,
                        charge_type=charge_type,
                        account_type=account_type,
                    )
                )

    return accrual_postings


def accrue_fees(
    vault,
    fee_details: list[FeeDetails],
    account_tside: str,
    event_type: str,
    charge_type: CHARGE_TYPES = "FEES",
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    Create customer and GL postings to accrue fixed fee amounts using accrual accounting

    :param vault:
    :param fee_details: List of FeeDetails used to construct fee postings.
        Negative fee amount implies receivable fee,
        positive amount implies payable fee.
    :param account_tside: str used to determine the directions of credits and debits
    :param event_type: String of the event name, such as "ACCRUE_FEE"
    :return: List of fee accrual postings
    """
    accrual_postings = []

    for fee_detail in fee_details:

        accrual_postings.extend(
            _create_postings_for_accruals(
                vault,
                payable_receivable_mapping=fee_detail.payable_receivable_mapping,
                denomination=fee_detail.denomination,
                accruals=[
                    PostingInfo(
                        tier_name="",
                        amount=amount,
                        description=f"Accrued fee {fee_name}.",
                    )
                    for fee_name, amount in fee_detail.fee.items()
                ],
                instruction_description=fee_detail.instruction_description,
                tside=account_tside,
                net_postings=False,
                event_type=event_type,
                charge_type=charge_type,
                account_type=account_type,
            )
        )

    return accrual_postings


def apply_charges(
    vault,
    balances: dict[tuple[str, str, str, Phase], Balance],
    charge_details: list[ChargeApplicationDetails],
    account_tside: str,
    event_type: str,
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    Create customer and GL postings to apply charges (interest or fees) that were accrued using
    accrual accounting (e.g. accrue_fees or accrue_interest)

    :param vault:
    :param balances: balance timeseries for the account used to determine application and
        remainder amount
    :param charge_details: List of ChargeApplicationDetails for the charge,
        used to create postings, see the definition of ChargeApplicationDetails
    :param account_tside: str used to determine the directions of credits and debits
    :param instruction_details: optional metadata to add to the r
    :param event_type: String of the event name, such as "APPLY_ACCRUED_INTEREST"
    :return: List of postings to apply charges
    """

    application_postings = []

    for charge_detail in charge_details:

        # FOR NOW: All interest addresses must have a suffix e.g. ACCRUED_INTEREST_PAYABLE

        charge_balances = [
            balances.get(
                _charge_to_balance_dimensions(
                    address,
                    charge_detail.denomination,
                )
            )
            for address in [
                charge_detail.payable_receivable_mapping.payable_address,
                charge_detail.payable_receivable_mapping.receivable_address,
            ]
            if address
        ]

        applications = _calculate_application_and_remainders(
            charge_balances,
            charge_detail.rounding_mode,
            charge_detail.precision,
            charge_detail.charge_type,
        )

        application_postings.extend(
            _create_postings_for_applications(
                vault,
                payable_receivable_mapping=charge_detail.payable_receivable_mapping,
                denomination=charge_detail.denomination,
                applications=applications,
                zero_out_remainder=charge_detail.zero_out_remainder,
                instruction_description=charge_detail.instruction_description,
                zero_out_description=charge_detail.zero_out_description,
                account_tside=account_tside,
                apply_address=charge_detail.apply_address,
                event_type=event_type,
                charge_type=charge_detail.charge_type,
                account_type=account_type,
            )
        )

    return application_postings


def reverse_interest(
    vault,
    balances: dict[tuple[str, str, str, Phase], Balance],
    interest_dimensions: list[AccrualDetails],
    account_tside: str,
    event_type: str,
    charge_type: CHARGE_TYPES = "INTEREST",
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    Create customer and GL postings to reverse accrued interest on an account
    when the account is closed

    :param vault:
    :param balances: balance timeseries for the account used to determine reversal amount
    :param interest_dimensions: List of AccrualDetails, used to parse in
        details used for the accrual reversal postings
    :param account_tside: str used to determine the directions of credits and debits
    :param event_type: String of the event name, such as "REVERSE_ACCRUED_INTEREST"
    :return: List of postings to apply charges
    """

    postings = []
    for interest_dimension in interest_dimensions:

        for address in [
            interest_dimension.payable_receivable_mapping.payable_address,
            interest_dimension.payable_receivable_mapping.receivable_address,
        ]:
            if address:
                balance_dimensions = _charge_to_balance_dimensions(
                    address,
                    interest_dimension.denomination,
                )
                description = (
                    interest_dimension.instruction_description or "Reversing accrued interest"
                )
                instruction_details = {
                    "description": description,
                    "event": event_type,
                    "gl_impacted": "True",
                    "account_type": account_type,
                }
                postings.extend(
                    _create_accrual_postings(
                        vault,
                        payable_receivable_mapping=interest_dimension.payable_receivable_mapping,
                        denomination=interest_dimension.denomination,
                        accrual_amount=balances[balance_dimensions].net,
                        instruction_details=instruction_details,
                        account_tside=account_tside,
                        reverse=True,
                        charge_type=charge_type,
                    )
                )

    return postings


def _charge_to_balance_dimensions(
    address: str,
    denomination: str,
) -> tuple[str, str, str, Phase]:
    """
    Generates balance dimensions by converting constituent parts into tuple:
    (address, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    """
    return (
        address,
        DEFAULT_ASSET,
        denomination,
        Phase.COMMITTED,
    )


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


def _calculate_accruals(
    accrual_details: AccrualDetails,
    effective_date: datetime,
    number_of_days: int,
) -> list[PostingInfo]:

    """
    Calculates accrual amounts AccrualDetails, using the tiered rates,
    accrual bases, precision and rounding modes defined in effective_balance_details.

    :param accrual_details: AccrualDetails NamedTuple used to calculate accrual amount
        accrual calculation, as defined in accrue_interest
    :param effective_date: date considered in accrual calculations. This will affect results for
     leap years if using 'actual'
    :param number_of_days: number of days of interest to be accrued - normally interest accrues on
     daily basis but in certain cases, backdated interest may be required. Defaults to 1
    :return: List of NamedTuples containing accrual amounts + tier information
    """

    accruals = []
    if accrual_details.balance != Decimal("0"):

        for tier_name, tier in accrual_details.rates.items():
            effective_balance = accrual_details.balance
            # Can't use .get(key, default) as the key may be present with value None
            tier_min = Decimal(tier.get("min") or 0)
            # balance could be < 0
            tier_max = Decimal(tier.get("max") or effective_balance)

            # When dealing with negative tiers, it is simpler to flip all the signs,
            # run through normal logic, and flip the signs again.
            # This means we can't support tiers where min and max are
            # different sign, but it seems very unlikely and can be
            # handled by splitting the tiers
            sign_flip = False

            # is_signed() detects negative 0 whereas < 0 comparison does not
            if tier_max.is_signed() or tier_min.is_signed():
                sign_flip = True
                # when flipping sign, the defaults must also be flipped
                tier_min = Decimal(tier.get("min") or effective_balance)
                tier_max = Decimal(tier.get("max") or 0)
                tier_min, tier_max = -tier_max, -tier_min
                effective_balance = -effective_balance

            if tier_max < tier_min:
                tier_balance = 0
            else:
                tier_balance = min(effective_balance, tier_max) - min(effective_balance, tier_min)

            tier_daily_rate = _yearly_to_daily_rate(
                days_in_year=accrual_details.base,
                yearly_rate=Decimal(tier.get("rate", 0)),
                rounding_mode=accrual_details.rounding_mode,
                year=effective_date.year,
            )
            accrual_amount = (
                _round_decimal(
                    tier_balance * tier_daily_rate,
                    accrual_details.precision,
                    accrual_details.rounding_mode,
                )
                * (-1 if sign_flip else 1)
                * number_of_days
            )
            accruals.append(
                PostingInfo(
                    tier_name=tier_name,
                    amount=accrual_amount,
                    description=f"Daily interest accrued at "
                    f"{(tier_daily_rate * 100):0.5f}%"
                    f" on balance of {-tier_balance if sign_flip else tier_balance:0.2f}.",
                )
            )

    return accruals


def _create_postings_for_accruals(
    vault,
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    accruals: list[PostingInfo],
    tside: str,
    event_type: str,
    charge_type: CHARGE_TYPES,
    net_postings: bool = True,
    instruction_description: str = None,
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    Create customer and GL postings for accruing multiple charges
    :param payable_receivable_mapping: NamedTuple defining the payable and receivable mapping
        of internal accounts and balance address suffixes to the balance address base.
        Used to determine which accounts and addresses to use in the posting instruction.
    :param denomination: the denomination the posting should be made in.
    :param accruals: List of PostingInfo NamedTuples storing accrual calculation results.
    :param event_type: String of the event name, such as "ACCRUE_INTEREST"
    :param net_postings: If true, a single pair of postings per accrual dimension is created
     (i.e. the tier amounts are netted). If false, a pair of postings per accrual dimension
     per interest tier is created
    :param instruction_description: Optional string to override the default posting
    instruction details' description field.
    :return: list of accrual postings
    """

    if net_postings:

        net_amount = Decimal(sum(accrual.amount for accrual in accruals))
        instruction_details = _get_posting_instruction_details(
            posting_infos=accruals,
            event_type=event_type,
            gl_impacted=True,
            account_type=account_type,
        )
        if instruction_description:
            instruction_details["description"] = instruction_description
        accruals_postings = _create_accrual_postings(
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=denomination,
            accrual_amount=net_amount,
            instruction_details=instruction_details,
            account_tside=tside,
            charge_type=charge_type,
        )
    else:
        accruals_postings = []
        for accrual in accruals:
            instruction_details = _get_posting_instruction_details(
                posting_infos=[accrual],
                event_type=event_type,
                gl_impacted=True,
                account_type=account_type,
            )
            if instruction_description:
                instruction_details["description"] = instruction_description
            accruals_postings.extend(
                _create_accrual_postings(
                    vault,
                    payable_receivable_mapping=payable_receivable_mapping,
                    denomination=denomination,
                    accrual_amount=accrual.amount,
                    instruction_details=instruction_details,
                    account_tside=tside,
                    tier_name=accrual.tier_name,
                    charge_type=charge_type,
                )
            )
    return accruals_postings


def _create_accrual_postings(
    vault,
    payable_receivable_mapping: PayableReceivableMapping,
    charge_type: CHARGE_TYPES,
    denomination: str,
    accrual_amount: Decimal,
    instruction_details: dict[str, str],
    account_tside: str,
    reverse: bool = False,
    tier_name: str = None,
) -> list[PostingInstruction]:

    """
    Create customer and GL postings for accruing a charge
    :param payable_receivable_mapping: NamedTuple defining the payable and receivable mapping
        of internal accounts and balance address suffixes to the balance address base.
        Used to determine which accounts and addresses to use in the posting instruction.
    :param denomination: the denomination the posting should be made in.
    :param accrual_amount: the charge amount to accrue
    :param account_tside: str, either ASSET or LIABILITY, used to determin posting directions
    :param reverse: set to True if reversing the accrual. This will invert the direction of all
     postings
    :return: list of accrual postings
    """
    denomination = denomination

    # Don't create postings for 0 amount
    if accrual_amount == 0:
        return []

    elif (accrual_amount > 0 and account_tside.upper() == "LIABILITY") or (
        accrual_amount < 0 and account_tside.upper() == "ASSET"
    ):
        # Paying interest scenario
        address = payable_receivable_mapping.payable_address

        if reverse:
            # Debiting pending interest from clients account
            debit_account = vault.account_id
            credit_account = payable_receivable_mapping.payable_internal_account
            debit_address = address
            credit_address = DEFAULT_ADDRESS
        else:
            # Paying interest to client account
            debit_account = payable_receivable_mapping.payable_internal_account
            credit_account = vault.account_id
            debit_address = DEFAULT_ADDRESS
            credit_address = address

    else:
        # Receiving interest scenario
        address = payable_receivable_mapping.receivable_address

        if reverse:
            # Crediting interest to the clients account
            debit_account = payable_receivable_mapping.receivable_internal_account
            credit_account = vault.account_id
            debit_address = DEFAULT_ADDRESS
            credit_address = address
        else:
            # Debiting interest from the clients account
            debit_account = vault.account_id
            credit_account = payable_receivable_mapping.receivable_internal_account
            debit_address = address
            credit_address = DEFAULT_ADDRESS

    # Suffix is at an accrual BalanceDimensions level to ensure uniqueness
    cti_suffix = f"{vault.get_hook_execution_id()}_{address}" f"_{DEFAULT_ASSET}_{denomination}"

    cti_prefix = f"REVERSE_ACCRUED_{charge_type}" if reverse else f"ACCRUE_{charge_type}"
    accrual_amount = abs(accrual_amount)

    if tier_name:
        cti_suffix = f"{tier_name.upper()}_" + cti_suffix

    accrual_postings = vault.make_internal_transfer_instructions(
        amount=accrual_amount,
        denomination=denomination,
        client_transaction_id=f"{cti_prefix}_{cti_suffix}",
        from_account_id=debit_account,
        from_account_address=debit_address,
        to_account_id=credit_account,
        to_account_address=credit_address,
        asset=DEFAULT_ASSET,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )

    return accrual_postings


def _create_capitalised_accrual_postings(
    vault,
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    accruals: list[PostingInfo],
    account_tside: str,
    event_type: str,
    instruction_description: str = None,
    account_type: str = "",
) -> list[PostingInstruction]:
    """
    create customer postings for capitalised accrual of charges using cash accounting

    :param payable_receivable_mapping: NamedTuple defining the payable and receivable mapping
        of internal accounts and balance address suffixes to the balance address base.
        Used to determine which accounts and addresses to use in the posting instruction.
    :param denomination: the denomination the posting should be made in.
    :param accruals: List of PostingInfo NamedTuples storing accrual calculation results.
    :param net_postings: If true, a single pair of postings per accrual dimension is created
     (i.e. the tier amounts are netted). If false, a pair of postings per accrual dimension
     per interest tier is created
    :param event_type: String of the event name, such as "ACCRUE_INTEREST"
    :param instruction_description: Optional string to override the default posting
    instruction details' description field.
    :return: list of accrual postings
    """

    # TODO - Consider 'accruals' of > than length 1 and whether
    # we always want to net postings
    accrual_amount = Decimal(sum(accrual.amount for accrual in accruals))
    if accrual_amount == 0:
        return []
    instruction_details = _get_posting_instruction_details(
        posting_infos=accruals,
        event_type=event_type,
        account_type=account_type,
    )
    if instruction_description:
        instruction_details["description"] = instruction_description

    cti = "_ACCRUE_AND_CAPITALISE_INTEREST"
    if (
        accrual_amount > 0
        and account_tside.upper() == "LIABILITY"
        or accrual_amount < 0
        and account_tside.upper() == "ASSET"
    ):
        address = payable_receivable_mapping.payable_address

        from_account = vault.account_id
        from_address = address
        to_account = payable_receivable_mapping.paid_internal_account
        to_address = DEFAULT_ADDRESS

    else:
        address = payable_receivable_mapping.receivable_address

        from_account = payable_receivable_mapping.received_internal_account
        from_address = DEFAULT_ADDRESS
        to_account = vault.account_id
        to_address = address

    cti += f"_{vault.get_hook_execution_id()}_{address}_{DEFAULT_ASSET}_{denomination}"

    return vault.make_internal_transfer_instructions(
        # GL postings
        amount=abs(accrual_amount),
        denomination=denomination,
        client_transaction_id=cti,
        from_account_id=from_account,
        from_account_address=from_address,
        to_account_id=to_account,
        to_account_address=to_address,
        asset=DEFAULT_ASSET,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )


def _calculate_application_and_remainders(
    interest_balances: list[Balance],
    rounding_mode: str,
    precision: int,
    charge_type: CHARGE_TYPES,
) -> list[dict[str, PostingInfo]]:
    """
    Determine amount to apply and remainder per balance.
    :param interest_balances: List of Balance objects
    :param rounding_mode: the `decimal` rounding mode to use
    :param precision: the number of decimal places to round to
    :param charge_type: Either "INTEREST" or "FEES"
    :return: List of dictionary of PostingInfo tuples. Each dictionary expects
    keys 'application' and 'remainder' to indicate the application and remainder amounts.
    """
    applications = []
    for balance in interest_balances:
        if balance is not None:
            application = PostingInfo(
                tier_name="",
                amount=_round_decimal(balance.net, precision, rounding_mode),
                description=f"Accrued {charge_type.lower()} applied.",
            )
            remainder = PostingInfo(
                tier_name="",
                amount=balance.net - application.amount,
                description=f"Zero out remainder after accrued " f"{charge_type.lower()} applied.",
            )
            applications.append({"application": application, "remainder": remainder})
    return applications


def _create_postings_for_applications(
    vault,
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    applications: list[dict[str, PostingInfo]],
    account_tside: str,
    zero_out_remainder: bool,
    apply_address: str,
    event_type: str,
    charge_type: CHARGE_TYPES,
    instruction_description: str = None,
    zero_out_description: str = None,
    account_type: str = "",
) -> list[PostingInstruction]:

    """
    Create customer and GL postings for applying an accrued charge, including handling of remainders

    :param payable_receivable_mapping: NamedTuple defining the payable and receivable mapping
        of internal accounts and balance address suffixes to the balance address base.
        Used to determine which accounts and addresses to use in the posting instruction.
    :param denomination: the denomination the posting should be made in.
    :param applications: List of dictionary of PostingInfo tuples. Each dictionary expects
    keys 'application' and 'remainder' to indicate the application and remainder amounts.
    :param zero_out_remainder: set to True if remainders should be zeroed out as part of
     application, or False otherwise.
    :param event_type: String of the event name, such as "ACCRUE_INTEREST"
    :param charge_type: Either "INTEREST" or "FEES"
    :param instruction_description: Optional string to override the default postings' description
    :param zero_out_description: Optional string to override the default remainder postings'
    description
    :return: list of application postings
    """

    application_postings = []
    for amounts in applications:
        application_amount = amounts["application"].amount
        remainder_amount = amounts["remainder"].amount
        application_instruction_details = _get_posting_instruction_details(
            [amounts["application"]],
            event_type,
            gl_impacted=True,
            account_type=account_type,
        )
        remainder_instruction_details = _get_posting_instruction_details(
            [amounts["remainder"]],
            event_type,
            gl_impacted=True,
            account_type=account_type,
        )
        if instruction_description:
            application_instruction_details["description"] = instruction_description
        if zero_out_description:
            remainder_instruction_details["description"] = zero_out_description
        application_postings.extend(
            _create_application_postings(
                vault,
                payable_receivable_mapping=payable_receivable_mapping,
                denomination=denomination,
                application_amount=application_amount,
                instruction_details=application_instruction_details,
                account_tside=account_tside,
                apply_address=apply_address,
                charge_type=charge_type,
            )
        )
        if zero_out_remainder and remainder_amount != 0:
            # reverse existing accrual if applying less than accrued
            reverse = (
                (remainder_amount > 0 and application_amount > 0)
                or (remainder_amount < 0 and application_amount < 0)
                or application_amount == 0
            )
            application_postings.extend(
                _create_accrual_postings(
                    vault,
                    payable_receivable_mapping=payable_receivable_mapping,
                    denomination=denomination,
                    # the amount must be negated for PAYABLE/RECEIVABLE to be correct if reverse is
                    # true as remainder and application would have different signs
                    accrual_amount=remainder_amount if reverse else -remainder_amount,
                    instruction_details=remainder_instruction_details,
                    account_tside=account_tside,
                    reverse=reverse,
                    charge_type=charge_type,
                )
            )

    return application_postings


def _create_application_postings(
    vault,
    payable_receivable_mapping: PayableReceivableMapping,
    denomination: str,
    application_amount: Decimal,
    instruction_details: dict[str, str],
    account_tside: str,
    apply_address: str,
    charge_type: CHARGE_TYPES,
) -> list[PostingInstruction]:
    """
    Create customer and GL postings for applying an accrued charge
    :param payable_receivable_mapping: NamedTuple defining the payable and receivable mapping
        of internal accounts and balance address suffixes to the balance address base.
        Used to determine which accounts and addresses to use in the posting instruction.
    :param denomination: the denomination the posting should be made in.
    :param application_dimensions: Address, asset, denomination and phase for the application
    :param application_amount: amount to apply
    :param account_tside: str, either ASSET or LIABILITY, used to determine posting directions
    :param charge_type: Either "INTEREST" or "FEES"
    :return: list of application postings
    """

    if application_amount == 0:
        return []

    elif (
        application_amount > 0
        and account_tside.upper() == "LIABILITY"
        or application_amount < 0
        and account_tside.upper() == "ASSET"
    ):
        primary_posting_debit_account = payable_receivable_mapping.paid_internal_account
        primary_posting_debit_account_address = DEFAULT_ADDRESS

        primary_posting_credit_account = vault.account_id
        primary_posting_credit_account_address = apply_address

        offset_posting_debit_account = vault.account_id
        offset_posting_debit_account_address = payable_receivable_mapping.payable_address

        offset_posting_credit_account = payable_receivable_mapping.payable_internal_account
        offset_posting_credit_account_address = DEFAULT_ADDRESS

        cti_suffix = f"{vault.get_hook_execution_id()}_{offset_posting_debit_account_address}"
        cti_suffix += f"_{DEFAULT_ASSET}_{denomination}"
    else:
        primary_posting_debit_account = vault.account_id
        primary_posting_debit_account_address = apply_address

        primary_posting_credit_account = payable_receivable_mapping.received_internal_account
        primary_posting_credit_account_address = DEFAULT_ADDRESS

        offset_posting_debit_account = payable_receivable_mapping.receivable_internal_account
        offset_posting_debit_account_address = DEFAULT_ADDRESS

        offset_posting_credit_account = vault.account_id
        offset_posting_credit_account_address = payable_receivable_mapping.receivable_address

        cti_suffix = f"{vault.get_hook_execution_id()}_{offset_posting_credit_account_address}"
        cti_suffix += f"_{DEFAULT_ASSET}_{denomination}"

    application_amount = abs(application_amount)

    application_postings = vault.make_internal_transfer_instructions(
        amount=application_amount,
        denomination=denomination,
        client_transaction_id=f"APPLY_{charge_type}_PRIMARY_{cti_suffix}",
        from_account_id=primary_posting_debit_account,
        from_account_address=primary_posting_debit_account_address,
        to_account_id=primary_posting_credit_account,
        to_account_address=primary_posting_credit_account_address,
        asset=DEFAULT_ASSET,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )

    application_postings.extend(
        vault.make_internal_transfer_instructions(
            amount=application_amount,
            denomination=denomination,
            client_transaction_id=f"APPLY_{charge_type}_OFFSET_{cti_suffix}",
            from_account_id=offset_posting_debit_account,
            from_account_address=offset_posting_debit_account_address,
            to_account_id=offset_posting_credit_account,
            to_account_address=offset_posting_credit_account_address,
            asset=DEFAULT_ASSET,
            instruction_details=instruction_details,
            override_all_restrictions=True,
        )
    )

    return application_postings


def _yearly_to_daily_rate(
    days_in_year: str,
    rounding_mode: ROUNDING_TYPES,
    yearly_rate: Decimal,
    year: Optional[int] = None,
) -> Decimal:
    """
    Converts  a yearly rates to a daily rate based on the number of days in the year
    :param days_in_year: The days in the year to use for calculations, or 'actual'
     to use actual days.
    :param yearly_rate: yearly rate to convert
    :param year: The year to be used to decide whether its a leap year or not
    :return: converted daily rate. Only required if using 'actual' days_in_year
    """
    allowed_values = ["actual", "366", "365", "360", 366, 365, 360]
    if days_in_year in allowed_values:
        if days_in_year == "actual":
            days_in_year = "366" if _is_leap_year(year) else "365"

        return (yearly_rate / Decimal(days_in_year)).quantize(
            Decimal(".0000000001"), rounding=rounding_mode
        )


def _is_leap_year(year: int) -> bool:
    """
    :param year: year extracted from date
    :return: true if leap year
    """
    if year % 400 == 0:
        return True
    elif year % 100 == 0:
        return False
    elif year % 4 == 0:
        return True
    else:
        return False


def _get_posting_instruction_details(
    posting_infos: list[PostingInfo],
    event_type: str,
    gl_impacted: bool = False,
    account_type: str = "",
) -> dict:
    """
    Generates default posting instruction details based off of posting information
    :param posting_infos: List of PostingInfo NamedTuples storing posting calculation results.
    :param event_type: String of the event name, eg "ACCRUE_INTEREST"
    :param gl_impacted: Boolean flag to indicate if this posting instruction has GL implications
    :return: Dict containing the instruction details with "event" and "description" fields
    """
    if len(posting_infos) == 1:
        description = posting_infos[0].description
    else:
        joined_descs = " ".join([info.description for info in posting_infos])
        description = f"Aggregate of: {joined_descs}"
    return {
        "description": description,
        "event": event_type,
        "gl_impacted": str(gl_impacted),
        "account_type": account_type,
    }
