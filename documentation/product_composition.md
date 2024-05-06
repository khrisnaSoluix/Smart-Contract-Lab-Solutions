_© (Thought Machine Group Limited) (2022)_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Product Composition

## Background

Product Composition refers to the ability to compose contracts from reusable, modular building blocks relating to specific business or technical features. These building blocks include parameters, helper functions, constants, and associated tests. This promotes re-use and standardisation across contracts whilst minimising overheads.

## Use Case

Clients who manage multiple smart contracts that share many but not all business features can use Product Composition to maintain these smart contracts more easily. For example, consider a product suite with a Current Account, Savings Account, Loan and Mortgage. Without Product Composition there are a few approaches:

- Maintain four entirely separate contracts for the four products:
  - There may be re-use between these contracts, but this is achieved by copy-pasting code.
  - Adding a new business feature to existing products can require multiple similar changes to be built and tested.
  - Adding a new product involves a new smart contract, which duplicates code further and increases overheads significantly, even if the new product is very similar.
  - Because the code re-use is not enforced, the additions of new features and products inevitably leads to a lack of standardisation, bugs in certain contracts but not others for the same features and other undesirable side-effects.
- Maintain a single contract per product group:
  - In this case we would likely have a single Current & Savings Account (CASA) contract to service the Current Accounts and Savings Accounts, and a single Loan contract to service the Loans and Mortgages.
  - Because business features may vary slightly between Current and Savings Accounts, or between Loans and Mortgages, certain features are enabled, disabled or modified by parameters. Instead of re-using code across contracts, contracts are re-used across products, but each smart contract now has a certain amount of complexity that will never be used by one or more of the products it is used for. For example, the Current Account may need an arranged overdraft that the Savings Account does not need.
  - Adding a new business feature to one product becomes harder as the smart contract is used for multiple products (i.e. consider adding a feature to the Savings Account without affecting the Current Account, when both use the CASA contract). As new business features pile up, managing the parameters for the different variations becomes increasingly complicated and increases the risk of mistakes. These contracts can ironically become harder to maintain than multiple individual contracts.
  - Adding a new product may or may not involve a new smart contract. We can add new features to an existing contract (see previous point), or we add a new contract and slowly move to a hybrid between the two approaches. This usually results in an awkward mix of each approach's cons.

With Product Composition we can get benefits of both approaches with fewer cons:

- Each separate contract can truly re-use code without copy-pasting, which mitigates the higher overheads of maintaining contracts and achieves similar levels of code re-use compared to re-using a single contract per product group. This also lowers the average complexity and unique code in each contract.
- New variants of products can quickly be composed from existing blocks, leaving most of the effort focused solely on the new blocks, which makes developer time more productive.

## Product Composition in the Product Library

As of release 2022-16, the Product Library has introduced an implementation of Product Composition, aiming to achieve re-use business features within product groups. We call this Product Group Feature Level Composition, and we refer to the blocks as features. This is progressively being applied across all products. The next sections provide some more details on our approach. It is important to note that we do not impose use of Product Composition as a concept, or its implementation as Product Group Feature Level Composition, even if we have used it ourselves in the development process.

### Overview

Our approach consists of defining contract templates that can import features wholly or partially, using native python `import`-style syntax. The `renderer` tool we have created then uses the native python `ast` library to render this template into a Vault-compliant smart contract that can then be used like any smart contract. At any point in time the developer has full visibility of the template, the standalone features and the fully rendered contract. Before rendering, developers can navigate through templates and features in any standard IDE, like regular python.

All existing features are made available under the `library/features` directory and are typically grouped by product or feature group (e.g. `library/features/v3/deposits` or `library/features/v3/shariah`). The examples below are based on Contracts API 3.x, but the concept is identical for Contracts API 4.x and there are many further examples in the library.
A product that uses Product Group Feature Level Composition will have a `library/<product>/contracts/template` directory (e.g. `library/shariah_savings_account/contracts/template`) and a fully rendered template at `library/<product>/contracts` (e.g. `library/shariah_savings_account/contacts/shariah_savings_account_rendered.py`)

We will use the `shariah_savings_account` example (slimmed down here for brevity) to illustrate what a template looks like:

1. Import required features

    ```python
    import library.features.v3.common.utils as utils
    import library.features.v3.deposits.fees.early_closure_fee as early_closure_fee
    ...

    # Transaction limits (pre-posting)
    import library.features.transaction_limits.deposit_limits.minimum_initial_deposit as minimum_initial_deposit  # noqa: E501
    import library.features.transaction_limits.deposit_limits.maximum_single_deposit as maximum_single_deposit  # noqa: E501
    ...

    # Schedule features
    import library.features.v3.shariah.profit_accrual as profit_accrual
    ```

2. Define common parameters and add the feature parameters

    ```python
    # Common parameters
    parameters = [
        ...
        Parameter(
            name="denomination",
            level=Level.TEMPLATE,
            description="Currency in which the product operates.",
            display_name="Denomination",
            shape=DenominationShape,
            default_value="MYR",
        ),
        ...
    ]
    # Add feature parameters
    parameters.extend(
        early_closure_fee.parameters
        + minimum_initial_deposit.parameters
        + maximum_single_deposit.parameters
        + minimum_single_deposit.parameters
        ...
    )
    ```

