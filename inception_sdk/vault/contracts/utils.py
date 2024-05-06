# standard libs
import ast
import inspect
from types import ModuleType

# third party
import semantic_version

# inception sdk
from inception_sdk.common.python import ast_utils


class InvalidApiMetadata(Exception):
    pass


class MissingApiMetadata(Exception):
    pass


def is_module_in_contracts_language_v4(module: ast.Module | ModuleType) -> bool:
    """
    Determines whether a module is a contract written in contracts language v4.
    The api version must be defined in the metadata as per the Contracts API:
    `api = "major.minor.patch"`
    :param module: the module to check
    :raises InvalidApiException: raised if `api` is found, but not an ast.Constant or
    not valid semver
    :raises MissingApiException: raised if `api` is not found
    :return: True if the contract is v4, False otherwise
    """
    if isinstance(module, ModuleType):
        _module = ast.parse(inspect.getsource(module))
    else:
        _module = module

    for stmt in _module.body:
        if isinstance(stmt, ast.Assign) and ast_utils.get_assign_node_target_name(stmt) == "api":
            if not isinstance(stmt.value, ast.Constant):
                raise InvalidApiMetadata(
                    f"Unable to determine contract language version from template.\n"
                    f"`api` value must be an ast.Constant but is {type(stmt)}"
                )
            version_string = str(stmt.value.value)
            if not semantic_version.validate(version_string):
                raise InvalidApiMetadata(
                    f"Unable to determine contract language version from template.\n"
                    f"Could not parse `api` value {version_string} as a semantic version"
                )
            return semantic_version.Version(version_string).major == 4

    raise MissingApiMetadata(
        "Unable to determine contract language version from template.\n"
        "Could not find an `api` assignment"
    )
