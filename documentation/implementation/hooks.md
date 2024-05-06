_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers guidance relating to specific hooks

# Hooks

Unless specified otherwise `PostingInstruction` (Contracts API 3.x) is interchangeable with `Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]` for fetched / hook argument data, or `CustomInstruction` for contract-generated data. `PostingInstructionBatch` (Contracts API 3.x) is interchangeable with `PostingInstructionsDirective` (Contracts API 4.x) for contract-generated data.  `PostingInstructionBatch` is replaced by `list[Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]]` in Contracts API 4.x for fetched / hook argument data, which won't have equivalents for class methods or attributes.

## Do not add Empty hooks

Never add empty hooks to a contract

### Why

A hook will always be executed by Vault if a relevant event occurs, even if the hook has neither logic nor fetching. For example, an empty post-parameter hook will be triggered after every parameter change. This has a performance cost for no benefit and should be avoided.

## Posting Hooks

In this section, `pre_posting_code` and `post_posting_code` (Contracts API 3.x) are interchangeable with `pre_posting_hook` and `post_posting_hook` (Contracts API 4.x).

### Posting Overrides

Consider having `PostingInstruction`/`PostingInstructionBatch` level overrides in both posting hooks.

#### Why

There are often scenarios, such as unusual operational requests, or incident remediation, where we want to bypass hooks processing at varying levels. At times this can be useful for testing purposes too. For example, we may prevent withdrawals from Deposit products with specific T&Cs, but need to bypass this if a customer was accidentally credited excessive balances.

#### How

It is ultimately up to the client/contract writer to make a call on the level at which these overrides sit, and where they sit inside the hook (e.g. should they bypass all processing, or just specific features?).
The following example works at an `PostingInstructionBatch` level, making use of the `batch_details` metadata. A custom `withdrawal_override` key is added and, if it's value is `true` (irrespective of case), we return early. The same concept could be applied to an individual posting, using `PostingInstruction`'s `instruction_details`.

```python
    if postings.batch_details.get("withdrawal_override", "false").lower() == "true":
        return
```

> While the `PostingInstruction` `advice` attribute aims to serve this purpose, we tend not to use is as a) it does not exist on all instruction types and b) it lacks the context-based granularity we sometimes need.

### Explicitly Support/Reject Multiple Instructions

A `PostingInstructionBatch` can include multiple `PostingInstruction`. We recommend explicitly rejecting these scenarios if the contract has not been designed with this in mind.

#### Why

There are a number of complexities that can arise from processing multiple `ProcessInstruction` in posting hooks. Unless the contract has been designed to handle these, blindly allowing them can be dangerous.

#### How

A simple block can be added to the `pre_posting_code` and `post_posting_code`. The latter is required as some instructions are not sent to `pre_posting_code` and won't be caught there. For example, a `PostingInstructionBatch` could contain multiple settlements that do not necessarily trigger `pre_posting_code`.
In Contracts API 3.x:

```python
    if len(postings) > 1:
        raise Rejected(
            "Multiple postings in batch not supported",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )
```

In Contracts API 4.x:

```python
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    if len(hook_arguments.posting_instructions) > 1:
        return PrePostingHookResult(rejection=Rejection(
            message="Multiple postings in batch not supported",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        ))
```

### Naming first positional argument as `incoming_posting_batch` instead of `postings`

This applies to Contracts API 3.x only, as the arguments are more clearly named in Contracts API 4.x.

#### Why

There are two things the posting hooks can have access to:

1. incoming posting batch to be processed
2. historical postings as specified by @requires decorator
if both are named as `postings` in the method implementation, it can be confusing especially for people unfamiliar with the code base;
Furthermore, the actual object type passed in is a `PostingInstructionBatch`, not `list[PostingInstruction]`, therefore, naming it as postings
can be slightly misleading.

#### How

Simply name the positional argument in posting hook method signatures to be something more explicit, `incoming_posting_batch` can be an adequate convention.

e.g.

```python
@requires(
    balances="latest live",
    postings="1 month",
)
def pre_posting_code(incoming_posting_batch: PostingInstructionBatch, effective_date: datetime):
    pass
```

instead of

```python
@requires(
    balances="latest live",
    postings="1 month",
)
def pre_posting_code(postings: list[PostingInstruction], effective_date: datetime):
    pass
```

## Close_code

In this section, `close_code` (Contracts API 3.x) is interchangeable with `deactivation_hook` (Contracts API 4.x).

### Zero-out Custom Addresses

The `close_code` hook should zero out any custom addresses that the contract uses.

#### Why

Contracts should encapsulate their logic as much as possible and not rely on other services knowing about implementation details like custom addresses. Otherwise we risk tightly coupling the contract and these services, making upgrades more complicated. This is actually the main purpose behind the `close_code` hook.

#### How

The `close_code` should follow a few simple rules:

