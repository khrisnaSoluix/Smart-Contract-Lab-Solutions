# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
"""
This is a contract for testing vault caller, sourced from:
/projects/goldfinger/contracts/youth_account.py
"""
api = "3.4.0"
version = "1.0.9"
display_name = "Supervised US Youth Account"
summary = "A youth account which will be linked to a checking account"

tside = Tside.LIABILITY

address_details = [
    AddressDetails(
        account_address="General Spend",
        description="An address for General Spend.",
        tags=[],
    ),
    AddressDetails(account_address="Food", description="An address for food purchases.", tags=[]),
    AddressDetails(
        account_address="Merchandise",
        description="An address for Merchandise purchases.",
        tags=[],
    ),
]

event_types = [
    EventType(name="CHECK_MAINTENANCE_FEE"),
    EventType(name="CLOSE_ORPHANED_STATEMENT_CYCLE"),
    EventType(name="CLOSE_ORPHANED_ZERO_BALANCE"),
    EventType(name="PUBLISH_EXTRACT"),
]

parameters = [
    # Instance parameters
    Parameter(
        name="statement_day",
        shape=NumberShape(min_value=1, max_value=31, step=1),
        level=Level.INSTANCE,
        description="Day of statement cycle",
        display_name="Statement Day",
        default_value="1",
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
    Parameter(
        name="orphaned",
        shape=StringShape,
        level=Level.INSTANCE,
        description="Is this account orphaned (not associated with an open checking account)",
        display_name="Orphaned",
        default_value="no",
        update_permission=UpdatePermission.OPS_EDITABLE,
    ),
    # Template parameters
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Currency in which the product operates.",
        display_name="Denomination",
        default_value="USD",
    ),
    Parameter(
        name="zero_bal_timeout",
        shape=NumberShape(min_value=1, step=1),
        level=Level.TEMPLATE,
        description="Days for an orphaned account to be at zero balance before being closed",
        display_name="Zero Balance timeout",
        default_value="10",
    ),
]


@requires(parameters=True)
def execution_schedules():
    check_maintenance_fee_schedule = {"day": "28", "hour": "23", "minute": "59"}
    close_orphaned_statement_cycle_schedule = {
        "year": "1971",
        "start_date": "1970-01-01",
        "end_date": "1970-01-01",
    }
    close_orphaned_zero_balance_schedule = {
        "year": "1971",
        "start_date": "1970-01-01",
        "end_date": "1970-01-01",
    }
    publish_extract_schedule = {
        # DISABLED
        "year": "1971",
        "start_date": "1970-01-01",
        "end_date": "1970-01-01",
    }
    return [
        ("CHECK_MAINTENANCE_FEE", check_maintenance_fee_schedule),
        ("CLOSE_ORPHANED_STATEMENT_CYCLE", close_orphaned_statement_cycle_schedule),
        ("CLOSE_ORPHANED_ZERO_BALANCE", close_orphaned_zero_balance_schedule),
        ("PUBLISH_EXTRACT", publish_extract_schedule),
    ]


@requires(
    event_type="CHECK_MAINTENANCE_FEE",
    parameters=True,
    balances="1 month",
    postings="1 month",
)
@requires(event_type="CLOSE_ORPHANED_STATEMENT_CYCLE", parameters=True)
@requires(event_type="CLOSE_ORPHANED_ZERO_BALANCE", parameters=True)
def scheduled_code(event_type, effective_date):
    if event_type == "CHECK_MAINTENANCE_FEE":
        # Handled in supervisor
        pass
    if (event_type == "CLOSE_ORPHANED_STATEMENT_CYCLE") or (
        event_type == "CLOSE_ORPHANED_ZERO_BALANCE"
    ):
        vault.start_workflow(
            workflow="CLOSE_YOUTH_ACCOUNT",
            context={"account_id": vault.account_id, "disbursement_account_id": "1"},
        )


