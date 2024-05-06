# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
"""
This is a contract for testing vault caller, sourced from:
/projects/goldfinger/contracts/checking_account.py
"""
api = "3.9.0"
version = "1.0.4"
display_name = "Supervised US Checking Account"
summary = "An everyday US bank account with optional overdraft facility. Fees and limits apply."
tside = Tside.LIABILITY


MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)
InterestRateShape = NumberShape(
    kind=NumberKind.PERCENTAGE,
    min_value=0,
    max_value=1,
    step=0.0001,
)
FlagShape = UnionShape(
    UnionItem(key="YES", display_name="Yes"), UnionItem(key="NO", display_name="No")
)

event_types = [
    EventType(name="CHECK_MAINTENANCE_FEE"),
    EventType(name="APPLY_ACCRUED_OVERDRAFT_FEES"),
    EventType(name="PUBLISH_EXTRACT"),
]


parameters = [
    # INSTANCE
    Parameter(
        name="overdraft_limit",
        level=Level.INSTANCE,
        description="Cap on the amount the account is able to go overdrawn",
        display_name="Overdraft limit",
        update_permission=UpdatePermission.OPS_EDITABLE,
        shape=MoneyShape,
        default_value=Decimal("1000.00"),
    ),
    Parameter(
        name="debit_card_coverage",
        level=Level.INSTANCE,
        description="Should debit card transactions be allowed when the account is overdrawn?",
        display_name="Debit card overdraft coverage",
        shape=FlagShape,
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=UnionItemValue(key="YES"),
    ),
    Parameter(
        name="maintenance_fee_check_day",
        level=Level.INSTANCE,
        description="Day of the month upon which to check and apply maintenance fee",
        display_name="Maintenance fee check day",
        shape=NumberShape(
            min_value=1,
            max_value=28,
            step=1,
        ),
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=Decimal("28"),
    ),
    # TEMPLATE
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="What denomination should the account use?",
        display_name="Denomination",
        update_permission=UpdatePermission.FIXED,
        default_value="USD",
    ),
    Parameter(
        name="maintenance_fee",
        level=Level.TEMPLATE,
        description="Monthly maintenance fee",
        display_name="Maintenance fee",
        shape=MoneyShape,
        default_value=Decimal("10.00"),
    ),
    Parameter(
        name="internal_maintenance_fee_account",
        shape=AccountIdShape,
        level=Level.TEMPLATE,
        description="Which internal account should the maintenance fee be paid into?",
        display_name="Internal fee account",
        default_value="1",
    ),
    Parameter(
        name="minimum_daily_checking_balance",
        level=Level.TEMPLATE,
        description="Minimum daily checking balance to not incur maintenance fee",
        display_name="Minimum daily checking balance",
        shape=MoneyShape,
        default_value=Decimal("1500.00"),
    ),
    Parameter(
        name="minimum_combined_balance",
        level=Level.TEMPLATE,
        description="Minimum combined balance of related accounts to not incur maintenance fee",
        display_name="Minimum combined accounts balance",
        shape=MoneyShape,
        default_value=Decimal("5000.00"),
    ),
    Parameter(
        name="minimum_monthly_deposit",
        level=Level.TEMPLATE,
        description="Minimum monthly direct deposit to not incur maintenance fee",
        display_name="Minimum monthly deposit",
        shape=MoneyShape,
        default_value=Decimal("500.00"),
    ),
    Parameter(
        name="overdraft_fee",
        level=Level.TEMPLATE,
        description="The per transaction charge when the account is overdrawn",
        display_name="Overdraft fee",
        shape=MoneyShape,
        default_value=Decimal("10.00"),
    ),
    Parameter(
        name="internal_overdraft_fee_account",
        shape=AccountIdShape,
        level=Level.TEMPLATE,
        description="Which internal account should the overdraft fee be paid into?",
        display_name="Internal overdraft fee account",
        default_value="1",
    ),
    Parameter(
        name="overdraft_fee_accrual",
        level=Level.TEMPLATE,
        description="Should overdraft fees accrue during the day and be applied at EOD?",
        display_name="Overdraft fee accrual (apply EOD)",
        shape=FlagShape,
        default_value=UnionItemValue(key="NO"),
    ),
    Parameter(
        name="overdraft_buffer",
        level=Level.TEMPLATE,
        description="The amount the account can be overdrawn without incurring a fee",
        display_name="Overdraft buffer",
        shape=MoneyShape,
        default_value=Decimal("0.00"),
    ),
]


OVERDRAFT_FEE = "OVERDRAFT_FEE"

