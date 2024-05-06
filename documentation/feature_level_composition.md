_© (Thought Machine Group Limited) (2022)_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Feature-Level Composition

## Background
Feature-level composition (FLC) refers to the ability to compose contracts from reusable, modular building blocks relating to specific business or technical features. These building blocks include parameters, helper functions, constants, and associated tests. This promotes re-use and standardisation across contracts whilst minimising overheads.

## Use Case
Clients who manage multiple smart contracts that share many but not all features can use FLC to maintain these smart contracts more easily. For example, consider a product suite with a Current Account, Savings Account, Loan and Mortgage. Without FLC there are a few approaches:
- Maintain four entirely separate contracts for the four products:
  - There may be re-use between these contracts, but this is achieved by copy-pasting code.
  - Adding a new feature to existing products can require multiple similar changes to be built and tested.
  - Adding a new product involves a new smart contract, which duplicates code further and increases overheads significantly, even if the new product is very similar.
  - Because the code re-use is not enforced, the additions of new features and products inevitably leads to a lack of standardisation, bugs in certain contracts but not others for the same features and other undesirable side-effects.
- Maintain a single contract per product group:
  - In this case we would likely have a single Current & Savings Account (CASA) contract to service the Current Accounts and Savings Accounts, and a single Loan contract to service the Loans and Mortgages.
  - Because features may vary slightly between Current and Savings Accounts, or between Loans and Mortgages, certain features are enabled, disabled or modified by parameters. Instead of re-using code across contracts, contracts are re-used across products, but each smart contract now has a certain amount of complexity that will never be used by one or more of the products it is used for. For example, the Current Account may need an arranged overdraft that the Savings Account does not need.
  - Adding a new feature to one product becomes harder as the smart contract is used for multiple products (i.e. consider adding a feature to the Savings Account without affecting the Current Account, when both use the CASA contract). As new features pile up, managing the parameters for the different variations becomes increasingly complicated and increases the risk of mistakes. These monolithic contracts can ironically become harder to maintain than multiple individual contracts.
  - Adding a new product may or may not involve a new smart contract. We can add new features to an existing contract (see previous point), or we add a new contract and slowly move to a hybrid between the two approaches. This usually results in an awkward mix of each approach's cons.

With FLC we can get benefits of both approaches with fewer cons:
  - Each separate contract can truly re-use code without copy-pasting, which mitigates the higher overheads of maintaining contracts and achieves similar levels of code re-use compared to re-using a single contract per product group. This also lowers the average complexity and unique code in each contract.
  - New variants of products can quickly be composed from existing features, leaving most of the effort focused solely on the features, which makes developer time more productive.
  - Because certain product groups use a different architecture it is likely that some features still need implementing once per product group (e.g. once for CASA and once for Loan/Mortgage). This is no different to either of the existing approaches though. Better yet, certain lower-level components of the features can be re-used and we will still see some improvements.

## Feature-Level Composition in the Inception Library
As of release 2022-16, the Inception Library has introduced one approach to achieving FLC, primarily within product groups. This is only applied to a subset of contracts, but will be rolled out to more contracts in future releases. The next sections provide some more details on our approach. It is important to note that we do not impose use of FLC on anyone, even if we have used it ourselves in the development process (more details on this below).

### Overview
Our approach consists of defining contract templates that can import features and utilities, wholly or partially, using native python `import`-style syntax. The `renderer` tool we have created then uses the native python `ast` library to render this template into a Vault-compliant smart contract that can then be used like any smart contract. At any point in time the developer has full visibility of the template, the standalone features and the fully rendered contract. Before rendering, developers can navigate through templates and features in any standard IDE, like regular python.

All existing features are made available under the `library/features` directory and are typically grouped by product or feature group (e.g. `library/features/deposits` or `library/features/shariah`).
A product that uses FLC will have a `library/<product>/contracts/template` directory (e.g. `library/murabahah/contracts/template`) and a fully rendered template at `library/<product>/contracts` (e.g. `library/murabahah/contacts/murabahah_rendered.py`)

We will use the `murabahah` example (slimmed down here for brevity) to illustrate what a template looks like:
  1. Import required features
