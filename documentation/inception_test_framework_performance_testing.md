_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Inception Test Framework Performance Testing

## General information

All Inception Global Product Library products are supplied with supporting Unit, Simulation, and E2E tests following the approach described in the `documentation`. In addition certain products also have supporting Performance tests (e.g. `library/wallet/tests/performance`). These tests are an extension of the E2E test framework and have been developed to test production-like performance. These tests set up Accounts with historic data (transactional or otherwise) based on the relevant Smart Contract fetching requirements, triggering specific behaviours (e.g. Schedule or Posting processing).

> **NOTE:** These tests **SHOULD NOT** be run on a standard development Vault environment without consulting with the environment owner first. Running these tests with large volumes of Accounts on a non-production-like environment may degrade the performance of your environment during the test, affecting other usage.

## Prerequisites
- Have read `documentation/inception_test_framework_e2e.md`

## Objectives
- Understand what performance testing means in relation to the Inception Library Test Framework
- Understand the different types of performance test, how they are configured, and how to run them
- Understand how to interpret the results of the tests

## Types of performance test

This section describes the types of tests we include and high-level approaches. We provide further details on configuration later on.
### Schedule tests
These test the throughput of Schedules defined in a Smart Contract. This approach is similar to the Accelerated End-to-End approach covered in `documentation/inception_test_framework_e2e.md` to avoid waiting for a job to occur in 'real-time', which could take weeks, months etc:

1. Pause all Schedules
This is done by creating Account Schedule Tags for each Schedule, and setting the `test_pause_at_timestamp` attribute of the Tags to a timestamp in the past.

2. Load a chosen number of Accounts using the given Smart Contract
Accounts must have a historic Account opening timestamp such that the paused Schedule should have occurred at least once in the meantime.
For example, for a monthly Schedule set the Account opening timestamp to 1 month and 1 day ago.

3. Generate historic data for the Accounts
We use the Simulation API to generate Postings to create a realistic transaction history for each Account.  These Postings are then transformed and sent to the Data Loader API, so that this history is populated within Vault for the Accounts. By using the simulator, we include Postings for both external (e.g. card transactions) and internal (e.g. interest accruals) triggers.

4. Trigger the specific Schedule of interest
Once loading is complete, we increment the relevant tag's `test_pause_at_timestamp` value by the frequency of the Schedule (e.g. 1 day for daily, 1 month for monthly).

5. Wait for the Schedules to process 
We listen to the `vault.core_api.v1.scheduler.operation.events` topic. The test waits for an `OperationEvent` corresponding to tag that was updated in the previous step. 



### Postings tests
These test both the latency for specific Posting rates to Accounts using a particular Smart Contract. The approach is:

1. Load the required number of Accounts using the given Smart Contract, based on desired Posting rates and test duration

2. Generate historic data for the Accounts - See step 3 for the Schedule tests

3. Send preconfigured Postings in a randomised order to the Accounts for fixed durations and at fixed rates.
The tests rely on stages, which are fixed durations for which Posting requests are produced at a fixed rate (also referred to as transactions-per-second or TPS). Stage duration is configurable but identical for all stages, whereas rates increase across the stages at a configurable interval. 

## Running performance tests
### Environment setup

#### Packages
Aside from the standard Vault deployment, the optional Data Loader and Postings Migration packages are required. Ensure they are included in the `packages.txt` whitelist for your environment:
- data-loader-api-package
- data-loader-package
- vault-postings-api-migration-pkg

#### Values YAML
In the `values.yaml` of your environment, ensure streaming API formats are set to JSON:
```yaml
common_stream_api:
  message_format: 'json'
  ......
  ......
data_loader_api:
  message_format: 'json'
  ......
  ......
postings:
  api:
    format: 'json'

```
If the format is not set to JSON then you will need to update the `values.yaml` file and then redeploy Vault to your environment.

Please consult your environment owner if you do not have access to either the `packages.txt` whitelist or `values.yaml` and refer to the Vault Installation Tools document that is provided with each Vault release.

#### E2E Framework Environment config
In `config/environment_config.json` ensure the target environment has the `performance_testing` key set to `true`. This is a safety mechanism to avoid accidentally loading more than 10 Accounts into an environment that has not been explicitly designated as suitable for performance testing.

e.g
```json
{
...
"my_perf_environment":
    ...
    ...
    "performance_testing": true,
}
```

See the 'inception_test_framework_configuration.md' for more details on framework configuration.

#### Environment Infrastructure

##### Sizing for Results
Performance depends on the size of the test environment (e.g. worker node and database instance types). The results can be used as relative and/or absolute measures of performance. For relative measures, it is important to have a consistent test environment across the tests. For absolute measures, it is also important to size the test environment as per your production setup, or the results will not be comparable. The Vault Performance Reports shipped alongside Vault releases provide details of the infrastructure setup we use internally.

