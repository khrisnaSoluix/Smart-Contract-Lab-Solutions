_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Unit Tests

Unless specified otherwise `PostingInstruction` (Contracts API 3.x) is interchangeable with `Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]` for fetched / hook argument data, or `CustomInstruction` for contract-generated data. `PostingInstructionBatch` (Contracts API 3.x) is interchangeable with `PostingInstructionsDirective` (Contracts API 4.x) for contract-generated data.  `PostingInstructionBatch` is replaced by `list[Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]]` in Contracts API 4.x for fetched / hook argument data, which won't have equivalents for class methods or attributes.

## Use of TestCase

We encourage the use of separate `TestCase` classes (or extensions thereof, such as `ContractTest`) to group a specific feature's unit tests.

### Why

This helps improve legibility, traceability of tests and features, and can promote reuse of code by highlighting opportunities for shared `setUp` or `setUpClass` functions. As these tests are run using `unittest` by default, there are no direct performance improvements. This is not a priority for unit tests, as they are inherently lightweight and quick to run and do not need better performance. However, the separate classes makes it easier to subsequently split the tests into separate files, which would easily enable more parallelism with `plz`, our build system of choice.

### How

For example, if a product named `CurrentAccount` has a `MinimumBalance` feature and an `InterestAccrual` feature, we can structure our unit test file like:

- `CurrentAccountTest(ContractTest)` - this is optional, but can be useful to share product-specific test utilities across the various features
- `MinimumBalanceTest(CurrentAccountTest)` - groups specific tests for the `MinimumBalance` feature
- `InterestAccrualTest(CurrentAccountTest)` - groups specific tests for the `InterestAccrual` feature

## Subtests

We do not use pseudo sub-tests (i.e. looping through a dictionary of test cases) in our unit test classes.

### Why

The pseudo sub-tests are an undesirable compromise that favours the initial test writer without considering impact to others:

1. They're difficult to maintain as you lose IDE refactor assistance (e.g. the dictionary keys won't be updated by an automated rename)
2. They make it hard to tell where coverage is coming from
3. They have worse visibility, as when one sub test fails it risks prevents some or all the others
4. The test execution itself drifts from the setup. Over time test writers start adding new cases without properly checking how the executor works and this leads to tests not doing what they are meant to

### How

We currently have issues with `unittest-xml-reporting` and `unittest`'s `subTest` feature. While we investigate this further, we recommend putting shared test setup into `setUp` or `setUpClass`, and defining additional helper methods to repeat any test execution. However, these should not impede legibility or the ability to understand what the test is asserting on.

## Vault Mocks

The test framework includes extensive mocks for unit tests, which are effectively indispensable.

### Why

Unit tests rely on mocks to isolate tests from external dependencies. The `vault` object is crucial in all contracts and mocking its methods and attributes accurately is therefore key to getting representative tests. However, it is not obvious how certain aspects should be mocked accurately without reverse engineering behaviour from simulator and/or end-to-end tests. This is compounded by the fact that the many `vault` methods and attribute behaviours are often derived from similar data (e.g. in Contracts API 3.x postings data will impact `vault.get_postings()` and `vault.get_client_transactions()`). Mocking these independently further adds to the risk that the mocks are not accurate and the tests do not actually provide good coverage.
To reduce this risk, we have developed mocks and associated helpers to get accurate tests and also reduce the burden on test writers/readers. We typically expose them via the `ContractTest` and `SupervisorContractTest` `TestCase` classes.

### How

The `create_mock()` methods on `ContractTest` and `SupervisorContractTest` (`inception_sdk/test_framework/unit/` for Contracts API 3.x, `inception_sdk/test_framework/unit/contracts_v4` for Contracts API 4.x) let test writers pass in data and create a mock `vault` object for use in tests. In some cases, the input data is fairly self-explanatory, but the next sections clarify some of the more complicated areas.
In Contracts API 3.x be careful to not mix up data relevant to the hook's data requirements (i.e. what is controlled by `@requires` and `fetch_account_data` decorators) and the inputs to the hook themselves. For example, the `postings` argument is a `PostingInstructionBatch` input available to `pre_posting_code` and `post_posting_code`. Conversely, the `vault.get_postings()` method can return additional historic postings, depending on the `@requires` specifics.

#### Parameters

Many tests revolve around different parameter values and how these affect contract execution outputs. As each contract can use different parameters, it makes sense to manage these at a contract level. To this end we recommend extending `ContractTest`'s `create_mock()` method to handle parameter inputs. `ContractTest` has a `locals_to_ignore` attribute that allows writers to easily filter out locals that won't be relevant and consider the rest as parameters.  For example:

