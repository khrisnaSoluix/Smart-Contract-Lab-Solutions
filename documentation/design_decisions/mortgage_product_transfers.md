# Mortgage Product Transfers

## Assumptions

N/A

## Scope

Product Transfers refer to the ability to switch from a given set of terms and conditions to another (e.g. to release equity, get more a favourable interest rate, reduce term). They encompass scenarios where the customer stays with their existing provider (product transfer), or moves to a different provider altogether (remortgaging). This can take place at any point in the mortgage lifecycle, possibly incurring fees (e.g. before a fixed interest term has completed).

As a remortgage across lenders (and therefore platforms) would simply involve opening a new mortgage account with the desired product and disbursing appropriately, we won't consider this scenario further in this document. It may be revisited separately, if necessary.

## Requirements

### Business

We do want to not be limited to specific transfer conditions (e.g. changing amortisation types, changing terms, changing principal etc), unless there is an explicit business reason to prevent it.

We need to preserve certain aspects of the current mortgage's state, beyond what is explicitly changing. This currently includes, but isn't limited to:

- existing customer-facing schedules

- existing owed balances

We need to reset other aspects. This currently includes, but isn't limited to:

- overpayment allowance

### Technical

We need to consider:

- Integration - how easy is it to effect the product transfer?

- Data Availability - how easy is it to retrieve customer account data after the product transfer?

- Preserving / Resetting technical state (e.g. elapsed due amount calculation counters)

## Potential Approaches

### Multi-Product Contract

This is generally considered to be an anti-pattern (see `design_anti_patterns.md`), but we will still
outline how it works and specifics about why it is undesirable.

#### Description

This approach involves a single contract that can implement all the different product types, and changing parameter values to effect a product transfer. For example, an `amortisation_method` parameter could change from `declining_principal` to `flat_interest`, or a `rate_type` could be adjusted from `fixed-to-variable` to just `variable`.

#### Pros

- Account data is in one place

- Integration is easy (simple parameter update)

#### Cons

- Encourages a design anti-pattern (see `design_anti_patterns.md`)

- Puts the onus on the contract to be aware of handling data differently based on historic product states, which increase the complexity significantly, and makes it harder to optimise performance. This is part of the anti-pattern, but we're highlighting here to draw explicit comparisons with other approaches

- Encourages monolith products, instead of more specific ones (e.g. fixed rate declining principal mortgage vs variable rate flat_interest mortgage), which in turn results in harder maintenance

- Requires explicit handling of product transfer scenarios within the contract, which makes it harder to meet our requirements

- Forces parameters to be created at in instance level to support use of `post_parameter_change_hook` when they may really be product-level

### Account Product Version Updates

#### Description

This approach involves a contract per product type and updating the account from one product version to another when required.

#### Pros

- Account data is in one place

- Integration is easy (simple account update)

- Doesn't violate any anti-patterns / best practices

- Only requires generic handling of product transfer scenarios

- Simple to preserve required state as most data is still available

- Expands our technical coverage for contracts to include `conversion_hook` (this has already led to some suggested improvements in the Cons section below)

#### Cons

- Like the multi-product contract approach, the onus is on the contract to handle data differently based on historic product states. However, the contract will not have the historic code in this case, nor will it be aware of when the product transfer occurred outside of the `conversion_hook`. If services require historic external state (e.g. derived parameter values before the product switch), this could be achieved via a notification

- The contract will need to distinguish product version upgrades that add functionality or fix bugs from actual product transfers. In an ideal world we could deduce from the `conversion_hook` arguments (e.g. has the product id changed, or just the product version id). For now we likely require a parameter to indicate the intent behind the upgrade (e.g. a boolean-esque `is_product_transfer_conversion` parameter). This is not particularly elegant and could cause issues if the parameter is not set correctly. This should form the basis of a platform improvement for additional data to drive conversion logic

- Until Vault 5.0 we will lose parameter timeseries at the time of conversion. However, this should not be problematic beyond what we've already covered above as historic parameters are only used in derived parameters (see first point) or to determine variable rate reamortisation,. From Vault 5.0 this would not be a problem for this approach

- Until Vault 5.0 we will not be able to reject conversions with incorrect parameter values. This also applies to opening new accounts

### New Account

#### Description

This approach involves a contract per product type and creating a new account to achieve the product transfer. This effectively models product transfers like remortgages, whereby the new account performs an early repayment of the old account

#### Pros

- Conceptually accurate, if we assume that an account is an instance of a product and the product has indeed changed

- Easy to access the historic state of the account across products

- Doesn't violate any anti-patterns / best practices

- Only requires generic handling of product transfer scenarios

#### Cons

- Account data is in multiple places, which will increase the work done by other services to provide a unified view, if required. This may also require client education to clarify that a customer account does not need to be 1-2-1 with a vault account

- The split data also means the new account's contract cannot natively access historic data to inform current decisions. A complex mechanism would be required to maintain the mortgage state to preserve, which will severely affect contract complexity and integration. These are listed below and effectively feel like a deal breaker:

  - Balances are relatively simple. A dedicated feature could assess the view of what is accrued/due/overdue, and make corresponding postings, although there is a risk of race conditions and would require both accounts open at once.

  - Schedules can also be recreated if we add additional parameters that would add a lot of overhead to features (e.g. a return of `loan_start_date`), but their last execution times would not be natively transferable without even further parameters

  - Parameters are also problematic, without adding further parameters and the associated overhead and complexity. As per the Account Product Version Updates approach, this isn't an issue right now but could be later

  - Flags are not a problem, as they are not associated in any way with the contract

## Preferred Approach

The Account Product Version Upgrade approach is the best option we have now and in the future:

- The Multi-Product Contract and New Account approaches effectively rule themselves out due to the overwhelming cons

- While there are some cons to the Account Product Version Upgrade approach, two will be addressed in Vault 5.0 and the others can be dealt with without excessive complexity

It is therefore the best option we have at the moment and in the near future.

## Proposed Implementation

- Add a 'product transfer' indicator parameter to the Mortgage as a 'boolean' UnionShape

- If this is is 'true' when the conversion hook runs:

  - Apply overpayment fee

  - Reamortise the mortgage (this could be no-op if the parameter values haven't changed). As we normally calculate the emi on activation we must therefore reamortise during conversion. The conversion hook has full access to data/directives, so we do not face the same challenges as with activation

  - Reset tracker balances used in the reamortisation process, as we've already reamortised using the balances at the time of conversion:

    - `OVERPAYMENT`, `PRINCIPAL_CAPITALISED`, `EMI_PRINCIPAL_EXCESS`, `ACCRUED_EXPECTED_INTEREST`, `DUE_AMOUNT_CALCULATION_EVENT_COUNTER` and `OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC` should all be zero'd out

    - This is identical to the `close_loan.net_balances` feature that we call in `deactivation_hook` today, so updates to the interface implementations will also handle product switching scenarios seamlessly

  - Preserve schedules when a conversion is run, other than the overpayment allowance schedule. As the allowance period is reset, the corresponding schedule is updated to run a year from the conversion date

The above is functionally equivalent to the previous design used in the CLv3 mortgage. The additional account notification mentioned in the approach is considered optional and will not be implemented initially.
