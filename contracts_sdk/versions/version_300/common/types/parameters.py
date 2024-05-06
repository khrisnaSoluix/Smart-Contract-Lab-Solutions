from copy import deepcopy
from decimal import Decimal
from functools import lru_cache

from .....utils import exceptions as utils_exceptions
from .....utils import symbols
from .....utils import types_utils
from .....utils.symbols import ContractParameterLevel


class Parameter:
    def __init__(self, **kwargs):
        if not kwargs.pop("_from_proto", False):
            self._validate_attributes(**kwargs)
        for name, value in kwargs.items():
            setattr(self, name, value)

    @staticmethod
    def _validate_attributes(**kwargs):
        if (
            kwargs["level"] == ContractParameterLevel.INSTANCE
            and kwargs.get("default_value", None) is None
            and not issubclass(kwargs.get("shape", None), OptionalShape)
        ):
            name = kwargs["name"]
            raise utils_exceptions.InvalidSmartContractError(
                f"Instance Parameters with non optional shapes must have a default value: {name}"
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
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
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
                name="shape",
                type=(
                    "Union[AccountIdShape, DateShape, DenominationShape, NumberShape, "
                    "OptionalShape, StringShape, UnionShape]"
                ),
                docstring="The shape of the parameter.",
            ),
        ]


class Shape:
    def __new__(cls, **kwargs):
        if not kwargs.pop("_from_proto", False):
            missing_kwargs = [
                kwarg for kwarg in kwargs.keys() if kwarg not in cls._attribute_names()
            ]  # noqa: SLF001, E501
            if missing_kwargs:
                raise utils_exceptions.InvalidSmartContractError(
                    f"{cls.__name__} does not have attribute"
                    f"{'s' if len(missing_kwargs) > 1 else ''} "
                    f"{', '.join(repr(missing_kwarg) for missing_kwarg in missing_kwargs)}"
                )

        fields = {}
        for name in cls._attribute_names():  # noqa: SLF001
            if hasattr(cls, name):
                if name == "items":
                    fields[name] = [item() for item in cls.items]
                else:
                    fields[name] = deepcopy(getattr(cls, name))

        fields.update(kwargs)

        return type(cls.__name__, (cls,), fields)

    @classmethod
    @lru_cache()
    def _attribute_names(cls):
        return set(cls._spec().public_attributes.keys())  # noqa: SLF001

    @classmethod
    def validate_value(cls, value):
        pass


class NumberShape(Shape):
    def __new__(cls, **kwargs):
        # convert int values to decimals
        for attr in ["min_value", "max_value", "step"]:
            value = kwargs.get(attr, None)
            if isinstance(value, int):
                kwargs[attr] = Decimal(value)
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="NumberShape",
            docstring="""
                A Parameter shape defining a floating-point number.

                Metadata `max_value`, `min_value` and `step` can be associated with the parameter,
                but not all metadata is validated by Vault. Only `GLOBAL` and `INSTANCE` level
                parameter fields `max_value` and `min_value` are validated.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new NumberShape.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="kind",
                type="Optional[NumberKind]",
                docstring="Metadata describing what the number represents.",
            ),
            types_utils.ValueSpec(
                name="min_value",
                type="Optional[Decimal]",
                docstring="Metadata describing the minimum allowed numerical value.",
            ),
            types_utils.ValueSpec(
                name="max_value",
                type="Optional[Decimal]",
                docstring="Metadata describing the maximum allowed numerical value.",
            ),
            types_utils.ValueSpec(
                name="step",
                type="Optional[Decimal]",
                docstring="Metadata describing the step in allowed values.",
            ),
        ]


class StringShape(Shape):
    def __new__(cls, **kwargs):
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="StringShape",
            docstring="A Parameter shape defining a string.",
            public_attributes=[],
            public_methods=[],
        )


class AccountIdShape(Shape):
    def __new__(cls, **kwargs):
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="AccountIdShape",
            docstring="A Parameter shape defining an Account id (a string).",
            public_attributes=[],
            public_methods=[],
        )


class DenominationShape(Shape):
    def __new__(cls, **kwargs):
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DenominationShape",
            docstring="A Parameter shape defining an denomination (a string).",
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new DenominationShape.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="permitted_denominations",
                type="Optional[List[str]]",
                docstring="Metadata describing which denominations are permitted.",
            ),
        ]


class DateShape(Shape):
    def __new__(cls, **kwargs):
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DateShape",
            docstring="""
                Specifies that the enclosing [Parameter](#classes-Parameter) object refers to a
                date, and whose value is a Python datetime. The datetime assignment takes the form
                `datetime(YYYY, MM, DD, hour=HH, minute=MM, second=SS)`, where the datetime
                value needs to be a valid date. Any incorrect date format will trigger an
                `IllegalPython` error.

                min_date and max_date may optionally be set to bound acceptable values.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new DateShape.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="min_date",
                type="Optional[datetime]",
                docstring="Metadata describing which the earliest allowed date.",
            ),
            types_utils.ValueSpec(
                name="max_date",
                type="Optional[datetime]",
                docstring="Metadata describing which the latest allowed date.",
            ),
        ]


