# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
"""
This is a contract for testing v3 vault caller, which matches the full_contract.py,
but with minor version incremented, and includes an upgrade_code hook.
"""
display_name = "Enter Contract Display Name Here"
api = "3.4.0"  # This is a V3 Smart Contract
version = "0.0.2"  # Use semantic versioning, this is explained in the overview document
summary = "Enter one line summary of contract here"
parameters = [
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Default denomination.",
        display_name="Default denomination for the contract.",
    ),
    Parameter(
        name="overdraft_limit",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01),
        level=Level.TEMPLATE,
        description="Overdraft limit",
        display_name="Maximum overdraft permitted for this account",
    ),
    Parameter(
        name="overdraft_fee",
        shape=NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=1, step=0.01),
        level=Level.TEMPLATE,
        description="Overdraft fee",
        display_name="Fee charged on balances over overdraft limit",
    ),
    Parameter(
        name="gross_interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.01),
        level=Level.TEMPLATE,
        description="Gross Interest Reate",
        display_name="Rate paid on positive balances",
    ),
    Parameter(
        name="interest_payment_day",
        level=Level.INSTANCE,
        description="Which day of the month would you like to receive interest?",
        display_name="Elected day of month to apply interest",
        shape=OptionalShape(
            NumberShape(
                min_value=1,
                max_value=28,
                step=1,
            )
        ),
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
    # Derived parameters
    Parameter(
        name="days_past_due",
        shape=NumberShape(step=Decimal(1)),
        level=Level.INSTANCE,
        derived=True,
        description="The source of truth on how many days since the DUE balance was >0",
        display_name="Days Past Due",
    ),
    Parameter(
        name="expected_end_date",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="Expected end date in the format Month/Day/Year",
        display_name="Expected end date",
    ),
]
internal_account = "1"


