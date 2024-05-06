api = "3.8.0"
version = "1.1.0"
global_parameters = ["central_bank_yearly_interest_rate"]
events_timezone = "US/Eastern"

_denomination = "USD"

PercentageShape = NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.00001)

MoneyShape = NumberShape(
    kind=NumberKind.MONEY,
    min_value=0,
    max_value=1000,
    step=1,
)

parameters = [
    Parameter(
        name="monthly_overdraft_rate",
        description="Monthly Overdraft Rate",
        display_name="Monthly Overdraft Rate",
        level=Level.TEMPLATE,
        shape=PercentageShape,
        update_permission=UpdatePermission.USER_EDITABLE,
    ),
]


def execution_schedules():
    create_date = vault.get_account_creation_date()
    return [
        (
            "TEST_EVENT",
            {
                "minute": "*",
                "start_date": vault.localize_datetime(create_date).isoformat(),
                "end_date": vault.localize_datetime(create_date + timedelta(minutes=1)).isoformat(),
            },
        ),
        ("ACCRUE_INTEREST", {"day": "27", "hour": "0", "minute": "0", "second": "0"}),
    ]


@requires(event_type="ACCRUE_INTEREST", parameters=True, balances="latest")
def scheduled_code(event_type, effective_date):
    yearly_interest_rate = vault.get_parameter_timeseries(
        name="central_bank_yearly_interest_rate"
    ).latest()

    monthly_interest_rate = Decimal(yearly_interest_rate) / 12
    # Monthly overdraft rate and fee are constants set at contract creation.
    monthly_overdraft_rate = vault.get_parameter_timeseries(name="monthly_overdraft_rate").latest()

    contract_denomination = _denomination
    # Pay any interest due on the balance of the account.
    accrue_balance = sum(
        balance.net
        for (address, asset, denom, phase), balance in vault.get_balance_timeseries()
        .latest()
        .items()
        if phase in (Phase.PENDING_OUT, Phase.COMMITTED)
        and address in (DEFAULT_ADDRESS, "ACCRUED_INCOMING", "ACCRUED_OUTGOING")
        and denom == contract_denomination
        and asset == DEFAULT_ASSET
    )
    posting_ins = None
    if accrue_balance > 0:
        interest_due = (
            (Decimal(monthly_interest_rate) * accrue_balance)
            .copy_abs()
            .quantize(Decimal(".01"), rounding=ROUND_HALF_DOWN)
        )
        if interest_due > 0:
            posting_ins = vault.make_internal_transfer_instructions(
                amount=interest_due,
                denomination=contract_denomination,
                from_account_id="1",
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                client_transaction_id="INTEREST_{}".format(vault.account_id),
            )

    # Charge any fees for going into the overdraft.
    elif accrue_balance < 0:
        fees_due = (
            (Decimal(monthly_overdraft_rate) * accrue_balance)
            .copy_abs()
            .quantize(Decimal(".01"), rounding=ROUND_HALF_DOWN)
        )
        if fees_due < 0:
            posting_ins = vault.make_internal_transfer_instructions(
                amount=fees_due,
                denomination=contract_denomination,
                from_account_id="1",
                from_account_address="ACCRUED_OUTGOING",
                to_account_id=vault.account_id,
                to_account_address="ACCRUED_INCOMING",
                asset=DEFAULT_ASSET,
                client_transaction_id="INTEREST_{}".format(vault.account_id),
            )

    # Submit a posting batch.
    if posting_ins:
        vault.instruct_posting_batch(
            posting_instructions=posting_ins, effective_date=effective_date
        )


def post_parameter_change_code(old_parameter_values, updated_parameter_values, effective_date):
    new_time = vault.get_account_creation_date() + timedelta(minutes=2)
    vault.update_event_type(
        event_type="TEST_EVENT",
        schedule=EventTypeSchedule(minute="*/2"),
        end_datetime=(vault.get_plan_creation_date() + timedelta(minutes=3)),
    )


@requires(parameters=True)
def derived_parameters(effective_date):
    permitted_denominations = vault.get_permitted_denominations()
    if _denomination not in permitted_denominations:
        raise Rejected(
            message="Invalid denominations used within this contract",
            reason_code=RejectedReason.AGAINST_TNC,
        )
    return {"denomination": _denomination}


@requires(calendar=["date_A", "date_B"])
def pre_posting_code(postings, effective_date):
    if len(postings) == 1:
        # Check that PI attributes and methods can be mocked.
        posting = postings[0]
        if (
            posting.client_batch_id != "123"
            or posting.value_timestamp != effective_date
            or posting.insertion_timestamp != effective_date
            or posting.batch_details != {}
            or posting.client_id != "1"
            or posting.batch_id != "2"
        ):
            raise Rejected(
                message="Not all PI attributes are set", reason_code=RejectedReason.AGAINST_TNC
            )
        if posting.balances()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)].net == 0:
            raise Rejected(
                message="Unexpected default PI balances", reason_code=RejectedReason.AGAINST_TNC
            )
        # Check that PIB balances method can be mocked.
        default_address = (
            vault.get_balance_timeseries()
            .latest()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)]
            .net
        )
        new_postings_balance = postings.balances()[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)
        ].net
        if default_address + new_postings_balance < 0:
            raise Rejected(
                message="Account Default address cannot go into overdraft",
                reason_code=RejectedReason.AGAINST_TNC,
            )
    if len(postings) == 2:
        # Check that Client Transaction attributes can be mocked.
        ct = vault.get_client_transactions()[("client-id", "client-transaction-id")]
        if ct.is_custom is True or ct.cancelled is True or ct.start_time != effective_date:
            raise Rejected(
                message="Unexpected Client Transaction attributes",
                reason_code=RejectedReason.AGAINST_TNC,
            )
        if (
            ct.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP")].settled != Decimal(10)
            or ct.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP")].authorised != Decimal(20)
            or ct.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP")].released != Decimal(0)
            or ct.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP")].unsettled != Decimal(10)
        ):
            raise Rejected(
                message="Unexpected Client Transaction effects",
                reason_code=RejectedReason.AGAINST_TNC,
            )

        if ct.balances()[(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)].net != Decimal(
            10
        ):
            raise Rejected(
                message="Unexpected Client Transaction balances",
                reason_code=RejectedReason.AGAINST_TNC,
            )
        return

    calendar_events = vault.get_calendar_events(calendar_ids=["date_A", "date_B"])
    if len(calendar_events) != 2:
        raise Rejected(
            "Wrong number of calendar events found", reason_code=RejectedReason.AGAINST_TNC
        )
    for event in calendar_events:
        if (
            event.start_timestamp.year != 2020
            or event.start_timestamp.month != 1
            or event.start_timestamp.day != 1
        ):
            raise Rejected(
                "Calendar event start_timestamp incorrect", reason_code=RejectedReason.AGAINST_TNC
            )


def post_posting_code(postings, effective_date):
    posting_count = sum(
        1 for p in vault.get_postings() if not p.credit and p.account_address == DEFAULT_ADDRESS
    )

    if posting_count >= 1:
        vault.add_account_note(
            body=str(posting_count),
            note_type=NoteType.RAW_TEXT,
            is_visible_to_customer=True,
            date=effective_date,
        )


# flake8: noqa