##### Test-specific Considerations
Test setup often involves ingestion of large volumes of Postings, as explained earlier. The setup effectively compresses large periods' worth of activity into a few hours, putting the platform and underlying infrastructure under a lot of load. This usually translates to a backlog that Vault will process without particular issues given enough time. In some cases, test-specific setup is needed:
- Review your Kafka Persistent Volume sizes and topic retention settings based on test size (number of Accounts for Schedule tests, stage duration and Posting rates for Posting tests). Your production setup will not necessarily cater for months' worth of Account, Posting and balance events being generated in a few hours, and the Kafka broker disks may unexpectedly fill up. In particular, we recommend that any unused public topics have their retention set to 0ms as an easy way of reducing disk usage.
- Ensure your database has sufficient remaining space before starting a test.


## Test Configuration

### Python Test File
This file is based on tooling and concepts described in `inception_test_framework_e2e.md`. However, the performance framework extends the tooling in a few key ways:
- Each test calls `self.run_performance_test()`, passing in the path to a test profile (see next section for further details on profiles).
- The call defaults to running a Schedule test, but the type can be explicitly specified as per the `test_posting_tps` example below. In this case no tags should be passed into the `set_paused_tags` decorator.
- If multiple tags are specified for a Schedule performance test, a single instance of each Schedule is executed in sequence. There is a delay, defined by `endtoend.testhandle.paused_schedule_tag_delay`. This helps ensure metrics from one Schedule do not affect the next Schedule due to averaging windows that are typically used. You may wish to override the value for smoke tests where the metrics themselves are not relevant.
```python
    @PerformanceTest.Decorators.set_paused_tags(
        {
            ...
        }
    )
    def test_casa_accrual_schedule(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_casa_accrual_schedule_profile.yaml"
        )

    @PerformanceTest.Decorators.set_paused_tags({})
    def test_posting_tps(self):
        self.run_performance_test(
            TEST_PROFILES_DIR + "test_posting_profile.yaml",
            PerformanceTestType.POSTINGS,
        )
```
### Test Profile
The test profile YAML file will define the majority of the test setup. A separate file is used for each test defined in the python test file. The test framework takes care of translating this setup into the relevant Vault API requests. The details of the conversion mechanics are beyond the scope of this document, but we use a multi-threaded approach to minimise setup time whilst avoiding common pitfalls (e.g. enforce ordering of Postings at an Account-level to prevent accidentally backdating Postings).

See `library/casa/tests/performance/test_posting_profile.yaml` and `library/casa/tests/performance/test_casa_accrual_schedule.yaml`
for examples of a Postings and Schedules test profile respectively. The following sections detail how to understand and edit the test profile YAML file.

#### `dataloader_setup`
This section describes how Data Loader Dependency Groups are configured, which we use to create the Accounts for a performance test (see the Data Loader reference on the documentation hub for more info).
For example, in this case the framework will create 10000 instances of a Dependency Group, each with:
- 1 Customer
- 1 Account with desired instance parameter values
It will also upload the relevant Contract with the desired template param values (defaults are defined in python test file)

```yaml
dataloader_setup:
  # This name must be present in the endtoend.testhandle.CONTRACTS map defined in your python test file
  contract_name: "casa"
  # These values can be used to override defaults from the relevant python test module (e.g. test_casa_performance.py)
  # This is useful if different tests for the same product need small tweaks to certain parameter values
  template_param_vals:
    minimum_balance_fee: 10
  dependency_groups:
    # instances only needs to be set for Schedule tests. It can also be passed as a command line argument to the test runner (e.g. --instances=10000)
    # This attribute governs the number of customers that are created, and each of the Accounts specified in the `accounts` selection below are created once for each customer
    - instances: 10000
      customer:
        id_base: 200
      flags: []
      accounts:
        # The account opening timestamp can be specified as an absolute value:
        # - account_opening_timestamp: "2020-01-10 09:00:00 UTC"
        # or as a delta to the current date (see below). Typically a fixed date is preferred to ensure a fixed test scenario with a known expected outcome that can be verified later
        # In either case, the Account Schedule Tags' test_pause_at_timestamp values must be set in conjunction to work as intended. For example,
        # if you set account_opening_timestamp to "2020-01-10 09:00:00" your tags will need to be set at an explicit date shortly before this
        - account_opening_timestamp:
            delta:
              days: -1
          instance_param_vals: &instance_param_vals
            arranged_overdraft_limit: "1000"
            unarranged_overdraft_limit: "2000"
            interest_application_day: "16"
            daily_atm_withdrawal_limit: "1000"
```

> **Note:** The number of instances will be automatically set for Postings performance tests, so **should not** be specified in the corresponding test profile YAML.

