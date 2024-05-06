# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
This is a minimal contract for testing global parameters in the simulator.
It accrues interest at the central bank cash rate, which is specified as a
global parameter.
"""
display_name = "Enter Contract Display Name Here"
api = "3.10.0"
version = "0.0.1"  # Use semantic versioning, this is explained in the overview document
summary = "Demonstrates global parameters."
tside = Tside.LIABILITY
supported_denominations = ["GBP"]

DENOMINATION = "GBP"  # hard coded for brevity
TAG_ID_SUFFIX = "_TAG_ID"

# Account Addresses
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"

# Internal account
_1 = "1"

# Event schedules
ACCRUE_INTEREST = "ACCRUE_INTEREST"

event_types = [EventType(name=ACCRUE_INTEREST, scheduler_tag_ids=[ACCRUE_INTEREST + TAG_ID_SUFFIX])]

# Parameters
CASH_RATE_PARAM = "cash_rate"
global_parameters = [CASH_RATE_PARAM]


def execution_schedules():
    # hard coded for brevity
    interest_accrual_schedule = {
        "hour": "0",
        "minute": "0",
        "second": "1",
    }
    return [(ACCRUE_INTEREST, interest_accrual_schedule)]


@requires(
    event_type="ACCRUE_INTEREST",
    parameters=True,
    balances="latest",
)
def scheduled_code(event_type: str, effective_date: datetime):
    events_table = {
        ACCRUE_INTEREST: _accrue_interest,
    }
    events_table[event_type](vault, event_type, effective_date)


def _accrue_interest(vault, event_type: str, effective_date: datetime):
    bal = _get_latest_balance(vault)
    daily_rate_percent: Decimal = _get_cash_rate_as_daily_rate(vault, effective_date)
    accrued_interest: Decimal = _round_decimal(bal * daily_rate_percent)
    posting_instructions = vault.make_internal_transfer_instructions(
        amount=accrued_interest,
        denomination=DENOMINATION,
        client_transaction_id=vault.get_hook_execution_id(),
        from_account_id=_1,
        from_account_address="ACCRUED_OUTGOING",
        to_account_id=vault.account_id,
        to_account_address=ACCRUED_INTEREST_PAYABLE,
        instruction_details={
            "description": "Daily interest accrued at %0.5f%% on balance of %0.2f"
            % (daily_rate_percent, bal)
        },
        asset=DEFAULT_ASSET,
    )
    vault.instruct_posting_batch(
        posting_instructions=posting_instructions,
        client_batch_id=f"BATCH_{vault.get_hook_execution_id()}_{event_type}",
        effective_date=effective_date,
    )


def _get_latest_balance(vault) -> Decimal:
    balances = vault.get_balance_timeseries().latest()
    return balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, DENOMINATION, Phase.COMMITTED)].net


def _get_cash_rate_as_daily_rate(vault, effective_date: datetime) -> Decimal:
    # Cash rate is a global parameter!
    cash_rate = Decimal(vault.get_parameter_timeseries(name=CASH_RATE_PARAM).latest())
    return cash_rate / _get_days_in_year(effective_date.year)


def _get_days_in_year(year: int) -> int:
    return 365 + (1 if calendar.isleap(year) else 0)


def _round_decimal(
    amount: Decimal,
    decimal_places: int = 5,
    rounding=ROUND_HALF_UP,
) -> Decimal:
    """
    Round an amount to specified number of decimal places
    :param amount: Decimal, amount to round
    :param decimal_places: int, number of places to round to
    :param rounding: the type of rounding strategy to use
    :return: Decimal, rounded amount
    """
    return amount.quantize(Decimal((0, (1,), -decimal_places)), rounding=rounding)


# flake8: noqa
