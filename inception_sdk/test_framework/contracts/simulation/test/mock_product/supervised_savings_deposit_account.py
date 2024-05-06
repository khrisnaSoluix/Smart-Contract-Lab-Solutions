# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
"""
This is a contract for testing vault caller, sourced from:
/projects/goldfinger/contracts/savings_deposit_account.py
"""
api = "3.4.0"
version = "1.0.4"
display_name = "Supervised US Savings Deposit Account"
summary = "Savings Deposit Account: A bank account that lets you put money away and receive interest on the balance. The balance is instantly accessible when you need to withdraw money. This account includes monthly transaction limits."
tside = Tside.LIABILITY


LimitsShape = NumberShape(
    kind=NumberKind.MONEY,
    min_value=0,
    step=0.01,
)

MoneyShape = NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=10000, step=0.01)

InterestRateShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.0001)

event_types = [
    EventType(name="ACCRUE_INTEREST"),
    EventType(name="APPLY_ACCRUED_INTEREST"),
    EventType(name="CHECK_MAINTENANCE_FEE"),
    EventType(name="PUBLISH_EXTRACT"),
]

parameters = [
    Parameter(
        name="interest_application_day",
        level=Level.INSTANCE,
        description="The day of the month upon which interest is paid. By default you'll get paid on the same day of the month as the account open date.",
        display_name="Elected day of month to pay interest on",
        shape=NumberShape(
            min_value=1,
            max_value=28,
            step=1,
        ),
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=Decimal("28"),
    ),
    Parameter(
        name="linked_current_account",
        level=Level.INSTANCE,
        description="Linked current account if this account is used as offset overdraft account. Requires the linked current account to also be linked to this account",
        display_name="Linked current account",
        shape=OptionalShape(AccountIdShape),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue("00000000-0000-0000-0000-000000000000"),
    ),
    Parameter(
        name="promotion_start_date",
        level=Level.INSTANCE,
        description="Promotional rate start date. The promotional rate is applied on this day, and on subsequent days",
        display_name="Promotional rate start date (inclusive)",
        shape=OptionalShape(
            DateShape(
                min_date=datetime.min,
                max_date=datetime.max,
            )
        ),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(datetime.min),
    ),
    Parameter(
        name="promotion_end_date",
        level=Level.INSTANCE,
        description="Promotional rate end date. The promotional rate is applied up to, but not including, this day",
        display_name="Promotional rate end date (exclusive)",
        shape=OptionalShape(
            DateShape(
                min_date=datetime.min,
                max_date=datetime.max,
            )
        ),
        update_permission=UpdatePermission.OPS_EDITABLE,
        default_value=OptionalValue(datetime.min),
    ),
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
        name="monthly_transaction_notification_limit",
        level=Level.TEMPLATE,
        description="The number of monthly transactions allowed before a notification is sent",
        display_name="Monthly transactions allowed before notification",
        shape=NumberShape(
            min_value=1,
            max_value=100,
            step=1,
        ),
        default_value=Decimal("4"),
    ),
    Parameter(
        name="monthly_transaction_soft_limit",
        level=Level.TEMPLATE,
        description="The number of monthly transactions allowed before charges apply",
        display_name="Monthly transactions soft limit before charges",
        shape=NumberShape(
            min_value=1,
            max_value=100,
            step=1,
        ),
        default_value=Decimal("5"),
    ),
    Parameter(
        name="monthly_transaction_hard_limit",
        level=Level.TEMPLATE,
        description="The maximum number of transactions allowed in a given month (hard limit)",
        display_name="Monthly transaction hard limit",
        shape=NumberShape(
            min_value=1,
            max_value=100,
            step=1,
        ),
        default_value=Decimal("6"),
    ),
    Parameter(
        name="monthly_transaction_charge",
        level=Level.TEMPLATE,
        description="The per transaction charge when over the monthly transaction soft limit",
        display_name="Transaction charge",
        shape=NumberShape(
            min_value=1,
            max_value=100,
            step=1,
        ),
        default_value=Decimal("15"),
    ),
    # Parameter(
    #     name='gross_interest_rate',
    #     level=Level.TEMPLATE,
    #     description='Gross interest rate',
    #     display_name='Gross interest rate',
    #     shape=InterestRateShape,
    #     default_value=Decimal('0.0149')
    # ),
    Parameter(
        name="gross_interest_rate_tiers",
        level=Level.TEMPLATE,
        description="Gross interest rate tiered by customer status",
        display_name="Gross interest rate tiers",
        shape=StringShape,
        default_value=json_dumps(
            {
                "customer_tier_high": "0.15",
                "customer_tier_medium": "0.10",
                "customer_tier_low": "0.01",
                "DEFAULT": "0.01",
            }
        ),
    ),
    Parameter(
        name="check_hold_percentage_tiers",
        level=Level.TEMPLATE,
        description="Check hold percentage tiered by customer status",
        display_name="Check hold percentage tiers",
        shape=StringShape,
        default_value=json_dumps(
            {
                "customer_tier_high": "0.40",
                "customer_tier_medium": "0.50",
                "customer_tier_low": "0.60",
                "DEFAULT": "0.60",
            }
        ),
    ),
    Parameter(
        name="minimum_deposit",
        level=Level.TEMPLATE,
        description="Minimum amount for a single deposit.",
        display_name="Minimum deposit amount",
        shape=MoneyShape,
        default_value=Decimal("0.01"),
    ),
    Parameter(
        name="maximum_balance",
        level=Level.TEMPLATE,
        description="Maximum balance amount.",
        display_name="Maximum balance amount",
        shape=LimitsShape,
        default_value=Decimal("100000"),
    ),
    Parameter(
        name="maximum_daily_deposit",
        level=Level.TEMPLATE,
        description="Maximum daily deposit amount.",
        display_name="Maximum daily deposit amount",
        shape=LimitsShape,
        default_value=Decimal("2000"),
    ),
    Parameter(
        name="maximum_daily_withdrawal",
        level=Level.TEMPLATE,
        description="Maximum daily withdrawal amount.",
        display_name="Maximum daily withdrawal amount",
        shape=LimitsShape,
        default_value=Decimal("1000"),
    ),
    Parameter(
        name="minimum_withdrawal",
        level=Level.TEMPLATE,
        description="Minimum amount for a single withdrawal",
        display_name="Minimum withdrawal amount",
        shape=LimitsShape,
        default_value=Decimal("0.01"),
    ),
    Parameter(
        name="promotion_rate",
        level=Level.TEMPLATE,
        description="Promotional bonus interest rate",
        display_name="Promotion interest rate",
        shape=InterestRateShape,
        default_value=Decimal("0.15"),
    ),
]

