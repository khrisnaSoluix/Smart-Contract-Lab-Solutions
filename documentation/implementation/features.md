_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers guidance specific to the way we implement features.

# Features

## Feature Structure

At a high level we want to structure our features in the following way:

- imports
- constants
- contract metadata fields
  - event_types
  - fetchers
  - parameters
- functions
- interface implementations

The following sections provide specific guidance for the individual sections, if applicable.

### Feature Constants

Features should aim to re-use common definitions. Feature-specific constants can also be added, taking care to avoid conflicts.

#### Why

It is crucial to keep this structure to avoid deviating duplicate definitions, or namespacing conflicts. As the renderer currently allows these conflicts, which are technically valid Python, they can cause tricky bugs that are hard to debug:

- Consider `feature.py` and `features/v4/common/addresses.py` that both define a list constant named `ACCRUAL_ADDRESSES` with different list items. Balance sums over these lists can differ and cause subtle changes to calculations.
- Upon rendering, the final contract will have two definition of `addresses_ACCRUAL_ADDRESSES`. Depending on the ordering of these definitions, the expected or definition may or may not be used.
- Although we plan to make the renderer stricter with these namespacing errors, redefining addresses unnecessarily at best adds unnecessary extra code, and at worst causes confusion.

#### How

Using overpayment and address constants as an example, we adopt the following import structure in the feature:

```plaintext
<feature>
    |__ own constants <- specific to the feature and defined in the feature module
    |__ features/v4/common/common_addresses.py <- potentially applicable to all features and should not be redefined by any feature
    |__ features/v4/product_group/<product_group>_addresses.py <- potentially applicable to all features within a product group (e.g. lending) and should not be redefined by any feature in that group
```

Within features, the python namespacing makes it clear where the constants come from (`feature.ADDRESS_X` vs `common_addresses.ADDRESS_Y`).

Within rendered contracts, the renderer namespacing preserves this clarity (`feature_ADDRESS_X` vs `common_addresses_ADDRESS_Y`).

Within tests, the addresses are all still easily accessible via the template's module (e.g. `feature.ADDRESS_X` or `feature.common_addresses.ADDRESS_Y`).

Be careful of product group vs feature addresses. Product group addresses are imposed by the product group architecture and avoid tight coupling between multiple features of the architecture. This does not mean any address used in multiple features is suitable, especially if the coupling between features is expected or if the address is  an interface implementation. For example:

- The lending architecture assumes the use of `PRINCIPAL -> PRINCIPAL_DUE -> PRINCIPAL_OVERDUE` addresses. These are referred to in multiple modules whose behaviours are independent. `due_amount_calculation` transfers amounts from `PRINCIPAL` to `PRINCIPAL_DUE`, `overdue` transfers amounts from `PRINCIPAL_DUE` to `PRINCIPAL_OVERDUE`, `delinquency` reads from `PRINCIPAL_OVERDUE`. These addresses are therefore defined once in `lending_addresses.py` to avoid coupling between the features.

- The `overpayment` feature implements a `lending` interface and should define its addresses in its own module.

- The `overpayment_allowance` feature inherently depends on `overpayment`'s implementation, not the interface. It should therefore import directly from the `overpayment` feature if required.

#### Naming Conventions

Mainly for consistency purposes, we adopt the following naming conventions for grouping certain types of constants in features.

| Constant Type | Convention | Example |
| - | - | - |
| Event Name | `<event name>_EVENT` | ACCRUAL_EVENT |
| Parameter Name | `PARAM_<parameter name>` | ACCRUAL_EVENT |
| List of Balance Address Names | `<address type>_ADDRESSES` | DUE_ADDRESSES |
| Balance Fetcher ID | `<fetcher name>_FETCHER_ID` | ACCRUED_INTEREST_EFF_FETCHER_ID |
| Prefix Names | `<prefix name>_PREFIX` | FEES_APPLICATION_PREFIX |
| List of Parameter Objects | `<param type prefix>_parameters` | account_parameters |

### Feature Parameters

Features should expose their parameters in sensible groupings to promote re-use.

#### Why

Certain product variants require a subset of a feature and therefore only want to import the specific parameters they need. In contrast, some products will use the entire feature and therefore want an easy way to import all parameters. It is also acceptable to import a specific parameter. If there are a large number of feature subsets, it may be a sign that the feature needs breaking down into individual features.

#### How

