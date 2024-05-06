_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers implementation guidance for the use of Contract parameters.

# Parameters

## Names

Parameters need to be explicit and have meaningful names. Contract readers should be able to instantly understand what the parameter is used for and what the value should be. For best practices see Clean Code (Robert C. Martin).

Names should be lower case, separated by underscores.

## Display Names

The display name for parameters should follow title caps naming convention.

## Description

The parameter description field should only have a full stop if it contains more than one complete sentence, otherwise leave it without. Question marks are acceptable.

## Defining New Shapes

Consider defining new shapes if you have multiple parameters with the same properties, but avoid them if they are used just once within the contract.

### Boolean Parameters

A very common use case is to define a parameter which should be treated as a boolean object and there are several different ways to define the parameter shape to achieve this, but the use of `UnionShape()` is advised. It's cumbersome to repeatedly define a `UnionShape()` parameter with two `UnionItem` objects for True and False, therefore, a BooleanShape custom shape should be defined to be re-used across all parameters.

```python
BooleanShape = UnionShape(
    items=[
        UnionItem(key="True", display_name="True"),
        UnionItem(key="False", display_name="False"),
    ]
)

BooleanValueTrue = UnionItemValue(key="True")
BooleanValueFalse = UnionItemValue(key="False")
```

## Shape Validation

NumberShape parameters have metadata `max_value`, `min_value` and `step` that associated with them, but not all metadata is validated by Vault. Only GLOBAL and INSTANCE level parameter fields max_value and min_value are validated.

## Optional parameters and the default_value field

The `default_value` field for a parameter is used in specific circumstances.

For instance parameters at the account level it is only used when converting an account from one product version to another. If the instance parameter is introduced in the new product version then the parameter `default_value` will be used for the parameter value in the converted contract if an alternate value is not specified during the conversion via the field `instance_param_vals_to_add`.

Parameters can be defined as `OptionalShape` and have value `OptionalValue`. In this case the parameter does not receive a default value, but the `is_set()` method should be used to detect whether a value is associated with the parameter for this account or not.

For template and global parameters the `default_value` is not used for the parameter value but it can be taken from the parameter definition for a UI hint for an operator that is entering values for these parameters.

Optional instance parameters can be converted into non-optional parameters only if they have a value in the old smart contract version. If no value is present, then the account conversion will be rejected with a `a value is required for non-optional parameters` error message.

## Defining a Parameter Getter Functions

Each feature or product template that defines a parameter should also define a parameter getter function to define a consistent way of retrieving the parameter value. The getter function should always use the `get_parameter(...)` method from the `utils` feature. The getter function should look similar to below:

```python
def _get_parameter(*, vault: SmartContractVault, effective_datetime: Optional[datetime]=None) -> bool:
    return utils.get_parameter(
        vault=vault,
        at_datetime=effective_datetime,
        is_optional=True,
        default_value=False,
        is_boolean=True
    )
```

### Why

A parameter getter function simplifies retrieving parameter values by:

- Avoiding constantly having to inline type hint the parameter value, as the getter function will have a clear return type
- Avoiding repetition of optional arguments to the `get_parameter(...)` (e.g. `is_union`, `is_optional` etc)