PNL_ACCOUNT = "1"
HARD_TRANSACTION_LIMIT_TYPE = "Hard Transaction Limit"
SOFT_TRANSACTION_LIMIT_TYPE = "Soft (Charge) Transaction Limit"
NOTIFICATION_TRANSACTION_LIMIT_TYPE = "Notification Transaction Limit"


@requires(parameters=True)
def execution_schedules():
    interest_application_day = vault.get_parameter_timeseries(
        name="interest_application_day"
    ).latest()
    # start_date = vault.get_account_creation_date()
    # enddate = start_date + timedelta(hours=1)

    return (
        ("ACCRUE_INTEREST", {"hour": "0"}),
        (
            "APPLY_ACCRUED_INTEREST",
            {"day": str(interest_application_day), "hour": "0", "minute": "1"},
        ),
        ("CHECK_MAINTENANCE_FEE", {"day": "28", "hour": "23", "minute": "55"}),
        (
            "PUBLISH_EXTRACT",
            {
                "hour": "23",
                "minute": "59",
                "second": "0"
                # 'minute': '*/2',
                # 'second': '0',
                # 'end_date': str(enddate)
            },
        ),
    )


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="1 day", flags=True)
@requires(event_type="APPLY_ACCRUED_INTEREST", parameters=True, balances="1 day")
@requires(
    event_type="CHECK_MAINTENANCE_FEE",
    parameters=True,
    balances="1 month",
    postings="1 month",
)
@requires(
    event_type="PUBLISH_EXTRACT",
    parameters=True,
    balances="1 day live",
    last_execution_time=["PUBLISH_EXTRACT"],
    postings="2 days",
)
def scheduled_code(event_type, effective_date):
    if event_type == "ACCRUE_INTEREST":
        end_of_day = effective_date - timedelta(microseconds=1)
        _accrue_interest(vault, end_of_day)
    elif event_type == "APPLY_ACCRUED_INTEREST":
        start_of_day = datetime(
            year=effective_date.year, month=effective_date.month, day=effective_date.day
        )
        _apply_accrued_interest(vault, start_of_day)
    elif event_type == "CHECK_MAINTENANCE_FEE":
        # Handled in supervisor
        pass
    elif event_type == "PUBLISH_EXTRACT":
        _publish_extract(vault, effective_date)