Sensible groupings include schedule time parameters or relevant internal accounts, but there is no set list.
We structure parameters as follows:

```python
subset_1_parameters = [
    Parameter(...),
    Parameter(...)
]
subset_2_parameters = [
    Parameter(...),
    Parameter(...)
]
all_parameters = [
    *subset_1_parameters,
    *subset_2_parameters
]
```

These can then be imported flexibly inside templates:

```python
import feature_1
parameters = [
    Parameter(...),
    Parameter(...),
    *feature_1.subset_1_parameters,
]
```

or

```python
import feature_1
parameters = [
    Parameter(...),
    Parameter(...),
    *feature_1.all_parameters,
]
```

### Feature Interface Implementations

Interface implementations should have a useful name so that they can be easily imported and to help distinguish between the multiple interfaces that a feature may implement.

#### How

For example:

```python
    # end of feature file
    interface1 = Interface1NamedTuple(method_1=feature_method_1, method_2=feature_method_2)
    interface2 = Interface2NamedTuple(method_1=feature_method_1, method_3=feature_method_3)
```

See the section below for how we structure interfaces themselves

## Promoting Reuse

We use several approaches and patterns to promote reuse across our library. This starts off at the product level (can I re-use an existing product?) and extends to the feature level (can I re-use an existing feature?) and all the way to specific utilities/helpers (can I re-use an existing method?).
The next sections describe these approaches and patterns.

### Decoupling Features - Extracting Constant Dependencies

A very simple approach to break dependencies between two features is to extract the dependency to a common location.

#### Why

Two features can rely on a same constant, such as a balance address. For example, interest accrual and interest application will both rely on a common address for the accrued interest, to accrue further interest or to apply the accrued interest. Defining this address in interest accrual and making interest application dependent on interest accrual introduces unnecessary coupling between these two features.

An easy way to reason about this is whether the constant in question  could be parameterised (in the python sense, but not necessarily in the contract sense). In the interest accrual example, it is perfectly reasonable to be able to accrue to different addresses (e.g. for different types of interest). Even if there is no requirement to do so initially, recognising this is a good sign that a hardcoded dependency between the relevant features should be avoided.

#### How

We prefer to extract the constant to a common file and make relevant features depend on this instead. Using interest accrual and interest application as an example (many aspects below are simplified for brevity), we would do:

```python
# addresses.py
ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
```

```python
# interest_accrual.py
from addresses import ACCRUED_INTEREST_RECEIVABLE
def accrue_interest(address_to_accrue_to: str = ACCRUED_INTEREST_RECEIVABLE):
    ...
```

```python
# interest_application.py
from addresses import ACCRUED_INTEREST_RECEIVABLE
def apply_interest(address_accrued_at: str = ACCRUED_INTEREST_RECEIVABLE):
    ...
```

```python
# contract_template.py
from addresses import ACCRUED_INTEREST_RECEIVABLE
from interest_accrual import accrue_interest
from interest_application import apply_interest

def my_helper():
    # An arbitrary helper that also needs to know about the address
    A
```

Within the template itself we also import the address from our constants file (`addresses.py` here). This doesn't prevent any further dependencies as the template inherently depends on the accrual and application features, but it helps avoid namespacing problems.

__Warning__: remember to prefix file/module names as required to avoid namespace clashes on rendering (e.g. if you have `folder_1/addresses.py` and `folder_2/addresses.py`, these should be called `folder_1/folder_1_addresses.py` and `folder_2/folder_2_addresses.py`)

### Decoupling Features - Dependency Injection via NamedTuples

We rely on a NamedTuple approach to declare and implement interfaces, which allows us to decouple features.

#### Why

We want decouple features to make them easy to add and remove. If a feature has a hardcoded dependency on another feature, it is impossible to remove one without the other and also avoid code changes to features. This tight coupling defeats a major objective of Product Composition.

#### How

We define a series of `NamedTuple` objects within interface files (e.g. `library/v4/features/lending_interfaces.py`), which will define the methods that a given interface should implement. These interfaces only hold methods/functions today.
Each feature can then implement these interfaces by instantiating the relevant NamedTuple(s) with the appropriate feature functions. Any features' functions can accept one or more instances of a specific interface's `NamedTuple` as arguments.
Not all uses of the feature need to go through the `NamedTuple` though. For example, as it is inevitable that a template is coupled to the features it uses, it is ok for the template to refer directly to the feature method.