```python
def create_mock(
    self,
    balance_ts=None,
    postings=None,
    creation_date=DEFAULT_DATE,
    client_transaction=None,
    flags=None,
    denomination=DEFAULT_DENOMINATION,
    param_1=DEFAULT_CUSTOMER_WALLET_LIMIT,
    param_2=DEFAULT_NOMINATED_ACCOUNT,
):
    [...]
    params = {
        key: {"value": value}
        for key, value in locals().items()
        if key not in self.locals_to_ignore
    }
    parameter_ts = self.param_map_to_timeseries(params, creation_date)
    [...]

    return super().create_mock(
        balance_ts=balance_ts,
        parameter_ts=parameter_ts,
        postings=postings,
        creation_date=creation_date,
        client_transaction=client_transaction,
        flags=flags,
    )
```

In Contracts API 4.x we typically use utility helpers to access parameters. As we mock these helpers/features, we have a much smaller need to directly set up this type of data. As a result, the `locals_to_ignore` attribute is not replicated.

#### Balances

Many tests revolve around different balance setups and how these affect contract execution outputs. As each contract can use different addresses, it makes sense to implement a single helper per contract that simplifies setting up the regularly used balances. To this end the Contracts API 3.x `ContractTest` class has an abstract `account_balances()` method that should be implemented once per contract. This can then be fed into `create_mock`'s `balance_ts` parameter.
This is less applicable to Contracts API 4.x due to the predominant use of `BalancesObservation` and the ease of creating `BalanceDefaultDict` objects. As a result the approach has not been replicated.

#### Postings and ClientTransactions

Many tests revolve around processing `PostingInstructionBatch` and `ClientTransaction` objects. Each `PostingInstructionBatch` object has attributes that depend on the list of `PostingInstruction` objects that it includes. There are many helpers to simplify the mocking posting inputs and requirement data:

1. Each instruction type has a corresponding method available on `ContractTest` which takes care of accurately determining mock behaviours for methods like `.balances()`. For example, `outbound_auth()` or `inbound_hard_settlement()`.
   1. These methods are always directional as only one side of the instruction should be affecting the customer account
   2. Each method exposes unique/mandatory attributes for that instruction type, but there are a number of generic attributes that can be passed in as kwargs, such as `client_id`, `client_transaction_id`, `value_timestamp`, `instruction_details` etc
   3. In some cases there are multiple methods for a given instruction (e.g. `settle_outbound_auth()` and `settle_inbound_auth()`). This is to simplify some of the mocking logic, but may be improved upon in the future. Because each instruction is considered separately, rather than as a part of a client transaction, each method has to know what preceded it. For example, `settle_outbound_auth()` needs to know the `unsettled_amount` prior to the settlement to accurately portray the resulting balance changes (e.g. the amount that the `Phase.PENDING_OUTGOING` balance is credited/debited depends on how much is still there)
   4. In general, exceptions due to Contracts API validation is a sign that the mocked object is invalid. However, in some conditions the `_from_proto` kwarg can be used to bypass Contracts API validation. For example, zero-amount postings can be committed by the Vault, but not created inside a contract, so mocking these correctly requires bypassing validation (see documentation/implementation/requirements_fetching_and_processing.md for more information about zero-amount postings)
2. There is a generic `mock_posting_instruction_batch()` method on `ContractTest` that can be initialised from a list of `PostingInstruction` and it will take care of accurately setting the `.balances()` method
3. If ClientTransaction mocks are also needed, use the `pib_and_cts_for_transactions()` and `pib_and_cts_for_instructions()` methods, which will provide a realistic `PostingInstructionBatch` and `ClientTransaction` dictionary that can be used:
    1. `pib_and_cts_for_transactions()` relies on very simple `Withdrawal` and `Deposit` objects (which map to outbound/inbound hard settlements, respectively). For example:

        ```python
        pib, client_transactions, client_transactions_excluding_proposed = self.pib_and_cts_for_transactions(
            hook_effective_date=datetime(2020, 1, 1),
            transactions=[
                contracts_unit.Withdrawal(amount=5, effective_date=datetime(2019, 1, 1)),
                contracts_unit.Withdrawal(amount=5, effective_date=datetime(2020, 1, 1)),
                contracts_unit.Deposit(amount=5, effective_date=datetime(2020, 1, 1)),
            ],
        )
        ```

    2. `pib_and_cts_for_instructions()` operates on the same principle, but lets users pass in lists of posting instructions if more flexibility around instruction types is needed than outbound/inbound hard settlements. For example:

        ```python
        pib, client_transactions, client_transactions_excluding_proposed = self.pib_and_cts_for_posting_instructions(
            hook_effective_date=datetime(2020, 1, 1),
            posting_instructions_groups=[
                [
                    self.outbound_auth(
                        amount=5,
                        value_timestamp=datetime(2019, 1, 1),
                        client_transaction_id="CT_ID_1",
                        client_id="CLIENT_ID_1",
                    ),
                    self.settle_outbound_auth(
                        unsettled_amount=5,
                        value_timestamp=datetime(2020, 1, 1),
                        client_transaction_id="CT_ID_1",
                        client_id="CLIENT_ID_1",
                    ),
                ],
            ]
        )
        ```

