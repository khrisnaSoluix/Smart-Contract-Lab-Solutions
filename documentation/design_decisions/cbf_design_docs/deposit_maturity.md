# Deposit Maturity CBF - Design Doc

## Scope

A deposit will reach maturity either at the end of its term or at a set date. When the deposit reaches maturity, a customer can withdraw funds without being charged any fees.

## Requirements

[CBF: Deposit maturity](https://pennyworth.atlassian.net/browse/CPP-2077)

## Assumptions

- The maturity time will be at midnight, on the day either calculated from the account creation date plus the term, or set by the `desired_maturity_date` parameter.

## Proposed Implementation

### Contract Parameters

- `term`: Instance parameter, `NumberShape` - The agreed length of time based on the term unit, in which the customer will receive interest on the deposit.
- `term_unit`: Template parameter, `UnionShape` - The unit at which the term is applied. Can have either 'days' or 'months' as options.
- `maturity_notice_period`: Template parameter, `NumberShape` - The number of days before the maturity date when the bank will be notified of an upcoming maturity.
- `desired_maturity_date`: Instance parameter, `DateShape` - Optional parameter for directly setting the date when a deposit matures.
- `maturity_date`: Derived parameter, `DateShape` - The date at which the deposit will mature. If `desired_maturity_date` is set, then `maturity_date` will be equal to `desired_maturity_date`, otherwise `maturity_date` will be calculated based on the `term` and `term_unit`.

### Technical Logic

- The account maturity date will be calculated by adding the term length to the account creation date. If a date is provided in the `desired_maturity_date` optional parameter, then it will override the date calculated based on the term.
- Within the `pre_posting_hook`, after maturity any postings should be rejected with the exception of `force_override` postings.
- A one-off schedule will be created to run at midnight after the end of the maturity day and send an account notification that the product has reached maturity. This schedule will also have logic to disable all incomplete schedules since the account has now reached end-of-life.
- A one-off schedule will be created to run at midnight, exactly `maturity_notice_period` days before maturity, in order to send an account notification that the deposit will mature in `maturity_notice_period` days