This is illustrated below:

```python
    # interface file
    MyInterface = NamedTuple(
        "MyInterface",
        [
            # These should be made as accurate as possible
            ("method1", Callable[..., Any]),
            ("method2", Callable[..., Any]),
        ]
    )
```

```python
    # within feature1
    from interfaces import MyInterface
    attribute = "value"

    def method1(vault: Vault) -> Decimal:
        ...

    def method2(vault: Vault) -> list[PostingInstruction]:
        ...

    def method3(some: str, other: int, args: list[str]) -> Decimal:
        ...

    feature1_myinterface = MyInterface(
        method1=method1,
        method2=method2,
    )
```

```python
    # within feature2
    from interfaces import MyInterface
    def method_3(vault: Vault, some_other_feature: MyInterface) -> Decimal:
        return some_other_feature.method1(vault)
```

```python
    # within contract template
    import feature1 as feature1
    import feature2 as feature2

    feature2.method_3(vault, feature1.my_interface)
```

Unfortunately there is no `Callable` syntax to indicate optional or keyword arguments. We can either have an inaccurate interface here and gets warnings in code, or use an non-specific interface (`...`) and not get warnings in code. We opt for the latter and add comments to the interface declaration for more information

### Consistent Method Signatures

We follow certain patterns when writing feature methods, which help promote re-use at a slightly lower level.

#### Why

As previously explained, our approach to re-use starts at the entire contract level, going down to the individual method/metadata level.
It is very easy to accidentally implement a feature such that any slight deviations are impossible to cater for, which results in an entire new feature being developed. For example, one might embed a hardcoded reference to a parameter or fetcher in core logic which makes it impossible to then remove the parameter for a product that only requires a fixed behaviour for a feature.

We can avoid such pitfalls by adopting a consistent structure to their signatures. This makes it possible to directly use a feature at a contract template level, or to achieve partial feature re-use by only modifying the way inputs are constructed, the way they are transformed, the way outputs are returned, or any combination of the above. This approach also helps us promote re-use between supervisor and non-supervisor uses, as we often need to extract data from slightly different sources.

#### How

We reason about our features in three stages, which dictate their typical signature:

1. Data extraction - getting the data required for the feature's core logic. Methods:
   1. Typically take `Vault` object, `<RelevantHook>Arguments`, and any interface implementations to inject
   2. Return fetched data from the `Vault` object in Contract API types (e.g. balances) or as native Python types (parameters), and useful attributes on the `HookArguments`
2. Core logic - applying whatever logic is required and returning the raw outputs (e.g. non-Contract API types). Methods:
   1. Typically take the outputs from data extraction. They should not take `Vault` objects
   2. Return native Python types (e.g. `Decimal`)
3. Output transformation - taking raw outputs and turning them into the directive types, or inputs to the directive types, required to commit the results of the logic. Methods:
   1. Typically take the outputs from Core logic (e.g. native Python types)
   2. Return directive-related Contract API types (e.g. `Posting`, `CustomInstruction`, `AccountNotificationDirective`, or containers thereof)
      1. The specific type to use can vary, but bear in mind that there is a performance gain to combining `Posting`s in a `CustomInstruction`, assuming there is no functional need for a dedicated instruction (e.g. specific instruction-details)
      2. We prefer returning `list[<Type>]` rather than `Optional[<Type>]` if there may not be an instance of `<Type>` to return, as this simplifies the caller manipulation (i.e. can simply do `type_list += function_returning_list_of_type`)
4. Top-Level Wrapper - a simple wrapper for default behaviour that applies all 3 steps that:
   1. Takes `Vault` object, `<RelevantHook>Arguments`, and any interface implementations to inject (e.g. like Data extraction)
      - In some cases we want to re-use data that is common to many features, primarily for performance purposes (e.g. the denomination parameter, or balances). It is acceptable to add these arguments as `Optional<type>=None`, provided that the wrapper extracts them from the `Vault` object if they are not provided.
      - The intent is to maintain features that will work without preceding template-level code, while also optimising for performance where relevant. We don't expect it to apply to many cases, and it may be a sign of a design issue if it occurs a lot.
   2. Returns directive-related Contract API types (e.g. like Output transformation)
   3. Special care must be taken when propagating the `Vault` object, which should only be passed to a data extraction helper, or to other interface implementations

