_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Inception Test Framework Workflow Simulation Testing

## General information

Workflow simulation testing involves registering and instantiating a Workflow Definition inside an in-memory sandbox approximation of the Workflow Engine, known as the Workflow Simulator. For convenience, a helper script is provided in the test framework to ease the process of using the simulation endpoint and making POST requests to `/v1/workflow-instances:simulate`.

## Configuration

The Workflow Simulation tests require access to a Vault instance in order to run. The Inception Library test framework uses a configuration file stored at `config/environment_config.json`.

The environment config file holds details for one or more environments. This includes the `wf_api_url` and service account tokens. A Service Token can be generated either by accessing the Vault Ops Dashboard (e.g. `https://ops.<REPLACE WITH ENVIRONMENT URL>/organisation-management/service-accounts`) or by making a request to the Core API Endpoint: `/v1/service-accounts POST`.

## Helper Methods

There is a set of helper methods exposed in `inception_sdk/test_framework/workflows/simulation/workflows_api_test_base.py` to parse the different types of simulation response.

## Writing Test Cases

1. Create the Test class using the `WorkflowsApiTestBase` template, for example:

    ```python
    class WorkflowSimulatorTest(WorkflowsApiTestBase):
    ```

2. In each test case, setup the workflow context, for example:

    ```python
    # an instantiation context with the key our Workflow expects
    instantiation_context = {"input_variable": "123"}
    ```

3. Trigger the API call by passing in the workflow yaml file and context, for example:

    ```python
    response = self.simulate_workflow(
        specification=specification, # The workflow yaml file content
        instantiation_context=instantiation_context, # Context defined in step 2
    )
    ```

4. Parse the response with the helper method in the test framework to get the workflow side effects, for example:

    ```python
    side_effects = self.get_side_effects(response)
    ```

    `side_effects` is a type of Dictionary, which contains a Generator of `side_effects`.
    Using the `next` function, it returns the next item in an iterator.

5. Assert the `side_effects` of the workflow steps are as expected. For example:

    ```python
    next_side_effect_event = next(side_effects["events"])
    self.assertEqual(next_side_effect_event["name"], "A_to_B_2")
    ```

More example tests can be found inside the file:
 `inception_sdk/test_framework/workflows/simulation/workflows_api_client_test.py`

For more information about possible values, please refer to the documentation:
`https://documentation.<REPLACE WITH ENVIRONMENT URL>/api/workflows_api/#Workflows-WorkflowInstance`