```python
import library.features.common.utils as utils
import library.features.deposits.fees.early_closure_fee as early_closure_fee
...

# Transaction limits (pre-posting)
import library.features.transaction_limits.deposit_limits.minimum_initial_deposit as minimum_initial_deposit  # noqa: E501
import library.features.transaction_limits.deposit_limits.maximum_single_deposit as maximum_single_deposit  # noqa: E501
...

# Schedule features
import library.features.shariah.profit_accrual as profit_accrual
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

During rendering, the code for each feature is inserted into the template and the corresponding import statements are removed, producing a syntactically valid Vault contract. As an example, this approach has turned a ~1800 line contract for the `murabahah` product into a ~300 line template, most of which are simple function calls rather than potentially complex logic to test. The rendered template is ~ 2100 lines, owing to some methods being made slightly more generic to be reusable by other contracts, and some slightly greedy rendering (see Limitations below).

### When to Use
As described earlier, the primary use case for any form of FLC involves multiple products that share entire features or even sub-features (aka utilities). The benefits of FLC will not be noticeable if there is a single product, or a very simple smart contract that services two products, so we do not recommend blindly using FLC in all scenarios.
However we still encourage everyone to think about FLC when writing code as it encourages good practices, such as breaking down features cleanly into methods. Also, writing features so that they could be used as part of FLC, but still leaving them inside the contract itself, will make using FLC much simpler when additional products need to be created.

### How to Use/Bypass the Renderer
There are three scenarios to consider when taking and/or modifying Inception products:
  1. The product's smart contract has not yet been decomposed into features (i.e. there is no `contract/templates` or `supervisor/templates` directory inside the product's directory). In this case the contract can be modified as per standard practice.
  2. The product's smart contract has been decomposed into features (i.e. there is a `contract/templates` and/or `supervisor/templates` directory inside the product's directory) and there is a use case to continue using FLC. In this case the contract template and features can be modified. The product-level tests (unit, simulator and end-to-end) will automatically render the contract. The rendered contract can also be generated using
     1.  `python inception_sdk/tools/renderer/main.py -in <path_to_template> -out <desired_output_path>`
     2.  or with plz `plz render -in <path_to_template> -out <desired_output_path>`
  3. The product's smart contract has been decomposed as per point 2 above and there is no use case to continue using FLC. In this case, the rendered contract itself, which is always shipped with the release, can be modified directly. At the moment, a small change is required to the sim/end-to-end test files to point them towards the pre-rendered contract. Using the `murabahah` again as an example, in end-to-end tests:
  ```python
    endtoend.testhandle.CONTRACTS = {
       "murabahah": {
           "source_contract": murabahah,
           "template_params": murabahah_template_params,
       }
    }
  ```
  becomes
  ```python
    endtoend.testhandle.CONTRACTS = {
       "murabahah": {
           "path": "library/murabahah/contracts/murabahah_rendered.py",
           "template_params": murabahah_template_params,
       }
    }
  ```
  In sim tests:
  ```python
    class MurabahahTest(RenderedContractSimulationTestCase):

       account_id_base = MURABAHAH_ACCOUNT
       source_contract = murabahah
  ```
  becomes
  ```python
    class MurabahahTest(SimulationTestCase):

       account_id_base = MURABAHAH_ACCOUNT
       contract_file_paths = ["library/murabahah/contracts/murabahah_rendered.py"]
  ```

### Testing Considerations
With FLC it makes most sense to focus unit tests on the features themselves, which we have done for the existing features in `library/features`. Product tests should continue to be at least maintained at a simulation and end-to-end level. It may still make sense to have product unit tests, as long as these don't completely duplicate the feature unit tests, and we are looking at automating some of this process (see below).


### Versioning
Due to the nature of having code split across multiple files its important to consider versioning. A single product could be made up of a template and any number of feature files each of which can independently change over time, making it difficult to keep track of exactly which versions of each feature were used for the rendered output you are working with. The key scenario where a robust versioning system is required is when investigating an issue with a rendered contract, where you only have the rendered output. In order to accurately determine the root cause of an issue you may need to review the original source code of each file that comprises the rendered contract.

To achieve this we have added a header to each imported file in the rendered output that contains both the checksum of the source code and the Git commit hash. Below is an example:
```python
# Objects below have been imported from:
#    library/features/common/utils.py
# md5:ff65c769b032333be8c0fb9fdb1be83b git:0697b8f2e1f3a8149fd836ae11cb721e1190dc2d
```
Using the hash information in the header we can retrieve the source using the tool at `inception_sdk/tools/git_source_finder`. See the `README.md` file in this directory for further information


### Limitations and Future Enhancements
We will be enhancing the `renderer` tool in subsequent releases to simplify the development experience and process further and address limitations. Of particular note we are investigating:
1. Minimise template boiler plate further (e.g.auto import common objects, parameters in templates)
2. Render product unit tests
3. Improve test experience by removing need for specific test classes when using rendered templates vs regular contracts
4. Extending scope to data requirements/fetchers
