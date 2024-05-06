# This module implements interest accrual differently for supervisors, as they do not have
# access to optimised data fetching in scheduled_hook yet. As a result, the approach taken for
# contracts is not performant as it requires fetching a month balance timeseries in order to
# differentiate emi and non-emi interest. Instead, two separate addresses are used. This is
# identical in most scenarios, except where the due amount calculation day changes and what was
# originally emi interest becomes non-emi interest, or vice-versa. This scenario is not handled
# for supervisors.

# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.interest_accrual_common as interest_accrual_common
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ASSET,
    AccountIdShape,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Parameter,
    ParameterLevel,
    Phase,
    ScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SuperviseeContractVault,
)

ACCRUED_INTEREST_RECEIVABLE = interest_accrual_common.ACCRUED_INTEREST_RECEIVABLE
NON_EMI_ACCRUED_INTEREST_RECEIVABLE = f"NON_EMI_{ACCRUED_INTEREST_RECEIVABLE}"

# Events
ACCRUAL_EVENT = interest_accrual_common.ACCRUAL_EVENT
INTEREST_ACCRUAL_PREFIX = interest_accrual_common.INTEREST_ACCRUAL_PREFIX
PARAM_INTEREST_ACCRUAL_HOUR = interest_accrual_common.PARAM_INTEREST_ACCRUAL_HOUR
PARAM_INTEREST_ACCRUAL_MINUTE = interest_accrual_common.PARAM_INTEREST_ACCRUAL_MINUTE
PARAM_INTEREST_ACCRUAL_SECOND = interest_accrual_common.PARAM_INTEREST_ACCRUAL_SECOND
event_types = interest_accrual_common.event_types
scheduled_events = interest_accrual_common.scheduled_events

# Fetchers
data_fetchers = [fetchers.EOD_FETCHER]

# Parameters
PARAM_DAYS_IN_YEAR = interest_accrual_common.PARAM_DAYS_IN_YEAR
PARAM_ACCRUAL_PRECISION = interest_accrual_common.PARAM_ACCRUAL_PRECISION

PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "accrued_interest_receivable_account"
accrued_interest_receivable_account_param = Parameter(
    name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    level=ParameterLevel.TEMPLATE,
    description="Internal account for accrued interest receivable balance.",
    display_name="Accrued Interest Receivable Account",
    shape=AccountIdShape(),
    default_value="ACCRUED_INTEREST_RECEIVABLE",
)

schedule_parameters = interest_accrual_common.schedule_parameters
accrual_parameters = interest_accrual_common.accrual_parameters
account_parameters = [accrued_interest_receivable_account_param]


def daily_accrual_logic(
    vault: SuperviseeContractVault,
    hook_arguments: ScheduledEventHookArguments,
    next_due_amount_calculation_datetime: datetime,
    interest_rate_feature: lending_interfaces.InterestRate,
    account_type: str = "",
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
    principal_addresses: Optional[list[str]] = None,
    inflight_postings: Optional[list[CustomInstruction]] = None,
    customer_accrual_address: Optional[str] = None,
    accrual_internal_account: Optional[str] = None,
) -> list[CustomInstruction]:
    """
    Accrue receivable interest on the sum of EOD balances held at the principal addresses.
    :param vault: Vault object for the account accruing interest
    :param hook_args: scheduled event hook arguments
    :param next_due_amount_calculation_datetime: if the accrual effective date is a month or more
    away from this date, the accrued interest is considered to be non-emi
    :param interest_rate_feature: interest rate feature to get the yearly interest rate
    :param account_type: the account type for GL purposes (e.g. to identify postings pertaining to
    current accounts vs savings accounts)
    :param balances: the eod balances to use for accrual. If None, EOD_FETCHER_ID is used to
    fetch the balances.
    :param denomination: the denomination to use for accrual. If None, the latest value of the
    `denomination` parameter is used.
    :param principal_addresses: the addresses of balances to accrue on. Defaults to `PRINCIPAL`
    :param inflight_postings: Any inflight postings that are to be merged with the EOD balances,
    common use case is when interest is capitalised at the end of a repayment holiday and so the
    accrual effective balance needs to be adjusted
    :param customer_accrual_address: the address to accrue to. If None, accrual address is either:
    - NON_EMI_ACCRUED_INTEREST_RECEIVABLE, if the midnight we're accruing for is more than a month
    from the next interest calculation due date, and the interest should not be considered as part
    of EMI
    - ACCRUED_INTEREST_RECEIVABLE otherwise
    :return: The custom instructions to accrue interest, if required
    """

    midnight = hook_arguments.effective_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    principal_addresses = principal_addresses or [lending_addresses.PRINCIPAL]
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")
    if balances is None:
        balances_mapping = vault.get_balances_timeseries()
        balances = utils.get_balance_default_dict_from_mapping(
            mapping=balances_mapping,
            effective_datetime=midnight,
        )

    if inflight_postings:
        balances = utils.update_inflight_balances(
            account_id=vault.account_id,
            tside=Tside.ASSET,
            current_balances=balances,
            posting_instructions=inflight_postings,  # type: ignore
        )

    # TODO: we'll need to make this more flexible (interface?)
    effective_balance = Decimal(
        sum(
            balances[
                BalanceCoordinate(
                    principal_address, DEFAULT_ASSET, denomination, phase=Phase.COMMITTED
                )
            ].net
            for principal_address in principal_addresses
        )
    )

    # We use a separate address so that when it comes to applying interest we can use a simple
    # observation to fetch latest balances and know how much emi and non-emi interest is accrued.
    # We could also use an observation to fetch the balances as of 1 month ago, but because we can't
    # dynamically configure fetchers or specify which fetchers to use, we would need to include
    # multiple fetchers if the repayment frequency is configurable. This would defeat part of the
    # perf gain.
    # Also, we don't increase the volume of postings being made by using a different address, so the
    # impact is purely one additional balance, which is negligible, especially given we can target
    # specific addresses to be fetched
    # We use '<=' rather than '<' because the accrual on 2020-01-02 is effectively 'for' 2020-01-01
    # TODO: we will need to make the month offset more flexible when it comes to configurable
    # repayment frequency and/or EMI in advance features
    if customer_accrual_address is None:
        if midnight <= next_due_amount_calculation_datetime - relativedelta(months=1):
            customer_accrual_address = NON_EMI_ACCRUED_INTEREST_RECEIVABLE
        else:
            customer_accrual_address = ACCRUED_INTEREST_RECEIVABLE

    if accrual_internal_account is None:
        accrual_internal_account = utils.get_parameter(
            vault=vault, name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
        )

    return interest_accrual_common.daily_accrual(
        customer_account=vault.account_id,
        customer_address=customer_accrual_address,
        denomination=denomination,
        internal_account=accrual_internal_account,
        days_in_year=utils.get_parameter(vault=vault, name=PARAM_DAYS_IN_YEAR, is_union=True),
        yearly_rate=interest_rate_feature.get_annual_interest_rate(
            vault=vault,
            effective_datetime=hook_arguments.effective_datetime,
            balances=balances,
            denomination=denomination,
        ),
        effective_balance=effective_balance,
        account_type=account_type,
        event_type=hook_arguments.event_type,
        effective_datetime=midnight,
        payable=False,
        precision=utils.get_parameter(
            vault=vault, name=interest_accrual_common.PARAM_ACCRUAL_PRECISION
        ),
        rounding=ROUND_HALF_UP,
    )


def get_accrual_internal_account(vault: SuperviseeContractVault) -> str:
    accrual_internal_account: str = utils.get_parameter(
        vault=vault, name=PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT
    )
    return accrual_internal_account
