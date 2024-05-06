from datetime import datetime
from typing import NamedTuple, Callable, Optional

# imports from the inception library
from inception_sdk.vault.contracts.types_extension import (
    AccountIdShape,
    Decimal,
    DEFAULT_ADDRESS,
    Level,
    Parameter,
    PostingInstruction,
    UnionItem,
    UnionItemValue,
    UnionShape,
    UpdatePermission,
    Vault,
)
import library.features.common.utils as utils
import library.features.lending.interest_accrual as interest_accrual

# Schedule event names
HANDLE_OVERPAYMENT_ALLOWANCE = "HANDLE_OVERPAYMENT_ALLOWANCE"

# Addresses
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
PENALTIES = "PENALTIES"
PRINCIPAL = "PRINCIPAL"
OVERPAYMENT = "OVERPAYMENT"
OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC = "OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC"

# Other
REPAYMENT = "REPAYMENT"


preference_parameters = [
    Parameter(
        name="overpayment_impact_preference",
        shape=UnionShape(
            UnionItem(key="reduce_term", display_name="Reduce term"),
            UnionItem(key="reduce_emi", display_name="Reduce EMI"),
        ),
        level=Level.TEMPLATE,
        description="Defines how to handle an overpayment on a loan:"
        "Reduce EMI but keep the term of the loan the same."
        "Reduce term but keep the monthly repayments the same.",
        display_name="Overpayment impact preference",
        default_value=UnionItemValue(key="reduce_term"),
    ),
]
fee_percentage_parameter = Parameter(
    name="overpayment_fee_percentage",
    shape=utils.PositiveRateShape,
    level=Level.TEMPLATE,
    description="Percentage of overpaid principal to charge when going over "
    "overpayment allowance.",
    display_name="Overpayment fee percentage",
    default_value=Decimal("0.05"),
    update_permission=UpdatePermission.FIXED,
)
fee_internal_account_parameter = Parameter(
    name="overpayment_fee_account",
    level=Level.TEMPLATE,
    description="Internal account for the overpayment fee income balance.",
    display_name="Overpayment fee income account",
    shape=AccountIdShape,
    default_value="OVERPAYMENT_FEE_INCOME",
)
fee_parameters = [
    fee_percentage_parameter,
    fee_internal_account_parameter,
]
all_parameters = [
    *fee_parameters,
    *preference_parameters,
]


def get_cleanup_residual_posting_instructions(
    vault: Vault, principal_address: str = PRINCIPAL
) -> list[PostingInstruction]:
    """
    Returns posting instructions to move any value left in the OVERPAYMENT, EMI_PRINCIPAL_EXCESS,
    and ACCRUED_EXPECTED_INTEREST addresses to or from either the PRINCIPAL or INTERNAL addresses
    to zero out all remaining balances.

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param principal_address: The address where the principal for the loan is stored.
    :return: The posting instructions to zero out any residual balance amounts.
    """
    denomination: str = utils.get_parameter(vault, name="denomination")
    hook_execution_id = vault.get_hook_execution_id()
    cleanup_repayment_instructions: list[PostingInstruction] = []

    overpayment_balance = utils.get_balance_sum(vault, [OVERPAYMENT])
    if overpayment_balance > 0:
        cleanup_repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=overpayment_balance,
                denomination=denomination,
                client_transaction_id=f"CLEAR_{OVERPAYMENT}_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=OVERPAYMENT,
                instruction_details={
                    "description": f"Clearing {OVERPAYMENT} address",
                    "event": "END_OF_LOAN",
                },
                override_all_restrictions=True,
            )
        )

    principal_excess_balance = utils.get_balance_sum(vault, [EMI_PRINCIPAL_EXCESS])
    if principal_excess_balance > 0:
        cleanup_repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(principal_excess_balance),
                denomination=denomination,
                client_transaction_id=f"CLEAR_{EMI_PRINCIPAL_EXCESS}_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=EMI_PRINCIPAL_EXCESS,
                instruction_details={
                    "description": "Clearing principal excess",
                    "event": "END_OF_LOAN",
                },
                override_all_restrictions=True,
            )
        )

    accrued_expected_interest_balance = utils.get_balance_sum(vault, [ACCRUED_EXPECTED_INTEREST])
    if accrued_expected_interest_balance > 0:
        cleanup_repayment_instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_expected_interest_balance,
                denomination=denomination,
                client_transaction_id=f"CLEAR_{ACCRUED_EXPECTED_INTEREST}_{hook_execution_id}",
                from_account_id=vault.account_id,
                from_account_address=INTERNAL_CONTRA,
                to_account_id=vault.account_id,
                to_account_address=ACCRUED_EXPECTED_INTEREST,
                instruction_details={
                    "description": f"Clearing {ACCRUED_EXPECTED_INTEREST} balance",
                    "event": "END_OF_LOAN",
                },
                override_all_restrictions=True,
            )
        )

    cleanup_repayment_instructions.extend(reset_overpayment_tracker(vault))

    return cleanup_repayment_instructions


