_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Unit Testing Metrics

When developing the Inception Library features and products, the Build teams create unit tests to test individual functions and some smaller units of code (as detailed in the Inception Test Framework Approach). Some basic metrics about the percentage of the smart contract code that is covered by a corresponding unit test can be obtained by following the approach detailed below. Developers are of course free to choose their tools and guidelines, but here we describe the approach used in the Inception Library. Unit testing metrics can be used as part of the code review process or a functional
testing report.

## Pre-requisites

- Python coverage library (`pip install coverage`)
- Optional: Python pycobertura library (`pip install pycobertura`)
- Optional: Please Build System

## How to judge if coverage is good enough

Ultimately, the definition of "good enough" is based on the judgement of the developer and the team but the following points can help inform the decision:

1. Is at least 70% of the new code covered? Ideally, the entire file should have 70% coverage. If the coverage of a file is low it might be worth creating a separate ticket to develop better coverage. Remember that statement coverage is not the same as coverage. The code coverage tool provides metrics on statement coverage; however it does assess the quality of the tests. Consideration needs to be given to the test cases themselves to ensure that they check edge scenarios and complex calculations. Even a 100% covered file could be badly tested if the tests are not well written.

2. Are all complex or key calculations covered (e.g. interest calculations, fee calculations etc.)?

3. Is the uncovered code hard to test? It is sometimes very difficult to unit test deeply nested `if` statements and `for` loops. If it is difficult to cover a piece of code, the first question should be whether the code could be simplified and refactored.

4. Does the uncovered code contain few failure points or other parts of the Smart Contract Language? Items like Parameters or Balance Addresses will not be explicitly called by unit tests and so will reduce the headline statement coverage percentage. This is acceptable.

## How to get unit testing metrics

Unit test coverage metrics for Smart Contracts are available using the Python `coverage` module. Only the actual smart contract file gets measured.

We currently expose the following settings.

| Name                    | Description                                                                          | CLI Flag                       | Environment Variable             | Default |
|-------------------------|--------------------------------------------------------------------------------------|--------------------------------|----------------------------------|---------|
| Unit test coverage      | Indicates whether the framework will generate unit test coverage stats for contracts | --unit_test_coverage           | INC_UNIT_TEST_COVERAGE           | False   |
| Unit test coverage path | The path to the folder in which coverage reports will be stored.                     | --unit_test_coverage_directory | INC_UNIT_TEST_COVERAGE_DIRECTORY | "."     |

### Using Python unittest

1. Set the environment variable `INC_UNIT_TEST_COVERAGE`:

    ```bash
    export INC_UNIT_TEST_COVERAGE=True
    ```

2. Run your desired unit test:

    ```bash
    python3 -m unittest path/to/unit/test.py
    ```

3. View the metrics:

    Two files are created in the coverage directory for each contract/supervisor covered by the relevant test:

    `test.coverage_contracts_<contract_filename_stem>` (e.g. `test_coverage_casa`) contains a high level coverage report

    `test.coverage_contracts_<contract_filename_stem>.xml` (e.g. `test_coverage_casa.xml`) contains a detailed report including the covered and missed line numbers

### Using Please

1. Set the environment variable `INC_UNIT_TEST_COVERAGE` - or enable it by default via the repository `.plzconfig` file

2. Run the relevant `plz cover` command

    ```bash
    plz cover //path/to/unit/test:test
    ```

3. The coverage is included in the `plz cover` output

## Interpreting unit testing metrics

| Name                                                 | Stmts | Miss | Cover |
|------------------------------------------------------|-------|------|-------|
| library/current_account/contracts/current_account.py | 483   | 39   | 92%   |
| TOTAL                                                | 483   | 39   | 92%   |

Notionally, the aim is for the coverage to reach 100% for unit tests although this is not always feasible and can be misleading. Instead, as noted above, ~70% coverage is the target generally used for anything in the Inception Library, and consider which lines are missed.

## Visualising code coverage

Tools exist to visualise the code coverage. The Python library pycobertura can be used to see which lines are covered or missed, by rendering Covertura coverage files.

```bash
pycobertura show --format html -p /inception --output coverage.html <path_to_report_xml>
```

This will create an html file in the current directory which when opened in a browser, displays the coverage in a visual manner.

## Known Issues

### Missing coverage for `def` statements

The approach to generate Contracts API 3.x contract/feature coverage metrics involves calling `coverage.start()` as part of test setup. As definitions are evaluated at import time, this means we never get coverage for these statements and cannot achieve 100%. This is especially relevant for features, as they are imported by the test module, whereas contracts themselves are not imported.
This issue does not apply to Contracts API 4.x contracts/features.