contract_module_imports = [
    ContractModule(
        alias="interest",
        expected_interface=[
            SharedFunction(
                name="get_parameter",
                args=[
                    SharedFunctionArg(name="vault"),
                    SharedFunctionArg(name="name"),
                    SharedFunctionArg(name="at"),
                    SharedFunctionArg(name="is_json"),
                    SharedFunctionArg(name="optional"),
                    SharedFunctionArg(name="default_value"),
                ],
            ),
        ],
    )
]


@requires(
    parameters=True,
    modules=["interest"],
)
def execution_schedules():
    maintenance_fee_check_day = vault.modules["interest"].get_parameter(
        vault, "maintenance_fee_check_day"
    )
    apply_accrued_overdraft_fees_schedule = {"hour": "23", "minute": "50"}
    check_maintenance_fee_schedule = {
        "day": str(maintenance_fee_check_day),
        "hour": "23",
        "minute": "55",
    }
    publish_extract_schedule = {"hour": "23", "minute": "59", "second": "0"}
    return [
        ("APPLY_ACCRUED_OVERDRAFT_FEES", apply_accrued_overdraft_fees_schedule),
        ("CHECK_MAINTENANCE_FEE", check_maintenance_fee_schedule),
        ("PUBLISH_EXTRACT", publish_extract_schedule),
    ]


@requires(
    event_type="APPLY_ACCRUED_OVERDRAFT_FEES",
    parameters=True,
    balances="1 day live",
    modules=["interest"],
)
@requires(
    event_type="CHECK_MAINTENANCE_FEE",
    parameters=True,
    balances="1 month",
    postings="1 month",
    modules=["interest"],
)
@requires(
    event_type="PUBLISH_EXTRACT",
    parameters=True,
    balances="1 day live",
    last_execution_time=["PUBLISH_EXTRACT"],
    postings="2 days",
    modules=["interest"],
)
def scheduled_code(event_type, effective_date):
    if event_type == "APPLY_ACCRUED_OVERDRAFT_FEES":
        _apply_accrued_overdraft_fees(vault, effective_date)
    elif event_type == "CHECK_MAINTENANCE_FEE":
        _check_maintenance_fee(vault, effective_date)
    elif event_type == "PUBLISH_EXTRACT":
        _publish_extract(vault, effective_date)


@requires(parameters=True, last_execution_time=["CHECK_MAINTENANCE_FEE"])
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if _has_parameter_value_changed("maintenance_fee_check_day", old_parameters, new_parameters):
        schedule_time = {"hour": "23", "minute": "55"}

        new_schedule = {
            "day": str(new_parameters.get("maintenance_fee_check_day")),
            **schedule_time,
        }

        vault.amend_schedule(event_type="CHECK_MAINTENANCE_FEE", new_schedule=new_schedule)


@requires(parameters=True, balances="latest live", modules=["interest"])
def pre_posting_code(postings, effective_date):
    denomination = vault.modules["interest"].get_parameter(vault, "denomination")
    overdraft_limit = vault.modules["interest"].get_parameter(vault, "overdraft_limit")

    balances = vault.get_balance_timeseries().latest()
    latest_outgoing_available_balance = _get_available_balance(balances, denomination)
    proposed_amount = sum(
        (1 if post.credit else -1) * post.amount
        for post in postings
        if post.account_address == DEFAULT_ADDRESS
    )
    if any(post.denomination != denomination for post in postings):
        raise Rejected(
            f"Cannot make transactions in given denomination; "
            f"transactions must be in {denomination}",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )
    proposed_outgoing_balance = latest_outgoing_available_balance + proposed_amount
    if proposed_outgoing_balance < -overdraft_limit:
        raise Rejected(
            "Posting would exceed overdraft limit.",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


@requires(parameters=True, balances="1 day", modules=["interest"])
def post_posting_code(postings, effective_date):
    denomination = vault.modules["interest"].get_parameter(vault, "denomination")
    overdraft_buffer = vault.modules["interest"].get_parameter(vault, "overdraft_buffer")
    overdraft_fee = Decimal(vault.modules["interest"].get_parameter(vault, "overdraft_fee"))
    overdraft_fee_accrual = vault.modules["interest"].get_parameter(vault, "overdraft_fee_accrual")
    internal_overdraft_fee_account = vault.modules["interest"].get_parameter(
        vault, "internal_overdraft_fee_account"
    )

    # Balances before latest posting
    balances = vault.get_balance_timeseries().at(timestamp=effective_date + timedelta(seconds=-1))

    # Consider existing COMMITTED and PENDING OUT funds
    effective_available_balance = _get_available_balance(balances, denomination)
    # Do not charge overdraft fee on new PENDING OUT posting
    posting_amount = postings.balances()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    outgoing_available_balance = effective_available_balance + posting_amount

    if posting_amount < 0 and outgoing_available_balance < -overdraft_buffer:
        posting_ins = []
        if overdraft_fee_accrual.key == "YES":
            posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=overdraft_fee,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address=OVERDRAFT_FEE,
                    to_account_id=internal_overdraft_fee_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"ACCRUE_OVERDRAFT_FEE_{vault.get_hook_execution_id()}"
                    f"_{denomination}",
                    instruction_details={
                        "description": "Accrue overdraft fee",
                        "event": "ACCRUE_OVERDRAFT_FEE",
                    },
                )
            )
        else:
            posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=overdraft_fee,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=internal_overdraft_fee_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"APPLY_OVERDRAFT_FEE_{vault.get_hook_execution_id()}"
                    f"_{denomination}",
                    instruction_details={
                        "description": "Apply overdraft fee",
                        "event": "APPLY_OVERDRAFT_FEE",
                    },
                )
            )
        if posting_ins:
            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )


