# standard libs
from typing import Any, Callable, Union

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)


def mock_utils_get_parameter(parameters: dict[str, Any]) -> Callable:
    """A re-usable mock for improved legibility

    :param parameters: a dictionary or parameter name to parameter value.
    :return: Callable that can be assigned to a mock's side_effect
    """

    def get_parameter(vault, name: str, *args, **kwargs):
        try:
            return parameters[name]
        except KeyError:
            raise KeyError(f"No value mocked for parameter {name}")

    return get_parameter


def mock_supervisor_get_supervisees_for_alias(supervisees: dict[str, list[Any]]) -> Callable:
    """A re-usable mock for improved legibility

    :param supervisees: a dictionary or supervisee alias to list of mock supervisee objects
    :return: Callable that can be assigned to a mock's side_effect
    """

    def get_supervisees_for_alias(vault, alias: str, *args, **kwargs):
        try:
            return supervisees[alias]
        except KeyError:
            raise KeyError(f"No mock supervisees provided for alias {alias}")

    return get_supervisees_for_alias


def mock_utils_get_parameter_for_multiple_vaults(
    parameters_per_vault: dict[Union[SmartContractVault, SuperviseeContractVault], dict[str, Any]]
) -> Callable:
    """A re-usable mock for improved legibility

    :param parameters: a dictionary of vaults to a dictionary of parameter name to parameter value.
    :return: Callable that can be assigned to a mock's side_effect
    """

    def get_parameter(vault, name: str, *args, **kwargs):
        try:
            return parameters_per_vault[vault][name]
        except KeyError:
            raise KeyError(f"No value mocked for vault '{vault}', parameter '{name}'")

    return get_parameter
