# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
"""
This is a contract for testing vault caller, sourced from:
/projects/goldfinger/contracts/supervisor_contract.py
"""
api = "3.4.0"
version = "1.0.7"

supervised_smart_contracts = [
    SmartContractDescriptor(alias="checking", smart_contract_version_id="&{checking}"),
    SmartContractDescriptor(alias="savings", smart_contract_version_id="&{savings}"),
    SmartContractDescriptor(alias="youth", smart_contract_version_id="&{youth}"),
]

event_types = [
    EventType(
        name="APPLY_MAINTENANCE_FEE",
        overrides_event_types=[
            ("checking", "CHECK_MAINTENANCE_FEE"),
            ("savings", "CHECK_MAINTENANCE_FEE"),
            ("youth", "CHECK_MAINTENANCE_FEE"),
        ],
    ),
    EventType(
        name="PUBLISH_COMBINED_EXTRACT",
        overrides_event_types=[
            ("checking", "PUBLISH_EXTRACT"),
            ("savings", "PUBLISH_EXTRACT"),
        ],
    ),
]


@requires(data_scope="all", parameters=True)
def execution_schedules():
    apply_maintentance_fee_schedule = {
        "hour": "23",
        "minute": "55",
    }
    # Also change extract_period
    publish_combined_extract_schedule = {"hour": "23", "minute": "59", "second": "0"}
    return [
        ("APPLY_MAINTENANCE_FEE", apply_maintentance_fee_schedule),
        ("PUBLISH_COMBINED_EXTRACT", publish_combined_extract_schedule),
    ]


@requires(
    event_type="APPLY_MAINTENANCE_FEE",
    data_scope="all",
    supervisee_hook_directives="all",
    parameters=True,
    balances="latest live",
)
@requires(
    event_type="PUBLISH_COMBINED_EXTRACT",
    data_scope="all",
    supervisee_hook_directives="none",
    parameters=True,
    balances="1 day live",
    last_execution_time=["PUBLISH_EXTRACT"],
    postings="2 days",
)
def scheduled_code(event_type, effective_date):
    if event_type == "APPLY_MAINTENANCE_FEE":
        _apply_maintenance_fee(vault, effective_date)
    elif event_type == "PUBLISH_COMBINED_EXTRACT":
        _publish_combined_extract(vault, effective_date)


def _apply_maintenance_fee(vault, effective_date):
    # Get on-boarded accounts, we must have at least the checking account
    checking_accounts = _get_supervisees_for_alias(vault, "checking")
    if not checking_accounts:
        return
    checking = checking_accounts[0]
    other_accounts = [v for (k, v) in vault.supervisees.items() if k != checking.account_id]

    # Check we have the correct day:
    maintenance_fee_check_day = int(
        checking.get_parameter_timeseries(name="maintenance_fee_check_day").at(
            timestamp=effective_date
        )
    )
    if maintenance_fee_check_day != effective_date.day:
        return

    denomination = checking.get_parameter_timeseries(name="denomination").at(
        timestamp=effective_date
    )
    maintenance_fee = Decimal(
        checking.get_parameter_timeseries(name="maintenance_fee").at(timestamp=effective_date)
    )
    minimum_combined_balance = Decimal(
        checking.get_parameter_timeseries(name="minimum_combined_balance").at(
            timestamp=effective_date
        )
    )
    internal_maintenance_fee_account = checking.get_parameter_timeseries(
        name="internal_maintenance_fee_account"
    ).at(timestamp=effective_date)

    # Maintenance fee waivers:
    # 1. Checking EOD balance consistently greater than X e.g. $1500 in month (done in checking acc)
    # 2. Checking total deposits in month greater than X e.g. $500 (done in checking acc)
    # 3. Total aggregate balance of related accounts is greater than X e.g. $5000 (done in super)

    # Find if we have a staged fee - if we do not there is already at least one waiver so return.
    found_staged_fee = False
    checking_pib_directives = checking.get_hook_directives().posting_instruction_batch_directives
    if checking_pib_directives:
        for directive in checking_pib_directives:
            if _check_maintenance_fee_in_batch(
                directive.posting_instruction_batch,
                maintenance_fee,
                checking.account_id,
            ):
                found_staged_fee = True
                break
    if not found_staged_fee:
        return

    # We have a staged fee - if we have no other accounts on-boarded apply the fee,
    # otherwise check for waiver 3
    if not other_accounts:
        checking.instruct_posting_batch(
            posting_instructions=checking.make_internal_transfer_instructions(
                amount=maintenance_fee,
                denomination=denomination,
                from_account_id=checking.account_id,
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
                    "description": "Maintenance fee applied by supervisor",
                    "event": "MAINTENANCE_FEE",
                    "note": "Savings account balance not considered",
                },
            ),
            effective_date=effective_date,
        )
    else:
        checking_available_balance = _get_available_balance(checking, effective_date, denomination)
        other_available_balance = 0
        for account in other_accounts:
            other_available_balance += _get_available_balance(account, effective_date, denomination)
        total_available_balance = checking_available_balance + other_available_balance

        if total_available_balance < minimum_combined_balance:
            # No final waiver so apply fee
            checking.instruct_posting_batch(
                posting_instructions=checking.make_internal_transfer_instructions(
                    amount=maintenance_fee,
                    denomination=denomination,
                    from_account_id=checking.account_id,
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
                        "description": "Maintenance fee applied by supervisor",
                        "event": "MAINTENANCE_FEE",
                        "checking_available_balance": str(checking_available_balance),
                        "other_available_balance": str(other_available_balance),
                    },
                ),
                effective_date=effective_date,
            )


