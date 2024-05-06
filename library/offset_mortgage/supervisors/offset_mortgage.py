# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
api = "3.8.0"
version = "1.1.1"

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="mortgage",
        smart_contract_version_id="&{mortgage}",
        supervise_post_posting_hook=False,
    ),
    SmartContractDescriptor(
        alias="easy_access_saver",
        smart_contract_version_id="&{easy_access_saver}",
        supervise_post_posting_hook=False,
    ),
    SmartContractDescriptor(
        alias="current_account",
        smart_contract_version_id="&{current_account}",
        supervise_post_posting_hook=False,
    ),
]

# Mortgage balance addresses
PRINCIPAL_DUE = "PRINCIPAL_DUE"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL = "PRINCIPAL"
OVERPAYMENT = "OVERPAYMENT"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

REMAINING_PRINCIPAL = [PRINCIPAL, OVERPAYMENT, EMI_PRINCIPAL_EXCESS]

# Mortgage constants
DAYS_IN_A_YEAR = 365

event_types = [
    EventType(
        name="ACCRUE_OFFSET_INTEREST",
        overrides_event_types=[
            ("mortgage", "ACCRUE_INTEREST"),
            ("easy_access_saver", "ACCRUE_INTEREST_AND_DAILY_FEES"),
            ("current_account", "ACCRUE_INTEREST_AND_DAILY_FEES"),
        ],
        scheduler_tag_ids=["OFFSET_MORTGAGE_ACCRUE_OFFSET_INTEREST_AST"],
    )
]


@requires(data_scope="all", parameters=True)
def execution_schedules():
    accrue_offset_interest_schedule = {"hour": "0", "minute": "0", "second": "1"}
    return [("ACCRUE_OFFSET_INTEREST", accrue_offset_interest_schedule)]


@requires(
    event_type="ACCRUE_OFFSET_INTEREST",
    data_scope="all",
    supervisee_hook_directives="all",
    parameters=True,
    balances="latest live",
)
def scheduled_code(event_type, effective_date: datetime):
    if event_type == "ACCRUE_OFFSET_INTEREST":
        _accrue_interest(vault, effective_date)


