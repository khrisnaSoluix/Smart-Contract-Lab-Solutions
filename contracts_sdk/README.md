# Contracts SDK

## Introduction

The Contracts SDK is a Python package that can be used to develop and unit test Smart and Supervisor
Contracts. It fully replaces the Contract Tester library as it offers the same unit testing
capabilities but provides more accurate typing, since it uses the actual Smart and Supervisor
Contract custom types rather than generating a testing-specific version of them. The Contracts SDK
comes with custom Smart and Supervisor Contract types, unit testing utilities and some example unit
tests.

> The Contract Tester library remains supported for Contracts Language API version 3.x, but version
> 4.0+ only supports the Contracts SDK.

## Installation

After downloading and unzipping the 'contracts_sdk' package into directory of your choice, you can
start using its custom types and unit test utilities in your python code by simply importing the
package modules.

### Contracts Language API 4.0

For the Contracts Language API 4.0+, the SDK contains the python package installable using pip. To
ensure `from contracts_api import ...` works in your contract code, install the `contracts_api`
package:

```bash
# Executed from the SDK root directory
pip install .
```

To uninstall the contracts_api package run:

```bash
pip uninstall contracts_api
```

To build a python wheel with a specific `CONTRACTS_API_VERSION` for the `contracts_api` package run:

```bash
# Note that if CONTRACTS_API_VERSION environment variable is not set,
# the package will have the version "0.0.0+latest"

CONTRACTS_API_VERSION="4.5.1" python setup.py bdist_wheel
```

Note each Vault release (including patch version release) will have a single version of the
`contracts_api` package associated to it, so it should be versioned the same as Vault.

## Directory Structure

### example_unit_tests

This directory contains example Smart and Supervisor Contracts with corresponding unit tests
designed using the Contracts SDK.

### utils

This directory contains a collection of utility functions that are used by the SDK and provide
functionality for local testing of sample Contracts.

### versions

This directory contains all of the Contract versions available in a particular Vault release, with
sub-directories separated into Common, Smart Contracts and Supervisor Contracts. These contain the
relevant Contract types and supported library functions for specific versions of Vault.

Sub-directories separating out the components:

```bash
common
contract_modules
smart_contracts
supervisor_contracts
```

Vault functions can be found in:

```bash
lib.py
```

Available types can be found in:

```bash
common/types/__init__.py
```

## Tests

The Contracts SDK comes with unit test utilities; these are base classes that should be used in
Contract unit tests. There are separate base classes for each Contracts API version and for Smart or
Supervisor Contracts.

There are several types of tests:

- `contracts_sdk/example_unit_tests` contains some sample Contracts unit tests using the SDK. These
  tests should be used as an example when writing Contract unit tests.
- `contracts_sdk/utils/tests` contains unit tests for the utilities used in the SDK. These are tests
  of the internal SDK code.
- `contracts_sdk/versions/version_*/*/tests/test_lib.py` contains unit tests against the Vault
  object. These are tests of the internal SDK code.
- `contracts_sdk/versions/version_*/*/tests/test_types.py` contains unit tests against the Contract
  types. These are tests of the internal SDK code.

To run the tests:

```bash
cd <parent of the sdk directory>
python3 -m unittest
```

### Contracts Language API 4.0

The unit tests for the Smart, Supervisor Contracts and Contract Modules of api version `4.0.0` can
be based on the standard unittest python module TestCase classes, importing the contracts being
tested as standard python modules. To import any custom types and the VaultFunctions classes for
assertions or data mocking, one can either install the `contracts_api` python package or import
necessary objects from the unzipped SDK in the local directory directly.

### Testing Contracts with Contract module dependencies

Note that any Smart or Supervisor Contracts that import Contract modules in their code need to have
the Contract module packages named by their alias available locally for the imports to work in unit
tests. To ensure that `from contract_modules import module_alias` works in your contract code,
create local directory `contract_modules` with the `module_alias.py` file and add its parent
directory to the python path before running the unit tests:

```bash
contract_modules_path="$(pwd)/example_unit_tests/contracts_api_400"
export PYTHONPATH="${PYTHONPATH}:${contract_modules_path}"
python3 -m unittest
```

> See example_unit_tests/contracts_api_400 for the unit test examples for the Contracts API 4.0.0.
