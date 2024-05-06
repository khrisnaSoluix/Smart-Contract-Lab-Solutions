api = "3.4.0"
version = "1.0.0"
_DENOMINATION = "GBP"

# We consider two types of supervisee accounts.
supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="savings",
        smart_contract_version_id="savings_contract_version",
    ),
    SmartContractDescriptor(
        alias="mortgage",
        smart_contract_version_id="mortgage_contract_version",
    ),
]

# The Supervisor Contract overrides the event types of the 2 supervisees
# Smart Contracts via a monthly-scheduled APPLY_MONTHLY_INTEREST_OFFSETTING event.
event_types = [
    EventType(
        # This is the name of the event type of the Supervisor
        name="APPLY_MONTHLY_INTEREST_OFFSETTING",
        # Our semantics also support scheduler tags
        scheduler_tag_ids=["EOM"],
        overrides_event_types=[
            # Here we declare a list of the supervisee event types that are
            # being overriden by APPLY_MONTHLY_INTEREST_OFFSETTING.
            # Note the use of aliases to reference supervisees
            ("savings", "PAY_MONTHLY_INTEREST"),
            ("mortgage", "CHARGE_MONTHLY_INTEREST"),
        ],
    ),
]


def execution_schedules():
    key_date = None
    for acc, supervisee in vault.supervisees.items():
        if supervisee.tside == Tside.LIABILITY:
            key_date = supervisee.get_parameter_timeseries(name="key_date").latest()
    if not key_date:
        raise InvalidContractParameter("Cannot get key_date parameter value from supervisees")
    return [
        (
            "APPLY_MONTHLY_INTEREST_OFFSETTING",
            {
                "day": f"{key_date}",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )
    ]


@requires(
    # Offsetting logic is implemented by invoking scheduled_code at an APPLY_MONTHLY_INTEREST_OFFSETTING
    # event type.
    event_type="APPLY_MONTHLY_INTEREST_OFFSETTING",
    # In order to implement the offsetting plan logic mentioned in the contract description, we
    # need parameter and balance information from 'all' the relevant supervisee contracts.
    data_scope="all",
    parameters=True,
    balances="latest live",
    # Other inputs we utilise are the results of savings and mortgage scheduled_code
    # execution, as per `supervisee_hook_directives='all'`
    supervisee_hook_directives="all",
)
def scheduled_code(event_type, effective_date):
    # Initialise the balances we use for offsetting:
    mortgage_balance = Decimal()
    mortgage_account_id = None
    savings_balance = Decimal()
    savings_account_id = None
    # We iterate through the supervisees via the `vault.supervisees` object.
    for acc_id, supervisee in vault.supervisees.items():
        # We access the hook directives that the supervisees have produced for
        # their corresponding supervised event type:
        directives = supervisee.get_hook_directives()
        # And in particular, their posting instruction batches
        for posting_directive in directives.posting_instruction_batch_directives:
            # The .tside property allows us to distinguish if the supervisee corresponds
            # to an interest bearing account (thus asset) or interest paying account (thus
            # liability)
            if supervisee.tside == Tside.ASSET:
                # Keep track of the mortgage account ID
                mortgage_account_id = acc_id
                # We also grab the mortgage account balance via the `supervisee` object.
                mortgage_balance = _get_effective_balance(
                    supervisee.get_balance_timeseries().latest()
                )
                # Inspect the hook directives in order to find the relevant revenue internal account id
                # used for counterposting:
                directives = supervisee.get_hook_directives()
                for posting_directive in directives.posting_instruction_batch_directives:
                    pib = posting_directive.posting_instruction_batch
                    revenue_account_id = next(
                        posting.account_id for posting in pib if posting.credit
                    )
            elif supervisee.tside == Tside.LIABILITY:
                # keep the savings account ID
                savings_account_id = acc_id
                # we grab the savings account balance via the `supervisee` object.
                savings_balance = _get_effective_balance(
                    supervisee.get_balance_timeseries().latest()
                )
                # inspect the hook directives in order to find the relevant expenses internal account id
                # used for counterposting:
                directives = supervisee.get_hook_directives()
                for posting_directive in directives.posting_instruction_batch_directives:
                    pib = posting_directive.posting_instruction_batch
                    expenses_account_id = next(
                        posting.account_id for posting in pib if not posting.credit
                    )
            else:
                raise Rejected(
                    "Got unexpected account T-side. It should be either an Asset or Liability type"
                )

    # Offset logic
    # -------------
    supervisee_pib = None
    if savings_balance > mortgage_balance:
        # Option 1: Credit Balance exceeds Debit Balance
        # In this case the customer has excess credit balance, thus we drop the mortgage interest charge
        # and in return we pay interest only on the excess credit balance.
        supervisee = vault.supervisees[savings_account_id]
        # Firstly we get the pay rate for the savings account from the contract parameters.
        pay_rate = supervisee.get_parameter_timeseries(name="effective_interest").latest()
        interest_amount = pay_rate * savings_balance
        supervisee_pib = supervisee.make_internal_transfer_instructions(
            amount=interest_amount,
            asset=DEFAULT_ASSET,
            denomination=_DENOMINATION,
            client_transaction_id="some_client_transaction_id",
            from_account_id=expenses_account_id,
            to_account_id=savings_account_id,
        )
    else:
        # Option 2: Debt Balance exceeds Credit Balance
        # In this case the customer has more outstanding debt than savings in the bank, thus we charge interest
        # on the excess debt balance.
        supervisee = vault.supervisees[mortgage_account_id]
        # We get the charge rate for the savings account from the contract parameters:
        charge_rate = supervisee.get_parameter_timeseries(name="effective_interest").latest()
        interest_amount = charge_rate * mortgage_balance
        supervisee_pib = supervisee.make_internal_transfer_instructions(
            amount=interest_amount,
            asset=DEFAULT_ASSET,
            denomination=_DENOMINATION,
            client_transaction_id="some_client_transaction_id",
            from_account_id=supervisee.account_id,
            to_account_id=revenue_account_id,
        )

    # Instruct the postings
    if supervisee_pib:
        supervisee.instruct_posting_batch(posting_instructions=pib)


def _get_effective_balance(balances):
    # For simplicity sake, we consider a common definition of effective balance for interest
    # calculations.
    return (
        balances[DEFAULT_ADDRESS, DEFAULT_ASSET, _DENOMINATION, Phase.COMMITTED].net
        + balances[DEFAULT_ADDRESS, DEFAULT_ASSET, _DENOMINATION, Phase.PENDING_OUT].net
    )


# flake8: noqa
