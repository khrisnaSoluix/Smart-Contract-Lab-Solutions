# standard lib
from decimal import Decimal
from datetime import datetime
from dateutil.relativedelta import relativedelta as timedelta

# inception lib
from inception_sdk.vault.contracts.types_extension import (
    Level,
    Parameter,
    Phase,
    PostingInstruction,
    NumberKind,
    NumberShape,
    UpdatePermission,
    AccountIdShape,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Vault,
)
import library.features.common.utils as utils

DEFAULT_EARLY_CLOSURE_FEE_ADDRESS = "EARLY_CLOSURE_FEE"

parameters = [
    Parameter(
        name="early_closure_fee",
        level=Level.TEMPLATE,
        description="The fee charged if the account is closed early.",
        display_name="Early closure fee",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=0, step=0.01),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name="early_closure_days",
        level=Level.TEMPLATE,
        description="The number of days that must be completed in order to avoid an early closure"
        "  fee, should the account be closed.",
        display_name="Early closure days",
        shape=NumberShape(min_value=0, max_value=90, step=1),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=90,
    ),
    Parameter(
        name="early_closure_fee_income_account",
        level=Level.TEMPLATE,
        description="Internal account for early closure fee income balance.",
        display_name="Early closure fee income account",
        shape=AccountIdShape,
        default_value="EARLY_CLOSURE_FEE_INCOME",
    ),
]

# This method is designed for use in the close_code hook
def get_fees(
    vault: Vault,
    denomination: str,
    effective_date: datetime,
    early_closure_fee_address: str = DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
) -> list[PostingInstruction]:
    """
    Applies the early closure fee if account is closed within 'early_closure_days' number of days
    (midnight inclusive) and if the fee hasn't been applied already
    """
    creation_date = vault.get_account_creation_date()
    early_closure_fee = Decimal(utils.get_parameter(vault, "early_closure_fee"))
    early_closure_days = int(utils.get_parameter(vault, "early_closure_days"))
    early_closure_fee_income_account = utils.get_parameter(
        vault, "early_closure_fee_income_account"
    )

    instructions = []

    if not early_closure_fee > 0:
        return instructions

    early_closure_cut_off_date = creation_date + timedelta(days=early_closure_days)

    # The postings below zero-out the address, as close_code should not leave any non-zero custom
    # balance definitions, so we can't check if net !=0. Instead we check the debit
    fee_has_not_been_charged_before = (
        vault.get_balance_timeseries()
        .latest()[(DEFAULT_EARLY_CLOSURE_FEE_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)]
        .debit
        == 0
    )

    # apply the fee if it has not already been applied
    if fee_has_not_been_charged_before and effective_date <= early_closure_cut_off_date:
        instructions.extend(
            vault.make_internal_transfer_instructions(
                amount=early_closure_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=early_closure_fee_income_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}",
                instruction_details={
                    "description": "EARLY CLOSURE FEE",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
        )
        instructions.extend(
            # This posting is net 0 for the balance definition so that the close_code does
            # not leave custom balance definitions with non-zero balances
            vault.make_internal_transfer_instructions(
                amount=early_closure_fee,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=early_closure_fee_address,
                to_account_id=vault.account_id,
                to_account_address=early_closure_fee_address,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id=f"APPLY_EARLY_CLOSURE_FEE"
                f"_{vault.get_hook_execution_id()}"
                f"_{denomination}_TRACKER",
                instruction_details={
                    "description": "EARLY CLOSURE FEE",
                    "event": "CLOSE_ACCOUNT",
                    "account_type": "MURABAHAH",
                },
            )
        )

    return instructions
