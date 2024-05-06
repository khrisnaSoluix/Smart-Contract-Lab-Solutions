# bcas
Thought Machine Gundala Syariah Project Repository

## Best practices for working
- Create small feature branches for tickets, e.g. `git branch ID-83-part-1`.
- Regularly pull changes from latest main and resolve any conflicts, e.g. `git pull origin main`.
- Raise changes as a pull request when a branch is complete for code review.
- Update pull requests by pushing to your branch on the Github repository e.g. `git push origin ID-83-part-1`
- Before merging changes, make sure all linting checks, unit, sim and E2E tests pass.


## Linting the code
TM style is to use both `black` and `flake8` to format our Python code.

Installation:

```$ pip3 install black```

```$ pip3 install flake8```


Running black:

```$ black --line-length=100 exercise/bcas```

Running flake8 (picks up configuration from .flake8 file):

```$ flake8 exercise/bcas```

## Running tests

Unit tests:

```$ python3 -m unittest exercise.bcas.<product>.contracts.tests.unit.<filename>```

Simulation tests:

```$ python3 -m unittest exercise.bcas.<product>.contracts.tests.simulation.<filename>```

E2E tests:

```$ python3 -m unittest exercise.bcas.tests.e2e.<filename>```

Accelerated E2E tests must be run 1 by 1:

```$ python3 -m unittest exercise.bcas.tahapan_wadiah_ib.tests.e2e.test_tahapan_wadiah_ib_product_schedules.WadiahProductSchedulesTest.test_bonus_distribution```

## Unit test coverage

Unit test coverage can be enabled for the Smart Contract by setting the following environment variable:

```$ export INCEPTION_UNIT_TEST_COVERAGE=True```

For the next steps, you may need to install the coverage module:

```$ pip3 install coverage```

Next, run the `tahapan_wadiah_ib_test` unit test which is an aggregation of all our different unit test classes:

``` $ python3 -m unittest exercise.bcas.tahapan_wadiah_ib.contracts.tests.unit.tahapan_wadiah_ib_test```

You can now use ```$ python3 -m coverage report -m``` to look at coverage results for the Smart Contract.

e.g:
```
python3 -m coverage report -m
Name                                                                  Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------------------------
exercise/bcas/tahapan_wadiah_ib/contracts/tahapan_wadiah_ib.py     518      3    99%   644, 1416, 2024
---------------------------------------------------------------------------------------------------
TOTAL                                                                   518      3    99%
```

In addition, we can also check the coverage of any Contract Modules. Currently, we only have the `utils` module.

```$ python3 -m unittest exercise.bcas.common.contract_modules.tests.unit.utils_test.UtilsModuleTest```

```$ python3 -m coverage report -m```

## Github workflows

Github workflows are setup to run the linting checks and unit tests. Results will appear in the 'checks' whenever a PR is raised. The workflows can be found in `.github/workflows`