def _accrue_interest(vault, effective_date: datetime):
    mortgage_accounts = _get_supervisees_for_alias(vault, "mortgage")
    eas_accounts = _get_supervisees_for_alias(vault, "easy_access_saver")
    ca_accounts = _get_supervisees_for_alias(vault, "current_account")
    all_offset_accounts = eas_accounts + ca_accounts

    # If no accounts associated with plan, no accrual needed
    if not mortgage_accounts and not all_offset_accounts:
        return

    # If only offset accounts and no mortgage, commit offset accounts accrual postings
    # If only mortgage and no offset accounts, commit mortgage accrual postings
    # In either case return from function
    if mortgage_accounts and not all_offset_accounts:
        for mortgage_account in mortgage_accounts:
            _commit_hook_posting_directives(mortgage_account, effective_date)
            return
    elif all_offset_accounts and not mortgage_accounts:
        for account in all_offset_accounts:
            _commit_hook_posting_directives(account, effective_date)
            return

    # We assume only one mortgage for now, in offset mortgage
    mortgage = mortgage_accounts[0]

    mortgage_denomination = mortgage.get_parameter_timeseries(name="denomination").latest()

    # Filter accounts with mortgage and other denominations
    (
        accounts_with_mortgage_denomination,
        other_denomination_accounts,
    ) = _split_accounts_by_denomination(all_offset_accounts, mortgage_denomination)

    # Let all non eligible offset accounts [different denomination] process it's hook directives
    for account in other_denomination_accounts:
        _commit_hook_posting_directives(account, effective_date)

    # If there are no valid offset accounts with correct denomination,
    # then process mortgage directives and exit.
    if not accounts_with_mortgage_denomination:
        _commit_hook_posting_directives(mortgage, effective_date)
        return

    positive_balance_accounts, negative_balance_accounts = _split_accounts_by_balance(
        accounts_with_mortgage_denomination, mortgage_denomination
    )

    # Let all non eligible offset accounts [balance < 0] process it's hook directives
    for account in negative_balance_accounts:
        _commit_hook_posting_directives(account, effective_date)

    # If there are no valid offset accounts [balance > 0],
    # then process mortgage directives and exit.
    # else continue processing since there are valid offset accounts
    if not positive_balance_accounts:
        _commit_hook_posting_directives(mortgage, effective_date)
        return

    # Get mortgage accrual posting directives (interest rate in metadata?)
    mortgage_hook_directives = mortgage.get_hook_directives()
    mortgage_pib_directives = mortgage_hook_directives.posting_instruction_batch_directives

    if not mortgage_pib_directives:
        # What to do if no mortgage pib directives?
        return
    mortgage_interest_received_account = mortgage.get_parameter_timeseries(
        name="interest_received_account"
    ).latest()
    mortgage_accrued_interest_receivable_account = mortgage.get_parameter_timeseries(
        name="accrued_interest_receivable_account"
    ).latest()
    mortgage_accrual_precision = mortgage.get_parameter_timeseries(
        name="accrual_precision"
    ).latest()

    mortgage_offset_interest_accrual_postings = []
    # Get mortgage outstanding principal
    mortgage_outstanding_principal = _get_balance_sum(mortgage, REMAINING_PRINCIPAL)

    # Get accounts total balance
    offset_accounts_available_balance = _get_accounts_available_balance(positive_balance_accounts)

    # Calculate accrued interest
    accrual_effective_principal = mortgage_outstanding_principal - offset_accounts_available_balance
    # Get mortgage daily interest rate
    mortgage_daily_interest_rate = Decimal(0)
    for mortgage_pib_directive in mortgage_pib_directives:
        mortgage_pib = mortgage_pib_directive.posting_instruction_batch
        mortgage_interest_accrual_postings = [
            posting
            for posting in mortgage_pib
            if _is_matching_posting(posting, "INTEREST_ACCRUAL_INTERNAL", "ACCRUE_INTEREST")
            or _is_matching_posting(posting, "INTEREST_ACCRUAL_CUSTOMER", "ACCRUE_INTEREST")
        ]
        mortgage_expected_interest_accrual_postings = [
            posting
            for posting in mortgage_pib
            if _is_matching_posting(posting, "INTEREST_ACCRUAL_EXPECTED", "ACCRUE_INTEREST")
        ]
        if not mortgage_interest_accrual_postings:
            # What to do if no mortgage interest accrual postings?
            continue

        # Reinstruct expected interest accrual postings as those aren't affected by offset
        if mortgage_expected_interest_accrual_postings:
            mortgage_offset_interest_accrual_postings.extend(
                mortgage_expected_interest_accrual_postings
            )

        # Get mortgage daily interest rate from supervisee interest accrual posting metadata
        mortgage_daily_interest_rate = Decimal(
            mortgage_interest_accrual_postings[0].instruction_details["daily_interest_rate"]
        )

    mortgage_accrued_interest = _round_to_precision(
        mortgage_accrual_precision,
        accrual_effective_principal * mortgage_daily_interest_rate,
    )

    # Make accrual postings
    if mortgage_accrued_interest > Decimal(0):
        mortgage_offset_interest_accrual_postings.extend(
            mortgage.make_internal_transfer_instructions(
                amount=mortgage_accrued_interest,
                denomination=mortgage_denomination,
                client_transaction_id=f"{mortgage.get_hook_execution_id()}_OFFSET_INTEREST_ACCRUAL_"
                f"CUSTOMER",
                from_account_id=mortgage.account_id,
                from_account_address=ACCRUED_INTEREST,
                to_account_id=mortgage.account_id,
                to_account_address=INTERNAL_CONTRA,
                instruction_details={
                    "description": f"Daily offset interest accrued at "
                    f"{mortgage_daily_interest_rate*100:0.6f}% on outstanding "
                    f"principal of {mortgage_outstanding_principal} offset with "
                    f"balance of {offset_accounts_available_balance}",
                    "event_type": "ACCRUE_OFFSET_INTEREST",
                },
            )
        )
        mortgage_offset_interest_accrual_postings.extend(
            mortgage.make_internal_transfer_instructions(
                amount=mortgage_accrued_interest,
                denomination=mortgage_denomination,
                client_transaction_id=f"{mortgage.get_hook_execution_id()}_OFFSET_INTEREST_ACCRUAL_"
                f"INTERNAL",
                from_account_id=mortgage_accrued_interest_receivable_account,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=mortgage_interest_received_account,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Daily offset interest accrued at "
                    f"{mortgage_daily_interest_rate*100:0.6f}% on outstanding "
                    f"principal of {mortgage_outstanding_principal} offset with "
                    f"balance of {offset_accounts_available_balance}",
                    "event_type": "ACCRUE_OFFSET_INTEREST",
                },
            )
        )

    # Commit interest accrual postings
    if len(mortgage_offset_interest_accrual_postings) > 0:
        mortgage.instruct_posting_batch(
            posting_instructions=mortgage_offset_interest_accrual_postings,
            effective_date=effective_date,
        )

    # Apply penalty interest postings
    _commit_hook_posting_directives(mortgage, effective_date, ["ACCRUE_PENALTY_INTEREST"])


def _commit_hook_posting_directives(
    supervisee_vault, effective_date: datetime, instruction_details_events=None
):
    """
    Filter and commit hook posting directives.
    :param supervisee_vault: vault, supervisee vault object
    :param effective_date: effective date
    :param events: None|List, events to filter on
    """
    supervisee_hook_directives = supervisee_vault.get_hook_directives()
    supervisee_pib_directives = supervisee_hook_directives.posting_instruction_batch_directives
    if not supervisee_pib_directives:
        return

    posting_ins = []
    for supervisee_pib_directive in supervisee_pib_directives:
        pib = supervisee_pib_directive.posting_instruction_batch
        for posting in pib:
            instruction_details = posting.instruction_details
            if (
                instruction_details_events
                and instruction_details.get("event") not in instruction_details_events
            ):
                continue

            # Workaround for TM-39681
            posting.custom_instruction_grouping_key = posting.client_transaction_id

            posting_ins.append(posting)

    if posting_ins:
        supervisee_vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=effective_date
        )