#### `simulation_setup`
This section describes how the historic data for the Accounts is generated via the simulator. In it, the start and end timestamps of the simulation are set, as well as the list of v3 simulation events to be considered. Some information will always be required (e.g. Account creation), while others depend on the Contract (e.g. specific Internal Accounts, Flag Definitions and Flags etc). In this example, the test simulates a time range of around 30 days, which would be useful for testing Schedules which require 30+ days of Postings.

```yaml
simulation_setup:
  # The simulation start/end timestamp can be specified as a delta and/or an absolute value. dataloader_setup account_opening_timestamp and simulation_setup
  # start and end values should be coordinated to avoid mismatches that will void the test. For example, an account_opening_timestamp of 2020-01-01T00:00:00Z
  # and a simulation with start/end date specified as -1 month and -1 day will result in Postings being created in the future relative to the account opening
  # instead of in the past
  start:
    delta:
      months: -1  # this provides a minimum dataset for 1 month's worth of Postings/balance entries
      days: -1
  end:
    delta:
      days: -1
  # The events contain all simulation events required: creation of accounts, Flag Definitions, Flags and any Postings.
  # The timestamps are currently either explicit datetimes, or "start" and "end" which are resolved to the simulation_setup start and end datetimes, as per the above configuration.
  # The following event types are supported: "create_account_instruction", "create_flag_definition_event", "create_flag_event", 
  # "create_inbound_hard_settlement_instruction", and "create_outbound_hard_settlement_instruction". Note that the Posting Instruction types are limited by
  # what the Postings Migration API supports.
  # The simulation will generate any contract-triggered events like scheduled accrual postings. The `expected_number_of_postings` helps validate that
  # the setup output is as expected.
  expected_number_of_postings: 3
  events:
    - type: create_account_instruction
      timestamp: start
      account_id: "1"
      product_id: "2"
      instance_param_vals: {}
    - type: create_account_instruction
      timestamp: start
      account_id: "Savings pot"
      product_id: "2"
      instance_param_vals: {}
    - type: create_account_instruction
      timestamp: start
      account_id: "Main account"
      product_id: "1"
      instance_param_vals: *instance_param_vals
    - type: create_inbound_hard_settlement_instruction
      amount: "1000"
      event_datetime: start
      denomination: "GBP"
      client_transaction_id: "123456"
      client_batch_id: "123"
```

#### `postings_setup`
This section only needs to be defined for Postings performance tests. Here we set-up:
- The different stages of TPS for Postings to generate, and the duration of each stage
- A list of Postings to be sent to each Account over each stage of the test

For example, here we set the starting TPS to 30, and the stopping TPS to 61. The test will increase in increments of
15 TPS for each stage (i.e. 30, 45, 60), and send Postings at that TPS for 300 seconds.

In the example, we send 2 Postings per Account, an inbound and outbound hard settlement. The number of instances (Accounts) created
via the Data Loader is automatic and is determined by the TPS, duration and number of Postings per Account. We ensure that each
Account is sent all of the specified PIBs, but the order is randomised.

```yaml
Postings_setup:
  stage_range:
    start: 30
    stop: 61
    step: 15
    duration: 300
    timeout: 600
  pib_template:
    - client_id: "AsyncCreatePostingInstructionBatch"
      client_batch_id: "123__tps3_33"
      posting_instructions:
        - client_transaction_id: "123456__tps3_33"
          inbound_hard_settlement:
            amount: "1000"
            denomination: "GBP"
            target_account:
              account_id: "Main account"
            internal_account_id: "1"
            advice: False
          pics: []
          instruction_details:
            description: "test"
          override:
            restrictions:
          transaction_code:
      batch_details:
        description: "test"
      dry_run: False
    - client_id: "AsyncCreatePostingInstructionBatch"
      client_batch_id: "123__tps3_33"
      posting_instructions:
        - client_transaction_id: "123456__tps3_33"
          outbound_hard_settlement:
            amount: "20"
            denomination: "GBP"
            target_account:
              account_id: "Main account"
            internal_account_id: "1"
            advice: False
          pics: []
          instruction_details:
            description: "Test ATM withdrawal"
            transaction_code: "6011"
          override:
            restrictions:
          transaction_code:
      batch_details:
        description: "test"
      dry_run: False
```

## Running performance tests

Tests should always be executed one by one for a given Vault instance, so their performance can be observed in isolation, e.g.:
`python3.7 -m unittest library.casa.tests.performance.test_casa_performance.CasaPerformanceTest.test_posting_tps --environment=my_environment`

## Observing results

Performance test results can be observed via Grafana dashboards, or through raw metric extracts. This section explains how to do either or both.