@requires(parameters=True, balances="latest")
def close_code(effective_date):
    _apply_accrued_overdraft_fees(vault, effective_date)


def _apply_accrued_overdraft_fees(vault, effective_date):
    denomination = vault.modules["interest"].get_parameter(vault, "denomination")
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    overdraft_fee_balance = balances[
        (OVERDRAFT_FEE, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    if overdraft_fee_balance < 0:
        overdraft_buffer = vault.modules["interest"].get_parameter(vault, "overdraft_buffer")
        internal_overdraft_fee_account = vault.modules["interest"].get_parameter(
            vault, "internal_overdraft_fee_account"
        )
        # Consider COMMITTED and PENDING OUT funds
        effective_available_balance = _get_available_balance(balances, denomination)

        posting_ins = []
        # Check if overdraft is still in use
        if effective_available_balance < -overdraft_buffer:
            overdraft_fee_fulfillment = _precision_fulfillment(overdraft_fee_balance)
            if overdraft_fee_fulfillment > 0:
                posting_ins.extend(
                    vault.make_internal_transfer_instructions(
                        amount=overdraft_fee_fulfillment,
                        denomination=denomination,
                        from_account_id=vault.account_id,
                        from_account_address=DEFAULT_ADDRESS,
                        to_account_id=vault.account_id,
                        to_account_address=OVERDRAFT_FEE,
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                        pics=[],
                        client_transaction_id=f"APPLY_ACCRUED_OVERDRAFT_FEES_"
                        f"{vault.get_hook_execution_id()}_{denomination}"
                        f"_CUSTOMER",
                        instruction_details={
                            "description": "Apply accrued overdraft fees",
                            "event": "APPLY_ACCRUED_OVERDRAFT_FEES",
                        },
                    )
                )
        else:
            posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=-overdraft_fee_balance,
                    denomination=denomination,
                    from_account_id=internal_overdraft_fee_account,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=vault.account_id,
                    to_account_address=OVERDRAFT_FEE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"REVERSE_ACCRUED_OVERDRAFT_FEES_"
                    f"{vault.get_hook_execution_id()}_{denomination}",
                    instruction_details={
                        "description": "Reverse accrued overdraft fees",
                        "event": "APPLY_ACCRUED_OVERDRAFT_FEES",
                    },
                )
            )
        if posting_ins:
            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )


def _check_maintenance_fee(vault, effective_date):
    # Check for either maintenance fee waivers:
    # 1. EOD balance consistently greater than $1500 in month (parameter)
    # 2. Total deposits in month greater than $1000 (parameter)
    maintenance_fee = Decimal(
        vault.modules["interest"].get_parameter(vault, "maintenance_fee", effective_date)
    )

    if maintenance_fee > 0:
        denomination = vault.modules["interest"].get_parameter(
            vault, "denomination", effective_date
        )
        minimum_daily_balance = vault.modules["interest"].get_parameter(
            vault, "minimum_daily_checking_balance", effective_date
        )
        minimum_monthly_deposit = vault.modules["interest"].get_parameter(
            vault, "minimum_monthly_deposit", effective_date
        )
        internal_maintenance_fee_account = vault.modules["interest"].get_parameter(
            vault, "internal_maintenance_fee_account", effective_date
        )

        minimum_daily_balance_breached = False
        minimum_monthly_deposit_breached = False
        balance_timeseries = vault.get_balance_timeseries()

        account_creation_date = vault.get_account_creation_date()
        start_date = effective_date - timedelta(months=1, hour=23, minute=55)
        if start_date < account_creation_date:
            start_date = account_creation_date + timedelta(hour=23, minute=55)

        for end_of_day in _daterange(start_date, effective_date + timedelta(days=1)):
            end_of_day_balances = balance_timeseries.at(timestamp=end_of_day)
            committed_end_of_day_balances = end_of_day_balances[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ].net
            pending_out_end_of_day_balances = end_of_day_balances[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
            ].net
            checking_end_of_day_balance = (
                committed_end_of_day_balances + pending_out_end_of_day_balances
            )
            if checking_end_of_day_balance < minimum_daily_balance:
                minimum_daily_balance_breached = True
                break

        if minimum_daily_balance_breached:
            client_month_transactions = vault.get_client_transactions()
            if (
                _sum_client_transactions(client_month_transactions, denomination)
                < minimum_monthly_deposit
            ):
                minimum_monthly_deposit_breached = True

        if minimum_daily_balance_breached and minimum_monthly_deposit_breached:
            vault.instruct_posting_batch(
                posting_instructions=vault.make_internal_transfer_instructions(
                    amount=maintenance_fee,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=internal_maintenance_fee_account,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"MONTHLY_MAINTENANCE_FEE_"
                    f"{vault.get_hook_execution_id()}"
                    f"_{denomination}",
                    instruction_details={
                        "description": "Maintenance fee applied",
                        "event": "MAINTENANCE_FEE",
                    },
                ),
                effective_date=effective_date,
            )


