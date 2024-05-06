_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers implementation guidance specific to the way we create and instruct different types of directives (schedules, workflows, postings)

# Directives

Unless specified otherwise `PostingInstruction` (Contracts API 3.x) is interchangeable with `Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]` for fetched / hook argument data, or `CustomInstruction` for contract-generated data. `PostingInstructionBatch` (Contracts API 3.x) is interchangeable with `PostingInstructionsDirective` (Contracts API 4.x) for contract-generated data.  `PostingInstructionBatch` is replaced by `list[PostingInstruction]` in Contracts API 4.x for fetched / hook argument data, which won't have equivalents for class methods or attributes.

## Posting Instruction Batches

### Atomicity and Consolidation of Batches

As a general rule, keep the number of batches instructed in a hook to a minimum (ideally one).

#### Why

A single `PostingInstructionBatch` is processed atomically. Either all `PostingInstruction` in the batch are accepted and committed or all are rejected and not committed. Instructing multiple `PostingInstructionBatch` breaks this atomicity and can lead to scenarios where some `PostingInstruction` are accepted and others are rejected, despite them coming from the same hook execution. This in turn introduces complex scenarios to debug and remediate.

Committing directives is also typically one, if not the longest part of contract execution. As the postings processor has a finite throughput reducing the number of batches to be committed helps with this.

#### How

There are many ways to accidentally instruct multiple batches. One common anti-pattern is (Contracts API 3.x):

```python
# DO NOT
for day in days:
    instructions = _some_method_to_generate_postings
    vault.instruct_posting_batch(
        posting_instructions=instructions,
        value_datetime=effective_date,
    )
```

Instead, put the instructions in the same batch, e.g.

```python
posting_instructions = []
for day in days:
    posting_instructions.extend(
        _some_method_to_generate_postings
    )
vault.instruct_posting_batch(
    posting_instructions=posting_instructions,
    value_datetime=effective_date,
)
```

The same applies in Contracts API 4.x:

```python
# DO NOT
for day in days:
    instructions = _some_method_to_generate_postings
    PostingInstructionsDirective(
        posting_instructions=instructions,
        value_datetime=hook_arguments.effective_date,
    )
```

versus

```python
posting_instructions = []
for day in days:
    instructions.extend(_some_method_to_generate_postings)
PostingInstructionsDirective(
    posting_instructions=instructions,
    value_datetime=hook_arguments.effective_date,
)
```

