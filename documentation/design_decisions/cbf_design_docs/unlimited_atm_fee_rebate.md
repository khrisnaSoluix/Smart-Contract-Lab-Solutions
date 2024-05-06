# Unlimited ATM Fee Rebate CBF - Design Doc

## Scope

The Inception library does not currently contain a feature that can be used to fulfil the requirements of this CBF. Foreseeing future requirements, a generic fee rebate feature should be designed and implemented, this approach allows for the feature to meet the requirements specified today and also have the flexibility to meet future requirements with minimal modifications. This document aims to outline the design to meet the requirements defined [here](#requirements).

## Requirements

[CBF: Unlimited ATM Fee Rebates](https://pennyworth.atlassian.net/browse/CPP-1996)

## Proposed Design

The proposed feature is designed for Liability type products, and will need to achieve the following:

- Determine if a fee is being charged, if so identify the fee type
- Determine whether the charged fee is eligible for a fee rebate
- Rebate the eligible fees
- Integrate seamlessly with existing balance / transaction limit features. The relevant features that currently exist in the product library are:
    1. `available_balance.py` - rebatable fees should not affect balance checks
    2. `overdraft_limit.py` - rebatable fees should not affect balance checks
    3. `maximum_daily_withdrawal.py` - fees should not affect daily withdrawal limit checks
    4. `maximum_withdrawal_by_payment_type.py` - fees should not affect withdrawal limit checks
    5. `maximum_single_withdrawal.py` - fees should not affect withdrawal limit checks

Customer transactions that contain fees must be sent to Vault in a specific format for this feature to be able to handle them appropriately. Therefore, this feature will mandate the following:

1. Any fee charges on a customer transaction must be sent to Vault within the same atomic wrapper (Posting Instruction Batch) but be split into a separate Posting Instruction objects. Note, if a customer transaction is subject to multiple fees then each fee must be sent to Vault as a separate Posting Instruction object, again within the same atomic wrapper.
2. The fee posting instructions must be clearly identifiable and must provide all of the necessary data. Therefore to distinguish a Posting Instruction as a charged fee on a customer transaction the instruction_details metadata field must be utilised. The metadata should must include the `fee_type` field, e.g. `instruction_details = {"fee_type": <fee_type>}`.
3. Chainable Posting Instructions (Outbound Authorisations, Settlements) will not be considered.

The above outlines the best approach for seamless integration with various other balance / transaction limit features as it makes it easy to:

1. Avoid rebatable fees being affecting balance checks
2. Avoid fees being counted as individual transaction in transaction limit checks

The aforementioned metadata field must be present, otherwise the fee Posting Instruction will be deemed as if there is the fee being charged is not valid for a rebate.
Examples are shown below:

- fee metadata valid, rebate considered: `instruction_details = {"fee_type": "fee_type_a"}`
- fee metadata invalid, rebate not considered: `instruction_details = {"type": "fee_type_a"}`
- fee metadata omitted, posting treated as if no fee has been charged: `instruction_details = {}`

## Agreed Implementation

### Data Definition

#### Contract Parameters

The feature must define 2 parameters:

- `fee_types_eligible_for_rebate`: Template parameter - `StringShape (list[str])` - A `fee_type` list, used to determine whether the proposed fee is eligible for a rebate.
- `fee_rebate_internal_accounts`: Template parameter - `StringShape (dict[str, str])` - maps the `fee_type` to the specific bank internal account used for the rebate

If a `fee_type` is defined in the metadata of a posting object which is not present in either of the `eligible_fee_types` or `fee_rebate_internal_accounts` parameters then the fee will not be eligible for a rebate.

#### Identify if a Fee Posting is Eligible for a Rebate

Noting what has been discussed previously, the feature must be able to determine whether a given posting instruction object satisfies the conditions required to rebate the charged fee, those conditions are:

1. the Posting Instruction object is a non-chainable debit
2. the Posting Instruction object is a fee that is being charged (identified by the fee_type metadata key)
3. the given `fee_type` exists in both the `eligible_fee_types` and `fee_rebate_internal_accounts` (where the boolean is true for the former)

This is trivial and an example function is defined below

```python
def is_posting_eligible_for_fee_rebate(
  posting_instruction: utils.PostingsTypeAlias,
  eligible_fee_types: dict[str, bool],
  fee_rebate_internal_accounts: dict[str, str]
) -> bool:
  """
  Verify the posting is of the right type (non-chainable debit) and the fee_type key is present, if so then:
    a) verify fee_type in eligible_fee_types and equal to True
    b) verify fee_type in fee_rebate_internal_accounts
  """
```

#### Determine Eligible Fee Postings

The proposed Postings must be categorised accordingly to allow for seamless integration with the various other balance / limit check features. To do so, the below steps should occur:

1. Group Posting Instruction objects by the `fee_type` metadata key
2. Given the grouping defined above, filter out those Posting Instructions that are eligible for a fee rebate
3. The proposed postings less the eligible fee rebate Posting Instructions should be passed through for balance checks
4. The proposed postings less all fee Posting Instructions should be passed through for transaction limit checks

##### Group Posting Instructions by Fee Type

The proposed Posting Instructions should be grouped by fee_type, this functionality should not necessarily sit within the feature itself and existing utility functions should be used where applicable. This will then be used by the feature, an example function highlighting the necessary functionality is shown below

```python
from collections import defaultdict
def group_posting_instructions_by_key(posting_instructions: utils.PostingInstructionListAlias, key: str) -> dict[str: utils.PostingInstructionListAlias]:
  grouped_postings = defaultdict(list)
  for posting in posting_instructions:
    if fee_type := posting.instruction_details.get(key):
      grouped_postings[fee_type].append(posting)

  return grouped_postings
```

##### Group Postings by Fee Eligibility

Given a group of fee postings the feature must be able to filter out postings that are eligible for a fee rebate from those that are not

```python
from collections import defaultdict

FEE_TYPE = "fee_type"

def group_posting_instructions_by_fee_eligibility(vault: Vault, proposed_posting_instructions: utils.PostingInstructionListAlias) -> dict[str, list[utils.PostingInstructionListAlias]]:
 """
 Filter postings for fee postings and then loop through the filtered postings and determine whether it is eligible for a fee rebate
 """
  filtered_fee_postings = group_posting_instructions_by_key(posting_instructions=proposed_posting_instructions, key=FEE_TYPE)
  #  use the vault object to get feature defined parameters
  categorised_fee_postings = defaultdict(list)
  for posting in filtered_fee_postings:
    if fee_type is_posting_eligible_for_fee_rebate(
      posting, eligible_fee_types, fee_rebate_internal_accounts
    ):
      categorised_fee_postings["eligible"].append(posting)
    else:
      categorised_fee_postings["non-eligible"].append(posting)

  return categorised_fee_postings
```

#### Refund Fees

The feature must define functionality to rebate eligible fees charged using in the post_posting_hook. Per execution, each fee rebate should be defined as a separate CustomInstruction object with relevant metadata.

A publicly exposed function should be defined taking in the vault object, alongside the invoking posting instructions. The former used to retrieve the feature specific parameters, a proposed function signature is shown below:

```python
def rebate_eligible_fees(vault: Vault, posting_instructions: utils.PostingInstructionTypeAlias) -> list[CustomInstructions]:
  """
  This function should do the following:
  1. fetch parameters from the vault object
  2. filter postings to get only the eligible postings
  3. construct the rebate custom instruction, 1 for each fee type
  """
```

### Further considerations

1. Support functionality to do partial fee rebates - an additional parameter can be defined storing a mapping of fee type to percentage rebated which can be used when rebating the fee. If a fee type is to be rebated but omitted in this parameter the feature should default to rebating the entire fee.
2. Fee rebates based on account tiers - This functionality should be addressed by a separate feature
3. Support fee rebate limits, e.g. maximum amount, per fee, over a given time period that can be rebated
