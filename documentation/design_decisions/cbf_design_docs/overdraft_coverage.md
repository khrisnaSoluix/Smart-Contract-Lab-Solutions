# Overdraft Coverage CBF - US Product - Design Doc

## Scope

This document outlines the behaviour for the transaction types supported during an arranged overdraftThis feature aims to help overdrafts comply with legal requirements that only specific transaction types may take an Account into overdraft.
If the transaction type is in the specified list then it may not take an account into overdraft or increase the overdraft balance unless explicitly opted in by the customer.

## Requirements

[CBF: Overdraft Coverage](https://docs.google.com/document/d/1NyrSim0RlbtWIoEWqhhQIA6YbvcuxF0bSuXu6lDT3iY/edit#heading=h.wde79d71lxlb)

## Assumptions

The CBF is designed for use with US Products. Alternatively, this should be considered as a transaction blacklist feature.
Transactions should be under the pretence that incoming posting transactions will conform to the following:
 `documentation/implementation/requirements_fetching_and_processing.md#Client Transactions`

## Agreed Implementation

### Description

Transaction details are obtained from a posting via the `type` key on `PostingInstruction.instruction_details` . A configured template parameter will contain a list of transaction types to blacklist. The list of types from the posting instruction details will then be compared via a set comparison. This helper function is due to be called in the pre-posting hook of the contract to check whether or not to accept the posting prior to calling the overdraft posting calculation function. This will allow for the check to only be performed when an incoming posting will trigger an overdraft.

### Pros

* closely integrates with the existing overdraft CBF

### Cons

* Requires the instruction details type to be accurately set.

### Data Definition

#### Contract Parameters

* `overdraft_coverage_opted_in`: Instance parameter - `BoolShape` - A Boolean containing whether or not the customer has opted into the blacklisted overdraft-covered transactions.
* `overdraft_coverage_transaction_types_list`: Template parameter - `StringShape` - a list of strings where transactions within this category need explicit approval before triggering an overdraft payment.

##### BoolShape

As Boolshape is not defined in the contracts API, the referenced BoolShape will be implemented as referenced in `documentation/implementation/parameters.md`

### Technical Logic

The goal here is to integrate the overdraft coverage logic into the overdraft payments logic so that the logic is only called when an overdraft payment is due to be triggered otherwise the posting will be rejected.
This feature will rely on the basis that the overdraft logic is already implemented in the contract. By ensuring that this parent feature dependency exists, allows this feature extension to not care about the given overdraft limits.

Current pre-posting hook logic relies on a cascading posting rejection pattern that something like the following.

```python
def pre_posting_hook(vault: SmartContractVault,pib: list[PostingInstructionTypeAlias]):
	if Condition1.validate(pib):
		return PostingRejection
	if Condition2.validate(pib):
		return PostingRejection
	if Condition3.validate(pib):
		return PostingRejection
```

#### Special considerations

Posting instructions are passed into the pre_posting_hooks in the form of PostingInstructionTypeAlias(es) [PITAs for short].
There exists a scenario where the order of PITA(s) matter when calculating the validity of a given batch, a breakdown of the scenario is described below.

##### Worked Example

Given a starting balance of $10 and an overdraft limit of $10. Given the PIs:
posting A - $9 (BAU Posting)
posting B - $7 (Limited Posting that requires Opt In)
posting C - $3 (BAU Posting)

If submitted in the order [A, B, C], the posting should be rejected as follows
After Posting A, the available balance is $1, Posting B requires the Overdraft Opt in as the posting will take the balance into overdraft, thus the batch is rejected

If submitted in the order [B, C, A], the posting should be accepted as follows
After Posting B, the available balance is $3, Overdraft coverage is not considered as the single posting does not break into the overdraft balance
Posting A makes the balance $0
Finally, Posting A will use the $9 from the Overdraft allowance.

As seen, even though the condensed effect of the list of postings will always use the overdraft, the acceptance criteria of the list varies. The contract should not optimise the order of postings for list Acceptance.
The order should be done by the upstream processor, which is done easily by ordering all the postings that require an Overdraft Opt in first in the list.

#### Implementation Example

```python
# Contract Template
def pre_posting_hook(vault: SmartContractVault, hook_arguments):
	pis: list[PostingInstructionTypeAlias] = hook_arguments.posting_instructions
    if rejection := StandardOverdraft.validate(vault, pis):
        return PostingRejection(rejection)
    if rejection := OverdraftCoverage.validate(vault, pis):
        return PostingRejection(rejection)

# OverdraftCoverage.py
def validate(vault: SmartContractVault, pib: list[PostingInstructionTypeAlias]):
    if utils.get_parameter(overdraft_opt_in):
        # overdraft coverage is enabled, dont need to validate
        return None
    check_list = json.loads(utils.get_parameter(overdraft_coverage_type_list))
    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    available_balance = utils.get_available_balance(balances=balances, denomination=denomination)

    for i, posting in enumerate(postings):
        posting_amount = utils.get_available_balance(
            balances=posting.balances(), denomination=denomination
        )
        available_balance -= posting_amount
        if available_balance <= 0:
            break
    # i should hold the index pointer
    for posting in postings[i:]:
        if transaction_type_check(posting, check_list):
            return Rejection(
                message=f"Posting {posting.instruction_details} requires overdraft coverage to be enabled"
                f" to use the overdraft balance.",
                reason_code=RejectionReason.INSUFFICIENT_FUNDS,
            )
    return None

def transaction_type_check(posting_instruction: PostingInstruction, check_list: list[str], key:str = "type"):
    return posting_instruction.instruction_details[key] in check_list
```
