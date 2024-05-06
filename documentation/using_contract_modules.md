_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

## Background

Contract Modules are a system of shared code which give Contract writers the ability to create and manage helper functions that exist outside of an individual Smart Contract so that they can be shared across developers and products. Currently, they are only supported by Smart Contracts but not Supervisor Contracts. An individual Contract Module can contain multiple functions and the same Contract Module can be linked to one or more Contracts. Similarly, a single Contract may have links to multiple Contract Modules. Each Contract linked to a Contract Module will have access to all the functions contained within it.

We do not have specific guidance for Contract Modules and Contracts API 4.x as we are building products using the `renderer` tool to achieve Product Composition, instead of Contract Modules.

### Advantages

* Logic can be tested and upgraded in isolation
* Reduces the risks of duplication and copying code between multiple financial products
* Reduces the maintenance cost as the overall number of lines of code between Contracts and tests can be reduced
* Encourages consistency and standardisation across products

## Further Supporting Documentation

Users are advised to consult the following sources for further information and more detailed explanations and examples. These resources are either supplied as part of the Inception Release Package or hosted on the Vault Documentation Hub:

1. `Configuration Layer Utility User Guide.pdf`
2. `https://docs.thoughtmachine.net/vault-core/latest/EN/reference/contracts/common_examples/#contract_modules_example`
3. `https://docs.thoughtmachine.net/vault-core/latest/EN/reference/contracts/contract_modules_overview/`

### Note

* The minimum Contracts API version is `3.9.0` which must be specified in both the Contract and Contract Module metadata.
* For performance reasons, Contract Modules must be specified on a per-hook basis by providing the module name as an argument to the existing `@requires` decorator in the Contract.
The syntax for this is:

    `@requires(modules=['alias_1', 'alias_2'])`

* Modules cannot import other modules.
* Other Contract elements, such as parameters, cannot be shared.
* Any constants declared in a Contract Module will be usable within the module functions themselves, but are not available on the Vault object.

## Design and Implementation Rules

1. Do not incorporate product-based logic inside modules

    ```python
    # DO
    def my_shared_function(vault, balances: BalanceTimeseries, some_parameter_value: str):
        if some_parameter_value == 'xyz' and balances.latest()[.....] == '0':
            …
        else:

    # DON'T
    def accrue_interest(vault, my_product: str):
        if my_product == 'credit_card':
            …
        elif my_product == 'current_account':
            …
        else
            …
    ```

2. Use explicit arguments for any data required by the function

    ```python
    # DO
    def my_shared_function(vault, balances: BalanceTimeseries, some_parameter_value: str):
        if some_parameter_value == 'xyz' and balances.latest()[.....] == '0':
            return vault.make_internal_transfer_instructions()....

    # DON'T
    def my_shared_function(vault):
        balances = vault.get_balance_timeseries()
        some_parameter_value = vault.get_parameter_timeseries('my_param').latest()
        if some_parameter_value == 'xyz' and balances.latest()[.....] == '0':
            return vault.make_internal_transfer_instructions()....
    ```

3. Do not hard-code inside shared functions

    ```python
    # DO
    def _create_accrual_postings(
        vault,
        accrual_dimensions: Tuple[str, str, str, Phase],
        accrual_amount: Decimal,
        internal_accounts: Dict[str, str],
        reverse: bool = False
    ) -> List[PostingInstruction]:

        accrual_postings = []
        address = accrual_dimensions[0].upper()
        asset = accrual_dimensions[1]
        denomination = accrual_dimensions[2]

        ....

        # Customer postings
        accrual_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=accrual_amount,
                denomination=denomination,
                client_transaction_id=f'{cti_prefix}_CUSTOMER_{cti_suffix}',
                from_account_id=vault.account_id,
                from_account_address=address,
                to_account_id=vault.account_id,
                to_account_address='INTERNAL_CONTRA',
                asset=asset,
                instruction_details={},
                override_all_restrictions=True
            )
        )

    # DON'T
    def _create_accrual_postings(
        vault,
        Denomination: str,
        accrual_amount: Decimal,
        internal_accounts: Dict[str, str],
        reverse: bool = False
    ) -> List[PostingInstruction]:

        accrual_postings = []

        ....

        # Customer postings using hardcoded values
        accrual_postings.extend(
            vault.make_internal_transfer_instructions(
                amount=accrual_amount,
                denomination=denomination,
                client_transaction_id=f'{cti_prefix}_CUSTOMER_{cti_suffix}',
                from_account_id=vault.account_id,
                from_account_address='ACCRUED_INTEREST',
                to_account_id=vault.account_id,
                to_account_address='INTERNAL_CONTRA',
                asset='COMMERCIAL_BANK_MONEY',
                instruction_details={},
                override_all_restrictions=True
            )
        )
    ```