# Offset accounts helpers
def _split_accounts_by_denomination(offset_accounts, mortgage_denomination: str):
    """
    Split accounts into two lists, ones with matching denomination of mortgage account and
    others which are not matching the denomination of mortgage account.

    :param offset_accounts: List of offset accounts
    :param mortgage_denomination: Denomination of the mortgage account
    :return: list of accounts that are eligible for offset, list of accounts that are not
             eligible for offset
    """
    accounts_with_mortgage_denomination = []
    remaining_accounts = []

    for account in offset_accounts:
        account_denomination = account.get_parameter_timeseries(name="denomination").latest()

        if account_denomination == mortgage_denomination:
            accounts_with_mortgage_denomination.append(account)
        else:
            remaining_accounts.append(account)

    return accounts_with_mortgage_denomination, remaining_accounts


def _split_accounts_by_balance(
    offset_accounts, mortgage_denomination: str, address: str = DEFAULT_ADDRESS
):
    """
    Constructs two lists of accounts, one with positive available balance, one with negative
    available balance.

    :param offset_accounts: List of offset accounts
    :param mortgage_denomination: Denomination of the mortgage account
    :param address: Balance address of offset account
    :return: list of accounts with positive balance, list of accounts with negative balance
    """
    accounts_with_positive_balance = []
    accounts_with_negative_balance = []

    for account in offset_accounts:
        account_balance = _get_available_balance(
            account.get_balance_timeseries().latest(), mortgage_denomination, address
        )

        if account_balance >= 0:
            accounts_with_positive_balance.append(account)
        else:
            accounts_with_negative_balance.append(account)

    return accounts_with_positive_balance, accounts_with_negative_balance


def _get_accounts_available_balance(accounts, address: str = DEFAULT_ADDRESS) -> Decimal:
    """
    Sums the available balances of the accounts.

    :param accounts: List of accounts
    :param address: balance address
    :return: total balance available
    """
    total_balance = Decimal(0)
    for account in accounts:
        account_denomination = account.get_parameter_timeseries(name="denomination").latest()

        # Get account balance
        account_balance = _get_available_balance(
            account.get_balance_timeseries().latest(), account_denomination, address
        )
        if account_balance > 0:
            total_balance = total_balance + account_balance

    return total_balance


# Supervisor helper functions
def _get_supervisees_for_alias(vault, alias):
    """
    Returns a list of supervisee vault objects for the given alias, ordered by account creation date
    :param vault: vault, supervisor vault object
    :param alias: str, the supervisee alias to filter for
    :return: list, supervisee vault objects for given alias, ordered by account creation date
    """
    return sorted(
        (
            supervisee
            for supervisee in vault.supervisees.values()
            if supervisee.get_alias() == alias
        ),
        key=lambda v: v.get_account_creation_date(),
    )


def _is_matching_posting(posting, transaction_id_stub, event_type):
    return (
        # posting.account_address == account_address
        transaction_id_stub in posting.client_transaction_id
        and posting.instruction_details["event_type"] == event_type
    )


# Balance helper functions
def _get_balance_sum(vault, addresses: List[str], timestamp: datetime = None) -> Decimal:
    """
    :param vault: balances, parameters
    :param addresses: list of addresses
    :param timestamp: optional datetime at which balances to be summed
    :return: sum of the balances
    """
    balances = (
        vault.get_balance_timeseries().latest()
        if timestamp is None
        else vault.get_balance_timeseries().at(timestamp=timestamp)
    )
    denomination = vault.get_parameter_timeseries(name="denomination").latest()

    return Decimal(
        sum(
            balances[(address, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
            for address in addresses
        )
    )


def _get_available_balance(
    balances,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
) -> Decimal:
    """
    Sum net balances including COMMITTED and PENDING_OUT only.

    :param balances: balance
    :param denomination: account denomination
    :param address: balance address
    :param asset: balance asset
    :return: sum of net balance
    """
    return (
        balances[(address, asset, denomination, Phase.COMMITTED)].net
        + balances[(address, asset, denomination, Phase.PENDING_OUT)].net
    )


# Rounding helper functions
def _round_to_precision(precision: Decimal, amount: Decimal) -> Decimal:
    """
    Round a decimal value to required precision

    :param precision: number of decimal places to round to
    :param amount: amount to round
    :return: rounded amount
    """
    decimal_string = str(1.0 / pow(10, precision))
    return amount.quantize(Decimal(decimal_string).normalize(), rounding=ROUND_HALF_UP)