@requires(parameters=True, last_execution_time=["APPLY_ACCRUED_INTEREST"])
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if _has_parameter_value_changed("interest_application_day", old_parameters, new_parameters):
        schedule_time = {"hour": "0", "minute": "1"}

        new_schedule = {
            "day": str(new_parameters.get("interest_application_day")),
            **schedule_time,
        }

        vault.amend_schedule(event_type="APPLY_ACCRUED_INTEREST", new_schedule=new_schedule)


@requires(parameters=True, balances="latest live", postings="1 month")
def pre_posting_code(postings, effective_date):
    # Allow overriding any contract restrictions
    if postings.batch_details.get("withdrawal_override") == "true":
        return

    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    balances = vault.get_balance_timeseries().latest()

    max_balance = vault.get_parameter_timeseries(name="maximum_balance").latest()
    minimum_deposit = vault.get_parameter_timeseries(name="minimum_deposit").latest()
    maximum_daily_deposit = vault.get_parameter_timeseries(name="maximum_daily_deposit").latest()
    minimum_withdrawal = vault.get_parameter_timeseries(name="minimum_withdrawal").latest()
    maximum_daily_withdrawal = vault.get_parameter_timeseries(
        name="maximum_daily_withdrawal"
    ).latest()
    monthly_transaction_hard_limit = vault.get_parameter_timeseries(
        name="monthly_transaction_hard_limit"
    ).latest()
    latest_outgoing_available_balance = sum(
        balance.net
        for ((address, asset, denom, phase), balance) in balances.items()
        if address == DEFAULT_ADDRESS
        and asset == DEFAULT_ASSET
        and phase != Phase.PENDING_IN
        and denom == denomination
    )

    latest_incoming_available_balance = sum(
        balance.net
        for ((address, asset, denom, phase), balance) in balances.items()
        if address == DEFAULT_ADDRESS
        and asset == DEFAULT_ASSET
        and phase != Phase.PENDING_OUT
        and denom == denomination
    )
    proposed_amount = sum(
        (1 if post.credit else -1) * post.amount
        for post in postings
        if post.account_address == DEFAULT_ADDRESS
    )

    # Validate denomination
    if postings[0].denomination != denomination:
        raise Rejected(
            "Cannot make transactions in given denomination; "
            "transactions must be in {}".format(denomination),
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )

    # Check proposed balance is positive or at least more than the current balance
    proposed_outgoing_balance = latest_outgoing_available_balance + proposed_amount
    if (
        proposed_outgoing_balance < 0
        and proposed_outgoing_balance < latest_outgoing_available_balance
    ):
        raise Rejected(
            "Insufficient funds for transaction.",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )

    # Check proposed balance is less than max allowed balance or at least less than current balance
    proposed_incoming_balance = latest_incoming_available_balance + proposed_amount
    if (
        proposed_incoming_balance > max_balance
        and proposed_incoming_balance > latest_incoming_available_balance
    ):
        raise Rejected(
            "Posting would cause the maximum balance to be exceeded.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    # track and limit transactions in month, ignoring interest and fee accrual applications
    client_transactions = vault.get_client_transactions()
    if (
        _count_client_transactions(client_transactions, denomination)
        > monthly_transaction_hard_limit
    ):
        raise Rejected(
            "Hard limit of allowed client transactions in 1 month for the account reached",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    for posting in postings:
        client_transaction = client_transactions.get(
            (posting.client_id, posting.client_transaction_id)
        )
        amount_authed = max(
            abs(
                client_transaction.effects()[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
                ].authorised
                - client_transaction.effects()[
                    (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
                ].released
            ),
            abs(
                client_transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
            ),
        )
        # amount_deposit is +ve. amount_withdrawal is -ve.
        amount_deposit, amount_withdrawal = _sum_without_current_client_trans(
            client_transactions,
            posting.client_transaction_id,
            datetime.combine(effective_date, datetime.min.time()),
            denomination,
        )
        # Check limits for single transaction
        if not posting.credit:  # It's an outgoing posting
            if posting.amount < minimum_withdrawal:
                raise Rejected(
                    "Transaction amount is less than the minimum withdrawal amount %s %s."
                    % (minimum_withdrawal, denomination),
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            # Check daily withdrawal limit
            if amount_authed - amount_withdrawal > maximum_daily_withdrawal:
                raise Rejected(
                    f"Transaction would cause the maximum daily withdrawal limit of "
                    f"{maximum_daily_withdrawal} {denomination} to be exceeded.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
        if posting.credit:
            if posting.amount < minimum_deposit:
                raise Rejected(
                    f"Transaction amount is less than the minimum deposit amount "
                    f"{minimum_deposit} {denomination}.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )
            # Check daily deposit limit
            if abs(amount_deposit + amount_authed) > maximum_daily_deposit:
                raise Rejected(
                    f"Transaction would cause the maximum daily deposit limit of "
                    f"{maximum_daily_deposit} {denomination} to be exceeded.",
                    reason_code=RejectedReason.AGAINST_TNC,
                )


@requires(parameters=True, balances="latest", postings="1 month", flags=True)
def post_posting_code(postings, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    monthly_transaction_hard_limit = vault.get_parameter_timeseries(
        name="monthly_transaction_hard_limit"
    ).latest()
    monthly_transaction_soft_limit = vault.get_parameter_timeseries(
        name="monthly_transaction_soft_limit"
    ).latest()
    monthly_transaction_notification_limit = vault.get_parameter_timeseries(
        name="monthly_transaction_notification_limit"
    ).latest()
    monthly_transaction_charge = vault.get_parameter_timeseries(
        name="monthly_transaction_charge"
    ).latest()

    # charge withdrawal transaction fee if charge limit exceeded and send appropriate notifications
    client_transactions = vault.get_client_transactions()
    client_transactions_count = _count_client_transactions(client_transactions, denomination)
    last_client_transaction = client_transactions.get(
        (postings[0].client_id, postings[0].client_transaction_id)
    )
    last_client_txn_amount = last_client_transaction.effects()[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
    ].settled
    if client_transactions_count > monthly_transaction_soft_limit and last_client_txn_amount < 0:
        posting_ins = vault.make_internal_transfer_instructions(
            amount=monthly_transaction_charge,
            denomination=denomination,
            from_account_id=vault.account_id,
            from_account_address="TRANSACTION_FEE",
            to_account_id=PNL_ACCOUNT,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            pics=[],
            client_transaction_id="APPLY_TRANSACTION_FEE_{}_{}_INTERNAL".format(
                vault.get_hook_execution_id(), denomination
            ),
            instruction_details={
                "description": "Transaction fee applied",
                "event": "ACCRUE_FEES",
            },
        )
        vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=effective_date
        )
        # generate workflow notification - customer has been charged
        vault.start_workflow(
            workflow="NOTIFY_TRANSACTION_LIMIT_REACHED",
            context={
                "account_id": str(vault.account_id),
                "limit_type": SOFT_TRANSACTION_LIMIT_TYPE,
                "limit": str(monthly_transaction_soft_limit),
                "value": str(client_transactions_count),
                "message": "Alert: Monthly withdrawal transaction limit reached - charges have been"
                " applied",
            },
        )
    elif (
        client_transactions_count > monthly_transaction_notification_limit
        and last_client_txn_amount < 0
    ):
        # generate workflow notification - customer near to exceeding limit
        vault.start_workflow(
            workflow="NOTIFY_TRANSACTION_LIMIT_REACHED",
            context={
                "account_id": str(vault.account_id),
                "limit_type": NOTIFICATION_TRANSACTION_LIMIT_TYPE,
                "limit": str(monthly_transaction_notification_limit),
                "value": str(client_transactions_count),
                "message": "Warning: Close to exceeding monthly withdrawal transaction limit, "
                "charges will be applied for the next transaction",
            },
        )

    # Make mirror posting of posting instruction batch from savings.reverse_mirror to current.savings_register
    linked_current_account_param = vault.get_parameter_timeseries(name="linked_current_account").at(
        timestamp=effective_date
    )
    pib_net_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net
    if _valid_linked_account(linked_current_account_param) and abs(pib_net_amount) > 0:
        if pib_net_amount > 0:
            vault.instruct_posting_batch(
                posting_instructions=vault.make_internal_transfer_instructions(
                    amount=pib_net_amount,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address="SAVINGS_REGISTER",
                    to_account_id=linked_current_account_param.value,
                    to_account_address="SAVINGS_REGISTER",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"SAVINGS_BALANCE_REGISTER_"
                    f"{vault.get_hook_execution_id()}",
                    instruction_details={
                        "description": f"Updating savings account mirror for PIB {postings.client_batch_id}",
                        "event": "SAVINGS_REGISTER",
                    },
                ),
                effective_date=effective_date,
            )
        else:
            vault.instruct_posting_batch(
                posting_instructions=vault.make_internal_transfer_instructions(
                    amount=abs(pib_net_amount),
                    denomination=denomination,
                    from_account_id=linked_current_account_param.value,
                    from_account_address="SAVINGS_REGISTER",
                    to_account_id=vault.account_id,
                    to_account_address="SAVINGS_REGISTER",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    pics=[],
                    client_transaction_id=f"SAVINGS_BALANCE_REGISTER_"
                    f"{vault.get_hook_execution_id()}",
                    instruction_details={
                        "description": f"Updating savings account mirror for PIB {postings.client_batch_id}",
                        "event": "SAVINGS_REGISTER",
                    },
                ),
                effective_date=effective_date,
            )


@requires(parameters=True, balances="latest")
def close_code(effective_date):
    _apply_accrued_interest(vault, effective_date)


def _accrue_interest(vault, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    effective_balance = (
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
        + balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)].net
    )

    if effective_balance <= 0:
        return

    promotion_start_date = _get_param_value(vault, "promotion_start_date")
    promotion_end_date = _get_param_value(vault, "promotion_end_date")
    if _check_if_in_promotion_window(effective_date, promotion_start_date, promotion_end_date):
        gross_interest_rate = vault.get_parameter_timeseries(name="promotion_rate").at(
            timestamp=effective_date
        )
    else:
        gross_interest_rate_tiers = json_loads(
            vault.get_parameter_timeseries(name="gross_interest_rate_tiers").at(
                timestamp=effective_date
            )
        )
        gross_interest_rate = _get_customer_interest_rate(
            vault, gross_interest_rate_tiers, effective_date
        )

    daily_rate = _yearly_to_daily_rate(gross_interest_rate)
    daily_rate_percent = daily_rate * 100
    interest = effective_balance * daily_rate

    if interest > 0:
        amount_to_accrue = _precision_accrual(interest)

        if amount_to_accrue > 0:
            posting_ins = vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id(),
                from_account_id=PNL_ACCOUNT,
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Daily interest accrued at %0.5f%% on balance of %0.2f"
                    % (daily_rate_percent, effective_balance),
                    "event": "ACCRUE_INTEREST",
                },
            )
            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )
    else:
        # Negative interest
        amount_to_accrue = _precision_accrual(interest)

        if amount_to_accrue > 0:
            posting_ins = vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id(),
                from_account_id=vault.account_id,
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=PNL_ACCOUNT,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                instruction_details={
                    "description": "Daily negative interest accrued at %0.5f%% on balance of %0.2f"
                    % (daily_rate_percent, effective_balance),
                    "event": "ACCRUE_NEGATIVE_INTEREST",
                },
            )
            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )


