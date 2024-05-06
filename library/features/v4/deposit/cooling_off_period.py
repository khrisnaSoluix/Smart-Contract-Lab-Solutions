# CBF: Cooling-off period

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import BalanceDefaultDict, DateShape, NumberShape, Parameter, ParameterLevel

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault

# Parameters
PARAM_COOLING_OFF_PERIOD = "cooling_off_period"
PARAM_COOLING_OFF_PERIOD_END_DATE = "cooling_off_period_end_date"

parameters = [
    Parameter(
        name=PARAM_COOLING_OFF_PERIOD,
        level=ParameterLevel.TEMPLATE,
        description="The number of days from the account creation datetime when a user can make a "
        "full withdrawal without penalties.",
        display_name="Cooling-off Period Length (days)",
        shape=NumberShape(min_value=0, step=1),
        default_value=5,
    ),
    # Derived Parameters
    Parameter(
        name=PARAM_COOLING_OFF_PERIOD_END_DATE,
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="The cooling-off period will end at 23:59:59.999999 on this day. If "
        "0001-01-01 is returned, this parameter is not valid for this account.",
        display_name="Cooling-off Period End Date",
        shape=DateShape(),
    ),
]


def get_cooling_off_period_end_datetime(*, vault: SmartContractVault) -> datetime:
    """
    Calculates and returns the cooling-off period end datetime. This date will represent the
    midnight of the account creation datetime plus the number of days in the cooling-off period,
    inclusive of the account creation datetime.
    :param vault: Vault object for the account
    :return: the datetime when the cooling-off period ends
    """
    cooling_off_period = _get_cooling_off_period_parameter(vault=vault)
    account_creation_datetime = vault.get_account_creation_datetime()
    cooling_off_period_end = (
        account_creation_datetime + relativedelta(days=cooling_off_period)
    ).replace(hour=23, minute=59, second=59, microsecond=999999)
    return cooling_off_period_end


def is_within_cooling_off_period(
    *, vault: SmartContractVault, effective_datetime: datetime
) -> bool:
    """
    Determines whether an effective datetime is within the cooling-off period of an account

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the cooling-off period
    :return: True if the effective datetime is less than or equal to the
    cooling-off period end datetime
    """
    return effective_datetime <= get_cooling_off_period_end_datetime(vault=vault)


def _get_cooling_off_period_parameter(
    *, vault: SmartContractVault, effective_datetime: Optional[datetime] = None
) -> int:
    return int(
        utils.get_parameter(
            vault=vault, name=PARAM_COOLING_OFF_PERIOD, at_datetime=effective_datetime
        )
    )


def is_withdrawal_subject_to_fees(
    *,
    vault: SmartContractVault,
    effective_datetime: datetime,
    posting_instructions: utils.PostingInstructionListAlias,
    denomination: Optional[str] = None,
    balances: Optional[BalanceDefaultDict] = None,
) -> bool:
    """
    For use in the post_posting_hook.
    Determine if a withdrawal is subject to fees. If a full withdrawal is made during the
    cooling-off period, then no fees will be charged, otherwise the withdrawal is subject to fees.
    Deposits are not subject to fees.

    :param vault: Vault object for the account
    :param effective_datetime: datetime to be checked whether is within the cooling-off period
    :param posting_instructions: posting instructions from the post_posting_hook
    :param denomination: the denomination of the account
    :param balances: the balances to determine if it's a full withdrawal. If no balances are
    provided, live balances are used.
    :return: True if the withdrawal is subject to fees, False otherwise
    """
    if denomination is None:
        denomination = common_parameters.get_denomination_parameter(vault=vault)

    if balances is None:
        balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    is_withdrawal = utils.get_available_balance(
        balances=utils.get_posting_instructions_balances(posting_instructions=posting_instructions),
        denomination=denomination,
    ) < Decimal("0")

    # Deposits are not subject to fees.
    if not is_withdrawal:
        return False

    is_full_withdrawal = is_withdrawal and (
        utils.get_available_balance(balances=balances, denomination=denomination) == Decimal("0")
    )

    if is_full_withdrawal and is_within_cooling_off_period(
        vault=vault, effective_datetime=effective_datetime
    ):
        return False

    return True
