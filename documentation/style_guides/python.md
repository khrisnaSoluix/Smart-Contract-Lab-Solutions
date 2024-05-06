_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Python

## Linting / Formatting

We use `flake8`, `black` and `isort` to consistently and effortlessly lint and format our python code.

### Why

Formatting can be a divisive and remarkably time-consuming activity. These tools remove the subjectivity and effort, and guarantee a high level of consistency.

### How

We provide configuration for these tools to ensure all developers have the same setup and avoid accidentally reformatting code due to diverging settings. This configuration is available in the `setup.cfg` and `pyproject.toml` files at the root of the repository/release.

The only exception to this approach is for smart contract/supervisor smart contract code. The 'magic' imports that are handled at execution time within the contract-executor service result in a high volume of `F821 undefined name` errors, so we ignore them in each contract file using the `per-file-ignores` option in `setup.cfg`. This allows us to preserve other useful advice/warnings/errors.

We should avoid using exceptions elsewhere unless there are very good reasons. One example of this is the `A001/A002/A003` set of flakes. These are triggered when we use built-in names in assign/argument/class attributes. This is sometimes imposed on us by the platform (e.g. `Account` has an attribute named `id` which shadows the python built-in method). Deviating would cause lots of other headaches (e.g. an extra translation layer needed across a large number of resources to convert the renamed attribute to `id` when making API requests), so we prefer to allow them in relevant files only.

`isort` has been configured within the `setup.cfg` file to organise our import statements in a readable order. This will run during the pre-commit stages so you do not need to worry about your imports being ordered. Please note that:

* you do **not** need to add comments any more to signify different sections - isort generates these when it runs
* when using `# noqa` during imports, please do **not** include an error code as this causes a bug with isort, i.e. do `# noqa` rather than `# noqa: A001`

### Custom Linters

#### flake8_Contracts

We have introduced a custom `flake8` plugin to flag the use of anti-patterns and other implementation no-nos within contracts, supervisor contracts and contract modules. The individual rules are associated to guidance from the `documentation/` sub-folders, which should provide the contract writer with more guidance. The plugin is currently loaded via the `setup.cfg` file's `[flake8:local-plugins]` section.

## Type Hints

We use type hints wherever possible, including contracts and framework assets, with a few exceptions.

### Why

Although dynamic typing allows for flexibility, we find that it also leads to bugs where unexpected/wrong datatypes are passed into functions. This may work accidentally until the function is expanded, making debugging tricky. Type hints clarify what the function expects and what to pass in, which helps anyone using it. They also force the writer/maintainer of the method to think about the types it supports and provide appropriate error handling.
Type hints can also enable IDE-level warnings to highlight incorrect usage, which is a useful aid.

### How

We add type hints as per the official Python docs (<https://docs.python.org/3/library/typing.html>) to public and private methods. We make an exception for:

* nested methods, although still encourage type hints, as the re-use is very localised and less prone to confusion
* the `Vault` type in Contracts API 3.x, which isn't available in contracts.

We use `mypy` to enforce this in all Contracts API 4.x code only, as Contracts API 3.x was not syntactically valid python. We provide configuration for `mypy` to ensure all developers have the same setup. This configuration is available in the `pyproject.toml` file at the root of the repository/release.

We provide additional types for `SmartContractVault`, `SuperviseeContractVault` and `SupervisorContractVault`, which represent the various `vault` argument types in the Contracts API 4.x. These do not officially exist in the Contracts API, and are stripped out by the renderer. Please see `inception_sdk/vault/contracts/extensions` for more information on how to deploy this.

We provide a stub-only package to enhance the Contracts API 4.x wheel for use with `mypy`. Please see `inception_sdk/vault/contracts/stubs` for more information on how to deploy this.

Note: As support was not always present in Smart Contracts, there may be legacy code without type hints.

A few examples:

Public method (test framework)

```python
def replace_supervisee_version_ids_in_supervisor(
    supervisor_contract_code: str, supervisee_alias_to_version_id: Dict[str, str]
) -> str:
```

Private method (contract)

```python
def _get_next_schedule_date(
    start_date: datetime, schedule_frequency: str, intended_day: int
) -> datetime:
```

## Docstrings

We use docstrings to clarify more complicated functions' behaviour and inputs/outputs

### Why

Very simple functions can use a suitable name and type hints to convey their inputs, outputs and behaviour. For example `def add(int:a, int:b) -> int` is fairly explicit. However, even in this case and in more complicated cases there may be additional information to provide, or ambiguity to dispel. Type hints often lack context and some relationships between parameters can be impossible to express accurately. The docstring helps with this so that users of the functions, classes etc know what to expect.

### How

Because we use type hints, we don't need to specify the types again (other than when they occur in natural language). We therefore follow the format:

```python
def convert_(input: str) -> str:
    """

    :param input: _description_
    :raises ValueError: _description_
    :return: _description_
    """
```

This maps to the 'sphinx-notypes' format if using VSCode and the `autoDocstring` plugin.

As an example:

```python
def get_balances(
    res: List[Dict[str, Any]], return_latest_event_timestamp: bool = True
) -> DefaultDict[str, TimeSeries]:
    """
    Returns a Balance timeseries by value_timestamp for each account
    The timeseries entries map a given datetime to a DefaultDict of BalanceDimensions to either
    Balance or a TimeSeries of Balances. The latter provides backdating support (i.e. if the view
    of the balances for a value_timestamp changes based on the event_timestamp). The caller is
    expected to know if and when their tests will have triggered backdating, set the
    `return_latest_event_timestamp` parameter accordingly and process the different return type

    WARNING: We do not support multiple events with same value and event_timestamp. Although the
    simulator may enable this, it is not reflective of real Vault behaviour as balance consistency
    constraints and timing would not allow identical insertion_timestamps

    :param res: output from simulation endpoint
    :param return_latest_event_timestamp: If False, the balance timeseries
    maps BalanceDimensions to a Timeseries of Balances. If True it maps BalanceDimensions to the
    last available Balance for the value_timestamp. Use False if you are expecting backdating and
    need to check values for a given value_timestamp at different event_timestamp values
    :return: account ids to corresponding balance timeseries
    """
```
