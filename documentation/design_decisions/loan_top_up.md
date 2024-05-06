# Loan Top Up

## Assumptions

N/A

## Scope

A loan top-up refers to the ability for a borrower to obtain further funds from the lender, and allowing for specific loans terms and conditions to be optionally updated (e.g. change of fixed or variable rate and the loan term). A loan top-up is handled within the scope of the existing loan account and no further accounts are required to be created.

## Requirements

### Business

A top-up involves the borrower being disbursed further funds and no more, therefore we do want to limit top-up conditions, where possible, and only support specific changes (e.g. we will not support changes to the amortisation type). Namely, we will only support changes to:

- loan principal
- loan term
- type of interest (fixed or variable)
- loan interest rate (fixed or variable rate adjustment, depending on the type of loan)
- loan disbursal account

We need to preserve certain aspects of the current loan state, beyond what is explicitly changing. This currently includes, but isn't limited to:

- existing customer-facing schedules
- existing owed balances

### Technical

We need to consider:

- Integration - how easy is it to effect the top up?

- Data Availability - how easy is it to retrieve customer account data after the top up?

- Preserving / Resetting technical state (e.g. elapsed due amount calculation counters)

## Potential Approaches

The potential approaches available are detailed in `documentation/design_decisions/mortgage_product_transfers.md`.

## Preferred Approach

The preferred approach is identical to that defined in `documentation/design_decisions/mortgage_product_transfers.md`.

## Proposed Implementation

- Add a 'product top-up' indicator parameter to the Loan as a 'boolean' `UnionShape`
- Update the loan parameters listed below:
  - product top-up indicator - set to True
  - `principal` - the total principal for the loan, the delta is disbursed during the top-up (e.g. if previously the principal was 1000 and then updated to 1500, the top-up would result in a disbursal of 500).
  - `total_repayment_count` - this should be the absolute total repayment count (i.e. original + extension, so for example if the `total_repayment_count` was originally 12 and the top-up extends the loan by 5 months, then the `total_repayment_count` should be set to 17)
  - `fixed_interest_loan` - update if switching between fixed or variable rate
  - `fixed_interest_rate` / variable_rate_adjustment - update if the interest rate of the loan should be changed
  - `deposit_account` - if the principal is to be disbursed into a different account compared to the initial disbursal

- If the 'product top-up' indicator parameter is 'true' when the conversion hook runs:

  - Reamortise the loan (this could be no-op if the parameter values haven't changed). As we normally calculate the emi on activation we must therefore reamortise during conversion. The conversion hook has full access to data/directives, so we do not face the same challenges as with activation

  - The `DUE_AMOUNT_CALCULATION_EVENT_COUNTER` should be preserved since the total_repayment_count parameter is the absolute value and we must be able to account for cases where the total_repayment_count is unchanged as a result of the top-up.

  - Reset tracker balances used in the reamortisation process, as we've already reamortised using the balances at the time of conversion:
        -`OVERPAYMENT`, `PRINCIPAL_CAPITALISED`, `EMI_PRINCIPAL_EXCESS`, `ACCRUED_EXPECTED_INTEREST` and `OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC` should all be zero'd out

    - This is identical to the `close_loan.net_balances` feature that we call in `deactivation_hook` today, so updates to the interface implementations will also handle product switching scenarios seamlessly

  - Disburse the additional principal to the disbursement account (may be different to the initial disbursement account)

  - Preserve all schedules when a conversion is run.

This implementation is more or less identical to the Mortgage product switch, except for the preservation of the `DUE_AMOUNT_CALCULATION_EVENT_COUNTER` and the addition of the extra fund disbursal. As a result the already implemented conversion logic can be extracted into a standalone feature to promote reuse. The preservation of the `DUE_AMOUNT_CALCULATION_EVENT_COUNTER` is required because a loan top-up is an extension to the original loan, whereas the Mortgage product switch behaves more akin to a new product, starting afresh.
