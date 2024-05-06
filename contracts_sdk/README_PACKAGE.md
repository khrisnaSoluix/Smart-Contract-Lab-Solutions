# The contracts_api python package

## Introduction

The `contracts_api` is a Python package that can be used to develop and unit test Smart and
Supervisor Contracts and Contract Modules. This package contains the version 4.x of the Contracts
Language API, therefore it can be used to develop 4.x version Contracts. The package itself is
versioned and released together with Vault releases. The `contracts_api` package includes custom
types and objects, smart and supervisor contracts libraries and the contract language utils.

## Installation

To install the `contracts_api` python package use `pip`:

```bash
pip install contracts_api.whl
```

To uninstall the contracts_api package run:

```bash
pip uninstall contracts_api
```

## Contracts development and unit tests

The unit tests for the Smart, Supervisor Contracts and Contract Modules of API version 4.x can be
based on the standard unittest python module TestCase classes, importing the contracts being tested
as standard python modules. To import any custom types and the VaultFunctions classes for assertions
or data mocking, one needs to have the `contracts_api` python package installed.

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