def _publish_extract(vault, effective_date):
    denomination = vault.modules["interest"].get_parameter(vault, "denomination", effective_date)
    balance_timeseries = vault.get_balance_timeseries()

    last_extract_exec = vault.get_last_execution_time(event_type="PUBLISH_EXTRACT")
    if last_extract_exec:
        end_of_last_extract = last_extract_exec
    else:
        end_of_last_extract = vault.get_account_creation_date()

    batches = vault.get_posting_batches() or []
    pib_data = {
        str(pib.value_timestamp): [
            pib.batch_id,
            "%0.2f" % _get_altered_balance(pib.balances(), denomination),
            "%0.2f"
            % _get_phase_balance(
                balance_timeseries.at(timestamp=pib.value_timestamp), denomination
            ),
        ]
        for pib in batches
        if end_of_last_extract <= pib.value_timestamp < effective_date
    }

    opening_balances = balance_timeseries.at(timestamp=end_of_last_extract)
    opening_committed_bal = _get_phase_balance(opening_balances, denomination)
    closing_balances = balance_timeseries.at(timestamp=effective_date)
    closing_available_bal = _get_available_balance(closing_balances, denomination)
    closing_committed_bal = _get_phase_balance(closing_balances, denomination)
    closing_pending_in_bal = _get_phase_balance(closing_balances, denomination, Phase.PENDING_IN)
    closing_pending_out_bal = _get_phase_balance(closing_balances, denomination, Phase.PENDING_OUT)

    vault.start_workflow(
        workflow="PUBLISH_EXTRACT_DATA",
        context={
            "account_id": str(vault.account_id),
            "extract_date": str(effective_date),
            "available_balance": "%0.2f" % closing_available_bal,
            "opening_balance": "%0.2f" % opening_committed_bal,
            "closing_balance": "%0.2f" % closing_committed_bal,
            "pending_in_balance": "%0.2f" % closing_pending_in_bal,
            "pending_out_balance": "%0.2f" % closing_pending_out_bal,
            "extract_data": str(pib_data).replace('"', '\\"').replace("'", '"'),
        },
    )


def _sum_client_transactions(client_transactions, denomination):
    # Sum all deposit transactions for all given client_transactions
    total_deposit = sum(
        client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
        for client_txn in client_transactions.values()
        if client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled > 0
    )
    return total_deposit


def _daterange(start_date, end_date):
    # Generator function for producing a range of dates
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(days=n)


def _get_available_balance(balances, denomination):
    committed_balance_net = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    # Pending out is -ve
    pending_out_balance_net = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
    ].net
    return committed_balance_net + pending_out_balance_net


def _get_phase_balance(balances, denomination, phase=Phase.COMMITTED):
    return balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, phase)].net


def _get_altered_balance(balances, denomination):
    return sum(
        balance.net
        for ((address, asset, denom, phase), balance) in balances.items()
        if asset == DEFAULT_ASSET and denom == denomination
    )


def _yearly_to_daily_rate(yearly_rate):
    days_in_year = 365
    return yearly_rate / days_in_year


def _precision_accrual(amount):
    return amount.copy_abs().quantize(Decimal(".00001"), rounding=ROUND_HALF_UP)


def _precision_fulfillment(amount):
    return amount.copy_abs().quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def _has_parameter_value_changed(parameter_name, old_parameter_values, updated_parameter_values):
    """
    Determines if a parameter has changed. To be used within post-parameter change hook
    :param parameter_name: str, name of the parameter
    :param old_parameter_values: dict, map of parameter name -> old parameter value
    :param updated_parameter_values: dict, map of parameter name -> new parameter value
    :return: bool, True if parameter value has changed, False otherwise
    """

    if parameter_name not in updated_parameter_values:
        return False

    if old_parameter_values[parameter_name] == updated_parameter_values[parameter_name]:
        return False

    return True


# flake8: noqa
