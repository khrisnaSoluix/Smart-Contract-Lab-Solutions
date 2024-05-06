_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# E2E Tests

## Use of Retry parameters

Avoid using custom retry parameter values inside tests

### Why

The retry parameters (`max_retries`, `timeout`, `sleep_time`, `back_off`) are useful tools to help write reliable tests in non-kafka scenarios. They help cater for processing delays that can mean an expected result is only eventually reached. This in a common scenario with any asynchronous API. These unpredictable delays can result in test failures that would not have occurred if the outcome was checked a small time later. As the intent of e2e tests is not to assess performance, we prefer to minimise the impact by retrying where possible.
However, setting these parameters inside tests promotes confusion and inconsistency:

1. These parameters are not relevant to tests using kafka helpers, but this may not be clear to a test reader and is misleading
2. Consider a test to retrieve an account update, which is updated asynchronously, and imagine that this test requires a custom back_off to pass reliably. If we make this change in the test, the next test writer with a similar scenario will need to make the same realisation, which may well result in interim flaky behaviour and extra work to then resolve this. If instead we were to update the helper to retrieve account updates, we would ensure all reliability for all other tests performing this step, usually at negligible cost.

### How

Set custom retry parameter values within the helper itself.

## Testing Internal Accounts

Internal accounts and their balances are not typically tested themselves in e2e tests for a few reasons:

1. Asserting on internal account balances in e2e tests is non-trivial. This is because:

    - Internal account balances are queried via the `/v1/ledger-balances` endpoint, which provides the balance value as of a given ledger_timestamp. As this corresponds to the PIB insertion timestamp, accelerated tests could prove problematic.
    - The e2e test framework allows internal accounts to be shared between products, and always shares them between tests for a given product. Guaranteeing an isolated test result at a balance level is therefore complex as we would not be able to distinguish balance updates from one product vs another, or even one product test vs another test.

    While isolating internal accounts on a per-test basis would mitigate the last bullet point above, it would also create a much larger number of internal accounts than is intended for regular use, and so this approach would need verification.

2. Internal account balances are typically verified using a simulation test. This is because internal accounts always accept postings, so e2e tests do not provide additional coverage to simulation tests, and simulation tests are less expensive to run.

If there is a valid use case for testing internal account balances in e2e tests, one option would be to assert on the postings created by the test account's contract as opposed to checking the internal account balances directly.
