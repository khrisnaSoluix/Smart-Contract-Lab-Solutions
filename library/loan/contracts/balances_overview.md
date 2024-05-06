© Thought Machine Group Limited 2021

All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW.

# Overview of balances used in the loan contract for the loan account

This overview is aimed at providing an initial introduction into understanding the inner works of the loan product and helping a contract writer in figuring out how the many balances inside the loan are used and how different events are reflected in the balances.

## List of addresses used by the loan account

Below you can find a list of all 14 addresses used by the loan account in the smart contract, together with a short description about the role they have:

* PRINCIPAL
    * Tracks remaining principal amount as if the standard repayment schedule is followed (overpayments and capitalised amounts are excluded)
    * Money gets moved out of this address at:
        * account activation
            * principal disbursement into deposit account
            * upfront fee disbursement into upfront fee account (if there is no amortisation of upfront fee, the fee amount will be added back to PRINCIPAL)
    * Money gets moved into this address at:
        * account closure (zeroing out addresses that track changes outside of standard declining principal repayments)
            * transferring principal capitalised interest amount
            * transferring overpayments
            * transferring EMI principal excess amount
        * repayment day schedule
            * transferring PRINCIPAL_DUE amount
        * balloon payment schedule
            * transferring PRINCIPAL_DUE amount (takes the remaining principal including overpayments, principal excess and capitalised interest/penalties)

* ACCRUED_INTEREST
    * Keeps track of daily accrued interest
    * Money gets moved out of this address at:
        * accrue interest schedule
            * daily interest accrual into the contra account
        * repayment day schedule
            * handles the remainder on the interest address and adds it to the contra account
        * post posting
            * clear out any remainder from rounding into the contra account, if repayment has paid off all accrued interest
    * Money gets moved into this address at:
        * post posting
            * repaying the accrued interest balance if we reach it in the repayment hierarchy
        * repayment day schedule
            * internal application of monthly accrued interest from the contra account
        * balloon payment schedule
            * internal application of remaining accrued interest from the contra account

* ACCRUED_EXPECTED_INTEREST
    * Calculated on the expected principal, which does not take the overpayments into account
    * This address is used to aid tracking the additional principal that has been paid off due to an overpayment.
    * Money gets moved out of this address at:
        * accrue interest schedule
            * adding expected daily interest accrued into the contra account
    * Money gets moved into this address at:
        * account closure
            * clearing accrued expected interest balance from contra account
        * repayment day schedule
            * monthly accrued interest excess gets applied and added to principal excess from contra account

* EMI_ADDRESS
    * Holds the value of the EMI, which is the fixed monthly payment amount for loan
    * Calculated as `EMI = [(P - (L/(1+R)^N)) x R x (1+R)^N]/[(1+R)^N-1]` where
        * P = remaining principal
        * R = monthly interest rate
        * N = remaining term
        * L = lump sum amount
    * For fixed emi, minimum repayment balloon loans, the emi is stored in the balloon_emi_amount parameter rather than the address
    * Money gets moved out of this address at:
        * repayment day schedule
            * updating the stored EMI amount into the contra account
    * Money gets moved into this address at:
        * account closure
            * clearing the EMI balance from the contra account
        * repayment day schedule
            * clearing the previously stored EMI amount from the contra account, before updating the new one

* PRINCIPAL_DUE
    * The amount part of the principal that is due every month
    * Calculated as EMI - ACCRUED_EXPECTED_INTEREST for repayment day schedules
    * For balloon payment schedule, the due amount takes the remaining principal including overpayments, principal excess and capitalised interest/penalties
    * Money gets moved out of this address at:
        * repayment day schedule
            * adding the monthly PRINCIPAL amount to the due address
            * adding the EMI_PRINCIPAL_EXCESS amount to the due address
        * balloon payment schedule
            * adding the remaining PRINCIPAL amount to the due address
            * adding the EMI_PRINCIPAL_EXCESS amount to the due address
    * Money gets moved into this address at:
        * check overdue schedule
            * marks the due amount as overdue
        * post posting
            * repayment according to the hierarchy


* INTEREST_DUE
    * Keeps track of the monthly applied interest
    * Money gets moved out of this address at:
        * repayment day schedule
            * adding the monthly interest from the interest received account
        * balloon payment schedule
            * adding the total remaining interest from the interest received account
        * post posting
            * adding the posting amount from the loan account if the posting is a debit and not a fee
    * Money gets moved into this address at:
        * post posting
            * early repayment interest adjustment to the interest received account
            * repayment made according to the hierarchy
        * check overdue schedule
            * marks the due amount as overdue

* OVERPAYMENT
    * Tracks all overpayments
    * Overpayments are currently disallowed for flat interest and minimum repayment balloon loans
    * Money gets moved out of this address at:
        * account closure
            * transferring overpayments to PRINCIPAL address
    * Money gets moved into this address at:
        * post posting
            * transferring the overpayment amount from the account default address

* EMI_PRINCIPAL_EXCESS
    * Tracks the increase in the principal portion of the EMI resulted from overpayments, calculated as the difference between the expected interest and the accrued one
    * Money gets moved out of this address at:
        * account closure
            * transferring principal excess to PRINCIPAL address
    * Money gets moved into this address at:
        * repayment day schedule
            * adding the monthly principal excess from PRINCIPAL_DUE
        * balloon payment schedule
            * adding the principal excess since the last repayment date from PRINCIPAL_DUE


