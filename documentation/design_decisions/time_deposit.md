# Time Deposit - Design Doc

## Scope

The Time Deposit is a type of savings account where the customer locks in their funds until the product reaches maturity. After maturity, the customer can choose to either close their account and withdraw their funds or reinvest their funds in a renewed Time Deposit.

## Requirements

[CPP: Time Deposit](https://pennyworth.atlassian.net/browse/CPP-1829)

## Feature List

- [Permitted Primary Denomination](https://pennyworth.atlassian.net/browse/CPP-1908)
- [Minimum Initial Deposit Amount](https://pennyworth.atlassian.net/browse/CPP-2086)
- [Maximum Balance Limit](https://pennyworth.atlassian.net/browse/CPP-1986)
- [Deposit Period and Number of Deposits](https://pennyworth.atlassian.net/browse/CPP-2082)
- [Cooling-Off Period](https://pennyworth.atlassian.net/browse/CPP-2084)
- [Grace Period](https://pennyworth.atlassian.net/browse/CPP-2083)
- [Scheduled Deposit Interest Accrual](https://pennyworth.atlassian.net/browse/CPP-1912)
- [Scheduled Deposit Interest Application](https://pennyworth.atlassian.net/browse/CPP-1913)
- [Withdrawals and Withdrawal Fees](https://pennyworth.atlassian.net/browse/CPP-2092)
- [Deposit Maturity](https://pennyworth.atlassian.net/browse/CPP-2077)
- [Deposit Interest Application upon Account Closure](https://pennyworth.atlassian.net/browse/CPP-1967)

## Product Design

The product contract is suitable for both new and renewed Time Deposit accounts, but some features are only applicable to one or the other. Two resources will be provided (`time_deposit` and `renewed_time_deposit`) which will have their own default template parameter configurations, so there will be two distinct resources defined by the same underlying contract to be uploaded.

- The product only allows single `HARD_SETTLEMENT` or `TRANSFER` posting types transacted in the permitted primary denomination.
- For any withdrawal outside of cooling-off period and grace period, a withdrawal fee is applied as per the CBF.
- If the bank requires a nominated account for the customer, this can be stored external to the contract (e.g. in the TD account details) as any money movements to this nominated account will need to be orchestrated by the bank.

### New Time Deposit Accounts

- Deposit period and cooling-off period can both be configured, and do not have any overlapping logic.
- Grace period is not applicable for new TD accounts and should be configured to `0` days on account opening.

### Renewed Time Deposit Accounts

- Grace period can be configured for renewed TD accounts.
- Deposit period and cooling-off period are not applicable for renewed TD accounts and should both be configured to `0` days on account opening. If the grace period is non-zero, the contract will not execute any logic related to deposit/cooling-off periods (see [Assumption](#assumptions) #3)

### Interest

#### Interest Accrual

The Time Deposit uses the `fixed_interest_accrual` feature for interest accrual.

#### Interest Application

- When the account is in either the deposit, cooling-off or grace period, interest application should not occur. To enforce this, the `activation_hook` delays the `APPLICATION_EVENT` `start_datetime` until the end of the periods.
  - This method preferable to leaving the `ScheduledEvent` to run as normal but adding in a check within the `scheduled_event_hook` to return `None` if still within the periods as this would not make it clear why there was no side-effects of the schedule.
  - This method is preferable to skipping the schedule until the end of all the periods as delaying the start time will prevent any skipped jobs being scheduled and emitted.
- In the case of any of the period lengths changing, the end dates derived on account creation will be honoured and the schedules will not be adjusted to account for the changes.

#### Interest Capitalisation and Forfeiture

- At account maturity, the product has the option to either capitalise or forfeit the accrued interest that has not yet been applied.
- When the account is closed during the deposit, cooling-off or grace periods, the accrued interest should be forfeited and there will be no applied interest.
- When the customer requests early closure outside of the cooling-off or grace period (new vs renewed time deposit), accrued interest should be forfeited and applied interest should not be affected.
- When a partial withdrawal occurs outside of the cooling-off or grace period (new vs renewed time deposit), the accrued interest on the amount withdrawn is forfeited and applied interest should not be affected.

### Account Closure Processes

The following scenarios should result in the closure of a TD account:

1. The account has reached maturity, and the bank has received the Maturity notification
    - See [Rollover](#rollover) for more information about the required external orchestration
2. The customer requests early closure of the account outside of the cooling-off period
    - Withdrawal fees should be applied
    - Any accrued interest should be forfeited, applied interest is unaffected
3. The account is unfunded at the end of the deposit period (*new TD accounts only*)
    - No fees should be applied
    - Any accrued interest should be forfeited, and no interest will have been applied at this point
4. The customer requests the account to be closed during the cooling-off period (*new TD accounts only*)
    - No fees should be applied
    - Any accrued interest should be forfeited, and no interest will have been applied at this point
5. The customer requests full withdrawal during the grace period (*renewed TD accounts only*)
    - No fees should be applied
    - Any accrued interest should be forfeited, and no interest will have been applied at this point

The `deactivation_hook` will zero out all non-capital addresses and clear any accrued interest (the maturity schedule will capitalise accrued interest and in all other cases, accrued interest is forfeited).

When a withdrawal results in a full withdrawal from the account (i.e. the `DEFAULT` balance is 0), a notification is sent containing the `account_id`.

## Assumptions

1. The contract is unaware of the maturity type of the Time Deposit account, and the bank will be responsible for orchestrating the required maturity type (see [Rollover](#rollover) for more information).
2. If the customer would like to withdraw all of their funds, since we reject postings which would result in a full withdrawal, they must request the bank to transfer the funds and as a consequence, the account will be closed. The posting made by the bank will need to include the `force_override` metadata to avoid this check rejecting the posting.
3. The periods will not be configured together so we will run *either* the grace period logic *or* the deposit & cooling-off period logic where applicable. In the case that they are misconfigured then grace period takes precedence:

    ```plaintext
    if grace_period != 0:
        # this logic is only applicable to renewed TD accounts
        # run grace period logic

    else:
        # this logic is only applicable to new TD accounts
        # run deposit & cooling-off period logic
    ```

4. The length of any of the periods will not exceed the total term of the account.

## Out of Scope

### Rollover

This feature allows a customer to either withdraw their funds or reinvest their balances in another Time Deposit account after maturity. The following maturity types are supported:

- Withdrawal
- Rollover (Principal + Interest, Principal only, Partial Principal)

When a TD account reaches maturity, external orchestration is required to handle the appropriate rollover type. The maturity process could look something like:

1. When the `MATURITY` schedule runs, a notification is emitted by the smart contract, indicating the account has reached maturity, as per the CBF. After the account has reached maturity, all the running activities ie interest accrual and application on the account will be stopped. Also, any postings on the account after the maturity will be rejected.
2. External to Vault, the bank orchestrates the following processes given the different maturity types:
    - Rollover:
        - a new TD account is created (this is the renewed TD for the customer)
        - dependent on the rollover type, the respective funds are transferred from the original account to the renewed TD account
    - Withdrawal: funds are transferred out of the TD account
3. The account can be moved to `PENDING_CLOSURE` which triggers the smart contract's `deactivation_hook` and any non-capital addresses will be zero'd out.
4. The bank is required to transfer any capital to the desired account before fully closing the account.

## Outstanding Questions

- Questions surrounding rollover process:
  - There needs to be guidance provided on the Minimum Initial Deposit Amount check when rolling over since if the amount rolled over does not exceed this minimum, the transfer would be rejected. Force override can be used to bypass the check, but since this only affected the external orchestration, this needs to be detailed in the supporting documentation, and does not affect the contract's behaviour.
