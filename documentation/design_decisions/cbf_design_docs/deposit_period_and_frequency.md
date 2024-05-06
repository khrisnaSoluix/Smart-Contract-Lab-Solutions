# Deposit Period and Number of Deposits CBF - Design Doc

## Scope

Deposit period is defined as the number of days from the account creation date during which the deposits are permitted on the account. No deposits are allowed once this period ends. Furthermore, the number of deposits allowed during this period can also be configured to either single or unlimited.

## Requirements

[CBF: Deposit Period and Number of Permitted Deposits](https://pennyworth.atlassian.net/browse/CPP-2082)

A deposit period gives customer some time from account opening to deposit funds in the account. These funds can be transferred through either a single deposit or multiple deposits as configured in the contract.

Any account failing to deposit money during this period will be deemed ready for account closure.

## Assumptions

- Each PIB shall contain only a single PI
- `DEFAULT` balance is not rebalanced in `post_posting` hook

## Agreed Implementation

### Data Definition

#### Contract Parameters

- `deposit_period`: Template parameter - `NumberShape`
- `number_of_permitted_deposits`: Template parameter - `UnionShape`
- `deposit_period_end_date`: Derived parameter - `DateShape`

### Technical Logic

- Calculate the `deposit_period_end_date` using the `vault.get_account_creation_date()` method and `deposit_period` contract parameter. The cut off point will be considered to be the end-of-day of the last day of the deposit period
- Within the `pre_posting_hook`, for every PostingInstructionBatch(PIB) that deposit's funds into the account (ie `posting_amount` > 0);
  - Reject if it is after the `deposit_period_end_date`
  - Reject if it does not follow the configuration defined in the `number_of_permitted_deposits` parameter. This can be either `single` or `unlimited` deposits
    - When contract is configured to allow `single` deposit, reject postings where the `.credit` attribute of the `DEFAULT` address is non zero. This is because credit attribute of the `DEFAULT` is monotonically increasing
    - No rejections are raised when contract is configured to allow `unlimited` deposits
- Create a one off schedule that runs after the `deposit_period_end_date` to send an account closure notification if the `DEFAULT` balance is zero
