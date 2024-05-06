# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
An example that shows a required Contract Module being declared and used in a Smart Contract
"""
display_name = "Contract with shared function"
api = "3.9.0"
version = "1.0.0"
summary = "Contract with shared function"
parameters = [
    Parameter(
        name="denomination",
        shape=DenominationShape,
        level=Level.TEMPLATE,
        description="Default denomination.",
        display_name="Default denomination for the contract.",
    ),
    Parameter(
        name="interest_rate",
        shape=NumberShape(kind=NumberKind.PERCENTAGE, min_value=0, max_value=1, step=0.01),
        level=Level.TEMPLATE,
        description="Gross Interest Reate",
        display_name="Rate paid on positive balances",
    ),
]

contract_module_imports = [
    ContractModule(
        alias="interest",
        expected_interface=[
            SharedFunction(
                name="round_accrual",
                args=[SharedFunctionArg(name="amount", type="Decimal")],
                return_type="Decimal",
            ),
            SharedFunction(
                name="round_fulfilment",
                args=[SharedFunctionArg(name="amount", type="Decimal")],
                return_type="Decimal",
            ),
            SharedFunction(
                name="round_interest_rate",
                args=[SharedFunctionArg(name="amount", type="Decimal")],
                return_type="Decimal",
            ),
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
    ),
    ContractModule(
        alias="module_2",
        expected_interface=[
            SharedFunction(
                name="get_parameter_2",
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
    ),
]

pnl_account = "1"


def execution_schedules():
    accrue_interest_schedule = {"hour": "00", "minute": "00", "second": "00"}
    return [
        ("ACCRUE_INTEREST", accrue_interest_schedule),
    ]


@requires(
    event_type="ACCRUE_INTEREST",
    modules=["interest", "module_2"],
    parameters=True,
    balances="latest",
)
def scheduled_code(event_type, effective_date):
    denomination = vault.modules["module_2"].get_parameter_2(vault, "denomination")
    interest_rate = vault.get_parameter_timeseries(name="interest_rate").latest()
    balances = vault.get_balance_timeseries().latest()

    if event_type == "ACCRUE_INTEREST":
        effective_balance = balances[
            (DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)
        ].net
        amount_to_accrue = 0
        if effective_balance > 0:
            daily_rate = vault.modules["interest"].round_interest_rate(Decimal(interest_rate / 365))
            amount_to_accrue = vault.modules["interest"].round_accrual(
                Decimal(effective_balance * daily_rate)
            )
        if amount_to_accrue > 0:
            posting_ins = vault.make_internal_transfer_instructions(
                amount=amount_to_accrue,
                denomination=denomination,
                client_transaction_id=vault.get_hook_execution_id() + "_ACCRUE_INTEREST",
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=pnl_account,
                to_account_address=DEFAULT_ADDRESS,
                pics=[],
                instruction_details={
                    "description": f"Daily interest accrued at {daily_rate} on balance "
                    f"of {effective_balance}",
                    "event": "ACCRUE_INTEREST",
                },
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
            )
            vault.instruct_posting_batch(
                posting_instructions=posting_ins, effective_date=effective_date
            )


def _get_parameter(vault, name, at=None, is_json=False, optional=False, default_value=None):
    return vault.modules["interest"].get_parameter(
        vault, name, at, is_json, optional, default_value
    )


def _round_accrual(
    vault,
    amount: Decimal,
):
    return vault.modules["interest"].round_accrual(amount)


# flake8: noqa: F821