### Vault Metrics and Observability
Vault components all generate metrics relating to performance and activity. Vault also ships with an Observability stack, which includes a set of Grafana dashboards, an open source analytics and interactive visualization web application, for visualising these metrics. Please contact your environment owner if you are not able to access these boards. The data that is visualised through Grafana is scraped from Vault services using a tool called Prometheus, which also exposes a query interface to these metrics.

### Automated Metrics Extraction
The performance framework will automatically collect certain metrics based on a set of Prometheus queries defined at `inception_sdk/test_framework//performance/performance_queries.json`. This facilitates easy extraction and storage of key metrics for performance tests:
- For Schedule tests, data will be extracted between the known timestamp when Schedules were triggered and the timestamp at which the Scheduler `OperationEvent` was received, marking the end of the Schedule processing.
- For posting tests, data will be extracted between the beginning of the first stage and the end of the last stage.

The CSV files produced as a result of the performance test runs contain the same data, or subsets thereof, that are displayed in Grafana dashboards. These metrics are extracted using a Prometheus helper found here `inception_sdk/test_framework/performance/prometheus_api_helper.py`.

> **Note:** The prometheus helper can be executed independently of the inception performance framework to retrieve metrics results files at any time after a performance test run. execute `prometheus_api_helper.py` with `--help` argument for more information

When running a performance test (any test class derived from the `inception_sdk/test_framework/performance/performance_helper/PerformanceTest` class) the CSV files will be created and zipped into the current working directory using the filename format: `perf-results-D{report_date}-{test_type}.zip`. They can be disabled by passing in `--create_reports=False`.

The header defined by the first row of the CSV file directly relates to the query performed. Below is a cut-down example of an output file (columns separated by comma):
```
|Datetime|Throughput|EngineFetcher.BatchGetAccountLiveBalances (99th %ile)|EngineFetcher.BatchGetContractModuleVersions (99th %ile)|EngineFetcher.BatchGetFlagTimeseries (99th %ile)|
|2021-10-28 14:03:00+00:00|24.241||||
|2021-10-28 14:03:30+00:00|357.069|14.049|0.048|0.484|
|2021-10-28 14:04:00+00:00|919.306|14.8|0.048|0.974|
|2021-10-28 14:04:30+00:00|1085.380|14.875|0.047|0.967|
|2021-10-28 14:05:00+00:00|962.876|14.937|0.009|0.980|
|2021-10-28 14:05:30+00:00|474.971|14.933|0.009|0.962|
|2021-10-28 14:06:00+00:00|124.180|14.535|3.349|
```
The metrics are typically measures of throughput or latency.

### Schedule Test Boards

The main focus for Schedule tests is the throughput and duration (duration is directly tied to throughput and number of Accounts). The following boards are of interest:

- "Contract Account Schedule Journey Health" provides specific information, including a decomposition of the Schedule execution processing time across the different stages.
- "Contract Async Directives Committer Journey" complements the above with details of async directives, which is limited to postings today (for Schedules only)

Exploring these boards will reveal the queries they use, which can then be added to `inception_sdk/test_framework/performance/performance_queries.json` for automated extraction.


### Posting Test Boards

For Postings, throughput and latency should both be seen as important, given Postings will likely be subject to round-trip Service Level Agreements (SLA). This means that there is an agreed time for how long it should take to send the request and process the response for a Posting. The following boards are of interest:
- "Postings Processor Pipeline" provides graphs showing latency and throughput of the end-to-end Posting processing.
- "Contract Postings Dashboard" provides graphs showing latency, throughput and decomposition of the pre and post processing execution, although this is specifically focused on the Contract execution and the end-to-end pipeline.

Exploring these boards will reveal the queries they use, which can then be added to `inception_sdk/test_framework/performance/performance_queries.json` for automated extraction.


## Interpreting results

In the simplest scenarios, we are only interested in the throughput and/or latency metrics. If these are within the desired ranges, no further investigation is needed.
However, if improvements are needed consider these initial lines of investigation based on where bottlenecks appear:
1. Requirements fetching (i.e. `EngineFetcher.*` metrics): can the Contract architecture or implementation be improved to reduce the amount of data being fetched?
2. Hook execution (i.e. `EngineExecutor.*` metrics): are there inefficiencies in the Contract python code itself? How do the various algorithms scale with volumes of data? It can help to profile this code directly via a simple unit test.
3. Directives committing (i.e. `AsyncDirectivesCommitterPostings`, `AsyncDirectivesCommitterSecondary.*` or `EngineCommitter.*`): can the Contract architecture or implementation be improved to reduce the number of directives to commit?

It is also possible that the maximum performance has been achieved given the test environment's size and/or Vault configuration. In this case it may be helpful to inspect:
- Database metrics, for signs of saturation (e.g. too many connections, reaching max IOPS, abnormally high queue length)
- GRPC metrics (see `gRPC metrics` and `gRPC services` Grafana boards) for signs of specific services being saturated with requests