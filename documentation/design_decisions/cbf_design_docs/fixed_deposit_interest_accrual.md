# Fixed Deposit Interest Accrual CBF - Design Doc

## Scope

Daily interest accrual for deposit products with a fixed interest rate.

## Requirements

[CBF: Fixed Deposit Interest Accrual](https://pennyworth.atlassian.net/browse/CPP-2347)

## Proposed Implementations

The CBF can be implemented leveraging existing logic from the `interest_accrual_common` feature, but some deposit products may require the interest rate to always be positive.

We have two options to enforce this requirement:

- Within the contract, we can restrict the `fixed_interest_rate` parameter to have a minimum value of `0` which forces the rate to be positive i.e. `shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01"))`.
- We can provided product level guidance to advise against this parameter configuration.

### Two Feature Files

#### Description

Two distinct feature files can be created with the following requirements:
|                                 | `fixed_interest_accrual`                                  | `fixed_positive_interest_accrual` |
|---------------------------------|-----------------------------------------------------------|-----------------------------------|
| `fixed_interest_rate` parameter | has no `min_value`                                        | has `min_value=Decimal("0")`      |
| accrual addresses               | `ACCRUED_INTEREST_PAYABLE`, `ACCRUED_INTEREST_RECEIVABLE` | `ACCRUED_INTEREST_PAYABLE`        |
| reversal logic                  | reverse both `PAYABLE` and `RECEIVABLE`                   | reverse only `PAYABLE`            |

#### Pros

- Easy for a contract writer to use the specific variant of feature without worrying about implementing correctly.
- Accrual with a positive interest rate on a deposit product does not need to consider `receivable` interest, so logic is simpler in `positive_fixed_interest_accrual` feature.

#### Cons

- Duplicated logic since the a number of calculations and data objects such as parameters will be almost identical between the two files - or this can be added to a deposit interest accrual common feature, which increases the feature scope

### Two Parameters In 1 Feature File

#### Description

One feature file called `fixed_interest_accrual` which contains two parameter definitions, i.e.:

```python
PARAM_FIXED_INTEREST_RATE = "fixed_interest_rate"
fixed_interest_parameter = Parameter(
    name=PARAM_FIXED_INTEREST_RATE,
    display_name="Fixed Interest Rate",
    shape=NumberShape(step=Decimal("0.01")),
    ...
)
positive_fixed_interest_parameter = Parameter(
    name=PARAM_FIXED_INTEREST_RATE,
    display_name="Fixed Interest Rate",
    shape=NumberShape(min_value=Decimal("0"), step=Decimal("0.01")),
    ...
)
```

where both parameters have the same value for `name`, and the contract template only includes one of the definitions in the parameter metadata.

By defining both parameters with the same `name` value, the logic does not have to worry about which implementation it is handling, but just uses the value of `fixed_interest_rate` as expected.

#### Pros

- No duplication of common logic, and logic which is only applicable to negative interest rates will not get triggered (since `+ x + = +`).
- With Parameters V2, we will be able to define one parameter resource with no `min_value`, and then within the specific product, define the `ExpectedParameter` with a `DecimalConstraint(min_value=Decimal("0"))` to enforce a positive interest rate.

#### Cons

- This does not match any implementations we already have, so will not be intuitive to implement.
- It is more complex to integrate for contract writer because they have to ensure they are choosing the correct parameter for their requirements.
- A rendered contract for positive interest only products will contain logic that is unused.

### Positive Interest Is Provided As Guidance For The Given Product

#### Description

Since the CBF has requirements for handling both positive and negative interest rates, the feature is implemented to these specifications. Then the given product can provide guidance surrounding what values are supported for the product. This implementation does not involve any technical restriction on the value.

#### Pros

- Generic feature which can be used by multiple products.
- Aligns with the requirements the CBF details.

#### Cons

- No way to protect against parameter being configured incorrectly, so may result in unknown behaviour.
- Might need to provide extra logic to handle negative interest rates for products where only positive interest rate is allowed (e.g. if rate is negative, assume it's zero).
- Doesn't take advantage of easily implementable restrictions which would prevent misconfiguration.

## Agreed Implementation - Two Parameters In 1 Feature File

The agreed implementation will define two parameter instances within the same `fixed_interest_accrual` feature with comments to explain to the contract writer how to correctly integrate the desired parameter into their template file.

### Data Definition

#### Contract Parameters

- `fixed_interest_rate`: Instance parameter - `NumberShape` - The fixed annual interest rate
  - There will be two versions of this parameter provided in the feature, `fixed_interest_parameter` and `positive_fixed_interest_parameter`
- `days_in_year`: Template parameter - `NumberShape` - The days in the year for interest accrual calculation. Valid values are "actual", "366", "365", "360" (defined in `interest_accrual_common`)
- `accrual_precision`: Template parameter - `UnionShape` - Precision needed for interest accruals (defined in `interest_accrual_common`)
- `interest_accrual_hour`: Template parameter - `NumberShape` - the hour of the day at which interest is accrued (defined in `interest_accrual_common`)
- `interest_accrual_minute`: Template parameter - `NumberShape` - the minute of the hour at which interest is accrued (defined in `interest_accrual_common`)
- `interest_accrual_second`: Template parameter - `NumberShape` - the second of the minute at which interest is accrued (defined in `interest_accrual_common`)

#### Balance addresses

- `ACCRUED_INTEREST_PAYABLE`: track payable interest (defined in `interest_accrual_common`)
- `ACCRUED_INTEREST_RECEIVABLE`: track receivable interest (defined in `interest_accrual_common`)

### Technical Logic

- Daily interest accrued is calculated with the following formula:

  ```plaintext
  total_daily_interest_accrued = deposit_balance * (annual_interest_rate / days_in_year)
  ```

  or

  ```plaintext
  total_daily_interest_accrued = deposit_balance * daily_interest_rate
  ```

- A function `get_annual_interest_rate` to return the value of the annual interest rate
- A function `get_daily_interest_rate` to return the value of the daily interest rate, which is calculated by `interest_rate / days_in_year`