Also see the [Avoid Instructing Posting Instruction Batches within helpers](#avoid-instructing-posting-instruction-batches-within-helpers)

### Avoid Instructing Posting Instruction Batches within helpers

While it may seem convenient to nest calls to `vault.instruct_posting_batch()` within helpers we recommend you avoid this. This only applies to Contracts API 3.x as there is no Contracts API 4.x equivalent.

#### Why

It is easy to end up with a hook + helper structure like

```python
def post_posting_code(postings: List[PostingInstruction], effective_date: datetime):
    _charge_withdrawal_fee_a(vault, postings, effective_date)
    _charge_withdrawal_fee_b(vault, postings, effective_date)

def _charge_withdrawal_fee_a(vault, postings, effective_date):
    fee_instructions = []
    # some logic to populate instructions
    vault.instruct_posting_batch(fee_instructions)

def _charge_withdrawal_fee_b(vault, postings, effective_date):
    fee_instructions = []
    # some logic to populate instructions
    vault.instruct_posting_batch(fee_instructions)
```

This makes it easy to:

- Lose track of where you are instructing PIBs and you risk instructing more than one per hook execution, which isn’t normally desirable (see [Atomicity and Consolidation of Batches](#atomicity-and-consolidation-of-batches))

- Reduce reusability of your methods. A given contract may want to create some instructions and instruct a PIB containing these instructions (e.g. a single post-posting fee), lumping the two together in a single helper. Another contract may want to use the same logic to create the instructions, but then add some further instructions related to another feature (e.g another post-posting fee), and finally instruct a PIB with both sets of instructions. The second contract cannot re-use the helper implementing the first fee without changing it to extract the logic to create the instructions.

####  How

Consider making your helper methods return `list[PostingInstruction]` which can then be instructed in a PIB later on. The earlier example would look like

```python
def post_posting_code(postings: List[PostingInstruction], effective_date: datetime):
    posting_instructions = []
    posting_instructions.extend(
        _charge_withdrawal_fee_a(vault, postings, effective_date)
    )
    posting_instructions.extend(
        _charge_withdrawal_fee_b(vault, postings, effective_date)
    )
    if posting_instructions:
        vault.instruct_posting_batch(posting_instructions)

def _charge_withdrawal_fee_a(vault, postings, effective_date) -> List[PostingInstruction]:
    fee_instructions = []
    # some logic to populate instructions
    return fee_instructions

def _charge_withdrawal_fee_b(vault, postings, effective_date) -> List[PostingInstruction]:
    fee_instructions = []
    # some logic to populate instructions
    return fee_instructions
```

### Avoid mutating contract API Types in place (Contracts API 4.x)

It may be necessary to modify or change the attributes of a Contracts API object after it has been instantiated. However it is strongly recommended to not modify the object in place.

#### Why

Modifying an object in place will bypass any class level validation

#### How

If it is necessary to modify an object after it has been instantiated then it is recommended that a new object is instantiated instead. An example is shown below:

```python
    original_custom_instruction = CustomInstruction(
        postings=[Posting(...), Posting(...)],
        override_all_restrictions=True,
        instruction_details={
            "description": "Example CustomInstruction object",
            "event": f"Best Practice Documentation",
        },
    )
    # now lets say we want to add 2 more Posting objects to the postings attribute of the CustomInstruction object
    new_postings = [Posting(...), Posting(...)]

    # DO NOT
    original_custom_instruction.postings += new_postings

    # Instead, instantiate a new CustomInstruction object. This will ensure class validation is not bypassed
    new_custom_instruction = CustomInstruction(
        postings=original_custom_instruction.postings + new_postings,
        override_all_restrictions=original_custom_instruction.override_all_restrictions,
        instruction_details=original_custom_instruction.instruction_details
    )
```

### Use of effective_date / value_timestamp

As of Vault 2.8.7, 3.0.1 and 3.1.? and subsequent Vault minors, the contract executor will not default `PostingInstructionBatch` value_timestamp to the hook effective_date. Instead `PostingInstructionBatch` `value_timestamp` will be left to default to `now()` at the postings processor level. We recommend still using the hook effective_date as the value_timestamp unless you have a specific reason to not do so as there are some tricky nuances to be aware of:

- Consider a `PostingInstructionBatch` that is accepted by a contract and committed at 2020-01-01T23:59:59.999999Z. Any side-effects (e.g. a `PostingInstructionBatch` containing a fee) will be committed a finite amount of time later and their `value_timestamp` will be larger (e.g. 2020-01-02T00:00:00.000100Z) if not explicitly set in the contract. A schedule that observes balances as of midnight (i.e. 2020-01-02T00:00:00.000000Z) will not see the side-effects, which is typically wrong.

- Consider two schedules in a schedule group with same `effective_date`, and the second schedule relies on a balance update from the first schedule's directives. Because fetching is based on effective_date, the second schedule won't pick up the update if it's using latest balances and the posting's `value_timestamp` is > `effective_date`. This would always be the case if `value_timestamp` is set to `now()` at the postings processor level. Should you switch to `latest live` requirements to accommodate for this, you could pick up unexpected data too, so be wary of this.

- If these two schedules have different `effective_date`, there's still potentially a risk due to processing delays. Although for a given account the second schedule won't start until the first schedule is completed, the `PostingInstructionBatch` could be processed such that `now()` is greater than the second schedule’s `effective_date`. E.g. schedule 1 runs at 00:00:00, schedule 2 runs 01:00:00. Processing delays means that some of schedule 1 jobs run at 01:01:00 and then the corresponding `PostingInstructionBatch` have a `value_timestamp` > 01:00:00.

More generally, we are investigating guidance around segregation of schedules to mitigate these potential issues.

### Client Batch Id

Set this field sensibly so it can be useful in relevant use cases.

#### Why

The client_batch_id has a functional use to group thematically related posting instructions that do not belong in the same batch (e.g. a client may decide to group postings related to a transaction and its disputes). It can be searched by in Ops Dash ledger and is a parameter to `/v1/posting-instruction-batches GET`. It may therefore be partially driven by client requirements.

#### How

A sensible convention to follow is `<hook_name/event type>-<hook_execution_id>`. The event type is used for scheduled code given there could be different event types with very different directives for the same hook. For example:

`POST_POSTING-<hook_execution_id>`

`ACCRUE_INTEREST-<hook_execution_id>`

### Batch Details

Batch details are intended for all sorts of metadata, whether for human or machine consumption. Here are some suggestions.

#### Linking PIBs to their triggers

It is useful to link the posting instruction batch created by `post_posting_code` (Contracts API 3.x) or `post_posting_hook` (Contracts API 4.x) to the triggering posting instruction batch via the batch_details. For example:

```python
batch_details = {
    'trigger_posting_instruction_batch_id' = postings.batch_id
}
```

Alternatively, we can tag them against an event_type for schedules.

#### Metadata for downstream systems

Integration requirements often drive what metadata is required. One example is providing a booking date for end-of-day processing like interest accrual, which may be delayed for operational reasons. Having the date will avoid confusion.

## Posting Instructions

### Netting Instructions

Consider whether multiple `PostingInstruction`s can be netted

#### Why

In the [Posting Instruction Batch](#posting-instruction-batches) section, we highlight that the number of batches has a significant throughput impact, but the number of instructions in a batch also matters. It is worth considering ‘netting’ postings where possible. However, this does result in a lack of granularity, so it must be confirmed against requirements (e.g. each `PostingInstruction` could have separate metadata and should be processed differently by downstream systems).

#### How

Consider a contract creating a single `PostingInstructionBatch` with the following `PostingInstruction`s:

1. Posting Instruction 1 - Accrue interest on balance tier 1 at 1%, totalling 0.12
2. Posting Instruction 2 - Accrue interest on balance tier 2 at 2%, totalling 0.05

Assuming instructions 1 and 2 are using the same accounts and balance definitions, they can be netted with no functional impact. The best option is to calculate the amounts for each accrual and then sum them to create a single `PostingInstruction`. This is preferable to generating separate `PostingInstruction` and then merging them later, as this is typically more expensive. As mentioned above, metadata can then be used to ensure no information is lost:

```python
{
    "tier_1": "0.12",
    "tier_2": "0.05"
}
```

In Contracts API 4.x we can also consider netting individual `Posting` objects within a `CustomInstruction`.

### Overriding Restrictions

Confirm desired behaviour with clients regarding restrictions and contract-initiated `PostingInstruction`

#### Why

Restrictions are a useful mechanism to limit or prevent certain actions, including credit and/or debit `PostingInstruction`. However, clients may have differing views on whether these should affect contract features, such as accruing interest or charging fees. Inception contracts default to `True` as this is a common request, but it can be changed easily. If there is a request to control these features more granularly, consider solutions such as flag-based controls.

#### How

Simply change the `override_all_restrictions` parameter when calling `vault.make_internal_transfer_instructions()` (Contracts API 3.x) or when instantiating a `CustomInstruction` (Contracts API 4.x)

### Client Transaction Id

Set this field sensibly to meet general posting constraints and functional use cases. This only applies to `PostingInstruction` on Contracts API 3.x, as this field is settable on `CustomInstruction` in Contracts API 4.x.

#### Why

The `client_transaction_id` has a functional use to group posting instructions that belong to the same transaction. It can be searched by in Ops Dash ledger and is a parameter to /v1/posting-instruction-batches GET. It may therefore be partially driven by client requirements.
As contracts only create custom instructions, postings-processor constraints mean we must guarantee `client_transaction_id` uniqueness within the instructed batch. However, we typically ensure it is unique across all posting instructions and batches to avoid accidentally grouping unrelated instructions and cause confusion.

#### How

To achieve the above, the proposed client_transaction_id structure is:

`<action>-<when/where>-<trigger>`, which may look like `REPAY_CASH_ADVANCE_FEES-<HOOK_EXECUTION_ID>-<POSTING_ID>`

- action is optional and provides a short indication of the intent. It can contribute to uniqueness. For example REPAY_CASH_ADVANCE_FEES, where CASH_ADVANCE_FEES is a balance address.

- when/where is critical to make the instruction unique enough across all posting instructions. The output of vault.get_hook_execution_id() is suitable as it contains the account id (where), hook id, and the effective date (when)

- trigger is critical to make the instruction unique enough within the batch. It explains what is causing the action.
  - Schedules can use the event_type, combined with a counter if they create similar postings that can’t be netted due to data requirements.
  - Posting-related triggers should use the posting_id. For example, a posting batch could contain multiple posting instructions that charge the same fee (identical what and where/when), in which case the trigger clarifies which posting triggers the fee. In some cases you may need a generic counter for enough uniqueness. For example, if you process instructions where one or more postings affect your account, posting_id will not provide enough uniqueness as it is technically a posting_instruction identifier (i.e. shared across all postings for the same posting instruction (also see [Netting Instructions](#netting-instructions) as a way to avoid clashing `client_transaction_id`).

> If the client is considering backdating, be aware that the hook execution id will be identical for postings with the same value timestamp (account id, hook id  and effective date are all the same). One option is to use incoming posting metadata in the CTI (e.g. pass in the incoming CTI to the outgoing CTI). Be mindful of using fields that must be unique (i.e. CTI is OK, client batch id is not). Be careful about contract-to-contract postings where the CTIs could in theory pile up and get longer and longer.

### Instruction Details

Set this field sensibly to meet contract or external system requirements

#### Why

Instruction details are often driven by client requirements who need specific metadata on a posting for downstream processing (e.g. feeding into the General Ledger). They are also displayed in Ops Dashboard, and provide a good opportunity to provide information to users.
In some cases, the requirements are driven by contracts themselves, as the metadata can provide additional information to the contract. Although this is typically used for external `PostingInstruction`s, contracts may also consume `PostingInstruction`s created by the same or another contract.

#### How

Some useful key-value pairs include:
    description - provides a human-friendly textual description of what this posting is doing/why
    event - if applicable, the event type that resulted in the posting instruction

## Schedules

### Updating Schedules

#### Known Race Condition

There is a known race condition when updating schedules in CLv4 where if a schedule is updated before the next schedule job is published, the updated schedule overrides the outstanding job and hence the original job may never get published. There is no way to handle this scenario from within the contract, so the guidance is to be cautious not to update schedules near to the expected execution time.