@requires(parameters=True, balances="1 days")
def post_parameter_change_code(old_parameters, new_parameters, effective_date):
    if _has_parameter_value_changed("orphaned", old_parameters, new_parameters):
        orphaned = _get_parameter_value("orphaned", old_parameters, new_parameters)
        if orphaned == "yes":
            denomination = vault.get_parameter_timeseries(name="denomination").latest()
            balances = vault.get_balance_timeseries().latest()

            # Start timer to close account in 2 statement cycles time
            statement_day = int(vault.get_parameter_timeseries(name="statement_day").latest())
            close_date = effective_date
            if (effective_date.day < statement_day) and (
                (effective_date + timedelta(day=statement_day)).day < statement_day
            ):
                # We haven't had a statement yet this month
                close_date += timedelta(months=1)
                close_date += timedelta(day=statement_day)
            else:
                close_date += timedelta(months=2)
                close_date += timedelta(day=statement_day)

            vault.amend_schedule(
                event_type="CLOSE_ORPHANED_STATEMENT_CYCLE",
                new_schedule={
                    "year": str(close_date.year),
                    "month": str(close_date.month),
                    "day": str(close_date.day),
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            )

            # Check if we're at zero balance
            if _is_zero_balance(balances, denomination):
                # start schedule
                zero_bal_timeout = vault.get_parameter_timeseries(name="zero_bal_timeout").latest()

                timeout = effective_date + timedelta(days=int(zero_bal_timeout))

                vault.amend_schedule(
                    event_type="CLOSE_ORPHANED_ZERO_BALANCE",
                    new_schedule={
                        "year": str(timeout.year),
                        "month": str(timeout.month),
                        "day": str(timeout.day),
                        "hour": "0",
                        "minute": "0",
                        "second": "0",
                    },
                )

        elif orphaned == "no":
            # We've just reassociated to a plan. Let's cancel the close schedules
            vault.amend_schedule(
                event_type="CLOSE_ORPHANED_STATEMENT_CYCLE",
                new_schedule={
                    "year": "1971",
                    "start_date": "1970-01-01",
                    "end_date": "1970-01-01",
                },
            )
            vault.amend_schedule(
                event_type="CLOSE_ORPHANED_ZERO_BALANCE",
                new_schedule={
                    "year": "1971",
                    "start_date": "1970-01-01",
                    "end_date": "1970-01-01",
                },
            )


@requires(parameters=True, balances="latest live", postings="1 month")
def pre_posting_code(postings, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()

    # Allow overriding any contract restrictions
    if postings.batch_details.get("withdrawal_override") == "true":
        return

    if any("category" not in post.instruction_details for post in postings):
        raise Rejected(
            f"No category information supplied ",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    if any(post.denomination != denomination for post in postings):
        raise Rejected(
            f"Cannot make transactions in given denomination; "
            f"transactions must be in {denomination}",
            reason_code=RejectedReason.WRONG_DENOMINATION,
        )

    latest_balances = vault.get_balance_timeseries().latest()

    # Ensure all postings in this batch have the same category
    category = ""
    for post in postings:
        postcategory = post.instruction_details.get("category")
        if not postcategory:
            raise Rejected(
                f"No category information supplied ",
                reason_code=RejectedReason.AGAINST_TNC,
            )

        if not category:
            category = postcategory
            continue

        if postcategory != category:
            raise Rejected(
                f"Different category information supplied ",
                reason_code=RejectedReason.AGAINST_TNC,
            )

    posting_committed_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net
    posting_pending_outbound_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
    ].net

    client_transactions = vault.get_client_transactions(include_proposed=False)

    latest_available_balance = _get_available_balance(
        latest_balances,
        category,
        [Phase.COMMITTED, Phase.PENDING_OUT],
        denomination,
        category,
        client_transactions,
    )

    if latest_available_balance + posting_committed_amount + posting_pending_outbound_amount < 0:
        raise Rejected(
            f"Transaction cannot bring available balance below 0. Available: {latest_available_balance}",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


@requires(parameters=True, balances="1 days", postings="1 month")
def post_posting_code(postings, effective_date):
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    orphan = vault.get_parameter_timeseries(name="orphaned").latest()

    category = ""
    amount_moved = Decimal(0)
    alert_candidate = False
    balanced_postings = []
    count = 0
    for post in postings:
        if "category" not in post.instruction_details:
            continue

        category = post.instruction_details["category"]

        # Inbound or outbound settlements hitting the account
        if post.type in [
            PostingInstructionType.HARD_SETTLEMENT,
            PostingInstructionType.SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ]:
            alert_candidate = True
            if post.credit is True:
                # Let's move this into the category pot
                balanced_postings.extend(
                    vault.make_internal_transfer_instructions(
                        amount=post.amount,
                        denomination=post.denomination,
                        from_account_id=vault.account_id,
                        from_account_address=DEFAULT_ADDRESS,
                        to_account_id=vault.account_id,
                        to_account_address=post.instruction_details["category"],
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                        client_transaction_id=f"MONIES_RECIEVED_"
                        f"{vault.get_hook_execution_id()}_"
                        f"{denomination}_CUSTOMER_{count}",
                        instruction_details={
                            "category": post.instruction_details["category"],
                            "description": "Money recieved onto DEFAULT",
                            "event": "post_posting_code",
                        },
                    )
                )
                amount_moved += post.amount
                count += 1
            else:
                # Let's move this out of the category pot to DEFAULT to balance
                balanced_postings.extend(
                    vault.make_internal_transfer_instructions(
                        amount=post.amount,
                        denomination=post.denomination,
                        from_account_id=vault.account_id,
                        from_account_address=post.instruction_details["category"],
                        to_account_id=vault.account_id,
                        to_account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        override_all_restrictions=True,
                        client_transaction_id=f"MONEY_OUT_"
                        f"{vault.get_hook_execution_id()}_"
                        f"{denomination}_CUSTOMER_{count}",
                        instruction_details={
                            "category": post.instruction_details["category"],
                            "description": "Money moved out of account",
                            "event": "post_posting_code",
                        },
                    )
                )
                amount_moved -= post.amount
                count += 1

    if balanced_postings:
        vault.instruct_posting_batch(
            posting_instructions=balanced_postings,
            effective_date=effective_date,
            client_batch_id=f"REBALANCE_{vault.get_hook_execution_id()}_{denomination}",
        )

    if category and alert_candidate:
        latest_balances = vault.get_balance_timeseries().latest()
        client_transactions = vault.get_client_transactions(include_proposed=True)

        latest_available_balance = _get_available_balance(
            latest_balances,
            category,
            [Phase.COMMITTED, Phase.PENDING_OUT],
            denomination,
            category,
            client_transactions,
        )

        if latest_available_balance + amount_moved < 10:
            vault.start_workflow(
                workflow="NOTIFY_LOW_BALANCE",
                context={
                    "account_id": str(vault.account_id),
                    "category": category,
                    "balance": str(latest_available_balance + amount_moved),
                    "message": "Alert: Low balance on account",
                },
            )

    # Do orphan and low balance check here
    if orphan == "yes":
        balances = vault.get_balance_timeseries().latest()
        if _is_zero_balance(balances, denomination):
            # start schedule
            zero_bal_timeout = vault.get_parameter_timeseries(name="zero_bal_timeout").latest()

            timeout = effective_date + timedelta(days=int(zero_bal_timeout))

            vault.amend_schedule(
                event_type="CLOSE_ORPHANED_ZERO_BALANCE",
                new_schedule={
                    "year": str(timeout.year),
                    "month": str(timeout.month),
                    "day": str(timeout.day),
                    "hour": "0",
                    "minute": "0",
                    "second": "0",
                },
            )
        else:
            # cancel schedule
            vault.amend_schedule(
                event_type="CLOSE_ORPHANED_ZERO_BALANCE",
                new_schedule={
                    "year": "1971",
                    "start_date": "1970-01-01",
                    "end_date": "1970-01-01",
                },
            )


@requires(parameters=True, balances="latest")
def close_code(effective_date):
    # Move all FUNDS to DEFAULT
    hook_execution_id = vault.get_hook_execution_id()
    denomination = vault.get_parameter_timeseries(name="denomination").latest()
    latest_balance_dict = vault.get_balance_timeseries().latest()
    payment_instructions = []
    vault.add_account_note(
        body=str(latest_balance_dict),
        note_type=NoteType.RAW_TEXT,
        is_visible_to_customer=True,
        date=datetime.utcnow(),
    )
    for ((address, asset, denom, phase), balance) in latest_balance_dict.items():
        if address == DEFAULT_ADDRESS:
            continue
        if balance.net > 0:  # Transfer to DEFAULT
            payment_instructions.extend(
                vault.make_internal_transfer_instructions(
                    amount=balance.net,
                    denomination=denomination,
                    client_transaction_id=f"AGGREGATE_BALANCE_IN_DEFAULT_{hook_execution_id}_FROM_{address}",
                    from_account_id=vault.account_id,
                    from_account_address=address,
                    to_account_id=vault.account_id,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": f"Moving balance to zero out {address} address"
                    },
                    asset=DEFAULT_ASSET,
                )
            )

    if payment_instructions:
        vault.instruct_posting_batch(
            posting_instructions=payment_instructions, effective_date=effective_date
        )


# Helper functions
def _get_available_balance(
    balances,
    balance_address,
    phases_to_include,
    denomination,
    category,
    client_transactions,
):
    """
    Retrieve available balance for provided balance address and list of phases.
    Note: Ringfencing funds in Phase.PENDING_OUT is opposite sign to committed, e.g. for liability
          account to get available balance should be Phase.COMMITTED + Phase.PENDING_OUT as
          Phase.PENDING_OUT will be negative
    """
    available_balance = Decimal(0)
    for phase in phases_to_include:
        available_balance += balances[balance_address, DEFAULT_ASSET, denomination, phase].net
        if phase == Phase.COMMITTED:
            continue

        available_balance += _total_ringfenced_for_category(
            balances, category, phase, denomination, client_transactions
        )

    return available_balance


def _total_ringfenced_for_category(balances, category, phase, denomination, client_transactions):
    """
    Returns the amount of ringfenced funds for the category as a negative number.
    """
    total_pending = Decimal(0)
    for (client_id, client_txn_id) in client_transactions:
        client_txn = client_transactions.get((client_id, client_txn_id))
        if "category" not in client_txn[0].instruction_details:
            raise Rejected(
                f"No category on transaction",
                reason_code=RejectedReason.AGAINST_TNC,
            )

        if client_txn[0].instruction_details["category"] == category:
            txn_unsettled = 0
            txn_unsettled = client_txn.effects()[
                (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)
            ].unsettled
            # Pending-in isn't available to spend yet, so only add the (negative) pending out amounts.
            if txn_unsettled < 0:
                total_pending += txn_unsettled

    return total_pending


def _is_zero_balance(balances, denomination):

    posting_pending_outbound_amount = balances[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT
    ].net
    posting_pending_inbound_amount = balances[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_IN
    ].net

    if (posting_pending_outbound_amount != 0) or (posting_pending_inbound_amount != 0):
        return False

    total_bucket_balance = sum(
        balance.net
        for ((address, asset, denom, phase), balance) in balances.items()
        if asset == DEFAULT_ASSET and phase == Phase.COMMITTED and denom == denomination
    )

    if total_bucket_balance > 0:
        return False
    else:
        return True


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


def _get_parameter_value(parameter_name, old_parameter_values, updated_parameter_values):
    """
    Returns value of a parameter - updated value if changed, otherwise takes original value.
    To be used in post_parameter_change hook
    :param parameter_name: str, name of the parameter
    :param old_parameter_values: dict, map of parameter name -> old parameter value
    :param updated_parameter_values: dict, map of parameter name -> new parameter value
    :return: Value of parameter
    """

    if parameter_name in updated_parameter_values:
        return updated_parameter_values[parameter_name]
    else:
        return old_parameter_values[parameter_name]


# flake8: noqa