1. Consider every existing address that can be non-zero when close_code is run and define if and how they should be zero'd out. In some cases, it may not be ok for `close_code` to not zero-out these balances (e.g. we expect the customer to repay outstanding balances before they can close the account). If this is the case, `close_code` should be made to fail explicitly when these conditions are not met. This can be achieved as follows (example from the credit card).

    In Contracts API 3.x:

    ```python
    if full_outstanding_balance != Decimal(0):
        raise Rejected(
            "Full Outstanding Balance is not zero",
            reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
        )
    ```

    In Contracts API 4.x:

    ```python
    if full_outstanding_balance != Decimal(0):
        return DeactivationHookResult(
            rejection=Rejection(
                message="Full Outstanding Balance is not zero",
                reason_code=RejectedReason.CLIENT_CUSTOM_REASON,
            )
        )
    ```

2. Do not create any new addresses within `close_code` that you cannot zero out within the same hook execution

A good example to consider is interest accrual. A contract may need closing before accrued interest has been applied, or there may be an accrued interest amount that is too small to be applied. In both cases there will be a non-zero accrual balance definition which `close_code` should deal with. The precise behaviour needs to be driven by business requirements. In this case the product may need to zero-out or apply any unapplied interest, and decide what to do with the remainder (zero-out, round up, round down).

## Conversion Hook

### Converting Non-Recurring Schedules Workaround

#### Why

There is a bug in Vault 4.x when converting CLv4 -> CLv4 accounts which have schedules that are in `SCHEDULE_STATUS_COMPLETED` state at the time of conversion. Schedules which could reach a completed state before conversion include:

1. schedules with a fixed number of runs which are defined with a discrete cron expression:

    ```python
    # (a) runs once on 2023-01-01 00:00:00
    ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(second=0, minute=0, hour=0, day=1, month=1, year=2023),
    )

    # (b) runs three times: 2023-01-01 00:00:00, 2023-02-01 00:00:00, 2023-03-01 00:00:00
    ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(second=0, minute=0, hour=0, day=1, month="1-3", year=2023),
    )
    ```

2. repeating schedules with a defined `end_datetime`:

    ```python
    ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(second=0, minute=0, hour=0),
        end_datetime=end_datetime,
    )
    ```

3. ad-hoc schedules that end after `n` events, such as schedules which are affected and updated based on parameter changes

If the account schedules are to be unchanged, the existing schedules have to be passed into the result in the `conversion_hook`:

```python
def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    return ConversionHookResult(scheduled_events_return_value=hook_arguments.existing_schedules)
```

This recreates the schedules in the scheduler for the converted account with the same `ScheduledEvent` definition. However, in the case of a schedule in `SCHEDULE_STATUS_COMPLETED` status, the following errors are observed:

1. The expression next run time is scheduled before the start time and does not have a next run time
2. The end datetime is before the schedule's start datetime

#### How

In the `conversion_hook`, the only information we have access to regarding the schedules is:

- the `ScheduledEvent` definition which includes a subset of `start_datetime`, `end_datetime`, `expression`, `schedule_method` and `skip`
- the `last_execution_datetime`

In the case of a one-off schedule, if `last_execution_datetime` is not None this implies that the schedule has run and hence is completed. However we can't leverage this in cases where the schedules run more than once.

Instead, we can utilise the `end_datetime` attribute on the `ScheduledEvent` object and set the `end_datetime` for the schedule as soon as we know what it will be.

- For example 1: the expressions will be generated during the `activation_hook`, and these calculations can be extended to derive the `end_datetime` of the schedule.

    ```python
    # (a) runs once on 2023-01-01 00:00:00
    ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(second=0, minute=0, hour=0, day=1, month=1, year=2023),
        end_datetime=datetime(2023, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    )

    # (b) runs three times: 2023-01-01 00:00:00, 2023-02-01 00:00:00, 2023-03-01 00:00:00
    ScheduledEvent(
        start_datetime=start_datetime,
        expression=ScheduleExpression(second=0, minute=0, hour=0, day=1, month="1-3", year=2023),
        end_datetime=datetime(2023, 3, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    )
    ```

- For example 2: by definition, the recurring cron expression is bound by the `start_datetime` and `end_datetime` (hence the schedule has a finite number of jobs defined) and clearly the `end_datetime` will be populated.
- For example 3: the ad-hoc schedules often have unique requirements so the guidance is to ensure that the `end_datetime` should be populated as soon as it is known. This could be in the `activation_hook`, during `scheduled_event_hook` execution or another trigger such as `post_parameter_change_hook`.

In the conversion hook, each schedule which could be in a `SCHEDULE_STATUS_COMPLETED` state must check if an `end_datetime` has been set, and if so, if it is before the `conversion_hook`'s `effective_datetime`. If this is true, then the schedule must be completed. The event should be updated with the end of time expression and the `end_datetime` set to the `effective_datetime`.

```python
def conversion_hook(
    vault: SmartContractVault, hook_arguments: ConversionHookArguments
) -> Optional[ConversionHookResult]:
    effective_datetime = hook_arguments.effective_datetime
    scheduled_events = hook_arguments.existing_schedules

    scheduled_events.update(
        utils.update_completed_schedules(
            scheduled_events=scheduled_events,
            effective_datetime=effective_datetime,
            potentially_completed_schedules=["EVENT_1", "EVENT_2"],
        )
    )

    return ConversionHookResult(
        scheduled_events_return_value=scheduled_events,
    )
```

Please keep in mind the [Known Race Condition](directives.md#known-race-condition) when updating schedules, as this is also applicable to the updating of schedules when running conversion.
