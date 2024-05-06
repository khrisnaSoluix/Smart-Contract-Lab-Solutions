© Thought Machine Group Limited 2023

All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW.

# Lending Product Group Architecture

This document describes the non-revolving lending architecture for Product Group Feature Level Composition-based products written in Contracts API 4.x. Products that use this architecture will be able to leverage existing features, and extend behaviours via the documented interfaces.
A product can also partially use the architecture (e.g. more flexibility is required for certain lifecycle events that we do not currently account for). In this case re-use can still be achieved, either by using the relevant subset of features, or by re-using parts of features. This is based on the re-use guidelines explained in `documentation/implementation/features.md`.

## Product Lifecycle

We assume that all non-revolving products will be based on a sequence of one or more lifecycle events. These events either happen at dates defined by the product, or on an adhoc basis, typically driven by the customer.

The architecture accounts for the following schedule-driven events:

- Loan Start: initialising the loan
- Interest Accrual (optional): accruing interest, if required
- Due Amount Calculation: determining the amounts due for payment
- Overdue Amount Calculation (optional): checking and handling missed payments
- Delinquency Checks (optional): checking and handling delinquency
- Closure: closing out the loan

The precise definition of these events, whether they are required if optional, and their behaviours may vary from product to product. Some events may also occur on the same dates, so it is not necessarily a one-to-one mapping with schedules.

The architecture accounts for the following customer-driven events:

- Payments (including Overpayments and Early Repayments)
- Repayment holidays

The next sections cover the responsibilities of these events, and how the architecture supports them, by offering centralised features and/or catering for variances in desired behaviours (e.g. via interfaces).

## Common Addresses

The following balance addresses are assumed to be used throughout the architecture, so we will introduce them here:

- `PRINCIPAL`: the total remaining principal owed by the customer but not yet due for payment
- `PRINCIPAL_DUE`: the principal due for payment, excluding missed payments
- `PRINCIPAL_OVERDUE`: the principal due that has not been paid on time
- `ACCRUED_INTEREST_RECEIVABLE`: accrued interest that is not yet due for payment
- `INTEREST_DUE`: the interest due for payment, excluding missed payments
- `INTEREST_OVERDUE`: the interest due that has not been paid on time
- `PENALTIES`: any penalties incurred by the customer. These are always considered to be due

These addresses are often combined to provide aggregate balances (e.g. `PRINCIPAL + PRINCIPAL_DUE + PRINCIPAL_OVERDUE` is the total outstanding `PRINCIPAL`). Their definition must not be compromised by other features, or the central features' behaviours may be affected.

## Available Interfaces

The following interfaces are referred to throughout the remainder of the document, so we will introduce them here:

- `AmortisationFeature` - determines if and how EMI is calculated for the product, and how the elapsed/remaining term of the product is determined.
- `InterestApplication` - determines if and how any accrued interest is applied.
- `InterestRate` - determines if and how the interest rate at a given point in time is calculated.
- `EarlyRepaymentFee` - determines if an early repayment fee is due and its amount.
- `Overpayment` - determines how overpayments are distributed.
- `PrincipalAdjustment` - determines if and how the actual principal needs adjusting.
- `ReamortisationCondition` - determines if a product needs re-amortising.
- `ResidualCleanup` - determines how a feature must clean itself up during loan closure.

## Feature Contents

We refer to various features found in `library/v4/features/lending` throughout this document. We won't cover the full contents of each feature file, as these are further implementation details to be documented separately. They can all be bypassed, complemented, or modified further based on specific needs.

## Lifecycle Event Breakdown

### Loan Start

#### Overview

Loan Start allows products to initialise any required features. There is no central interface/feature as it is effectively just a list of function calls. Features typically include:

- Disbursing the principal to the relevant customer account
- Amortising the loan on the basis of this principal

Any features using schedules must provide an initial definition at this point even if activation doesn't involve the feature per se (e.g. Interest Accrual)

#### Relevant Interfaces

Although there is no central interface/feature, the typical product features use the following interfaces:

