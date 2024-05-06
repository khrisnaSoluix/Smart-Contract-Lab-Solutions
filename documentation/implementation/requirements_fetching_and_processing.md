_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers guidance and assumptions relating to fetching and processing data requirements, regardless of the hooks they take place in.

# Requirements Fetching and Processing

Unless specified otherwise `PostingInstruction` (Contracts API 3.x) is interchangeable with `Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]` for fetched / hook argument data, or `CustomInstruction` for contract-generated data. `PostingInstructionBatch` (Contracts API 3.x) is interchangeable with `PostingInstructionsDirective` (Contracts API 4.x) for contract-generated data.  `PostingInstructionBatch` is replaced by `list[Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]]` in Contracts API 4.x for fetched / hook argument data, which won't have equivalents for class methods or attributes.

## General Considerations

### Use of Observations and Intervals

Observations are preferred and Intervals should only really be used if there is no suitable Observation syntax for the required data.

#### Why

An observation allows us to constrain fetched data to (1 x n) data points. Using balances as an example,  `n` is the number of unique Balance Coordinates on the account. `n` is fairly well controlled by the contract writer, as they usually dictate the addresses being used. Of course, integrations can create postings with any combination of address, asset, denomination, and phase, but there is little to be done about that.
In contrast, an Interval will return (m x n) data points, where `m` is the number of entries in the timeseries. The contract writer has fairly little control on `m` as this is dictated by integrations. For example, an account may
have received any number of postings between two datetimes. Even if the interval is small, this only reduces the likelihood of `m` being large.

#### How

Contract writers must understand exactly why they need an interval and consider alternatives. There are tell-tale signs that an interval isn't actually needed:

- the contract only ever uses the `.latest()` method on the interval's timeseries - this is a clear indication that a latest or live observation could be used
- the contract only ever uses `.at()` method on the interval's timeseries, with a single datetime. In some cases this is acceptable, if that datetime is not known at fetching time

Even if an interval seems necessary, it is also worth considering alternatives. For example, using an extra address to avoid using an interval is likely to be much more performant.

### Performance

Please refer to the documentation hub reference at `<your_docs_hub_url>/reference/contracts/performance_considerations` for information concerning requirements fetching and impact to performance.

### Missing Data

Until the next Major version of Contracts API (4.0) is shipped, requesting data inside your hooks for datetimes that aren’t covered by the data requirements does not result in an Exception. Changing this behaviour would not be backwards compatible, so it is left as-is inside 3.x.

### Relative Fetching

Contracts must account for data requirements being fetched relative to the hook effective date (apart from ‘live’ balances/postings).

#### Why

For example, imagine that a schedule:

- Runs weekly at 01:00:00 on Mondays.
- Needs data for the last week (e.g. Week x Monday 00:00:00 to Week x Sunday 23:59:59)