class OptionalShape(Shape):
    def __new__(cls, shape):
        return super().__new__(cls, shape=shape)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="OptionalShape",
            docstring="Specifies that the enclosed Shape is optional.",
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new OptionalShape.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="shape",
                type="Union[NumberShape, StringShape, DateShape, UnionShape]",
                docstring="The optional inner Shape.",
            ),
        ]


class OptionalValue:
    def __init__(self, value=None):
        self.value = value

    def is_set(self):
        return self.value is not None

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="OptionalValue",
            docstring="Specifies an optional Parameter value",
            public_attributes=[
                types_utils.ValueSpec(
                    name="value", type="Any", docstring="The value, if specified."
                )
            ],
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=[
                    types_utils.ValueSpec(
                        name="value",
                        type=f"Optional[{_parameter_value_type_str}]",
                        docstring="The optional parameter value.",
                    )
                ],
            ),
            public_methods=[
                types_utils.MethodSpec(
                    name="is_set",
                    docstring="Returns True if the value is set, otherwise False.",
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="bool",
                        docstring="True if the value is set, otherwise False.",
                    ),
                )
            ],
        )


class UnionShape(Shape):
    def __new__(cls, *args, **kwargs):
        if args:
            return super().__new__(cls, items=args)
        return super().__new__(cls, **kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="UnionShape",
            docstring="Specifies a choice of multiple values.",
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new UnionShape.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="items", type="List[UnionItem]", docstring="The allowed values."
            )
        ]


class UnionItem:
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="UnionItem",
            docstring="Specifies a permissible value inside a [UnionShape](#classes-UnionShape).",
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new UnionItem.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="key",
                type="str",
                docstring=("The string value by which this choice is programmatically accessible."),
            ),
            types_utils.ValueSpec(
                name="display_name",
                type="str",
                docstring=(
                    "The name of the option as could be shown on a front-end user interface."
                ),
            ),
        ]


class UnionItemValue:
    # Will eventually hold a typed shaped too.

    def __init__(self, *, key, _from_proto=False):
        if _from_proto:
            self._spec().assert_constructor_args(self._registry, {"key": key})
        self.key = key

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="UnionItemValue",
            docstring="A value inside a [UnionItem](#classes-UnionItem).",
            public_attributes=cls._public_attributes(),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="key",
                type="str",
                docstring="The string value by which this choice is programmatically accessible.",
            )
        ]


_parameter_value_type_str = "Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]"


class ParameterTimeseries(types_utils.Timeseries(_parameter_value_type_str, "parameter value")):
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.merge_class_specs(
            derived_spec=types_utils.ClassSpec(
                name="ParameterTimeseries", docstring="A timeseries of Parameter objects."
            ),
            base_spec=super()._spec(language_code),
        )
