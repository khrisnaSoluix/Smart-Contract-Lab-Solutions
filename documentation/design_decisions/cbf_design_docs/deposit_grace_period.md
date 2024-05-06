# Grace Period CBF - Design Doc

## Scope

The grace period is a length of time during which amendments can be made to a deposit account without incurring any fees or penalties. The following changes can be made during the grace period:

- Deposit more funds
- Make full or partial withdrawal
- Change term

## Requirements

[CBF: Grace Period](https://pennyworth.atlassian.net/browse/CPP-2083)

## Assumptions

- The grace period cut off point will be considered to be the end-of-day of the last day of the grace period. There is no functionality for configuring a different time except end-of-day.

## Agreed Implementation

### Data Definition

#### Contract Parameters

- `grace_period`: Template parameter - `NumberShape` - the period (in days) in which amendments to the account without incurring fees or penalties
- `grace_period_end_date`: Derived parameter, `DateShape` - The date in which the grace period ends

### Technical Logic

- A function that calculates the `grace_period_end_date` by retrieving the account creation date, adding the value of the `grace_period` parameter and setting the time to end-of-day on this date.
- A function that checks whether we are inside the grace period by comparing `effective_datetime` with `grace_period_end_date`.
- Checks are implemented in `pre_posting_code` to accept postings inside of the grace period:
  - additional deposits
- Change to the `term` parameter outside of the grace period are rejected in `pre_parameter_change_code`
- Withdrawals within the `grace_period` should be accepted without fees being incurred, outside of the period fees should be incurred.
- Create a one off schedule that runs after the `grace_period_end_date` to send an account closure notification if the `DEFAULT` balance is zero

#### Validating Withdrawals

The grace period must dictate whether fees should be charged on a withdrawal, it should not be responsible for charging the fee. Withdrawals are always accepted in `pre_posting`, and therefore this functionality is handled in `post_posting`. The following function is proposed:

```python
  def is_withdrawal_subject_to_fees(vault: SmartContractVault, effective_datetime: datetime, posting_instructions: utils.PostingInstructionListAlias, denomination: Optional[str]) -> bool:
    if denomination is None:
      denomination = common_parameters.get_denomination_parameter()

    posting_balances = utils.get_posting_instructions_balances()

    is_withdrawal = utils.get_available_balance(balances=posting_balances, denomination=denomination) < Decimal("0")

    if is_withdrawal and not is_within_grace_period():
      return True

    return False
```