- `AmortisationFeature`: used to determine how the principal is amortised
- `InterestRate`: optionally used as part of amortisation
- `PrincipalAdjustment`: optionally used to adjust the actual principal being amortised beyond the official loan principal. For example, a loan fee may be deducted from or added to the principal.

### Interest Accrual

#### Overview

Interest Accrual provides the opportunity to accrue interest on the relevant balances, if required. There is no central interface, but we do provide a `interest_accrual` feature for standard interest accrual. This includes parameters, event types and functions to debit `ACCRUED_INTEREST_RECEIVABLE` and credit the parameterised internal account` on a daily basis at the specified time.

#### Relevant Interfaces

`interest_accrual` relies on the following interface(s):

- `InterestRate` - determines if and how the interest rate at a given point in time is calculated

### Due Amount Calculation

#### Overview

Due amount calculation refers to the process of determining how much principal and/or interest should be paid by the customer in the relevant loan cycle. The loan architecture provides a `due_amount_calculation` feature for handling due amount calculation in a standardised way. This includes parameters, event types and functions to perform the following on a monthly basis:

- Reamortise the loan, if needed
- Determine the correct amounts to credit to `PRINCIPAL` and `ACCRUED_INTEREST_RECEIVABLE` and debit from `PRINCIPAL_DUE` and `INTEREST_DUE`, respectively

#### Relevant Interfaces

`due_amount_calculation` relies on the following interface(s):

- `AmortisationFeature`: used to reamortise the loan, if required
- `InterestApplication`: used to determine the amount of interest to debit from INTEREST_DUE
- `InterestRate`: used as part of reamortisation
- `PrincipalAdjustment`: used as part of reamortisation
- `ReamortisationCondition`: used to determine if the loan needs reamortisation due to events happening since the previous due amount calculation

### Overdue Amount Calculation

#### Overview

Overdue amount calculation refers to the process of determining and handling the portion of due amounts that have not been repaid in time. The loan architecture provides an `overdue` feature for handling overdue amount calculation in a standardised way.  This includes parameters, event types and functions to perform the following on a monthly basis:

- Check for any remaining `INTEREST_DUE` and `PRINCIPAL_DUE` balances
- Transfer any non-zero amounts to the `INTEREST_OVERDUE` and `PRINCIPAL_OVERDUE` balances
- Emit a notification if to trigger relevant downstream processes if required

#### Relevant Interfaces

None.

### Delinquency Checks

#### Overview

Delinquency checks refer to the process of determining and handling any overdue amounts that have not been repaid in time. The loan architecture provides a `delinquency` feature for handling delinquency in a standardised way. This includes parameters, event types and functions to perform the following on a monthly basis:

- Check for any remaining `INTEREST_OVERDUE` and `PRINCIPAL_OVERDUE` balances and emit a notification to trigger relevant downstream processes

#### Relevant Interfaces

None.

### Closure

#### Overview

Closure allows loans to allow/prevent account closure and prepare for closure if applicable. The former involves business checks (e.g. has the loan been repaid) whereas the latter typically involves more technically-focused activities (e.g. zeroing out tracker balances). There is no central interface/feature for the whole of closure, but we do provide in `close_loan`:

- A standardised function `reject_closure_when_outstanding_debt` to prevent closure if applicable balances have not been repaid. This can be given the relevant list of addresses, or use pre-defined aggregates (e.g. `ALL_OUTSTANDING` to ensure all standard balances are repaid)
- A standardised function `net_balances` to zero-out non-repayable balances

#### Relevant Interfaces

`close_loan` depends on the following interface(s):

- `ResidualCleanup`: used by any feature in the loan lifecycle to zero out non-repayable addresses they are responsible for

### Payment Handling

#### Overview

Payment handling defines when a payment is accepted and how it affects the account's balances. This can be functionally driven (implementing a repayment hierarchy) or more technically driven (updating a tracker balance).
There is no central interface/feature to determine whether to accept a payment or not, as this is typically a sequential list of checks for the relevant features inside the `pre_posting_hook`.
There are two features to determine how to handle an accepted payment, which can be bypassed or complemented, based on precise requirements:

- `payments` provides a `generate_repayment_postings` method that allows a given posting's amount to be distributed according to a repayment hierarchy. It also uses interfaces to help specify the overpayment behaviour and early repayment fees.

- `close_loan` provides a `does_repayment_fully_repay_loan` method that will check if the relevant balances are fully repaid as a result of posting. This can then be used to trigger relevant downstream processes (e.g. by emitting a notification)

#### Relevant Interfaces

`payments` depends on the following interface(s):

- `Overpayment`: used to customise overpayment handling. This should include rebalancing beyond the normal hierarchy (e.g. paying to PRINCIPAL) and additional features (e.g. fees).
- `EarlyRepaymentFee`: used add early repayment fees if the whole loan is repaid as a result of an overpayment.

### Repayment Holiday

#### Overview

Repayment holidays require certain product features to be disabled to assist customers facing financial difficulties. There is no central interface to determine whether a repayment holiday is active or not, but the `repayment_holiday` feature provides:

- reusable parameters and corresponding helpers to control relevant lifecycle events (interest accrual, due amount calculation etc.)
- reusable functions (`should_trigger_reamortisation_no_impact_preference` and `should_trigger_reamortisation_with_impact_preference`) that can be used to trigger reamortisation as a result of a repayment holiday ending

#### Relevant Interfaces

`repayment_holiday` implements the following interface(s):

- `ReamortisationCondition`: used to reamortise a loan at the end of a repayment holiday

## Worked Example

Let's consider a simple loan named 'FIXED_RATE_LOAN' with the following features:

- Single disbursement at loan start
- Declining principal amortisation
- Daily interest accrual using a fixed rate and due monthly with repayments
- Monthly repayments, for which the customer is 'overdue' after 1 day and delinquent after a further 1 day
- Overpayments are not restricted and not subject to any fees

### Standard Features In Scope

Based on the specification, we will be using parameters, event types and functions from:

- `disbursement` to disburse principal at loan start
- `interest_accrual` to accrue interest daily
- `interest_application` to make accrued interest due monthly
- `due_amount_calculation` to make repayments due monthly
- `overdue` - to make repayments overdue at a fixed number of days from due amount calculation
- `delinquency` - to make repayments delinquent at a fixed number of days from overdue checks

### Additional Features/Interfaces To Implement

We will then need to implement the following interfaces:

- `AmortisationFeature`, to implement the desired declining principal amortisation. Note that this is already available under `amortisations/declining_principal`
- `InterestRate`, to implement the fixed rate behaviour when accruing. Note that this is already available under `interest_rate/fixed`
- `InterestApplication`, to implement the interest application behaviour when calculating repayments. Note that this is already available under `interest_application`
- `Overpayment`, to implement the rebalancing of overpayments

### Balance Examples For Lifecycle Events

The following examples only include the loan account itself and assume:

- A principal of 1000
- A 12 month term
- A 1% gross annual interest rate.

We will only detail a single occurrence of relevant events to keep brief.

#### Disbursement

At disbursement the principal is disbursed to the relevant customer account and the loan is amortised using declining principal.

| Address   | Before | After   |
|-----------|--------|---------|
| PRINCIPAL | 0      | 1000.00 |
| EMI       | 0      | 83.79   |

#### Interest Accrual

At the end of the day, interest is accrued on `PRINCIPAL` address to `ACCRUED_INTEREST_RECEIVABLE` address using the 1% gross annual interest rate, rounded to 5 decimal places.

| Address                     | Before  | After   |
|-----------------------------|---------|---------|
| PRINCIPAL                   | 1000.00 | 1000.00 |
| EMI                         | 83.79   | 83.79   |
| ACCRUED_INTEREST_RECEIVABLE | 0       | 0.27400 |

#### Due Amount Calculation

A month after opening, the due principal and interest amounts are calculated and stored in `PRINCIPAL_DUE` and `INTEREST_DUE`. We assume there are 30 accruals in this particular month.

| Address                     | Before  | After  |
|-----------------------------|---------|--------|
| PRINCIPAL                   | 1000.00 | 924.43 |
| EMI                         | 83.79   | 83.79  |
| ACCRUED_INTEREST_RECEIVABLE | 8.22    | 0.00   |
| INTEREST_DUE                | 0       | 8.22   |
| PRINCIPAL_DUE               | 0       | 75.57  |

#### Customer Payment

Later that day, the customer makes a repayment for 80 (i.e. less than total _DUE amounts), which is distributed to `INTEREST_DUE` first and then `PRINCIPAL_DUE`.

| Address                     | Before | After  |
|-----------------------------|--------|--------|
| PRINCIPAL                   | 924.43 | 924.43 |
| EMI                         | 83.79  | 83.79  |
| ACCRUED_INTEREST_RECEIVABLE | 0.00   | 0.00   |
| INTEREST_DUE                | 8.22   | 0.00   |
| PRINCIPAL_DUE               | 75.57  | 3.79   |

#### Overdue Check

1 day later, an additional accrual has happened and the overdue checks are carried out, moving any _DUE amounts to_OVERDUE. As there are non-zero amounts, a `FIXED_RATE_LOAN_OVERDUE_REPAYMENT` notification is also sent.

| Address                     | Before | After   |
|-----------------------------|--------|---------|
| PRINCIPAL                   | 924.43 | 924.43  |
| EMI                         | 83.79  | 83.79   |
| ACCRUED_INTEREST_RECEIVABLE | 0.00   | 0.02533 |
| INTEREST_DUE                | 0.00   | 0.00    |
| PRINCIPAL_DUE               | 3.79   | 0.00    |
| INTEREST_OVERDUE            | 0.00   | 3.79    |
| PRINCIPAL_OVERDUE           | 0.00   | 0.00    |

#### Delinquency Check

1 day later, an additional accrual has happened and the delinquency checks are carried out. As there are non-zero amounts, a `FIXED_RATE_LOAN_DELINQUENT_NOTIFICATION` notification is sent.

| Address                     | Before  | After   |
|-----------------------------|---------|---------|
| PRINCIPAL                   | 924.43  | 924.43  |
| EMI                         | 83.79   | 83.79   |
| ACCRUED_INTEREST_RECEIVABLE | 0.02533 | 0.05066 |
| INTEREST_DUE                | 0.00    | 0.00    |
| PRINCIPAL_DUE               | 0.00    | 0.00    |
| INTEREST_OVERDUE            | 3.79    | 3.79    |
| PRINCIPAL_OVERDUE           | 0.00    | 0.00    |

#### Early Repayment

Later that day, an early repayment is made to pay off all repayable balances, which excludes EMI. A `FIXED_RATE_LOAN_CLOSURE` notification is sent.

| Address                     | Before  | After   |
|-----------------------------|---------|---------|
| PRINCIPAL                   | 924.43  | 0.00    |
| EMI                         | 83.79   | 83.79   |
| ACCRUED_INTEREST_RECEIVABLE | 0.05066 | 0.00000 |
| INTEREST_DUE                | 0.00    | 0.00    |
| PRINCIPAL_DUE               | 0.00    | 0.00    |
| INTEREST_OVERDUE            | 3.79    | 0.00    |
| PRINCIPAL_OVERDUE           | 0.00    | 0.00    |

#### Closure

As part of the downstream processing triggered by the notification, the bank determines it is ready to close the Vault account. It updates the account status to `PENDING_CLOSURE` to trigger the `deactivation_hook`, which zeroes out any remaining non-repayable balances (EMI in this case). All the account balances are now 0, and the account status can be updated to `CLOSED`.

| Address                     | Before | After |
|-----------------------------|--------|-------|
| PRINCIPAL                   | 0.00   | 0.00  |
| EMI                         | 83.79  | 0.00  |
| ACCRUED_INTEREST_RECEIVABLE | 0.00   | 0.00  |
| INTEREST_DUE                | 0.00   | 0.00  |
| PRINCIPAL_DUE               | 0.00   | 0.00  |
| INTEREST_OVERDUE            | 0.00   | 0.00  |
| PRINCIPAL_OVERDUE           | 0.00   | 0.00  |
