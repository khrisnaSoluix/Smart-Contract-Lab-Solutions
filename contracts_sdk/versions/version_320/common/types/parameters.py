from ....version_310.common.types import parameters as parameters310

from .....utils import exceptions
from .....utils import symbols


class Parameter(parameters310.Parameter):

    @staticmethod
    def _validate_attributes(**kwargs):
        level = kwargs['level']
        default_value = kwargs.get('default_value', None)
        update_permission = kwargs.get('update_permission', None)
        optional = issubclass(kwargs.get('shape', None), parameters310.OptionalShape)
        derived = kwargs['derived']
        name = kwargs['name']
        if (
            level == symbols.ContractParameterLevel.INSTANCE and default_value is None and
            not optional and not derived
        ):
            raise exceptions.InvalidSmartContractError(
                f'Instance Parameters with non optional shapes must have a default value: {name}'
            )
        if (
            not optional and isinstance(default_value, parameters310.OptionalValue)
        ):
            raise exceptions.InvalidSmartContractError(
                f'Non optional shapes must have a non optional default value: {name}'
            )
        if derived and not level == symbols.ContractParameterLevel.INSTANCE:
            raise exceptions.InvalidSmartContractError(
                f'Derived Parameters can only be INSTANCE level: {name}'
            )
        if derived and (default_value or update_permission):
            raise exceptions.InvalidSmartContractError(
                f'Derived Parameters cannot have a default value or update permissions: {name}'
            )