def get_accrual_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    accrual_formula: Callable,
    capital_addresses: Optional[list[str]] = None,
) -> list[PostingInstruction]:
    """
    Creates the posting instructions to accrue expected interest, ignoring overpayments, on the
    balances specified by the denomination and capital addresses parameters.
    The posting instructions:
    - debit ACCRUED_EXPECTED_INTEREST and credit INTERNAL_CONTRA with the expected accrued interest
    amount, which ignores overpayment effects

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param effective_date: the effective date to use for retrieving capital balances to accrue on
    :param denomination: the denomination of the capital balances and the interest accruals
    :param accrued_formula: Feature that encapsulates the rate type structure
    as well as the accrual formula
    :param capital_addresses: balance addresses to consider as capital to accrue on.
    Defaults to [PRINCIPAL, EMI_PRINCIPAL_EXCESS, OVERPAYMENT], which means impact of overpayment
    is included
    :return: the accrual posting instructions
    """
    capital_addresses = capital_addresses or [PRINCIPAL, EMI_PRINCIPAL_EXCESS, OVERPAYMENT]

    expected_accrual_capital = interest_accrual.get_accrual_capital(
        vault, effective_date, denomination, capital_addresses
    )

    amount_to_accrue_excluding_overpayment_effects = accrual_formula(
        vault, expected_accrual_capital, effective_date
    )
    hook_execution_id = vault.get_hook_execution_id()

    return (
        vault.make_internal_transfer_instructions(
            amount=amount_to_accrue_excluding_overpayment_effects,
            denomination=denomination,
            client_transaction_id=f"UPDATE_{ACCRUED_EXPECTED_INTEREST}_{hook_execution_id}",
            from_account_id=vault.account_id,
            from_account_address=ACCRUED_EXPECTED_INTEREST,
            to_account_id=vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            instruction_details={
                "description": (
                    f"Daily interest excluding overpayment effects accrued on balance of "
                    f"{expected_accrual_capital}"
                )
            },
            override_all_restrictions=True,
        )
        if amount_to_accrue_excluding_overpayment_effects > 0
        else []
    )


def get_application_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    accrued_at_address: Optional[str] = None,
    applied_to_address: Optional[str] = None,
) -> list[PostingInstruction]:
    """
    Creates posting instructions to use when applying interest (e.g. as part of due amount
    calculation). These simply clear the ACCRUED_EXPECTED_INTEREST balance, by default, which will
    always be >= 0 as there are no rounding concerns:
    - credit ACCRUED_EXPECTED_INTEREST and debit INTERNAL_CONTRA by the current expected accrued
    interest amount

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param effective_date: the effective date to use for retrieving capital balances to accrue on
    :param denomination: the denomination of the existing ACCRUED_EXPECTED_INTEREST balances
    :param accrued_at_address: Unused - part of interface
    :param applied_to_address: Unused - part of interface
    :return: the relevant posting instructions
    """
    accrued_expected_interest = utils.get_balance_sum(
        vault, addresses=[ACCRUED_EXPECTED_INTEREST], timestamp=effective_date
    )
    hook_execution_id = vault.get_hook_execution_id()
    return (
        vault.make_internal_transfer_instructions(
            amount=accrued_expected_interest,
            denomination=denomination,
            client_transaction_id=f"UPDATE_{ACCRUED_EXPECTED_INTEREST}_{hook_execution_id}",
            from_account_id=vault.account_id,
            from_account_address=INTERNAL_CONTRA,
            to_account_id=vault.account_id,
            to_account_address=ACCRUED_EXPECTED_INTEREST,
            instruction_details={"description": f"Clear {ACCRUED_EXPECTED_INTEREST}"},
            override_all_restrictions=True,
        )
        if accrued_expected_interest > 0
        else []
    )