4. Do not instruct posting instruction batches within shared functions
5. Always explicitly specify the _SharedFunction_ arguments and return in the Contract metadata. The _SharedFunctionArg_ type is validated against the function argument type in the Contract Module.

    ```python
    # DO
    contract_module_imports = [
        ContractModule(
            alias='interest',
            expected_interface=[
                SharedFunction(
                    name='round_accrual',
                    args=[
                    SharedFunctionArg(
                        name='amount',
                        type='Decimal'
                        )
                    ],
                    return_type='Decimal'
                )
            ]
        )
    ]

    # DON'T
    contract_module_imports = [ContractModule(alias='interest')]
    ```

## Testing Contract Modules

### Unit

Each Contract Module can be unit-tested independently from any calling Contract. The approach for these tests can follow that used for Contracts and details on the Inception approach are included in `inception_test_framework_approach.md`. Example unit tests for a Contract Module can be seen in `library/common/contract_modules/tests/unit/utils_test.py`.

## Testing Contracts that Import Modules

Contract Modules cannot be tested directly by either simulation or end-to-end (E2E) tests. Instead, their functionality must be tested through the relevant Contract. Within the Inception Test Framework this means that any Contract Modules required by the Contract must be defined as part of the test set-up and then linked.

### Unit

Any Contract unit tests which rely on a Contract Module shared function will need to either mock the Contract Module return value or else import the Contract Module. In the Inception Test Framework, the Contract Module is imported as part of the test setup, e.g.:

```python
CONTRACT_FILE = "library/wallet/contracts/wallet.py"
UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"

...

class WalletTest(ContractTest):
    contract_file = CONTRACT_FILE
    side = Tside.LIABILITY
    linked_contract_modules = {
        "utils": {
            "path": UTILS_MODULE_FILE,
        }
    }
    ...
```

and examples of Contract unit tests which make use of Contract Modules can be found in `library/wallet/contracts/tests/unit/wallet_test.py`.

### Simulation

The simulation endpoint has been updated to include validation to ensure that all necessary Contract Modules have been included for the given Contracts.

Within the Inception Test Framework, the mapping between a Contract Module alias and the corresponding Contract Module file must be defined in the simulation test file and then linked to the calling Contract, e.g.:

```python
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "interest": "library/common/interest.py"
}

...

contract_modules = [
    ContractModuleConfig(alias, file_path)
    for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
]

contract_config = ContractConfig(
    contract_file_path=self.contract_with_contract_module,
    template_params=template_params,
    smart_contract_version_id=main_account["smart_contract_version_id"],
    account_configs=[
        AccountConfig(
            instance_params={},
            account_id_base="Main account",
        )
    ],
    linked_contract_modules=contract_modules,
)
```

### E2E

Within the Inception Test Framework, Contract Modules are handled similarly to other resources such as Workflows. The mapping between the Contract Module alias and the corresponding file must be defined in the e2e test file, e.g.:

```python
endtoend.testhandle.CONTRACT_MODULES = {
    "utils": {"path": "library/common/contract_modules/utils.py"}
}
```

The framework will then add a unique ID to the resource, upload to the test environment, and link it to the calling Contract.

## Managing Contract Module Resource Files

Using Contract Modules requires the management of three different resource types:

1. `CONTRACT_MODULE`
2. `CONTRACT_MODULE_VERSION`
3. `SMART_CONTRACT_MODULE_VERSIONS_LINK`

For example, there may be an initial `interest` CONTRACT_MODULE which has its first CONTRACT_MODULE_VERSION code associated with it. Then, at a later point, a new version of this Contract Module code may be created which will require a new CONTRACT_MODULE_VERSION to be associated with the parent CONTRACT_MODULE. At each iteration, the Contract Module will need to be linked to the calling Contract by creating a link between the CONTRACT_MODULE_VERSION and the SMART_CONTRACT_VERSION_ID using the SMART_CONTRACT_MODULE_VERSIONS_LINK resource.

> **_NOTE:_** If a Contract has multiple versions of a single CONTRACT_MODULE_VERSION associated with it, then it is the latest version (by timestamp) that will be used by the Contract.

The deployment of Contract Module resources is handled by the Configuration Layer Utility (CLU) similarly to any other resource (e.g. Contracts, Workflows etc.). As such, the CLU doesn't specify any particular location for the resource files other than that the location of the `manifest.yaml` effectively specifies the top-level directory.

For convenience, the Inception Library defines the Contract Modules and their associated `resources.yaml` within the `library/common/contract_modules` directory. Then each Contract which calls one or more Contract Modules contains a separate `resource.yaml` which creates the link between the Contract and all Contract Modules that it uses. An example can be seen in `library/wallet/contracts/wallet_module_versions_link.resource.yaml`.
