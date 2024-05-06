# Offset Mortgage - Design Doc

## Requirements

The defined requirements can be found here: [Mortgage Product Specification](https://docs.google.com/document/d/1YkjiLLLL4_tmy07nrkyI8drkEizp-ieEtWn-kjXSox8/edit#heading=h.4qjjcaq1qvmv)

### Business

An offset mortgage is a way to reduce the amount of interest customers pay back over the life (term) of a mortgage. Our mortgage product supports the balance offset variant, which links an active mortgage to multiple savings or current accounts. The total effective balance of any savings or current accounts linked to the offset mortgage account  reduces the effective mortgage principal that interest is accrued on. This lowers the interest portion of monthly mortgage payments and lowers the total payments over the lifecycle of the mortgage, and instead the customer will not earn any interest on the savings or current account balance.

As customers usually pay more interest on a mortgage than is earned from savings or current accounts, an offset mortgage can save customers a substantial amount of money over its lifetime. This means that as a month goes on, the daily interest accrued on an offset mortgage will differ depending on the offset account balance.

The offset mortgage feature performs an interest accrual daily on the outstanding mortgage principal after offsetting at the end of the day and applies it on the monthly repayment date. The interest will accrue at 5 decimal places (this is configurable) and the accrued interest is later rounded-up to 2 decimal places (this is configurable) and added to the customer’s interest due balance.

A mortgage can use either the offset or redraw feature, but use of both simultaneously is not supported.

### Supported eligibility matrix

| Mortgage types | Repayment plans      | Eligibility  |
|----------------|----------------------|--------------|
| Fixed-rate     | Principal + Interest | Eligible     |
| Fixed-rate     | Interest Only        | Not Eligible |
| Variable-rate  | Principal + Interest | Eligible     |
| Variable-rate  | Interest Only        | Not Eligible |

### Technical

The offsetting happens based on the End of Day balances of the associated mortgage and CA/SAs.

For this product, the yearly day count is configured by the `days_in_year` parameter in the mortgage account.

### Financial calculations

The daily accrual amount is calculated using:

`daily accrued interest = round(annual interest rate / days in year), 10) * effective principal`

The effective principal to be accrued on is calculated using the following formula:

`effective principal = mortgage principal - offset balance (from linked savings or current accounts)`

## Proposed Design

The proposed feature is designed to associate a mortgage account with current and savings accounts (denoted by **CA/SAs**)
We will need to achieve the following:

- associate a mortgage account with CA/SAs

- calculate offset interest accrual based on the balance of CA/SAs which fulfil the following criteria:

  - account has the same denomination as the mortgage account (as defined by the `denomination` parameter)
  - the account has a positive effective balance

- accrue interest using the formulae defined in the [financial calculations](#financial-calculations) section - we should only calculate offset accrual if the mortgage's scheduled code execution generates standard interest accrual postings as this will ensure that we respect accrual blocking factors such as a repayment holiday. All other non-interest postings from all accounts will be unaffected and instructed as expected.

### Supervisor setup

- provide the facility to supervise ***one*** existing mortgage account
- provide the facility to supervise CA/SAs
- the supervisor does ***not*** need to supervise any of the posting hooks, only `scheduled_event_hook`
- define an `ACCRUE_OFFSET_INTEREST` `SupervisorEventType` which will override the mortgage/CA/SAs accrual `EventType`

### Accrual behaviour

- do not accrue any interest if no accounts have been associated, i.e. the mortgage account continues to behave as usual
- if only CA/SAs are associated without an associated mortgage, commit all CA/SAs postings without performing any offset accrual manipulation
- if only a mortgage account is associated without CA/SAs, commit all mortgage postings without performing any offset accrual manipulation
- interest accrual postings should be updated to reflect the offset adjustment
- any non-standard interest accrual postings should not be modified and re-instructed as they aren't affected by offset adjustment