def get_overpayment_fee_posting_instructions(
    vault: Vault,
    amount: Decimal,
    penalty_address: str = PENALTIES,
    event: str = REPAYMENT,
    description: Optional[str] = None,
) -> list[PostingInstruction]:
    """
    Creates postings to apply an overpayment fee

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param amount: The fee amount. If <=0 no postings are created
    :param penalty_address: The address where the loan fees are stored.
    :param event: the value for the `event` key in the instruction details
    :param description: the value for the `description` key in the instruction details.
    :return: The posting instructions to transfer a fee
    """

    denomination: str = utils.get_parameter(vault, name="denomination")
    overpayment_fee_account: str = utils.get_parameter(vault, name="overpayment_fee_account")
    return (
        vault.make_internal_transfer_instructions(
            amount=amount,
            denomination=denomination,
            client_transaction_id="CHARGE_OVERPAYMENT_FEE_" + vault.get_hook_execution_id(),
            from_account_id=vault.account_id,
            from_account_address=penalty_address,
            to_account_id=overpayment_fee_account,
            to_account_address=DEFAULT_ADDRESS,
            instruction_details={
                "description": description or f"Charging {denomination} {amount} overpayment fee",
                "event": event,
            },
            override_all_restrictions=True,
        )
        if amount > 0
        else []
    )


def get_principal_adjustment_amount(vault: Vault) -> Decimal:
    """
    Returns the sum of the overpayment amounts made into the account as well as
    the sum of any principal amount that was modified as a result of the overpayment(s).

    :param vault: The vault object containing parameters, flags, balances, etc.
    :return: The sum of the overpayment effects.
    """
    return Decimal(0)


def get_principal_adjustment_posting_instructions(
    vault: Vault, denomination: str, principal_address: str = PRINCIPAL
) -> list[PostingInstruction]:
    """
    Returns posting instructions to update the principal excess on due amount calculation.
    This amount reflects the difference in accrued interest due to an overpayment reducing
    principal. This in turn increases principal portion of the EMI and decreases the
    remaining principal.
    Debits EMI_PRINCIPAL_EXCESS address and Credits INTERNAL_CONTRA

    :param vault: The vault object containing parameters, flags, balances, etc.
    :param denomination: denomination
    :param principal_address: Unused, required to match the interface
    :return: The posting instructions to move the principal excess amount to the principal address.
    """

    hook_execution_id = vault.get_hook_execution_id()
    accrued_interest_excluding_overpayment = utils.get_balance_sum(
        vault, [ACCRUED_EXPECTED_INTEREST]
    )

    # expected interest includes both emi and non-emi portions of interest
    accrued_interest_including_overpayment = interest_accrual.get_accrued_interest(
        vault
    ) + interest_accrual.get_additional_interest(vault)
    emi_principal_excess_amount = utils.round_decimal(
        accrued_interest_excluding_overpayment, 2
    ) - utils.round_decimal(accrued_interest_including_overpayment, 2)

    return (
        vault.make_internal_transfer_instructions(
            amount=emi_principal_excess_amount,
            denomination=denomination,
            client_transaction_id=f"UPDATE_{EMI_PRINCIPAL_EXCESS}_{hook_execution_id}",
            from_account_id=vault.account_id,
            from_account_address=EMI_PRINCIPAL_EXCESS,
            to_account_id=vault.account_id,
            to_account_address=INTERNAL_CONTRA,
            instruction_details={
                "description": f"Increase {EMI_PRINCIPAL_EXCESS} by {emi_principal_excess_amount}"
            },
            override_all_restrictions=True,
        )
        if emi_principal_excess_amount > 0
        else []
    )


