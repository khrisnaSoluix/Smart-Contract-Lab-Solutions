
# Minimum Initial Deposit Amount CBF - Design Doc

## Scope

Minimum Initial Deposit Amount is defined as the minimum permitted amount of the first deposit posting to the account after opening.

## Requirements

[CBF: Minimum Initial Deposit Amount](https://pennyworth.atlassian.net/browse/CPP-2086)

The minimum amount that is required to be deposited on the account when transferring the initial deposit.

## Assumptions

- The net affect of the posting instruction batch is used to determine whether the posting instructions should be accepted or rejected

## Agreed Implementation

### Data Definition

#### Contract Parameters

- `minimum_initial_deposit_amount`: Template parameter - `NumberShape`

### Technical Logic

- Determine whether a deposit posting has already been made to the account by checking `.credit` of the `DEFAULT` address.
- Within the `pre_posting_hook`, if the posting instructions list results in a net deposit into the account (ie > 0 credit to the `DEFAULT` balance):
  - Reject if no other deposits have been made, and the amount is less than the configured `minimum_initial_deposit_amount`