def _apply_accrued_interest(vault, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    linked_current_account_param = vault.get_parameter_timeseries(name="linked_current_account").at(
        timestamp=effective_date
    )
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)

    accrued_incoming_balance = balances[
        ("ACCRUED_INCOMING", DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    # to support negative interest
    accrued_outgoing_balance = balances[
        ("ACCRUED_OUTGOING", DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net
    transaction_fee_balance = balances[
        ("TRANSACTION_FEE", DEFAULT_ASSET, denomination, Phase.COMMITTED)
    ].net

    accrued_incoming_fulfillment = _precision_fulfillment(accrued_incoming_balance)
    accrued_outgoing_fulfillment = _precision_fulfillment(accrued_outgoing_balance)
    posting_ins = []
    transaction_fee_fulfillment = _precision_fulfillment(transaction_fee_balance)
    mirror_posting_ins = []
    if accrued_incoming_fulfillment > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_incoming_fulfillment,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address="ACCRUED_INCOMING",
                to_account_id=vault.account_id,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="APPLY_ACCRUED_INTEREST_{}_{}_CUSTOMER".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Interest Applied",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )
        if _valid_linked_account(linked_current_account_param):
            mirror_posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=accrued_incoming_fulfillment,
                    denomination=denomination,
                    from_account_id=vault.account_id,
                    from_account_address="SAVINGS_REGISTER",
                    to_account_id=linked_current_account_param.value,
                    to_account_address="SAVINGS_REGISTER",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="REGISTER_APPLY_ACCRUED_INTEREST_{}_{}_CUSTOMER".format(
                        vault.get_hook_execution_id(), denomination
                    ),
                    instruction_details={
                        "description": "Mirroring Interest Applied",
                        "event": "SAVINGS_REGISTER",
                    },
                )
            )
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_incoming_fulfillment,
                denomination=denomination,
                from_account_id=PNL_ACCOUNT,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=PNL_ACCOUNT,
                to_account_address="ACCRUED_OUTGOING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="APPLY_ACCRUED_INTEREST_{}_{}_INTERNAL".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Interest Applied",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )

    # negative interest
    if accrued_outgoing_fulfillment > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_outgoing_fulfillment,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_OUTGOING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="APPLY_ACCRUED_NEGATIVE_INTEREST_{}_{}_CUSTOMER".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Negative Interest Applied",
                    "event": "APPLY_NEGATIVE_ACCRUED_INTEREST",
                },
            )
        )
        if _valid_linked_account(linked_current_account_param):
            mirror_posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=accrued_outgoing_fulfillment,
                    denomination=denomination,
                    from_account_id=linked_current_account_param.value,
                    from_account_address="SAVINGS_REGISTER",
                    to_account_id=vault.account_id,
                    to_account_address="SAVINGS_REGISTER",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="REGISTER_APPLY_ACCRUED_NEGATIVE_INTEREST_{}_{}_CUSTOMER".format(
                        vault.get_hook_execution_id(), denomination
                    ),
                    instruction_details={
                        "description": "Mirroring Interest Applied",
                        "event": "SAVINGS_REGISTER",
                    },
                )
            )
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=accrued_outgoing_fulfillment,
                denomination=denomination,
                from_account_id=PNL_ACCOUNT,
                from_account_address="ACCRUED_INCOMING",
                to_account_id=PNL_ACCOUNT,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="APPLY_ACCRUED_NEGATIVE_INTEREST_{}_{}_INTERNAL".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Negative Interest Applied",
                    "event": "APPLY_NEGATIVE_ACCRUED_INTEREST",
                },
            )
        )

    if transaction_fee_fulfillment > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=transaction_fee_fulfillment,
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=vault.account_id,
                to_account_address="TRANSACTION_FEE",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                pics=[],
                client_transaction_id="APPLY_ACCRUED_TRANSACTION_FEE_{}_{}_CUSTOMER".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Transaction fees applied",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )
        if _valid_linked_account(linked_current_account_param):
            mirror_posting_ins.extend(
                vault.make_internal_transfer_instructions(
                    amount=transaction_fee_fulfillment,
                    denomination=denomination,
                    from_account_id=linked_current_account_param.value,
                    from_account_address="SAVINGS_REGISTER",
                    to_account_id=vault.account_id,
                    to_account_address="SAVINGS_REGISTER",
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    client_transaction_id="REGISTER_ACCRUED_TRANSACTION_FEE_{}_{}_CUSTOMER".format(
                        vault.get_hook_execution_id(), denomination
                    ),
                    instruction_details={
                        "description": "Mirroring Transaction fees applied",
                        "event": "SAVINGS_REGISTER",
                    },
                )
            )

    remainder = accrued_incoming_balance - accrued_incoming_fulfillment

    if remainder > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address="ACCRUED_INCOMING",
                to_account_id=PNL_ACCOUNT,
                to_account_address="ACCRUED_OUTGOING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="REVERSE_ACCRUE_INTEREST_{}_{}".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Reversing accrued interest after application",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )
    if remainder < 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(remainder),
                denomination=denomination,
                from_account_id=PNL_ACCOUNT,
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="REVERSE_ACCRUE_INTEREST_{}_{}".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Reversing accrued interest after application",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )

    negative_interest_remainder = accrued_outgoing_balance + accrued_outgoing_fulfillment

    if negative_interest_remainder > 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(negative_interest_remainder),
                denomination=denomination,
                from_account_id=vault.account_id,
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=PNL_ACCOUNT,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="REVERSE_ACCRUE_NEGATIVE_INTEREST_{}_{}".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Reversing accrued negative interest after application",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )
    if negative_interest_remainder < 0:
        posting_ins.extend(
            vault.make_internal_transfer_instructions(
                amount=abs(negative_interest_remainder),
                denomination=denomination,
                from_account_id=PNL_ACCOUNT,
                from_account_address="ACCRUED_INCOMING",
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_OUTGOING",
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="REVERSE_ACCRUE_NEGATIVE_INTEREST_{}_{}".format(
                    vault.get_hook_execution_id(), denomination
                ),
                instruction_details={
                    "description": "Reversing accrued negative interest after application",
                    "event": "APPLY_ACCRUED_INTEREST",
                },
            )
        )

    if posting_ins:
        vault.instruct_posting_batch(
            posting_instructions=posting_ins,
            effective_date=effective_date,
            client_batch_id="APPLY_ACCRUED_INTEREST_AND_FEES_{}_{}".format(
                vault.get_hook_execution_id(), denomination
            ),
        )

    if mirror_posting_ins:
        vault.instruct_posting_batch(
            posting_instructions=mirror_posting_ins,
            effective_date=effective_date,
            client_batch_id=f"REGISTER_APPLY_ACCRUED_INTEREST_AND_FEES"
            f"_{vault.get_hook_execution_id()}",
        )


