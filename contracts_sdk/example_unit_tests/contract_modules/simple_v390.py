api = "3.9.0"

ACCRUAL_DECIMAL_PLACES = 5
FULFILMENT_DECIMAL_PLACES = 2


def round_accrual(amount: Decimal) -> Decimal:
    pad = f".{0:0{ACCRUAL_DECIMAL_PLACES}}"
    return amount.quantize(Decimal(pad), rounding=ROUND_HALF_UP)


def round_fulfilment(amount: Decimal) -> Decimal:
    pad = f".{0:0{FULFILMENT_DECIMAL_PLACES}}"
    return amount.quantize(Decimal(pad), rounding=ROUND_HALF_UP)


def build_posting_instruction_batch(
    amount: Decimal, effective_date: datetime
) -> PostingInstructionBatch:
    if amount < Decimal("0"):
        raise Rejected("Cannot build PostingInstructions with negative amount")

    return PostingInstructionBatch(
        posting_instructions=[
            PostingInstruction(
                custom_instruction_grouping_key="some_key",
                client_transaction_id="id_12345",
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                pics=[],
                credit=True,
                amount=amount,
                denomination="GBP",
                account_id="account_id",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            )
        ],
        value_timestamp=effective_date,
        insertion_timestamp=effective_date,
        batch_details={},
        client_batch_id="123",
    )


# flake8: noqa
