# Withdrawals and Withdrawal Fees CBF - Design Doc

## Scope

This feature performs the following actions upon withdrawals for a fixed term deposit product:

- Send a notification detailing the incurred withdrawal fees on withdrawals that exceed the fee free withdrawal limit. These fees include:
  - A flat fee
  - A percentage fee
  - Note that these will both be charged when both non-zero, or can individually be set to zero.
- Reject withdrawals which exceed the current balance
- Reject partial withdrawals which exceed the maximum withdrawal limit
- Reject withdrawals which are less than the incurred withdrawal fee amount
- Reject withdrawals on a calendar event which do not include `"calendar_override": "true"` in their metadata
- Accept withdrawals which fall within the fee free limit and do not charge any fees for these withdrawals

The bank then must externally orchestrate the fee charging logic to deduct the required fees from the withdrawal amount before it is returned to the customer.

## Requirements

[CBF: Withdrawals and Withdrawal Fees](https://pennyworth.atlassian.net/browse/CPP-2092)

## Agreed Implementation

### Data Definition

#### Contract Parameters

- `early_withdrawal_flat_fee`: Template parameter - `NumberShape` - a flat fee amount deducted from the withdrawal amount at the point of withdrawal.
- `early_withdrawal_percentage_fee`: Template parameter - `NumberShape` - a fee amount deducted at the point of withdrawal calculated as a percentage of the withdrawal amount.
- `maximum_withdrawal_percentage_limit`: Template parameter - `NumberShape` - the percentage of the deposited amount that can be withdrawn.
- `fee_free_withdrawal_percentage_limit`: Instance parameter - `NumberShape` - the percentage of the deposited amount which can be withdrawn without incurring fees
- `maximum_withdrawal_limit`: Derived parameter - `NumberShape` - the total amount of withdrawals cannot exceed this limit
- `fee_free_withdrawal_limit`: Derived parameter - `NumberShape` - the fee free withdrawal limit allowed on the account.

#### Balance addresses

- `WITHDRAWALS_TRACKER`: a tracking address used to track the total amount of withdrawals made. It can be used to calculate the deposited amount (`DEFAULT + WITHDRAWALS_TRACKER` will give the deposited amount when no other features affect the default balance)

#### Notifications

- `WITHDRAWAL_FEE`: notification containing `account_id`, `withdrawal_amount`, `flat_fee_amount`, `percentage_fee_amount`, `total_fee_amount` and `client_batch_id` to be used in bank orchestration for deducting the fee from the withdrawal amount. This notification is sent for any withdrawal, even if the fee amount is 0. Note that a notification is being used to orchestrate the fee charging since we are unable to change posting amounts in pre-posting hence the fees cannot be deducted from the withdrawal amount before it is committed. The notification can be used by the bank to deduct the required fee from the withdrawal amount before the withdrawal is returned to the customer.

### Technical Logic

#### Functions

The following functions need to be defined:

- A function that calculates `customer_deposit_amount` which sums the balances in the `DEFAULT` and `WITHDRAWALS_TRACKER` addresses, and takes a list of `DefaultBalanceAdjustment` interface objects to handle default balance adjustments made by other features implemented in the product template. The interface will look like:

  ```python
  DefaultBalanceAdjustment = NamedTuple(
      "DefaultBalanceAdjustment",
      [
          (
              "calculate_balance_adjustment",
              Callable[
                  # vault: SmartContractVault,
                  # balances: Optional[BalanceDefaultDict],
                  # denomination: Optional[str]
                  ...,
                  Decimal,
              ],
          ),
      ],
  )
  ```

  and can be used to provide any values which would adjust the value of the available balance. If the balance adjustment increases the `DEFAULT` balance, `calculate_balance_adjustment` should return a negative adjustment value, and similarly if balance adjustment decreases the `DEFAULT` balance, `calculate_balance_adjustment` should return a positive adjustment value.

  The method would then look like:

  ```python
  def get_customer_deposit_amount(
    *,
    vault: SmartContractVault,
    balance_adjustments: Optional[list[deposit_interfaces.DefaultBalanceAdjustment]] = None,
  ) -> Decimal:
    return DEFAULT + WITHDRAWALS_TRACKER + sum(balance_adjustments if balance_adjustments else [])
  ```

- A function that calculates `maximum_withdrawal_limit` as `maximum_withdrawal_percentage_limit * customer_deposit_amount`, where `customer_deposit_amount` can be retrieved using the features helper.
- A function that calculates `fee_free_withdrawal_limit` as `fee_free_withdrawal_percentage_limit * customer_deposit_amount`, where `customer_deposit_amount` can be retrieved using the features helper.
- A function to calculate the amount subject to fee. When there's multiple postings, the net effect on the committed phase of the list will be subject to fee charging.
  - This is calculated by `withdrawal_amount_subject_to_fee = withdrawal_amount - fee_free_withdrawal_limit_remaining` where `fee_free_withdrawal_limit_remaining = (fee_free_withdrawal_limit - WITHDRAWALS_TRACKER) if (fee_free_withdrawal_limit - WITHDRAWALS_TRACKER > 0) else 0`
- A function to calculate the total fee to be charged against the withdrawal:
  - Get the amount amount subject to the fee using the helper defined
  - Calculate a flat fee of the amount defined by `early_withdrawal_flat_fee`
  - Calculate a percentage fee by `early_withdrawal_percentage_fee * withdrawal_amount_about_fee_free_withdrawal_limit`

#### Posting Hooks Logic

Within the `pre_posting_hook`:

- Reject withdrawals which exceed the current balance.
- Reject any partial withdrawals that cause the total amount of withdrawals to exceed the `maximum_withdrawal_limit`.
- Reject withdrawals on a calendar event which do not include `"calendar_override": "true"` in their metadata.
- Reject any withdrawals that are less than the incurred withdrawal fee amount.

```python
def validate():
  if withdrawal_amount > current_balance:
    return Rejection

  if partial_withdrawal and withdrawal_amount > maximum_withdrawal_limit:
    return Rejection

  if on_calendar_day and "calendar_override" not in posting_metadata:
    return Rejection

  fee_amount = calculate_fee()
  if withdrawal_amount < fee_amount:
    return Rejection
```

Within the `post_posting_hook`:

- For any withdrawal posting:
  - Create a `WITHDRAWALS_TRACKER` instruction with the amount of the withdrawal
  - Using the helper defined, calculate the fees to be charged against the withdrawal
  - Construct `WITHDRAWAL_FEE` notification with the required fee amounts (this notification is then used by the bank to orchestrate the fee charging externally)

```python
def handle_withdrawal():
  create_withdrawal_tracker_instructions()
  generate_withdrawal_fee_notification()
```
