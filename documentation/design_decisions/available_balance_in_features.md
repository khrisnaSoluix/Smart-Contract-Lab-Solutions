# Available Balances in Features

## Overview

It is becoming increasingly necessary to adjust the available balance of an account as viewed by a specific feature. For example, a fee charging feature may be required to have knowledge of the account available balance in order to limit the fee charged to the customer. However, other features may alter the net available balance of the account and therefore accessing the account balances from the fetched data alone may be insufficient. For example, overdraft features effectively increase the available balance of an account. So, if an account has a balance of `£3` and an overdraft of `£100`, the net available funds of the account is `£103`.

Although this definition is valid for a fee charging feature, it isn't valid for a round up autosave feature, as you cannot use your overdraft to round up into a savings account. The difference between available balance definitions across features leads to complexity in how each feature accesses the net available balance of an account. Therefore, a flexible and sensible solution needs to be defined in order for features to account for available balance adjustments from other features without introducing cross feature dependencies.

Currently, the definition of available balance is hard coded across the library. Although this currently presents no immediate issue, later down the line this inflexible approach may lead to difficult refactoring.

## Implementation Options

### DEFAULT Address Balance Injection

This proposed implementation is to apply a balance injection at the contract template level. Thereby modifying the fetched balances to provide an alternative `BalancesDefaultDict` to the relevant feature.

#### Template Layer

Generally in the template features are called like below

```python
custom_instructions = []
balances = vault.get_balances_observation(fetcher_id=fetcher_id).balances
custom_instructions.extend(feature_a.apply(vault, balances, *params))
```

To use make use of the modified balances one would clone the balances and inject the modifications into the fetched balances, the modified balances are then passed through to the feature. Care has to be taken to account for various features that may, or may not, require the available balance modifications. Saying this, it still may be necessary to update the fetched_balances with any in-flight `CustomInstructions`.

```python
custom_instructions = []
fetched_balances = vault.get_balances_observation(fetcher_id=fetcher_id).balances
modified_balances = feature_a.apply_modification_to_balances(balances)
custom_instructions.extend(feature_b.apply(vault, modified_balances, *params))

# Modified balances should not be considered for feature c
custom_instructions.extend(feature_c.apply(vault, fetched_balances, *params))
```

#### Feature Layer

There is no change to code on the feature layer since from the feature perspective it us unaware of the fetched data manipulation.

#### Balance Modification Feature Implementation

Below is an example of how the existing overdraft features would define a function to modify the fetched balances

```python
_OVERDRAFT_UPDATED_TRACKER = "_OVERDRAFT_UPDATED_TRACKER"

def apply_overdraft_to_balances(
    balances: BalanceDefaultDict,
    denomination: str,
    address: str = DEFAULT_ADDRESS,
    asset: str = DEFAULT_ASSET,
):
    # Check if the overdraft operation is already applied
    if utils.get_available_balance(
        balances=balances,
        denomination=denomination,
        asset=asset,
        address=_OVERDRAFT_UPDATED_TRACKER,
    ) != Decimal("0"):
        return balances

    arranged_overdraft_amount: Decimal = utils.get_parameter(
    vault, PARAM_ARRANGED_OVERDRAFT_AMOUNT, is_optional=True, default_value=Decimal("0")
    )
    unarranged_overdraft_amount: Decimal = utils.get_parameter(
        vault, PARAM_UNARRANGED_OVERDRAFT_AMOUNT, is_optional=True, default_value=Decimal("0")
    )

    total_overdraft_amount = arranged_overdraft_amount + unarranged_overdraft_amount
    offset_balance = Balance(credit=total_overdraft_amount, debit=0, net=total_overdraft_amount)
    balances[address] += offset_balance
    balances[_OVERDRAFT_UPDATED_TRACKER] = Balance(credit=Decimal(1), debit=0, net=Decimal(1))

    return balances
```

#### Pros

- The complexity is obscured from the feature
- Feature implementations (signature and functionality) do not need to be updated
- This approach is very flexible

#### Cons

- Modifying fetched data during the hook execution can be dangerous as both fetched and modified fetched data are now being handled
- It becomes very difficult to define whether a feature expects modified or unmodified balances
- This solution is onerous
- The definition of 'available balance' is hardcoded into the feature

### Available Balance Adjustment Interface Callable

This solution relies on passing through an interface to those features that require it. The feature would then determine the available balance by looping through the available balance adjustment interfaces.

#### Available Balance Adjustment Interface Definition

  ```python
  AvailableBalanceAdjustment = NamedTuple(
      "AvailableBalanceAdjustment",
      [
          (
              "calculate_available_balance_adjustment",
              Callable[
                  # vault: SmartContractVault,
                  # balances: Optional[BalanceDefaultDict],
                  # denomination: Optional[str]
                  ...,
                  Decimal,
              ],
          ),
      ],
  )
  ```

#### Template level

```python
balance_adjustment = feature_a.AvailableBalanceAdjustment
feature_a.apply(*original_args, balance_adjustment)
```

#### Feature Level

```python
def apply(*args):
    balances = (balances or vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances)

    available_balance = utils.get_available_balance()

    if balance_adjustment:
        available_balance += sum(balance_adjustment.calculate_available_balance_adjustment() for balance_adjustment in balance_adjustments)
```

#### Pros

- Clear
- Consistent with how we handle principal adjustments in lending products

#### Cons

- Feature function signature and logic updates are required
- A new interface needs to be implemented and maintained
- The definition on 'available balance' is hardcoded into the feature
- Less flexible

### Available Balance Callable

This solution relies on passing through a callable to the feature which is used to calculate the available balance. This callable can be optional with each feature defaulting sensibly.

#### Available Balance Interface Definition

```python
AvailableBalance = NamedTuple(
    "AvailableBalance",
    [
        (
            "calculate_available_balance",
            Callable[
                # vault: SmartContractVault,
                # balances: Optional[BalanceDefaultDict],
                # denomination: Optional[str]
                ...,
                Decimal,
            ],
        ),
    ],
)
```

#### Template level

```python
def calculate_available_balance(
    vault: SmartContractVault,
    balances: Optional[BalanceDefaultDict],
    denomination: Optional[str]
) -> Decimal:
    # some logic
    return available_balance

feature_a_.apply(*original_args, available_balance=calculate_available_balance)
```

#### Feature Level

```python
def apply(*args, available_balance_callable: Optional[AvailableBalance] = None):
    balances = (balances or vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances)

    available_balance = available_balance_callable.calculate_available_balance() if available_balance_callable else utils.get_available_balance()

```

#### Pros

- Clear
- Most flexible
- Each template can define what available balance actually is, making use of features that alter the available balance
- The upfront workload to introduce this across the library is fairly light as the existing definition suffices for most of the existing scenarios

#### Cons

- Feature function signature and logic updates are required
- A new interface needs to be implemented and maintained

## Proposed Implementation

The available balance callable is the preferred implementation as it provides the most flexible and scalable solution to the problem. Also, it is the only proposed solution that solves the hardcoded definition of `available balance` that currently exists across the library. In addition, this approach provides the flexibility to allow the contract writer to make use of the [balance injection approach](#default-address-balance-injection)