We do not mandate that every feature systematically breaks their helpers down into all of these discrete steps when there may not be an immediate need to do so, but they should never prevent easy extraction into these steps if need be. For example, it is common to see the top-level wrapper directly contain the data extraction logic. It is also common for one feature to use another's wrapper that may combine Core logic and Output transformation.
If a given helper takes both a `Vault` object and data extraction outputs it is a good sign that the guidelines have not been met and the helper should be restructured.

As an example, consider the following interest accrual feature (this closely matches actual implementation, but with some tweaks to illustrate the points above more clearly).
If a new interest accrual feature is required to handle a different calculation (e.g. tiered interest), we now have two options:

1. Define an interface for the core logic and add this to the top-level wrapper. This may be harder than it sounds if the interface is not clear enough
2. Create a new wrapper that re-uses the extraction and transformation steps and has its own custom core logic

If the accrual feature is now needed for a supervisor implementation where some of the parameters come from different `Vault` objects, we can implement custom data extraction to handle this, but still re-use all the Core logic and Output transformation.

```python
def daily_accrual_schedule_logic(
    vault,
    hook_arguments: ScheduledEventHookArguments,
    account_type: str = "",
    principal_addresses: Optional[list[str]] = None,
) -> list[CustomInstruction]:
    [...]

    #####
    ##### Data extraction, explicitly in top-level wrapper
    #####
    midnight = hook_arguments.effective_datetime - relativedelta(hour=0, minute=0, second=0)
    denomination = utils.get_parameter(vault=vault, name="denomination")
    principal_addresses = principal_addresses or [addresses.PRINCIPAL]
    eod_balances: BalancesObservation = vault.get_balances_observation(
        fetcher_id=fetchers.EOD_FETCHER_ID
    )
    effective_balance = Decimal(
        sum(
            eod_balances.balances[
                BalanceCoordinate(
                    principal_address, DEFAULT_ASSET, denomination, phase=Phase.COMMITTED
                )
            ].net
            for principal_address in principal_addresses
        )
    )

    #####
    ##### Execute core logic
    #####
    accrual_detail = calculate_daily_accrual(
        effective_balance=effective_balance,
        effective_datetime=effective_datetime,
        yearly_rate=yearly_rate,
        days_in_year=days_in_year,
        rounding=rounding,
        precision=precision,
    )
    if accrual_detail is None:
        return []

    #####
    ##### Output transformation
    #####
    return accruals.accrual_custom_instruction(
        customer_account=customer_account,
        customer_address=customer_address,
        denomination=denomination,
        amount=accrual_detail.amount,
        internal_account=internal_account,
        payable=payable,
        instruction_details=utils.standard_instruction_details(
            description=accrual_detail.description,
            event_type=event_type,
            gl_impacted=True,
            account_type=account_type,
        ),
    )
```

### Returning Posting Instructions

As a general rule of thumb, feature functions should return one or more `CustomInstruction` objects. The feature writer is generally best placed to determine whether one or multiple `CustomInstruction` objects are required.

#### Why

A feature may not have knowledge or control over posting-generation, for example when interfaces for other features are used. In this case they should rely on the interfacing function to match the return type described above.

There can be several reasons why multiple `CustomInstruction` objects are required:

1. Different postings may require different metadata and so should be segregated into separate CustomInstructions
2. There are non-functional limits, a `CustomInstruction` can contain up to 64 Posting objects, and a `PostingInstructionsDirective` object can contain up to 64 `CustomInstruction` objects

Since there are currently no performance metrics detailing the performance benefits / detriment of multiple `CustomInstruction` objects vs a single `CustomInstruction` object containing a large number of Posting objects within a single `CustomInstruction` (e.g. is 2 CI with 32 postings each better than 4 CI with 16 postings each more or less performant), there are no known drawbacks to this approach. However, if the feature writer deems it necessary to modify the existing CustomInstruction object then the practice detailed in `documentation/implementation/directives.md` should be followed.

#### How

The feature function should always return the posting instructions in a list to allow for consistent and easy integration with consumers. This way consumers can easily combine the output of multiple feature function calls. A very simple example is shown below:

```python
def some_function_that_returns_posting_instructions() -> list[CustomInstruction]:
    if <some condition>:
        return [CustomInstruction(...)]

    return []

# The consumer can easily extend their existing list with what the function returns
posting_instructions = [CustomInstruction(...)]
posting_instructions.extend(some_function_that_returns_posting_instructions())
```