3. Use the features in hooks

    ```python
    @requires(event_type="ACCRUE_PROFIT", flags=True, parameters=True, balances="1 day")

    def scheduled_code(event_type, effective_date):
        posting_instructions = []
        denomination = utils.get_parameter(vault, "denomination")

        if event_type == "ACCRUE_PROFIT":
            posting_instructions.extend(
                profit_accrual.get_accrual_posting_instructions(vault, effective_date, denomination)
            )
    ...

    @requires(parameters=True, balances="latest live", postings="1 day")
    def pre_posting_code(postings, effective_date):
        ...
        utils.validate_denomination(vault, postings)
        ...
        denomination = utils.get_parameter(vault, "denomination")
        balances = vault.get_balance_timeseries().latest()
        ...
        minimum_initial_deposit.validate(
            vault=vault, postings=postings, balances=balances, denomination=denomination
        )

        minimum_single_deposit.validate(vault=vault, postings=postings, denomination=denomination)
    ```

During rendering, the code for each feature is inserted into the template and the corresponding import statements are removed, producing a syntactically valid Vault contract. As an example, this approach has turned a ~1800 line contract for the Contracts API 3.x `shariah_savings_account` product into a ~300 line template, most of which are simple function calls rather than potentially complex logic to test. The rendered template is ~2100 lines, owing to some methods being made slightly more generic to be reusable by other contracts, and some slightly greedy rendering (see Limitations below).

### Using constants in decorators

When using features, we often import constants such as event names, but the Contracts Language only permits hard-coded string in the @requires and @fetch_account_data decorators. For Product Group Feature Level Composition contracts, you can now provide the constants/variables in the decorators.

### When to Use

As described earlier, the primary use case for any form of Product Composition involves multiple products that share entire features or even sub-features (aka utilities). The benefits of Product Composition will not be noticeable if there is a single product, or a very simple smart contract that services two products, so we do not recommend blindly using Product Composition in all scenarios.
However we still encourage everyone to think about Product Composition when writing code as it encourages good practices, such as breaking down features cleanly into methods. Also, writing features so that they could be used as part of Composition, but still leaving them inside the contract itself, will make using Product Composition much simpler when additional products need to be created.

### How to Use/Bypass the Renderer

There are three scenarios to consider when taking and/or modifying Inception products:

1. The product's smart contract has not yet been decomposed into features (i.e. there is no `contract/templates` or `supervisor/templates` directory inside the product's directory). In this case the contract can be modified as per standard practice.
2. The product's smart contract has been decomposed into features (i.e. there is a `contract/templates` and/or `supervisor/templates` directory inside the product's directory) and there is a use case to continue using Product Group Feature Level Composition. In this case the contract template and features can be modified. The product-level tests (unit, simulator and end-to-end) will automatically render the contract. The rendered contract can also be generated using
    1. `python inception_sdk/tools/renderer/main.py -in <path_to_template> -out <desired_output_path>`
    2. or with plz `plz render -in <path_to_template> -out <desired_output_path>`
3. The product's smart contract has been decomposed as per point 2 above and there is no use case to continue using Product Group Feature Level Composition. In this case, the rendered contract itself, which is always shipped with the release, can be modified directly. At the moment, a small change is required to the sim/end-to-end test files to point them towards the pre-rendered contract. Using the `shariah_savings_account` again as an example, in end-to-end tests:

    ```python
      endtoend.testhandle.CONTRACTS = {
        "shariah_savings_account": {
            "source_contract": shariah_savings_account,
            "template_params": shariah_savings_account_template_params,
        }
      }
    ```

    becomes

    ```python
      endtoend.testhandle.CONTRACTS = {
        "shariah_savings_account": {
            "path": "library/shariah_savings_account/contracts/shariah_savings_account_rendered.py",
            "template_params": shariah_savings_account_template_params,
        }
      }
    ```

    In sim tests:

    ```python
      class ShariahSavingsAccountTest(RenderedContractSimulationTestCase):

        account_id_base = SHARIAH_SAVINGS_ACCOUNT
        source_contract = shariah_savings_account
    ```

    becomes

    ```python
      class ShariahSavingsAccountTest(SimulationTestCase):

        account_id_base = SHARIAH_SAVINGS_ACCOUNT
        contract_file_paths = ["library/shariah_savings_account/contracts/shariah_savings_account_rendered.py"]
    ```

### Testing Considerations

With Product Group Feature Level Composition it makes most sense to focus unit tests on the features themselves, which we have done for the existing features in `library/features`. Product tests should continue to be at least maintained at a simulation and end-to-end level. It may still make sense to have product unit tests, as long as these don't completely duplicate the feature unit tests, and we are looking at automating some of this process (see below).

### Versioning

Due to the nature of having code split across multiple files its important to consider versioning. A single product could be made up of a template and any number of feature files each of which can independently change over time, making it difficult to keep track of exactly which versions of each feature were used for the rendered output you are working with. The key scenario where a robust versioning system is required is when investigating an issue with a rendered contract, where you only have the rendered output. In order to accurately determine the root cause of an issue you may need to review the original source code of each file that comprises the rendered contract.

To achieve this we have added a header to each imported file in the rendered output that contains both the checksum of the source code and the Git commit hash. Below is an example:

```python
# Objects below have been imported from:
#    library/features/v3/common/utils.py
# md5:ff65c769b032333be8c0fb9fdb1be83b git:0697b8f2e1f3a8149fd836ae11cb721e1190dc2d
```

Using the hash information in the header we can retrieve the source using the tool at `inception_sdk/tools/git_source_finder`. See the `README.md` file in this directory for further information
