<!-- markdownlint-disable MD033 -->
_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Inception Test Framework E2E

## General information

### Configuration

See `documentation/inception_test_framework_configuration.md`.

### Test Run Isolation

The framework takes care of test setup by creating the configuration layer resources (e.g. Smart Contracts, Workflows etc.) specified by the test classes, on the specified Vault instance. It also handles tear-down at the end of the test run by e.g. closing any accounts created by the test.<sup id="a1">[1](#f1)</sup>

Beyond handling the relevant REST API calls, the framework ensures that test runs are suitably isolated from each other using the following steps:

1. Unique account schedule tags can be created per test run, which allows schedule behaviour to be controlled for specific accounts/test runs.

2. Each unique contract version is assigned a unique E2E `/v1/products` product id based on its python code, so two developers testing different work-in-progress do not affect each other. For example, the 'real' `product id` is `loan`, then at test runtime,  a product is uploaded with `product id:` `e2e_loan_e94d25b1605492f5caeb6daafd461847` comprising the `e2e` prefix, the 'real' `product_id`, and a suffix based on a hash of the code.<sup id="a2">[2](#f2)</sup>

3. Each unique workflow definition is assigned a unique E2E `/v1/workflow-definitions` definition id based on its definition yaml. Again, this allows us to test multiple variations of the same workflow in isolation. For example, the 'real' `definition id` is `APPLY_FOR_LOAN`, then at test runtime, a workflow definition is uploaded with `definition id:` `APPLY_FOR_CREDIT_CARD_e2e_SIPJCCVJRI` comprising the 'real' `definition id`, and a suffix of `e2e` plus a random ten character.<sup id="a3">[3](#f3)</sup>

4. Each flag definition id is assigned a unique E2E `/v1/flag-definitions` definition id.

5. Each internal account id is assigned a unique E2E `/v1/internal-accounts` account id.

Test writers can continue referring to the original ids, as the framework maps these to the unique E2E ids. It also takes care of substituting the real ids with E2E ids within the contract and workflow definitions themselves, although this sometimes requires configuration (see `Configuring a Test Class` below). Where possible the E2E ids are re-used.

### Test Helpers

The test framework exposes helpers to make direct REST API calls, or produce to/consume from Kafka topics, as well as wrappers around these to simplify test writing and reading. The helpers can be found in `inception_sdk/test_framework/endtoend`. In general, they are either split by the underlying Vault API that they relate to (e.g. `core_api_helpers.py`) or the test areas they relate to (e.g. `contract_helpers.py`).

A common pattern is to create a direct REST API call (e.g. fetching a resource) and wrapping it inside a retry function. This abstracts most timing issues/flakes from the test writer, but it is not completely foolproof. An example of such a flake would be:

- a test instantiates a workflow that creates a posting to an account
- the test calls the balances API to assert that the posting has been accepted and the account balances have been updated
- however, the call is made before the workflow has processed the posting and so the test would fail
- wrapping a retry on the balances API call would give more time for the workflow to complete and the test can pass as intended

As polling APIs is not an efficient approach, the framework is gradually adopting Kafka within helpers. By default Kafka will be used when a corresponding helper is available. This can be disabled by setting the `--use_kafka` argument to `false`. If use kafka is set to false the framework will either:

- skip the test if the test has been decorated as kafka-only
- fall back to corresponding REST helper if available
- fail if the test has not been decorated and relies on a Kafka helper with no corresponding REST helper

### Test Types

The framework supports two end-to-end test types. These will be covered in more detail, but as a summary:

- Standard end-to-end tests are used to test features that do not require any schedule execution. These tests trigger contract/workflow functionality through Vault APIs (REST or Streaming). The configuration layer test setup is typically at a product level (e.g. running the same test 10 times will usually only result in a single contract being uploaded).

- Accelerated end-to-end tests are intended for two use cases. To test features that need to execute a schedule or to test features that need to create an account as of a specific point in time so that the expected outcome does not vary with each test execution (e.g. to ensure that account schedules are created correctly without having code to determine what the expected outcome is.)

> NOTE: These tests extend the standard tests, so can also trigger contract/workflow functionality through APIs. However, for technical reasons the contract setup must take place at a test level (i.e. running the same test 10 times will always result in 10 contracts being uploaded). This is the biggest reason for not using accelerated tests all the time.

### Standard End-to-End

Standard E2E tests are included for each product in `/library/[product_name]/tests/e2e/`. A useful example to consult is `/library/wallet/tests/e2e/test_wallet.py` which contains many of the standard components used in E2E tests. Reading from top to bottom, this includes:

- Python package imports and custom helper module imports
- Definition of Account Balance Addresses, Flags, and Contract Parameters
- Definition of the resources required for the test (Smart Contracts, Workflows, Account Schedule Tags, and Flag Definitions) and which will be uploaded to the test environment by the helper functions
- Definition of the test class
- Definitions of the individual tests to be run

Looking at the test `test_apply_wallet_via_workflow_with_eas_account`, it has the following features:

- A docstring describing the purpose of the test
- A Core API call to the Customer endpoint to create a customer
- A Core API call to the Accounts endpoint to create an open account using the `easy_access_saver`
- A Workflows API call to instantiate the `OPEN_WALLET` workflow with the given instantiation_context. This workflow will open a second account for the customer with the product `wallet`.
- A series of Workflows API calls which progress the state of the instantiated workflow by supplying the workflow with the expected field data. As workflows take time to progress, wait methods are included.
- When the workflow has completed, the customer should have a new `wallet` account associated. A Core API call to the Accounts endpoint retrieves this new `account_id` and a series of `assert` statements check that the account has the correct status and contract parameters.

#### Configuring a Test Class

Test classes extend the `endtoend.End2Endtest` class.

Each test class must configure the resources used by its tests. The exact resources required for a test will vary according to the product and what is being tested. Not all resources are required for any test and the method for configuring each is detailed below:

1. Contracts - There can be multiple entries, either because multiple contracts are involved in a single test, or because different tests need different template parameter values. `ca_template_params` is a Dict[str, str] of template parameter names and values.

    ```python
    endtoend.testhandle.CONTRACTS = {
        "casa": {
            "path": "library/casa/contracts/casa.py",
            "template_params": ca_template_params
        },
    }
    ```

2. Supervisor Contracts - Where a product makes use of a Supervisor Contract (for example `library/savings_sweep/supervisors/savings_sweep.py`) they are configured separately.

    ```python
    endtoend.testhandle.SUPERVISORCONTRACTS = {
        "savings_sweep": {
            "path": "library/savings_sweep/supervisors/savings_sweep.py"
        }
    }
    ```

3. Workflows - There should only ever be one entry per workflow

    ```python
    endtoend.testhandle.WORKFLOWS = {
        "CASA_APPLICATION":
            "library/casa/workflows/casa_application.yaml"
    }
    ```

4. Flag Definitions - There should only ever be one entry per flag definition.

    ```python
    endtoend.testhandle.FLAG_DEFINITIONS = {
        CASA_TIER_UPPER": "library/casa/flag_definitions/casa_tier_upper.resource.yaml
    }
    ```

5. Internal Accounts - This is a mapping of TSIDE to internal account id. The account id is prefixed with "E2E_" and either "A" or "L", depending on the TSIDE. For example "E2E_L_ACCRUED_INT_RECEIVABLE". The final length must be <= 32 characters, as mandated by the `/v1/accounts` API

    ```python
    endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = internal_accounts_tside = {
        "TSIDE_ASSET": [
            "ACCRUED_INT_RECEIVABLE",
        ],
        "TSIDE_LIABILITY": [
            "INT_RECEIVED"
        ],
    }
    ```

While the test framework automatically replaces the original ids of the resources with the e2e ids in contracts and workflows, there is further configuration needed to handle values within parameters. This is facilitated via `inception_sdk/test_framework/endtoend/contracts_helper.py`'s `prepare_parameters_for_e2e` helper.

1. Flag Definitions - These are often stored in parameter values as json lists of containing the flag definition ids, or dictionaries where the flag definition id is the key:
    1. For a parameter expecting a list, populate the contract e2e parameter map with:

        ```json
        "<parameter_name>": {"flag_key": ["CASA_TIER_UPPER"]}
        ```

    2. For a parameter expecting a dictionary, populate the contract e2e parameter map with:

        ```json
        "<parameter_name>": {"flag_key": {"CASA_TIER_UPPER" : "25"}}
        ```

   In both cases, this will allow "CASA_TIER_UPPER" to be replaced with the e2e equivalent id.

2. Internal Accounts - These are often stored as scalar string parameter values:
    - Populate the contract e2e parameter map with:

        ```json
        "<parameter_name>": {
            "internal_account_key": "INT_RECEIVED",
        }
        ```

    This will allow INT_RECEIVED to be replaced with the e2e equivalent id. As a safety measure, the framework logs
    warnings for any parameter name ending in "_account" that doesn't make use of the `internal_account_key` structure

3. Nested Internal Accounts - These are often stored in parameter values as json dictionaries with the value of each key being the internal account string
    - Populate the contract e2e parameter map with:

        ```json
        "<parameter_name>": {
            "nested_internal_accounts": {
                "key_1": {"internal_account_key": "INTERNAL_ACCOUNT_1"},
                "key_2": {"internal_account_key": "INTERNAL_ACCOUNT_2"}
            },
        }
        ```

    This will allow `INTERNAL_ACCOUNT_1` and `INTERNAL_ACCOUNT_2` to be replaced with the e2e equivalent id

#### Setting Up Tests

There is typically no generic setup beyond the test-class level creation of resources that is handled by the framework.

#### Writing Test Cases

Tests will consist of the following steps, which essentially consist of creating, amending and fetching resources via Vault APIs. Some are optional and/or repeatable:

1. Create ‘base’ resources via the API, like customers and accounts. In some cases this is covered by the next step (e.g. the test might execute a workflow that creates accounts)

    ```python
    cust_id = endtoend.core_api_helper.create_customer()

    account = endtoend.contracts_helper.create_account(
        customer=cust_id,
        contract='casa',
        instance_param_vals=ca_instance_params,
        permitted_denominations=['GBP', 'USD', 'EUR'],
        status='ACCOUNT_STATUS_OPEN'
    )
    ```

2. Trigger configuration layer behaviour by creating/amending Vault resources. For example:

    1. Creating a workflow and sending in events to mimic a user interacting with the workflow

        ```python
        wf_id = endtoend.workflows_helper.start_workflow(
            'CLOSE_CASA',
            context=wf_context
        )

        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_external_disbursement_reference",
            event_name="payment_selected",
            context={"external_account_reference": "external_account_reference"}
        )
        ```

    2. Creating postings to mimic transaction-based events

        ```python
        postingID = endtoend.postings_helper.inbound_hard_settlement(
            account_id=casa_account_id,
            amount='10',
            denomination='USD'
        )
        ```

    3. Updating accounts to mimic account lifecycle events

        ```python
        endtoend.core_api_helper.update_account(
            casa_account_id,
            endtoend.core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE
        )
        ```

3. Asserting outcomes by observing the status of Vault resources. For example:

    1. Were balances updated as expected?

        ```python
        endtoend.balances_helper.wait_for_account_balances(
            casa_account_id,
            expected_balances=[
                (endtoend.balances_helper.BalanceDimensions(address='DEFAULT', denomination='GBP'), '0')
            ]
        )
        ```

### Accelerated End-to-End

Accelerated end-to-end tests rely on Account Schedule Tags and time cursor functionality to trigger account schedule execution at will. Other than this, the tests use the same resources and helpers as regular end-to-end tests.
We prefer to create backdated resources and used an Account Schedule Tag paused in the past to control the schedule catch-up by moving the time cursor forward. This is because:

   1. Future-dated resources can cause confusion and clog up views that are ordered by descending value_timestamp etc.
   2. Future-dated tests do not have a pre-determined static outcome. This means part of the test involves calculating the expected outcome, rather than defining it. As a result, the test coverage fluctuates, which is usually undesirable

However, this is not always possible as certain resources cannot be backdated. Notable examples include plans or flags. In these scenarios we instead use the tag to fast forward schedule executions and simply have to manage the disadvantages mentioned above.

#### Configuring a Test Class

Test classes extend the `endtoend.AcceleratedEnd2EndTest` class, which itself extends `endtoend.End2EndTest`.
Like regular end-to-end tests, the test class must configure the resources used by its tests

#### Setting Up Tests

The use of test-specific account schedule tags means we have to create certain configuration layer resources at a test level, instead of test-class level. This is because each test-run requires new account schedule tag resources, whose ids must then be substituted into smart contract code, resulting in a new product. At the moment this is achieved by calling the `standard_setup` function inside the test, so that it is triggered after the decorator.

Each test defines the schedules it needs to control, and the framework will automatically create unique tags for these schedules. These schedules are specified on a per-contract and supervisor contract basis. In the example below we expect
`endtoend.testhandle.CONTRACTS` to have a `casa` entry.

```python
@endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules({'casa': ["ACCRUE_INTEREST"]})
def test_accrue_interest(self):
    endtoend.standard_setup()
```

When using the `trigger_next_schedule_job_and_wait` helper, the framework will determine the suitable tag to update, and the values for the relevant attributes.

#### Writing Test Cases - Backdated Approach (Recommended)

The following examples illustrate how to create a customer and casa account, trigger the interest accrual schedule, and check that the expected interest was accrued.

##### Creating a Test Customer and Account

```python
@endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules({'casa': ["ACCRUE_INTEREST"]})
def test_accrue_and_apply_interest(self):
    endtoend.standard_setup()
    opening_date = datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
    first_accrual_date = datetime(2020, 1, 2, tzinfo=timezone.utc)
    customer_id = endtoend.core_api_helper.create_customer()
    casa = endtoend.contracts_helper.create_account(
        customer=customer_id,
        contract="casa",
        instance_param_vals=dict(
            arranged_overdraft_limit="1000",
            unarranged_overdraft_limit="2000",
            interest_application_day="16",
            daily_atm_withdrawal_limit="1000",
        ),
        status="ACCOUNT_STATUS_OPEN",
        opening_timestamp=opening_date.isoformat(),
    )
    account_id = casa["id"]
```

Important notes:

1. The `account_opening_timestamp` defines when the account opening is backdated to. This must be determined by the test writer based on the test scenario and the frequency of the schedule(s) being tested. For example, if the scenario covers a schedule that runs a year from account opening, the account opening must be set to over a year in the past. We recommend always using absolute values to get repeatable outcomes.
2. Changing products is simply a case of changing the `instance_param_vals` and `product_id`.
3. The helper technically allows multiple sets of customers and accounts to be created by changing the `instances` - this functionality **should only be used for performance testing** in environments that have been designed to handle large volumes. Standard development environments may experience severe performance degradation if put under heavy load.

##### Triggering a Schedule Job

The `trigger_next_schedule_job_and_wait` helper guarantees execution of the relevant schedule's next job by moving the corresponding tag's `pause_at_timestamp` to 1 second after the schedule's `next_run_timestamp`. This is the smallest increment that can be added, which prevents the risk of accidentally triggering multiple jobs. We recommend setting the `effective_date` parameter to the datetime for the expected job to be triggered, as a sanity check.
The helper also waits until the job is completed in order to handle the asynchronous nature of the schedule execution journey.

```python
    endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
        account_id=account_id,
        schedule_name="ACCRUE_INTEREST",
        effective_date=first_accrual_date,
    )
```

The above steps can be repeated multiple times if required.

##### Asserting on Schedule Outcomes

After this, it is a case of using regular end-to-end helpers to assert on outcomes. For example:

```python
endtoend.balances_helper.wait_for_account_balances(
    account_id=account_id,
    expected_balances=[
        (BalanceDimensions('DEFAULT'), '1000'),
        (BalanceDimensions('ACCRUED_DEPOSIT'), '0.13699')
    ]
)
```

#### Writing Test Cases - Fast Forward Approach

The following example illustrates how to create a plan and fast-forward its schedules.

##### Creating a Test Customer, Plan and Account

Unlike the backdated approach, we do not set any explicit creation dates.

```python
@endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules({'savings_sweep': ["ACCRUE_INTEREST"]})
def test_supervisor_fast_forward(self):
    endtoend.standard_setup()
    cust_id = endtoend.core_api_helper.create_customer()

    checking_account = endtoend.contracts_helper.create_account(
        customer=cust_id,
        contract="us_checking_account",
        instance_param_vals=ca_instance_params,
        status="ACCOUNT_STATUS_OPEN",
    )
    checking_account_id = checking_account["id"]

    savings_instance_params = {"interest_application_day": "1"}
    us_savings_account = endtoend.contracts_helper.create_account(
        customer=cust_id,
        contract="us_savings_account",
        instance_param_vals=savings_instance_params,
        status="ACCOUNT_STATUS_OPEN",
    )
    savings_account_id = us_savings_account["id"]

    plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
        "savings_sweep",
        [checking_account_id, savings_account_id],
    )
```

##### Triggering a Schedule Job

This step is almost identical to the Backdated Approach for the test writer. However, in the background the test framework will be updating the tag to fast forward to the schedule's next run time, rather than updating the `test_pause_at_timestamp`

```python
endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
    plan_id=plan_id,
    schedule_name="ACCRUE_INTEREST",
    effective_date=first_accrual_date,
)
```

##### Asserting on Schedule Outcomes

This step is identical to the Backdated Approach

## Troubleshooting

### Asynchronous Calls

Many of the APIs in Vault are asynchronous, this means that test should never attempt to assert a result immediately if the call is asynchronous. Asynchronous requests should not be stacked up and checked only once for the expected result. Instead each async request should be processed separately and validated once for each call.

To make sure that the result is actually processed, `retry_call` can be used, which polls for a result with a set timeout (see example below).

```python
endtoend.helper.retry_call(
    func=endtoend.core_api_helper.get_account_update,
    f_args=[account_update_id],
    expected_result=target_status,
    result_wrapper=lambda x: x['status'],
    timeout=10
)
```

**Guidelines to follow**

- Do not poll/re-retrieve results of synchronous processes. For example:
  - Creating an account and fetching the account immediately after
  - Creating a flag and fetching the flag immediately after

- Do use kafka notifications/poll for results of asynchronous processes. For example:
  - Postings being accepted/rejected
  - Balances being updated
  - Account updates finishing (completed, rejected, errored)

- Avoid using `retry_call` directly in tests. Dedicated helpers should be used (e.g. `wait_for_account_update`). If none exist then new helpers can be added to `/inception_sdk/test_framework/`

### Retry call parameters

There are multiple parameters that can be used to improve retry calls and to avoid using the maximum timeout value.

- `timeout` for total seconds to elapse before timing out.
- `sleep_time` for number of seconds between each retry.
- `max_retries` for number of retries to process a given function.
- `back_off` for multiplier to increase the sleep_time between each call. If set to `1` sleep time will remain unchanged.

```python
endtoend.helper.retry_call(
    func=endtoend.workflows_helper.reload_workflow,
    f_args=[wf_id],
    expected_result='20000',
    result_wrapper=lambda x:
        x['global_state'].get('chosen_daily_atm_limit'),
    sleep_time=1,
    max_retries=5,
    back_off=1.5
)
```

---
<b id="f1">1.</b> As a reminder, it is not possible to delete resources from Vault. Test Smart Contracts and Workflows will remain on the instance but can be either updated or marked `inactive`. [↩](#a1)

<b id="f2">2.</b> See `inception_sdk/test_framework/endtoend/contracts_helper.py` for more details on how the resources are created, mapped, and uploaded. [↩](#a2)

<b id="f3">3.</b> See `inception_sdk/test_framework/endtoend/workflows_helper.py` for more details on how the resources are created, mapped, and uploaded. [↩](#a3)
