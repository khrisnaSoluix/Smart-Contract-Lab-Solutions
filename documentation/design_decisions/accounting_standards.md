# Accounting Standards

This document outlines our standardised approach to accounting within the Product Library.

## Design Considerations

The Product Library features often have associated industry-standard accounting flows that the features should be aligned to. While these are fully implementable in Vault, we want to ensure Vault is used as intended, without taking on the role of other systems in the bank-wide architecture, such as an accounting system. This ensures a maintainable and performant solution. As such, we avoid orchestrating complex flows that are not required for implementation of a product's financial behaviours, which is the primary purpose of a Smart Contract.

## Scope

### Standard Events

The following accounting events are widely used in the Product Library:

- Accruing/Applying Interest - Payable
- Accruing/Applying Interest - Receivable
- Charging Fees

### Accounting Types

In general we see two types of accounting:

1. Cash Accounting - revenue/expense recognised when money is received/paid. A single internal account is posted to and there is no receivable/payable concept. This is typically used for fees.
2. Accrual Accounting - revenue/expense recognised when earned, which can be before it is received/paid. This implies use of a receivable/payable account and an revenue/expense account. The former tracks what is due to be received/paid and the latter tracks what is actually received/paid. This is typically used for interest, but can also be used for fees.

### Interest - Payable

We use accrual accounting for payable interest.

#### Internal Accounts

| Account Name                       | Purpose                                         |
|------------------------------------|-------------------------------------------------|
| `interest_paid_account`            | Records interest paid to the customer           |
| `accrued_interest_payable_account` | Records interest due to be paid to the customer |

#### Events

| Event                     | DR/CR | Account                            | Address                    |
|---------------------------|-------|------------------------------------|----------------------------|
| Accrue Interest (Payable) | DR    | `accrued_interest_payable_account` | `DEFAULT`                  |
|                           | CR    | Customer Account                   | `ACCRUED_INTEREST_PAYABLE` |
| Apply Interest (Payable)  | DR    | `accrued_interest_paid_account`    | `DEFAULT`                  |
|                           | CR    | Customer Account                   | `DEFAULT`                  |
|                           | DR    | Customer Account                   | `ACCRUED_INTEREST_PAYABLE` |
|                           | CR    | `accrued_interest_payable_account` | `DEFAULT`                  |

**Note:** The addresses can be made more specific if required by a given product (e.g. different types of payable interest)

### Interest - Receivable

We use accrual accounting for receivable interest.

#### Internal Accounts

| Account Name                          | Purpose                                               |
|---------------------------------------|-------------------------------------------------------|
| `interest_received_account`           | Records interest received from the customer           |
| `accrued_interest_receivable_account` | Records interest due to be received from the customer |

#### Events

| Event                        | DR/CR | Account                               | Address                       |
|------------------------------|-------|---------------------------------------|-------------------------------|
| Accrue Interest (Receivable) | DR    | Customer Account                      | `ACCRUED_INTEREST_RECEIVABLE` |
|                              | CR    | `accrued_interest_receivable_account` | `DEFAULT`                     |
| Apply Interest (Receivable)  | DR    | Customer Account                      | `DEFAULT`                     |
|                              | CR    | `interest_received_account`           | `DEFAULT`                     |
|                              | DR    | `accrued_interest_receivable_account` | `DEFAULT`                     |
|                              | CR    | Customer Account                      | `ACCRUED_INTEREST_RECEIVABLE` |

**Note:** The addresses can be made more specific if required by a given product (e.g. different types of payable interest)

### Charging/Applying Fees

We typically use cash accounting for fees, as they are normally charged/applied immediately. However, it can make more sense to use accrual accounting, in which case the previously described events can be easily adapted. The information below applies to the cash accounting scenario.

#### Internal Accounts

| Account Name                 | Purpose                                 |
|------------------------------|-----------------------------------------|
| `<fee_name>_revenue_account` | Records fees received from the customer |

#### Events

| Event      | DR/CR | Account                      | Address   |
|------------|-------|------------------------------|-----------|
| Charge Fee | DR    | Customer Account             | `DEFAULT` |
|            | CR    | `<fee_name>_revenue_account` | `DEFAULT` |

## Implementation Considerations

### Parameters

Each product should offer parameterised internal account ids, based on the features supported by the product and the relevant internal accounts according to the previous section. Structure these parameter names as `<purpose>_<type>_account`. For example, the purpose might be accrued_interest, the type receivable and the parameter would be accrued_interest_receivable_account. There are many possible values for purpose based on variants of fees, interest and so on. Type so far is limited to:

- receivable, received, payable, paid - accrual accounting for interest or fees
- income - cash accounting for fees

### Negative Interest

If a product supports both positive and negative interest rates, the resulting accounting flows are inverted when the sign changes (e.g. what is normally Payable interest suddenly becomes receivable and vice-versa), which will require both receivable and payable parameters + logic in the contract

## Integration

We expect individual postings affecting the Sub-Ledger/General Ledger to be transformed and ingested by an external accounting system. The standards described in this document can be used to interpret Vault's Core API Posting-related events and determine what to feed to the accounting system. In order to further facilitate integration with external accounting systems, we also populate relevant posting instructions `instruction_details` with the following metadata:

```json
{
    "event": "ACCRUE_INTEREST",
    "gl_impacted": "True",
    "account_type": "MORTGAGE"
}
```

The `event` value will vary from accounting event to event. The `account_type` field will vary from product to product, and is there to inform the integration on the type of account that the event affects.

**Note:** We include other fields in the `instruction_details` for other purposes. Do not expect to solely see these three fields
