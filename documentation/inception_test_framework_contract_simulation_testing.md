_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Inception Test Framework Contract Simulation Testing

## General information

Simulation tests are provided for each product and can be found in `library/<product_name>/contracts/tests/simulation/<product_name>_test.py`. These tests are designed to demonstrate the features of a product such as charging fees, accruing interest, and preventing postings by creating a series of Events (e.g. an inbound posting) which are sent to the `/v1/contracts:simulate` endpoint and then parsing the response to verify that e.g. the correct balances have been updated. The test defines the simulated time-period which can be days or years, allowing tests on scheduled events to also be created.

## Configuration

See `documentation/inception_test_framework_configuration.md`

## Running Simulation Tests

Thought Machine uses Please as the BUILD system which can be used for running tests (among other things). Alternatively, the Python `unittest` module can also be used to run the packaged tests. Instructions for each method are given below.

### Python

Ensure that all necessary Python packages are present by running:

```bash
pip install -r requirements.txt
```

> NOTE: The minimum supported Python version is `3.9`

To run all simulation tests for a product, run:

```bash
python3.9 -m unittest library/current_account/contracts/tests/simulation/current_account_test.py
```

To run a specific test, run:

```bash
python3.9 -m unittest library.current_account.contracts.tests.simulation.current_account_test.CurrentAccountTest.<test_name>
```

### Please

To run all tests, run `plz test`.

To run a specific test, run `plz test //path/to/build/file:test_name`

E.g. `plz test //library/current_account/contracts/tests/simulation:current_account_test`

To run all tests in a folder, you can use `plz test //path/to/folder/...`

## Navigating the Contract Simulation Test Utils

The Inception Release folder contains a set of helper utilities for writing simulation tests along with tests that test the functionality of the helpers themselves. From the top-level of the folder, these can be found by navigating to `inception_sdk/test_framework/contracts/simulation/`. The below table highlights some of the key files and folders and gives a brief summary of their contents:

```bash
$: ~/inception_sdk/test_framework/contracts/simulation/
```

| File or Folder               | Description                                                                                                                                              |
|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| common/helper.py             | Exposes easy helper methods for  sending each type of posting instruction and settings flags with minimal effort from the test writer                    |
| mock_product/                | A set of contracts for testing vault_caller.py                                                                                                           |
| sample_simulator_response    | An example of the JSON response from a request sent to the simulation endpoint for a regular smart contract. Used as input for simulation_utils_test.py  |
| sample_supervisor_response   | An example of the JSON response from a request sent to the simulation endpoint for a supervisor contract. Used as input for simulation_utils_test.py     |
| utils.py                     | This module exposes helper methods for asserting test outputs e.g. balances or workflow events                                                           |
| test_utils.py                | This tests the integration test utils                                                                                                                    |
| backdated_simulator_response | An example of the JSON response from a request which includes a backdated posting                                                                        |
| helper.py                    | This module extends many of the methods from `common/helper.py`                                                                                          |
| vault_caller_helper_test.py  | A set of tests which use the mock products and the vault_caller.py to test the endpoint functionality                                                    |
| vault_caller.py              | A helper script which provides a way of calling the simulate endpoint without writing REST requests directly. Available from the Vault Documentation Hub |

## Helper Methods

There is a set of helper methods exposed in `inception_sdk/test_framework/contracts/simulation/common/helper.py` to construct a simple version of every available type of Posting Instructions. These helper methods will return a SimulationEvent of a Posting Instruction Batch containing a single Posting Instruction.

It is recommended to make use of the `SubTest` data object (see `inception_sdk/test_framework/contracts/simulation/data_objects/data_objects.py`) for constructing simulation tests. This allows the construction of an easier-to-follow narrative of event and expected side-effects rather than a list of events followed by a list of side-effects/checks. An example of the suggested structure is shown below:

```python
def test_grace_period(self):
    # Checks for scenarios when grace period is active.
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    end = datetime(2019, 1, 25, tzinfo=timezone.utc)
    template_params = default_template_params.copy()
    instance_params = default_instance_params.copy()
    instance_params["deposit_period"] = "0"
    instance_params["cool_off_period"] = "0"
    instance_params["grace_period"] = "11"
    instance_params["period_end_hour"] = "0"

    sub_test_1_ts = start + relativedelta(days=8, hour=21, minute=0, second=1)
    sub_test_2_ts = start + relativedelta(days=9, hours=23, minutes=59, seconds=59)
    sub_test_3_ts = start + relativedelta(days=11, hour=0, minute=0, second=1)
    sub_test_4_ts = start + relativedelta(days=12, hour=0, minute=0, second=1)

    sub_tests = [
        SubTest(
            description="Withdrawal within grace period should be accepted",
            events=[
                create_inbound_hard_settlement_instruction(
                    target_account_id=TD_ACCOUNT,
                    amount="100.00",
                    event_datetime=start + relativedelta(days=1),
                ),
                create_outbound_hard_settlement_instruction(
                    target_account_id=TD_ACCOUNT,
                    amount="25.00",
                    event_datetime=sub_test_1_ts,
                ),
            ],
            expected_balances_at_ts={
                sub_test_1_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "75")]},
            },
        ),
        SubTest(
            description="Deposit within grace period should be accepted",
            events=[
                create_inbound_hard_settlement_instruction(
                    target_account_id=TD_ACCOUNT,
                    amount="17.00",
                    event_datetime=sub_test_2_ts,
                ),
            ],
            expected_balances_at_ts={
                sub_test_2_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
            },
        ),
        SubTest(
            description="Deposit outside grace period should be rejected.",
            events=[
                create_inbound_hard_settlement_instruction(
                    target_account_id=TD_ACCOUNT,
                    amount="18.00",
                    event_datetime=sub_test_3_ts,
                ),
            ],
            expected_balances_at_ts={
                sub_test_3_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
            },
        ),
        SubTest(
            description="Withdrawal outside grace period should be rejected.",
            events=[
                create_outbound_hard_settlement_instruction(
                    target_account_id=TD_ACCOUNT,
                    amount="17.00",
                    event_datetime=sub_test_4_ts,
                ),
            ],
            expected_balances_at_ts={
                sub_test_4_ts: {TD_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "92")]},
            },
        ),
    ]

    test_scenario = self._get_simulation_test_scenario(
        start=start,
        end=end,
        sub_tests=sub_tests,
        template_params=template_params,
        instance_params=instance_params,
        internal_accounts=default_internal_accounts,
    )
    self.run_test_scenario(test_scenario)
```

## Constructing Objects from Scratch

For more complex test scenarios, it is necessary to construct SimulationEvents from scratch. This allows the test writer to test complex scenarios.

*NOTE: Events need to be converted to Dict form using the class methods `to_dict` before passing into SimulationEvent*

Example:

The following creates a Posting Instruction Batch event with one InboundAuthorisation event and one Inbound Hard Settlement event.

```python
events.append(
    SimulationEvents(
        datetime(year=2019, month=1, day=2, tzinfo=timezone.utc),
        PostingInstructionBatchEvent(
            client_batch_id='Special Client Batch ID',
            posting_instructions=[
                PostingInstruction(
                    client_transaction_id=client_transaction_id,
                    instruction=InboundAuthorisation(
                        amount=amount,
                        denomination=denomination,
                        internal_account_id='Special PNL ACCOUNT',
                    )
                ),
                PostingInstruction(
                    client_transaction_id=client_transaction_id,
                    instruction=InboundHardSettlement(
                        amount=amount,
                        denomination=denomination
                    )
                )
            ],
            value_timestamp=datetime.isoformat(value_timestamp)
        ).to_dict()
    )
)
```
