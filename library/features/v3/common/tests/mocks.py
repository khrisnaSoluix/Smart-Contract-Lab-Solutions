from typing import Any, Callable

from inception_sdk.vault.contracts.types_extension import Vault


def mock_utils_get_parameter(parameters: dict[str, Any]) -> Callable:
    """A re-usable mock for improved legibility

    :param parameters: a dictionary or parameter name to parameter value.
    :return: Callable that can be assigned to a mock's side_effect
    """

    def get_parameter(vault: Vault, name: str, *args, **kwargs):
        try:
            return parameters[name]
        except KeyError:
            raise KeyError(f"No value mocked for parameter {name}")

    return get_parameter