def should_trigger_reamortisation_supervisor(
    vault: Vault,
    elapsed_term_in_months: Optional[int] = None,
    due_amount_schedule_details: Optional[utils.ScheduleDetails] = None,
    **kwargs,
) -> bool:
    """
    Determines whether to trigger reamortisation based on whether the overpayment tracker balance
    is non-zero, and whether the overpayment preference is to reduce emi (as opposed to reducing
    the term). This is a low data requirements alternative for supervisors, which don't have
    access to ODF and cannot efficiently fetch the overpayment balance as of a previous date.

    :param vault: Vault object used to fetch balances/parameters
    :param elapsed_term_in_months: the number of elapsed terms in months. Unused but required by
    the interface
    :param due_amount_schedule_details: the details of the due amount schedule. Unused but
    required by the interface
    :param kwargs: used to retrieve the overpayment impact preference under key
    `overpayment_impact_preference`
    :return: True if reamortisation is needed, False otherwise
    """

    overpayments_since_last_due_amount_calc = utils.get_balance_sum(
        vault, addresses=[OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC]
    )

    overpayment_preference = kwargs.get("overpayment_impact_preference", "reduce_term")
    return overpayments_since_last_due_amount_calc > 0 and overpayment_preference == "reduce_emi"


def track_overpayment(
    vault: Vault,
) -> list[PostingInstruction]:

    return vault.make_internal_transfer_instructions(
        amount=Decimal("1"),
        denomination=utils.get_parameter(vault, "denomination"),
        client_transaction_id=f"TRACK_OVERPAYMENT_{vault.get_hook_execution_id()}",
        from_account_id=vault.account_id,
        from_account_address=OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
        to_account_id=vault.account_id,
        to_account_address=INTERNAL_CONTRA,
        override_all_restrictions=True,
    )


def reset_overpayment_tracker(
    vault: Vault,
) -> list[PostingInstruction]:
    current_tracker_value = utils.get_balance_sum(vault, [OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC])
    return (
        vault.make_internal_transfer_instructions(
            amount=current_tracker_value,
            denomination=utils.get_parameter(vault, "denomination"),
            client_transaction_id=f"RESET_OVERPAYMENT_TRACKER_{vault.get_hook_execution_id()}",
            from_account_id=vault.account_id,
            from_account_address=INTERNAL_CONTRA,
            to_account_id=vault.account_id,
            to_account_address=OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
            override_all_restrictions=True,
        )
        if current_tracker_value > 0
        else []
    )


# Overpayment helper functions


Overpayment = NamedTuple(
    "Overpayment",
    [
        ("all_parameters", list),
        ("fee_parameters", list),
        ("preference_parameters", list),
        ("get_cleanup_residual_posting_instructions", Callable),
        ("get_accrual_posting_instructions", Callable),
        ("get_application_posting_instructions", Callable),
        ("get_overpayment_fee_posting_instructions", Callable),
        ("get_principal_adjustment_amount", Callable),
        ("get_principal_adjustment_posting_instructions", Callable),
        ("should_trigger_reamortisation", Callable),
        ("track_overpayment", Callable),
        ("reset_overpayment_tracker", Callable),
    ],
)

feature = Overpayment(
    all_parameters=all_parameters,
    fee_parameters=fee_parameters,
    preference_parameters=preference_parameters,
    get_cleanup_residual_posting_instructions=get_cleanup_residual_posting_instructions,
    get_accrual_posting_instructions=get_accrual_posting_instructions,
    get_application_posting_instructions=get_application_posting_instructions,
    get_overpayment_fee_posting_instructions=get_overpayment_fee_posting_instructions,
    get_principal_adjustment_amount=get_principal_adjustment_amount,
    get_principal_adjustment_posting_instructions=get_principal_adjustment_posting_instructions,
    should_trigger_reamortisation=should_trigger_reamortisation_supervisor,
    track_overpayment=track_overpayment,
    reset_overpayment_tracker=reset_overpayment_tracker,
)
