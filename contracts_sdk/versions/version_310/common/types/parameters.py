import datetime
from decimal import Decimal
from functools import lru_cache

from ....version_300.common.types import parameters as parameters300, UnionItemValue, OptionalValue
from .....utils import exceptions
from .....utils import symbols
from .....utils import types_utils


_parameter_value_type_str = "Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]"


class NumberShape(parameters300.NumberShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, Decimal) and not isinstance(value, int):
            raise exceptions.InvalidSmartContractError(
                f"NumberShape value should be Decimal, instead got {value} of type {type(value)}"
            )


class StringShape(parameters300.StringShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, str):
            raise exceptions.InvalidSmartContractError(
                f"StringShape value should be string, instead got {value} of type {type(value)}"
            )


class AccountIdShape(parameters300.AccountIdShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, str):
            raise exceptions.InvalidSmartContractError(
                f"AccountIdShape value should be string, instead got {value} of type "
                f"{type(value)}"
            )


class DenominationShape(parameters300.DenominationShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, str):
            raise exceptions.InvalidSmartContractError(
                f"DenominationShape value should be string, instead got {value} of type "
                f"{type(value)}"
            )


class DateShape(parameters300.DateShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, datetime.datetime):
            raise exceptions.InvalidSmartContractError(
                f"DateShape value should be datetime, instead got {value} of type {type(value)}"
            )


class OptionalShape(parameters300.OptionalShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, OptionalValue):
            raise exceptions.InvalidSmartContractError(
                f"OptionalShape value should be OptionalValue, instead got {value} of type "
                f"{type(value)}"
            )

        if value.value is not None:
            cls.shape.validate_value(value.value)


class UnionShape(parameters300.UnionShape):
    @classmethod
    def validate_value(cls, value):
        if not isinstance(value, UnionItemValue):
            raise exceptions.InvalidSmartContractError(
                f"UnionShape value should be UnionItemValue, instead got {value} of type "
                f"{type(value)}"
            )
        if not any(item.key == value.key for item in cls.items):
            raise exceptions.InvalidSmartContractError(
                f"UnionItemValue with key {value.key} not allowed in this UnionShape"
            )


class Parameter:
    def __init__(self, derived=False, **kwargs):
        kwargs["derived"] = derived
        if not kwargs.pop("_from_proto", False):
            self._validate_attributes(**kwargs)
        for name, value in kwargs.items():
            setattr(self, name, value)

    @staticmethod
    def _validate_attributes(**kwargs):
        level = kwargs["level"]
        default_value = kwargs.get("default_value", None)
        update_permission = kwargs.get("update_permission", None)
        optional = issubclass(kwargs.get("shape", None), OptionalShape)
        derived = kwargs["derived"]
        name = kwargs["name"]
        if (
            level == symbols.ContractParameterLevel.INSTANCE
            and default_value is None
            and not optional
            and not derived
        ):
            raise exceptions.InvalidSmartContractError(
                f"Instance Parameters with non optional shapes must have a default value: {name}"
            )
        if derived and not level == symbols.ContractParameterLevel.INSTANCE:
            raise exceptions.InvalidSmartContractError(
                f"Derived Parameters can only be INSTANCE level: {name}"
            )
        if derived and (default_value or update_permission):
            raise exceptions.InvalidSmartContractError(
                f"Derived Parameters cannot have a default value or update permissions: {name}"
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Parameter",
            docstring="A contract parameter.",
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new Parameter.",
                args=cls._public_attributes(language_code),  # noqa SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="name",
                type="str",
                docstring="""
                    The name of the Parameter. This is how the Parameter is referred to
                    programmatically by the Smart Contract when it fetches the Parameter
                    value from the ParameterTimeseries.
                """,
            ),
            types_utils.ValueSpec(
                name="description",
                type="Optional[str]",
                docstring="""
                    The description of the Parameter. This may be used in a front-end
                    user interface to show a user the meaning of the Parameter.
                """,
            ),
            types_utils.ValueSpec(
                name="display_name",
                type="Optional[str]",
                docstring="The name of Parameter as may be show in a front-end user interface.",
            ),
            types_utils.ValueSpec(
                name="level", type="Level", docstring="The level of the Parameter."
            ),
            types_utils.ValueSpec(
                name="value",
                type="Optional[%s]" % _parameter_value_type_str,
                docstring="The value of the Parameter.",
            ),
            types_utils.ValueSpec(
                name="default_value",
                type="Optional[%s]" % _parameter_value_type_str,
                docstring="The default value of the Parameter.",
            ),
            types_utils.ValueSpec(
                name="update_permission",
                type="UpdatePermission",
                docstring="""
                    Whether the user is allowed to update the Parameter or not.
                    Only applicable to INSTANCE level Parameter objects.
                """,
            ),
            types_utils.ValueSpec(
                name="derived",
                type="Optional[bool]",
                docstring="""
                    Whether this parameter is derived or not.
                    Only applicable to INSTANCE level Parameter objects.
                """,
            ),
            types_utils.ValueSpec(
                name="shape",
                type=(
                    "Union[AccountIdShape, DateShape, DenominationShape, NumberShape, "
                    "OptionalShape, StringShape, UnionShape]"
                ),
                docstring="The shape of the parameter.",
            ),
        ]