In Contracts API 4.x we typically use utility helpers and/or features to manipulate posting classes. As we mock these helpers/features, we have a much smaller need to directly set up this type of data. As a result, while the posting instruction helpers (`outbound_auth()` etc) have been replicated, the others have not.

#### Other Data

Please refer to the `ContractTest.create_mock` doc strings for information on Flags and Calendar Events

## Testing Templates and Features

Templates and features should be tested individually at a unit level, mocking any features they depend on.

### Why

We consider templates and features to be the equivalent to a class in traditional programming. As such, we wish to test their public methods at a unit level, mocking dependencies on other classes. This helps keep the tests focused on what they actually need to test.
It also enables us to generate meaningful coverage metrics for all templates and features, which in turn gives us better confidence that changes do not introduce unintended side effects.

### How

As templates and features are syntactically valid python, we no longer need the historic `run()` wrapper that is used to test traditionally developed contracts. This wrapper makes flexible mocking complicated. Instead, we can simply import functions from the relevant template/feature and test them as one would a regular python module.
Some of our tests do not reflect this practice yet (e.g. the line of credit), so for backwards-compatibility we have added the `disable_rendering: bool` attribute on the BaseContractTest. Setting this to `True` will prevent rendering from occurring in the unit test framework and enable the practice to be followed.
The example below illustrates an approach to this, and contract writers should feel free to re-use the approaches they are familiar with as there are no longer any restrictions.

```python
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest
)
from library.features.example_feature import example_function

class TestExampleFeature(ContractFeatureTest):
    target_test_file = (
        "library/features/example_feature.py
    )
    disable_rendering = True
    def test_example_feature(self):
        actual_output = example_function(
             arg_1="arg_1_value",
             arg_2="arg_2_value",
        )
        expected_output = "desired_output_value"
        self.assertEqual(actual_output, expected_output)

```

Note: If you are patching the `vault` object, make sure that the test argument is passed into `create_mock()` using the `existing_mock` kwarg (e.g. `self.create_mock(existing_mock=mock_vault)`). Otherwise a new `Mock` object is created and your patched `vault` will not be set up as expected.

Note: if you need to assert on a value from a dependency of the feature or template you are testing, do so via the feature or template. This helps simplify dependency management, ensures you are asserting against the right value, and can help with refactoring (e.g. immediate highlighting of errors if the feature is removed from the contract). For example:

```python
# DO
from library.my_product.contracts.template import my_product
...
self.assertEqual(result, my_product.my_feature.A_CONSTANT)

# DON'T
from library.my_product.contracts.template import my_product
from library.features import my_feature
...
self.assertEqual(result, my_feature.A_CONSTANT)
```

## Contracts API 4.x and Classes

Ensure you use the appropriate classes/sub-classes in tests.

### Why

Contracts API 4.x comes with a number of enhancements, including the `contracts_api` package. The importable classes expose contract writers to the same validation that contracts use in simulation and end-to-end and enables them to write more accurate unit tests. However, there are a few complications:

- `contracts_api` classes don't currently have useful equality methods, which makes assertion failures in tests harder to understand
- The extra validation can make unit testing approaches such as using sentinels more complicated (sentinels will cause richer validations to fail)

As a result, the Inception SDK provides some additional classes:

- `inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension` exposes the classes from `contracts_api` that are sub-classed to add a generic `__eq__` methods to provide more useful information when comparisons fail.
- `inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels` exposes a subset of replacements for classes from `contracts_api` that can be used instead of a regular `unittest.sentinel`. This allows us to preserve `contracts_api` validation and benefit from a sentinel-like approach

### How

Follow this guidance when deciding which to use in a test:

- if the object is being provided to a contract or feature method, whether as an argument or via a mock, and the object is not simply passed-through, always use the original `contract_api` class. This ensures no one accidentally introduces a dependency on methods that aren't available in the actual API and that will fail in simulation or end-to-end execution. This is reflected in the types we use on the v4 `create_mock` function.
- if the object in the above scenario is not passed-through, or is passed into the constructor for another `contract_api` class, use the `contracts_api_sentinels` equivalent. These try to use `unittest.sentinel`s on the individual attributes in a way that will not fail validation. Please note we are still in the processing of building these out.
- if the object is solely being used in a test assertion, use the `contracts_api_extension` equivalent. Python 3.x's approach to evaluating `a == b` means that if one of the objects (say `b`) is a subclass of the other (say `a`), `b.__eq__` is evaluated first. We therefore only need the expected result to use the `contracts_api_extension` sub classes.
