# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.v4.common.fees as fees
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    NumberShape,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    Phase,
    Posting,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters
DEFAULT_EARLY_CLOSURE_FEE_ADDRESS = "EARLY_CLOSURE_FEE"

PARAM_EARLY_CLOSURE_FEE = "early_closure_fee"
PARAM_EARLY_CLOSURE_DAYS = "early_closure_days"
PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT = "early_closure_fee_income_account"

parameters = [
    Parameter(
        name=PARAM_EARLY_CLOSURE_FEE,
        level=ParameterLevel.TEMPLATE,
        description="The fee charged if the account is closed early.",
        display_name="Early Closure Fee",
        shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("0.00"),
    ),
    Parameter(
        name=PARAM_EARLY_CLOSURE_DAYS,
        level=ParameterLevel.TEMPLATE,
        description="The number of days that must be completed in order to avoid an early closure"
        "  fee, should the account be closed.",
        display_name="Early Closure Days",
        shape=NumberShape(min_value=0, max_value=90, step=1),
        update_permission=ParameterUpdatePermission.OPS_EDITABLE,
        default_value=Decimal("90"),
    ),
    Parameter(
        name=PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT,
        level=ParameterLevel.TEMPLATE,
        description="Internal account for early closure fee income balance.",
        display_name="Early Closure Fee Income Account",
        shape=AccountIdShape(),
        default_value="EARLY_CLOSURE_FEE_INCOME",
    ),
]

data_fetchers = [
    fetchers.EFFECTIVE_OBSERVATION_FETCHER,
]


def apply_fees(
    vault: SmartContractVault,
    effective_datetime: datetime,
    account_type: str,
    early_closure_fee_tracker_address: str = DEFAULT_EARLY_CLOSURE_FEE_ADDRESS,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> list[CustomInstruction]:
    """
    Applies the early closure fee if account is closed within 'early_closure_days' number of days
    (midnight inclusive) and if the fee hasn't been applied already.

    :param vault: The vault object containing parameters, balances, etc.
    :param denomination: The denomination of the fee.
    :param effective_datetime: The effective datetime for fee application.
    :param account_type: The account type to be noted in the custom instruction detail.
    :param early_closure_fee_tracker_address: The address used to track if fee was applied.
    :return: Returns the Custom Instruction for charging the fee and tracking the fee.
    """

    creation_datetime: datetime = vault.get_account_creation_datetime()
    early_closure_fee = Decimal(utils.get_parameter(vault, PARAM_EARLY_CLOSURE_FEE))
    early_closure_days = int(utils.get_parameter(vault, PARAM_EARLY_CLOSURE_DAYS))
    early_closure_fee_income_account: str = utils.get_parameter(
        vault, PARAM_EARLY_CLOSURE_FEE_INCOME_ACCOUNT
    )

    instructions: list[CustomInstruction] = []

    if early_closure_fee <= 0:
        return instructions

    early_closure_cut_off_datetime = creation_datetime + relativedelta(days=early_closure_days)

    if denomination is None:
        denomination = str(
            utils.get_parameter(vault, name="denomination", at_datetime=effective_datetime)
        )
    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances

    # Check if early closure fee was not charged before.
    # Since this fee's tracker postings zero out the tracker address (i.e. net zero) so the
    # close code hook does not leave any non-zero custom balance definitions, we cannot
    # check for net != 0. Instead, we check the debit.
    early_closure_fee_coord = BalanceCoordinate(
        account_address=early_closure_fee_tracker_address,
        asset=DEFAULT_ASSET,
        denomination=denomination,
        phase=Phase.COMMITTED,
    )
    fee_has_not_been_charged_before = balances[early_closure_fee_coord].debit == 0

    if fee_has_not_been_charged_before and effective_datetime <= early_closure_cut_off_datetime:
        fee_postings = fees.fee_postings(
            customer_account_id=vault.account_id,
            customer_account_address=DEFAULT_ADDRESS,
            denomination=denomination,
            amount=early_closure_fee,
            internal_account=early_closure_fee_income_account,
        )

        tracker_postings = _update_closure_fee_tracker(
            denomination=denomination,
            account_id=vault.account_id,
            account_tracker_address=early_closure_fee_tracker_address,
        )

        postings = [*fee_postings, *tracker_postings]

        instructions = [
            CustomInstruction(
                postings=postings,
                instruction_details=utils.standard_instruction_details(
                    description="EARLY CLOSURE FEE",
                    event_type="CLOSE_ACCOUNT",
                    gl_impacted=True,
                    account_type=account_type,
                ),
                override_all_restrictions=True,
            )
        ]

    return instructions


def _update_closure_fee_tracker(
    denomination: str,
    account_id: str,
    account_tracker_address: str,
) -> list[Posting]:
    """
    Create postings to track early closure fee applied. Whereas other trackers
    normally make non-zero net postings, here the postings net zero so as to
    not leave custom balance definitions with non-zero balances since it is
    intended for use in the close code hook. Since the sole purpose is to track
    if a fee was applied, the amount can be hardcoded to 1.

    :param denomination: The denomination of this instruction.
    :param account_id: Account id.
    :param account_tracker_address: Address for tracking purposes.
    :return: Returns debit and credit entries for early closure fee tracking.
    """

    postings = utils.create_postings(
        amount=Decimal("1"),
        debit_account=account_id,
        debit_address=account_tracker_address,
        credit_account=account_id,
        credit_address=account_tracker_address,
        denomination=denomination,
    )

    return postings