@requires(parameters=True)
def pre_posting_code(postings, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    if any(post.denomination != denomination for post in postings):
        raise Rejected(
            "Cannot make transactions in given denomination; "
            "transactions must be in {}".format(denomination),
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )


@requires(parameters=True, balances="latest")
def post_posting_code(postings, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    overdraft_limit = vault.get_parameter_timeseries(name="overdraft_limit").latest()
    balances = vault.get_balance_timeseries().latest()
    committed_balance = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    # We ignore authorised (PENDING_OUT) transactions and only look at settled ones (COMMITTED)
    if committed_balance < -overdraft_limit:
        # Charge the fee
        _charge_overdraft_fee(vault, effective_date + timedelta(minutes=1))


@requires(parameters=True)
def execution_schedules():
    selected_day = vault.get_parameter_timeseries(name="interest_payment_day").latest()
    interest_payday = (
        selected_day.value
        if selected_day.is_set()
        else min(vault.get_account_creation_date().day, 28)
    )
    apply_accrued_interest_schedule = {
        "day": str(interest_payday),
        "hour": "0",
        "minute": "1",
    }
    accrue_interest_schedule = {"hour": "00", "minute": "00", "second": "00"}
    return [
        ("APPLY_ACCRUED_INTEREST", apply_accrued_interest_schedule),
        ("ACCRUE_INTEREST", accrue_interest_schedule),
    ]


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="1 day")
@requires(event_type="APPLY_ACCRUED_INTEREST", parameters=True, balances="1 day")
def scheduled_code(event_type, effective_date):
    if event_type == "ACCRUE_INTEREST":
        _add_account_note(vault, event_type, effective_date)
        _accrue_interest(vault, effective_date)
    elif event_type == "APPLY_ACCRUED_INTEREST":
        _add_account_note(vault, event_type, effective_date)
        _apply_accrued_interest(vault, effective_date)


@requires(parameters=True, balances="1 day")
def derived_parameters(effective_date):

    # The logic is simplified just for testing return of derived parameter
    return {"days_past_due": Decimal("10"), "expected_end_date": "2020-12-22"}


@requires(parameters=True, balances="1 day")
def close_code(effective_date):
    _add_account_note(vault, "close_code", effective_date)

    balances = vault.get_balance_timeseries().latest()
    denomination = vault.get_parameter_timeseries(name="denomination").latest()

    if balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net != 0:
        raise Rejected(
            "Cannot close account until account balance nets to 0",
            reason_code=RejectedReason.AGAINST_TNC,
        )


def upgrade_code():
    # effective_date is not available to upgrade_code at the moment,
    # we will just set effective_date to be vault.get_account_creation_date()
    _add_account_note(vault, "upgrade_code", vault.get_account_creation_date())


def _charge_overdraft_fee(vault, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    overdraft_fee = vault.get_parameter_timeseries(name="overdraft_fee").latest()
    instruction = vault.make_internal_transfer_instructions(
        amount=overdraft_fee,
        denomination=denomination,
        from_account_id=vault.account_id,
        from_account_address=DEFAULT_ADDRESS,
        to_account_id=internal_account,
        to_account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        client_transaction_id="{}_OVERDRAFT_FEE".format(vault.get_hook_execution_id()),
        instruction_details={"description": "Overdraft fee charged"},
    )
    vault.instruct_posting_batch(
        posting_instructions=instruction,
        effective_date=effective_date,
        client_batch_id="BATCH_{}_OVERDRAFT_FEE".format(vault.get_hook_execution_id()),
    )
    vault.start_workflow(
        workflow="MOCK_FULL_CONTRACT_OVERDRAFT_FEE_NOTIFICATION",
        context={
            "account_id": vault.account_id,
            "fee_effective_date": str(effective_date.date()),
            "overdraft_fee": str(overdraft_fee),
        },
    )


def _add_account_note(vault, event_type, effective_date):
    vault.add_account_note(
        body=f"Account note {str(event_type)} - {str(effective_date)}",
        note_type=NoteType.RAW_TEXT,
        date=effective_date,
        is_visible_to_customer=True,
    )


def _accrue_interest(vault, end_of_day_datetime):
    # Get the balance at the end of the previous day
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    balances = vault.get_balance_timeseries().at(timestamp=end_of_day_datetime)
    effective_balance = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    gross_interest_rate = vault.get_parameter_timeseries(name="gross_interest_rate").before(
        timestamp=end_of_day_datetime
    )
    daily_rate = gross_interest_rate / 365
    daily_rate_percent = daily_rate * 100
    amount_to_accrue = effective_balance * daily_rate
    if amount_to_accrue > 0:
        posting_ins = vault.make_internal_transfer_instructions(
            amount=amount_to_accrue,
            denomination=denomination,
            client_transaction_id=vault.get_hook_execution_id(),
            from_account_id=internal_account,
            from_account_address="ACCRUED_OUTGOING",
            to_account_id=vault.account_id,
            to_account_address="ACCRUED_INCOMING",
            instruction_details={
                "description": "Daily interest accrued at %0.5f%% on balance of %0.2f"
                % (daily_rate_percent, effective_balance)
            },
            asset=DEFAULT_ASSET,
        )
        vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=end_of_day_datetime
        )

    vault.start_workflow(
        workflow="MOCK_INTEREST_ACCRUAL_WORKFLOW",
        context={
            "account_id": vault.account_id,
            "end_of_day_datetime": str(end_of_day_datetime.date()),
            "amount_to_accrue": str(amount_to_accrue),
        },
    )


def _apply_accrued_interest(vault, end_of_day_datetime):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    latest_bal_by_addr = vault.get_balance_timeseries().at(timestamp=end_of_day_datetime)
    incoming_accrued = latest_bal_by_addr[
        ("ACCRUED_INCOMING", DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    amount_to_be_paid = _precision_fulfillment(incoming_accrued)
    # Fulfil any incoming interest into the account
    if amount_to_be_paid > 0:
        posting_ins = vault.make_internal_transfer_instructions(
            amount=amount_to_be_paid,
            denomination=denomination,
            from_account_id=vault.account_id,
            from_account_address="ACCRUED_INCOMING",
            to_account_id=vault.account_id,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            client_transaction_id="APPLY_ACCRUED_INTEREST_{}_{}_CUSTOMER".format(
                vault.get_hook_execution_id(), denomination
            ),
            instruction_details={
                "description": "Interest Applied",
                "event": "APPLY_ACCRUED_INTEREST",
            },
        )
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=amount_to_be_paid,
                denomination=denomination,
                from_account_id=internal_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=internal_account,
                to_account_address="ACCRUED_OUTGOING",
                asset=DEFAULT_ASSET,
                client_transaction_id="APPLY_ACCRUED_INTEREST_{}_{}_INTERNAL".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Interest Applied",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )
        # only zero out accrued interest if the remainder is positive
        # (i.e. we rounded interest down)
        remainder = incoming_accrued - amount_to_be_paid
        if remainder > 0:
            posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=abs(remainder),
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address="ACCRUED_INCOMING",
                    to_account_id=internal_account,
                    to_account_address="ACCRUED_OUTGOING",
                    asset=DEFAULT_ASSET,
                    client_transaction_id="REVERSE_ACCRUE_INTEREST_{}_{}".format(
                        vault.get_hook_execution_id(), denomination
                    ),
                    instruction_details={
                        "description": "Reversing negative accrued interest after payment.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                )
            )
        # instructions to apply interest and optional reversal of remainder must be executed
        # in a batch to ensure the overall transaction is atomic
        vault.instruct_posting_batch(
            posting_instructions=posting_ins,
            effective_date=end_of_day_datetime,
            client_batch_id="APPLY_ACCRUED_INTEREST_{}_{}".format(
                vault.get_hook_execution_id(), denomination
            ),
        )


def _precision_accrual(amount):
    return amount.copy_abs().quantize(Decimal(".00001"), rounding=ROUND_HALF_UP)


def _precision_fulfillment(amount):
    return amount.copy_abs().quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


# flake8: noqa
