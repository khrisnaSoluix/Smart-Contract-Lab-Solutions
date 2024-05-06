# Partial Fee Collection - Design Doc

## Scope

Partial fee collection is the ability to partially charge a fee to prevent the customer's balance becoming negative. The remaining fee amount will be held until the account is funded which will result in the outstanding fee amount being charged.

This is additional scope that has been added to all existing fee CBFs, therefore we need a general approach to handle the new requirements.

## Requirements

This design document pertains to several CBFs, a non-exhaustive list is presented below:

* [Inactivity and Inactivity Fee](https://pennyworth.atlassian.net/browse/CPP-2031)
* [Paper Statement Fee](https://pennyworth.atlassian.net/browse/CPP-1991)
* [Monthly Maintenance Fee](https://pennyworth.atlassian.net/browse/CPP-1921)

## Assumptions

* Partial fee collection is only supported by deposit (Liability) products
* All scheduled fees will have the requirement to handle partial fee collection
* All fees will charge the account's DEFAULT address to collect the fee

## Proposed Implementations

### Single Outstanding Fee Tracking Address

#### Description

This approach utilises a single tracking address to track the outstanding fees

#### Pros

* Only a single tracking balance address required, this scales O(1)

#### Cons

* Loss of information when since every fee posts to the same address
* Unable to determine which outstanding partially charged fee is being charged upon account funding (without intensive historic posting fetching and analysis)

### Outstanding Fee Tracking Address Per Fee Type

#### Description

This approach utilises a tracking address per fee type to track the outstanding fees.

#### Pros

* Each fee type is tracked separately

#### Cons

* A separate tracking balance address required per fee, this scales O(n)

## Agreed Implementation

Each fee type will define a tracking address and the fees will be collected upon account funding using a fee type hierarchy. To ensure consistency across fees a partial fee handler should be defined. This handler will define a standard interface for fee features and contract templates to handle partial fee charging and collecting. Any uncharged fee amount will be tracked against the aforementioned tracking address, this can then be collected upon account funding.

Performance considerations mean that repaying pending fees by age is undesirable as the worst case scenario will mean that the entire balance history for each pending address is required.

Therefore, upon account funding each outstanding fee will be collected using a fee hierarchy rather than an age hierarchy. For example:

```plaintext
dt_1 < dt_2 < dt_3 < dt_4

dt_1: fee_a_pending = 5
dt_2: fee_b_pending = 7
dt_3: fee_a_pending increased by additional 5 (total = 10)
```

Assuming a fee hierarchy of a then b:

```plaintext
dt_4: account is funded by 15, the following will be observed
fee_a_pending paid off in full (10)
fee_b_pending partially paid off (5)
```

### Data Definition

#### Contract Parameters

* `<fee_name>_allow_partial_fees`: Template parameter - `OptionalShape(common_parameters.BoolShape)` - boolean to define whether the fee should be partially charged, if applicable. This is a per fee parameter.

#### Balance addresses

* `OUTSTANDING_<FEE_TYPE>_TRACKER`: the balance address where outstanding fee amounts to be charged are tracked

### Technical Logic

#### Update Existing Fee Features

Each existing fee that now supports partial fee collection should be updated to:

* Define the template parameter
* Define the partial fee balance address
* The apply/charge function signature should be updated to support balances being passed through

The apply/charge function should create the CustomInstruction to charge the full fee amount, this should then be passed to the fee handler which determines whether the CustomInstruction should be instructed or whether it should be overridden to be partially charged.

#### Define Partial Fee Handler

* The PartialFeeCollection interface should be defined in each fee feature that supports partial fees, an example definition is:

```python
PartialFeeCollection = NamedTuple(
    "PartialFeeCollection",
    [
        ("outstanding_fee_address", str),
        ("fee_type", str),
        (
            "get_internal_account_parameter",
            Callable[
                # vault: SmartContractVault,
                ...,
                str,
            ],
        )
    ],
)
```

* The partial fee handler must define a function to charge fees partially on a scheduled event

```python
def charge_partial_fee(
    vault: SmartContractVault,
    fee_custom_instruction: CustomInstruction,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None
  ) -> list[CustomInstruction]:

    if balances is None:
        balances = get_balances(EFFECTIVE_OBSERVATION)

    if denomination is None:
        denomination = get_denomination_parameter()

    postings: list[Posting] = []

    available_balance = utils.balance_at_coordinate(
       balances=balances, address=DEFAULT_ADDRESS, denomination=denomination
    )

    fee_charged = utils.balance_at_coordinates(
        balances=fee_custom_instruction.balances()
        address=DEFAULT_ADDRESS,
        denomination=denomination
    )

    chargeable_fee = min(fee_charged, available_balance)
    outstanding_fee = fee_charged - chargeable_fee

    if chargeable_fee > Decimal("0"):
        postings += fees.fee_postings()

    if outstanding_fee > Decimal("0"):
        # update the _pending address with the unpaid fee amount
        postings += utils.create_postings()

    if postings:
        return [
            CustomInstruction(
                postings=postings,
                instruction_details=fee_custom_instruction.instruction_details
                override_all_restrictions=True
            )
        ]

```

* The partial fee handler must define a function to be able to charge outstanding fees upon an account being funded

```python
def charge_outstanding_fees(
    vault: SmartContractVault,
    fees: list[deposit_interfaces.PartialFeeCollection],
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None
) -> list[CustomInstruction]:

    if balances is None:
        balances = get_balances(LIVE_OBSERVATION)

    if denomination is None:
        denomination = get_denomination_parameter()

    custom_instructions: list[CustomInstruction] = []
    available_balance = utils.balance_at_coordinate(
        address=DEFAULT_ADDRESS, denomination=denomination
    )

    for fee in fees:
        if available_balance <= Decimal("0"):
            break

        postings: list[Posting] = []
        outstanding_fee_amount = utils.balance_at_coordinate(address=fee.outstanding_fee_address, denomination=denomination)
        amount_to_charge = min(outstanding_fee_amount, available_balance)

        if amount_to_charge > Decimal("0"):
            # charge the fee
            postings = fees.fee_postings()
            # reduce the outstanding balance by the charged amount
            postings += utils.create_postings()

            custom_instructions.append(
                CustomInstruction(
                    postings=postings,
                    instruction_details={
                        "description": fee.fee_type,
                        "event": f"Collect outstanding {fee.fee_type} amount",
                    },
                    override_all_restrictions=True,
                )
            )

            available_balance -= amount_to_charge

    return custom_instructions
```

#### Accounting Considerations

The `_TRACKER` address is used for tracking the outstanding fee to be collected upon account funding. As a result, the outstanding fee amount is only recognised once it is collected and the `INTERNAL_CONTRA` address should be used for double entry bookkeeping purposes when crediting/debiting the tracker address. Any fee that is realised must debit the `DEFAULT` address of the account and credit the relevant internal account.

#### Preventing Account Closure

All fees must be fully paid before an account can be closed. Therefore any balance in the outstanding fee tracking addresses should raise a `Rejection` in the `deactivation_hook()`

### Further considerations

* Collecting outstanding fees in datetime order (oldest first). Ideally outstanding fees should be collected in order in which they become overdue. Considering the example given in the [Agreed Implementation section](#agreed-implementation), this would result in the fees being collected in the following order: outstanding `fee_a` from `dt_1` being repaid first, then the outstanding `fee_b` from `dt_2` then partially repaying outstanding `fee_a` from `dt_3`.
