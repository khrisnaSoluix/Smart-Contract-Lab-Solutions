# Paper Statement Fee CBF - Design Doc

## Scope

The proposed feature is designed for use in deposit and transaction accounts.
The feature should be able to determine the following.

* Determine if a paper statement fee amount is setup for the account and if the account has paper statements enabled.
* a monthly schedule to charge the fee, if the day does not exist, it will roll over to the first day of the next month
* Payment Options (insufficient funds):
  * have the ability to charge the fee to the account balance and take the account balance negative
  * Partially extract funds from the account, if there are insufficient funds, take the existing funds to partially cover the payment whilst collecting new funds on deposit.
* Otherwise the payment will be taken in full.

## Requirements

[CBF: Paper Statement Fee](https://pennyworth.atlassian.net/browse/CPP-1991)

## Agreed Implementation

## Implementation

### Data Definition

#### Contract Parameters

The feature must define following parameters:

1. `PAPER_STATEMENTS_RATE`: Template parameter - `NumberShape` - a parameter which determines the amount to be charged.
2. `PAPER_STATEMENT_FEE_DAY`: Instance parameter - `NumberShape` - a that determines the day that the fee is collected
3. `PAPER_STATEMENT_FEE_HOUR`: Template parameter - `NumberShape` - a parameter that determines the hour that the fee is collected
4. `PAPER_STATEMENT_FEE_MINUTE`: Template parameter - `NumberShape` - a parameter that determines the minute that the fee is collected
5. `PAPER_STATEMENT_FEE_SECOND`: Template parameter - `NumberShape` - a parameter that determines the second that the fee is collected
6. `PAPER_STATEMENT_FEE_INCOME_ACCOUNT`: Template parameter - `StringShape`, a parameter that determines the account that the statement fee income should go to.

Additionally some optional parameters may be defined to customise the behaviour in certain scenarios.
7. `PAPER_STATEMENTS_PARTIAL_PAYMENTS`: Template parameter - `BoolShape` - a parameter that determines if a partial fee is allowed if there is a insufficient balance, or whether a partial payment strategy will be used, Defaults to false: Any insufficient funds will lead to a negative balance.

##### BoolShape

As Boolshape is not defined in the contracts api, the referenced BoolShape will be implemented as follow.

```py
UnionShape(
    items=[
        UnionItem(key="True", display_name="True"),
        UnionItem(key="False", display_name="False"),
    ]
),
```

#### Balance Addresses

1. PAPER_STATEMENT_FEE_PENDING:  a address to store the fee that is due. This is used as a tracking address for any partially charged fee amount.

### Technical Logic

#### Schedule implementation

The schedule should be defined using `utils.monthly_scheduled_event` the default behaviour for this event puts the failover as the day before. The requirements state that if the failover is required, it should be rolled over the the first day of the next month, this can be achieved by setting the failover value to `ScheduleFailover.FIRST_VALID_DAY_AFTER`

Schedule start datetime, the first schedule start datetime should be calculated from 1 month after the account opening datetime so that a fee is not charged in the first month.
On schedule execution, fetching the latest parameter would return the current state of the schedule at the execution timestamp. This would allow for the schedule to know whether or not to instruct the final statement fee.

#### Fee Payment Options

2 Fee Payment Options are supported:

1. Overdraw the statement fee from the account balance, turning it negative.
2. Extract a partial fee amount from the account balance, keeping track of what is owed. This owed amount is extracted from the balance after the account is funded. This will be done via the post posting hook.

The fee will be charged by transferring the due amount from the default balance to the Fee Income Account.

##### Partial Payment Implementation

In the event there is not sufficient funds in the default balance to cover the required fees. If the partial payments parameter is enabled, in the event a payment were to take an account balance negative, only the total remaining balance will be deducted, zeroing out the primary balance and leaving the remaining due in the `PAPER_STATEMENT_FEE_PENDING` address.
On a post posting, the extraction step would then also be ran to instruct any inflows of money to pay off the pending fee.
There will be a singular partial payment address, this means that the collection will not be differentiable from other partial payment features.
Be wary that the fee settlement step should account for when the main balance is negative and it does not zero out the negative balance and transfer this to the pending paper statement fee.
The partial payments implementation will be detailed in the partial payments document.

##### Payment Instruction Breakdown

Given the following Addresses:

* Default Address (or multiple addresses, these are the balance addresses for the account related with customer money)
* Internal Account (This is the address where the fees will be moved to)
* Contra (Internal Address for Double Entry Bookkeeping)
* Pending Fee Address ( PAPER_STATEMENT_FEE_PENDING)

**Payment Logic:**
Payments will be broken up into 2 stages. Fee Collection and Partial Fee Collection.

Fee Collection:

1. If the default balance exceeds the fee, then collect the fee by instructing a posting from the default address to the internal fee collection account.
2. If partial payments are disabled, then the amount will be the full amount regardless of the balance
     if partial payments are enabled then the posting amount will be $min(balance, fee)$

3. Partial Payments are collected from a partial payments address, this will be detailed in the partial payments design document