def _publish_extract(vault, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").at(timestamp=effective_date)
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


def _sum_without_current_client_trans(
    client_transactions, client_transaction_id, cutoff_timestamp, denomination
):
    amount_withdrawal = 0
    amount_deposit = 0
    for (client_id, transaction_id), transaction in client_transactions.items():
        if transaction_id == client_transaction_id:
            continue
        if transaction.cancelled:
            continue
        amount_now = (
            transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
            + transaction.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].unsettled
        )
        amount_before_cutoff = (
            transaction.effects(timestamp=cutoff_timestamp)[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
            ].settled
            + transaction.effects(timestamp=cutoff_timestamp)[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
            ].unsettled
        )

        amount = amount_now - amount_before_cutoff
        if amount > 0:
            amount_deposit += amount
        else:
            amount_withdrawal += amount
    return amount_deposit, amount_withdrawal


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


def _count_client_transactions(client_transactions, denomination):
    # count withdrawal transactions only, excludes 'APPLY_ACCRUED_' transaction ids
    txns_this_month = []
    for (client_id, client_txn_id) in client_transactions:
        client_txn = client_transactions.get((client_id, client_txn_id))
        if client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled:
            if client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled < 0:
                if "APPLY_ACCRUED_" not in client_txn_id:
                    txns_this_month.append(client_txn_id)
    return len(txns_this_month)


def _check_if_in_promotion_window(effective_date, promotion_start_date, promotion_end_date):
    in_promo = False
    if promotion_start_date and promotion_end_date:
        in_promo = effective_date > promotion_start_date and effective_date <= promotion_end_date
    return in_promo


def _get_customer_interest_rate(vault, gross_interest_rate_tiers, effective_date):
    tier_found = False
    for tier in gross_interest_rate_tiers.keys():
        if vault.get_flag_timeseries(flag=tier).at(timestamp=effective_date):
            customer_interest_rate = Decimal(gross_interest_rate_tiers[tier])
            tier_found = True
            break
    if not tier_found:
        customer_interest_rate = Decimal(gross_interest_rate_tiers["DEFAULT"])
    return customer_interest_rate


def _valid_linked_account(linked_account_id_param):
    if (
        linked_account_id_param.is_set()
        and linked_account_id_param.value != "00000000-0000-0000-0000-000000000000"
    ):
        return True
    else:
        return False


def _get_param_value(vault, param_name, default_value=None):
    param = vault.get_parameter_timeseries(name=param_name).latest()
    param_value = param.value if param.is_set() else default_value
    return param_value


# flake8: noqa