* PENALTIES
    * Can hold the values of either:
        * Late repayment fees if the full amount due is not repaid by the end of the repayment period
        * Flat fee penalty
        * Penalty interest rate
    * Money gets moved out of this address at:
        * accrue interest schedule
            * penalty interest accrual on overdue amount into penalty interest account
        * check overdue schedule
            * charging late repayment fees into the repayment fee account
        * post posting
            * charging a fee from the loan account
    * Money gets moved into this address at:
        * post posting
            * repayment according to the hierarchy

* PRINCIPAL_OVERDUE
    * Principal amount that had not been repaid during the repayment period
    * Money gets moved out of this address at:
        * check overdue schedule
            * marks the due amount as overdue
    * Money gets moved into this address at:
        * post posting
            * repayment according to the hierarchy

* INTEREST_OVERDUE
    * Interest amount that has not been repaid during the repayment period
    * Money gets moved out of this address at:
        * check overdue schedule
            * marks the due amount as overdue
    * Money gets moved into this address at:
        * post posting
            * repayment according to the hierarchy


* ACCRUED_INTEREST_PENDING_CAPITALISATION
    * Keeps track of accrued interest during due amount blocking flag (for example, repayment holiday)
    * Money gets moved out of this address at:
        * accrue interest schedule
            * daily capitalised interest accrual into the capitalised interest account during due amount blocking flag
    * Money gets moved into this address at:
        * accrue interest schedule
            * transferring accrued interest during due amount blocking flag to PRINCIPAL_CAPITALISED_INTEREST

* ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION
    * Keeps track of all the interest accrued from penalties
    * Money gets moved into this address at:
        * repayment day schedule
            * capitalising interest accrued to PRINCIPAL_CAPITALISED_INTEREST adress
        * post posting
            * repayment from capitalised interest overdue if it reaches that point after going through the repayment hierachy
    * Money gets moved out of this address at:
        * accrue interest schedule
            * penalty interest accrual on overdue amount transferred to capitalised interest received account

* PRINCIPAL_CAPITALISED_INTEREST
    * Tracks capitalised interest that is added to principal
    * Money gets moved out of this address at:
        * account closure
            * transferring principal capitalised interest amount to PRINCIPAL address
        * accrue interest schedule
            * moving capitalised interest from ACCRUED_INTEREST_PENDING_CAPITALISATION address to principal after due amount blocking flag expiry
        * repayment day schedule
            * transferring accrued interest from ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION address

* PRINCIPAL_CAPITALISED_PENALTIES
    * Tracks late repayment fees that are added to principal
    * Money gets moved out of this address at:
        * check overdue schedule
            * capitalising the late repayment fees into the capitalised penalties received account

* INTERNAL_CONTRA
    * Internal address used for double-entry bookkeeping purposes

## Repayment hierarchy

Another important piece of information is the order of the addresses that get updated when the customer performs a repayment.
The contract is using the following hierarchy:

1. PRINCIPAL_OVERDUE
2. INTEREST_OVERDUE
3. PENALTIES
4. PRINCIPAL_DUE
5. INTEREST_DUE
6. PRINCIPAL
7. ACCRUED_INTEREST
8. ACCRUED_OVERDUE_INTEREST_PENDING_CAPITALISATION

## Basic example of loan lifecycle

The simulation test `test_regular_events` (located in library/loan/contracts/tests/simulation/loan_test.py) has been created in order to show how the different addresses get updated depending on different account events. We can see an overview of those events and the movement of money in the table below:

| EVENT | PRINCIPAL | PRINCIPAL DUE | PRINCIPAL OVERDUE | INTEREST DUE | INTEREST OVERDUE | OVERPAYMENTS | PENALTIES | EMI PRINCIPAL EXCESS | PRINCIPAL CAPITALISED INTEREST | CAPITALISED INTEREST OVERDUE | DEPOSIT ACCOUNT | LATE REPAYMENT FEE INCOME ACCOUNT | OVERPAYMENT FEE INCOME ACCOUNT|
| ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- | ----------- |
| activation | -1000 | | | | | | | | | | 1000 | | |
| repayment schedule Feb | 99.61 | -99.61 | | -1.15 | | | | | | | | | |
| deposit of 101 | | 99.61 | | 1.15 | | 0.23 | | | | | -101 | | 0.01 |
| repayment schedule Mar | 99.77 | -99.77 | | -0.69 | | | | | | | | | |
| deposit of 50 | | 50 | | | | | | | | | -50 | | |
| overdue check | | 49.77 | -49.77 | 0.69 | -0.69 | | -15 | | | | | 15 | |
| repayment schedule Apr | 99.78 | -99.78 | | -0.68 | | | | | -0.63 | 0.63 | | | |
| deposit of 500 | | 99.78 | 49.77 | 0.68 | 0.69 | 317.38 | 15 | | | | -500 | | 16.7 |
| repayment schedule May | 99.88 | -0.26 -99.78 | | -0.32 | | | | 0.26 | | | | | |
| overdue check | | 100.14 | -100.14 | 0.32 | -0.32 | | -15 | | | | | 15 | |
