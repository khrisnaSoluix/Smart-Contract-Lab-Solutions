# Monthly Maintenance Fee CBF Extension - Maintenance Fee Waiver - Design Doc

## Scope

The design doc will specify the way that the monthly maintenance fee waiver can be implemented as a extension to the existing maintenance fee CBF.
Though not a part of the CBF, this design document will also outline the implementation details for calculations of possible configuration options of when a monthly fee should be waived.

## Requirements

[CBF: Monthly Maintenance Fee Waivers](https://pennyworth.atlassian.net/browse/CPP-1925)

## Assumptions

This design doc is based on the assumption that the Monthly Maintenance Fee feature is implemented and this will build on top of that.

## Agreed Implementation

### Description

Monthly Maintenance Fee Waiver check uses an interface to allow for customisation of different waiver methods. If the waive condition is true, then skip the fee calculation for the maintenance fee.

### Pros

* Much more customisable
* Interfaces allow for better integration
* Simplifies the number of postings
* Simplifies testing requirements

### Cons

* Postings reversal / rebate not visible on posting history

### Data Definition

#### Contract Parameters

No additional parameters need to be defined specifically for the CBF specifically. Parameters defining the waive conditions should be done on a contract template level.

#### Data fetchers

Although no data fetchers are required, additional data fetchers may be required to implement the common waive condition checkers.

### Existing feature integration

Existing logic looks like this

```python
def apply_monthly_fee(*, vault: SmartContractVault) -> list[CustomInstruction]:
    """
    Gets monthly maintenance fees and the account where it will be credited.
    :param vault: Vault object for the account getting the fee assessed
    :return: Custom instructions to generate posting for monthly maintenance fees
    """
```

To help make with the versatility of this feature the proposed change to the function signature will look like the following:

```python
def apply_monthly_fee(
    *,
    vault: SmartContractVault,
    fee_waive_features: Optional[list[interfaces.WaiveFeeCondition]] = None,
) -> list[CustomInstruction]:
    if fee_waive_features and any([f.waive_fees() for f in fee_waive_features]):
        return []
    ...
    return cis
```

where `interfaces.waive_fee_condition` will look something like this:

```python
WaiveFeeCondition = NamedTuple(
    "WaiveFeeCondition",
    [
        (
            "waive_fees",
            Callable[
                # vault: SmartContractVault,
                # balances: Optional[BalanceDefaultDict] = None,
                ...,
                bool,
            ],
        ),
    ],
)

```

### Further considerations

#### Monthly Maintenance Fee Waiver Conditions

The following waiver conditions are fairly commonly used and will be used as an example of a implementation of a `WaiveFeeCondition` interface.

Waive by min monthly deposits:
The fee is waived if the total deposits in an account is over a certain threshold:
These functions should fulfil the interface signature.
An example of the monthly minimum deposit waiver condition can be seen below.

```python
def monthly_min_deposit(vault, balance_timeseries) -> bool:
    balance_threshold = get_parameter_balance_threshold(vault)
    if balances is None:
        balances = fetch_deposit_balances_timeseries(vault)
    total_credit = sum([b.credit for b in balance_timeseries])
    return total_credit > balance_threshold

WaiveCondition = interfaces.WaiveFeeCondition(waive_fees=waive_fees)
```

#### Monthly Average Balance

The monthly fee can be used to fetch the daily EOD observer.
The monthly balance can be defined by the $\frac{\sum EOD\, balances}{n\, days}$.

```python
data_fetchers = [*fetchers.PREVIOUS_EOD_OBSERVATION_FETCHERS]
# Example usage in library/features/v4/deposit/fees/minimum_monthly_balance.py
# look at apply_minimum_balance_fee -> balances_to_average
```