def _publish_combined_extract(vault, effective_date):
    # Get on-boarded accounts, we must have at least the checking account
    checking_accounts = _get_supervisees_for_alias(vault, "checking")
    if not checking_accounts:
        return
    checking = checking_accounts[0]
    all_accounts = [v for (k, v) in vault.supervisees.items()]

    # Generate data for all plan accounts
    combined_extract_data = {}
    for account in all_accounts:
        denomination = account.get_parameter_timeseries(name="denomination").at(
            timestamp=effective_date
        )

        extract_period = timedelta(days=1)  # Don't currently have access to supervisor schedules
        plan_start = vault.get_plan_creation_date()
        if effective_date > plan_start + extract_period:
            end_of_last_extract = effective_date - extract_period
        else:
            end_of_last_extract = plan_start

        batches = account.get_posting_batches() or []
        pib_data = {
            str(pib.value_timestamp): [
                pib.batch_id,
                "%0.2f" % _get_altered_balance(pib.balances(), denomination),
                "%0.2f" % _get_phase_balance(account, pib.value_timestamp, denomination),
            ]
            for pib in batches
            if end_of_last_extract <= pib.value_timestamp < effective_date
        }

        opening_timestamp = end_of_last_extract
        opening_committed_bal = _get_phase_balance(account, opening_timestamp, denomination)
        closing_timestamp = effective_date
        closing_available_bal = _get_available_balance(account, closing_timestamp, denomination)
        closing_committed_bal = _get_phase_balance(account, closing_timestamp, denomination)
        closing_pending_in_bal = _get_phase_balance(
            account, closing_timestamp, denomination, Phase.PENDING_IN
        )
        closing_pending_out_bal = _get_phase_balance(
            account, closing_timestamp, denomination, Phase.PENDING_OUT
        )

        account_context = {
            "available_balance": "%0.2f" % closing_available_bal,
            "opening_balance": "%0.2f" % opening_committed_bal,
            "closing_balance": "%0.2f" % closing_committed_bal,
            "pending_in_balance": "%0.2f" % closing_pending_in_bal,
            "pending_out_balance": "%0.2f" % closing_pending_out_bal,
            "extract_data": str(pib_data).replace('"', '\\"').replace("'", '"'),
        }

        combined_extract_data[account.account_id] = account_context

    if len(combined_extract_data) == 0:
        return

    # Initiate combined extract workflow from checking account
    checking.start_workflow(
        workflow="PUBLISH_COMBINED_EXTRACT_DATA",
        context={
            "extract_date": str(effective_date),
            "combined_extract_data": str(combined_extract_data)
            .replace('"', '\\"')
            .replace("'", '"'),
        },
    )


def _get_available_balance(vault, effective_date, denomination):
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    committed_balance_net = 0
    if vault.get_alias() == "youth":
        # Ensure we take into account all balance addresses for the youth account
        for address in {k[0] for (k, v) in balances.items()}:
            committed_balance_net += balances[
                (address, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ].net
    else:
        committed_balance_net = balances[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
        ].net
    pending_out_balance_net = balances[
        (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.PENDING_OUT)
    ].net
    return committed_balance_net + pending_out_balance_net


def _check_maintenance_fee_in_batch(pib, fee_amount, from_account_id):
    staged_amount = 0
    details = []
    for post in pib:
        if post.account_id == from_account_id and post.account_address == DEFAULT_ADDRESS:
            staged_amount += (1 if post.credit else -1) * post.amount
            details.extend(post.instruction_details.values())
    matched_details = [s for s in details if "MAINTENANCE_FEE" in s]
    return True if staged_amount == -fee_amount and len(matched_details) > 0 else False


def _get_phase_balance(vault, effective_date, denomination, phase=Phase.COMMITTED):
    balances = vault.get_balance_timeseries().at(timestamp=effective_date)
    phase_balance_net = 0
    if vault.get_alias() == "youth":
        for address in {k[0] for (k, v) in balances.items()}:
            phase_balance_net += balances[
                (address, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ].net
    else:
        phase_balance_net = balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, phase)].net

    return phase_balance_net


def _get_altered_balance(balances, denomination):
    return sum(
        balance.net
        for ((address, asset, denom, phase), balance) in balances.items()
        if asset == DEFAULT_ASSET and denom == denomination
    )


def _get_supervisees_for_alias(vault, alias):
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    result = {v.get_alias(): {} for v in vault.supervisees.values()}
    for k in result.keys():
        result[k] = {i: v for (i, v) in vault.supervisees.items() if v.get_alias() == k}
    return sorted(
        [v for v in result.get(alias, {}).values()],
        key=lambda v: v.get_account_creation_date(),
    )


# flake8: noqa