If the requirement is set to 7 days, this will retrieve data Monday `X` 01:00:00 to Monday `X+1` 01:00:00. This means you won’t get data from 00:00:00 to 01:00:00 for Monday `X`. As per [Missing Data](#missing-data) you will not get an explicit error if you access data in this range.  This only applies to contracts that need a range of data other than `latest`.

#### How

One solution is to keep schedules with an effective_date at midnight, but this is not always possible.

Alternatively, add an additional day to your fetchers requirements to guarantee inclusion of the appropriate data, and then filter the data within the retrieved data:

- For methods returning timeseries, the `.at()` / `.before()` / `.latest()` methods may be sufficient. In more complicated cases the `.all()` method lets you retrieve an ordered `List[Tuple[datetime, BalanceDefaultDict]]`, which can then be filtered on datetime.
- Other data types can be filtered on specific attributes, such as `PostingInstruction` and `value_timestamp`

## Postings

### Contracts API and Core/Postings API Differences (CL 3.x only)

The Contracts API has two relevant types, `PostingInstructionBatch` and `PostingInstruction`. These appear to be aligned to the corresponding Core/Postings API types, which we will prefix with `core` for clarity going forward, but there are some subtle differences that can catch contract writers out.

#### Why

The Contracts API types are typically flattened and include attributes from higher order types to simplify processing. For example the `PostingInstruction` has a number of attributes that belong to `core_PostingInstructionBatch`, such as `value_timestamp` or `batch_id`. These are fairly obvious and don't cause too many issues.

However, it is less clear that the Contracts API `PostingInstruction` is actually based off a `core_Posting`, and then has flattened `core_PostingInstructionBatch` and `core_PostingInstruction` attributes added to it. For example, consider an outbound authorisation. As per the Core/Postings API documentation, this results in two `core_Posting`s: a debit on the target account, and a credit on the internal account. The contract is only exposed to the `core_Posting`(s) affecting the account in question, which are then enriched with attributes from the `core_PostingInstruction` that causes the `core_Posting` and the `core_PostingInstructionBatch` that contains the `core_PostingInstruction`. Combined, this results in the `PostingInstruction`. There are two main consequences:

1. In some cases, a contract execution may see multiple `core_Posting` from the same `core_PostingInstruction`. For example, a custom instruction with multiple `core_Posting`s that affect a given account, or an accidental transfer that is set to debit and credit the same account. The contract will therefore see multiple `PostingInstruction`s for a single `core_PostingInstruction`.
2. Certain fields are not as unique as they seem, as they may actually identify the `core_PostingInstruction` and not the `core_Posting`. Combined with the previous point, this could affect contract behaviours, such as logic to generate unique ids for `client_transaction_id` . For example the `id` field is at a `core_PostingInstruction` level, so it is possible to have two `PostingInstruction` with the same `id` value.

#### How

In general, these issues arise from bugs/accidents, or remediating incidents. It shouldn't be necessary for an external custom instruction to modify multiple Balance dimensions on an account _and_ require the contract to process these postings on top. The processing can be avoided with overrides (see pre/post-posting hook guidance)
One alternative is to define what the contract should handle and reject the rest. For example, you could explicitly reject custom instructions that affect the same account multiple times. See  pre/post-posting hook guidance for further information.
Finally, it is possible to combine the `PostingInstruction` level attributes with loop counters to generate truly unique ids.

### Determining posting amounts

Avoid relying on `amount` and `credit` `PostingInstruction` attributes to determine the impact of a `PostingInstruction` to an account's balances

#### Why

Relying `amount` and `credit` will work with the simplest uses of the various `PostingInstruction` types (e.g. hard settlements, transfers). As soon as multiple settlements, releases or authorisation adjustments are involved, the behaviour of these fields is not as intuitive. For example, the `credit` attribute is derived from the original `PostingInstruction` within a `ClientTransaction`. This means that releasing an inbound authorisation is still considered to be a `credit` even though it is effectively 'cancelling' an inbound amount and that could be considered to be a `debit`. It is simpler and safer not to try and replicate these mechanics inside a contract.

#### How

The `PostingInstruction` and `PostingInstructionBatch` types both have a `.balances()` method that will safely provide the net impact to each set of Balance dimensions. It can be useful to have a reusable helper to extract a Decimal from these balances. For example:

```python
def _available_balance(balances: BalanceDefaultDict) -> Decimal:
    pass
```

This helper can be used to check the available balance at a given point in time, by passing in data from `vault.get_balance_timeseries().latest()/at()/before()`, or can be used to check the impact of a given `PostingInstruction` or `PostingInstructionBatch` by passing in the relevant `.balances()` output.

It is ok to rely on `amount` and `credit` provided you have already filtered for the hard settlement/transfer types, as these behave intuitively

> It is not currently possible to use `.balances()` in Supervisor Contracts.

### Handling 0 amount Postings

Logic that handles `PostingInstruction`/`PostingInstructionBatch` amounts (see [Determining posting amounts](#determining-posting-amounts)) should account for 0 and None amount postings.

#### Why

Although 0 amounts are not allowed on the Core/Postings API, there are scenarios where Vault's `posting-processor` behaviour can result in 0 amounts. For example:

- Outbound authorisation for $1
- Non-Final settlement for $1
- Final settlement with no amount - this last instruction result in 0 amount, as would a release

or when creating an authorisation adjustment with a replacement amount equal to the currently authorised amount:

- Outbound authorisation for $1
- Authorisation adjustment with replacement_amount = $1

#### How

If you use a condition like below, be aware that the `== 0` will go into one of the branches and the logic must be able to handle it.

```python
if amount > 0: # (or < 0)
    ...
else:
    ...
```

Alternatively, you might find it easier to discard/no-op the `== 0` scenario

```python
if amount<0:
    ...
elif amount > 0:
    ...
else
    pass
```

## Client Transactions

### Client Transaction Types

We allow client transactions to have a 'type' that is set by the first posting instruction in the client transaction.

#### Why

Product features often operate on a transaction type level (e.g. limit the number of ATM withdrawals in a month, charge a different interest rate for purchases). We need a consistent way of identifying the type, to reduce integration burden.
We are unaware of significant use cases where the type will change across the lifecycle of a client transaction, so we can reduce contract complexity by assuming that it is fixed at the creation of the client transaction (i.e. the first posting instruction with the specific client transaction id).

#### How

- We prefer to use the `type` key on `PostingInstruction.instruction_details`. Our client transaction utils support other keys if further granularity is required.
- We read this key on the first `PostingInstruction` returned by `ClientTransaction.posting_instructions`

### Client Transaction Granularity

We assume that each posting instruction within a client transaction that alters the client transaction's net balance represents an additional debit/credit of that client transaction's type.

#### Why

Consider an initial authorisation for $100. If this is settled via a non-final settlement and a subsequent final settlement, each for $50, we consider it would be arguably unfair to count it twice with respect to a transaction type limit.
Now consider that this authorisation is increased explicitly via authorisation adjustment or implicitly via a settlement above the initial authorisation amount. We consider this amendment to be more like an additional transaction, and would therefore count it with respect to a transaction type limit.

#### How

N/A
