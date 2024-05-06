import bisect
import inspect
from abc import ABC
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from inspect import isclass
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from . import exceptions, symbols


class StrictInterface(ABC):
    """
    This class enforces the 'public' interface on derived classes, and is used to ensure the
    shared Vault interface used in tests matches the actual Vault interface.
    """

    def __new__(cls, *args, **kwargs):

        abstract_methods = set()
        allow_non_abstract = ["get_posting_batches"]
        for base in inspect.getmro(cls):
            try:
                abstract_methods = abstract_methods.union(base.__abstractmethods__)
            except AttributeError:
                continue

        for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            if name in abstract_methods:
                continue
            if name in allow_non_abstract:
                continue
            raise TypeError(f"Method {repr(name)} missing from public abstract base class")
        return super().__new__(cls)


class TypeQualifier:
    def __init__(
        self,
        optional: bool = False,
        repeated: bool = False,
        deprecated: bool = False,
        description: Optional[str] = None,
    ):
        self._optional = optional
        self._repeated = repeated
        self._deprecated = deprecated
        self._description = description

    def _check(
        self,
        owner_str: str,
        value: Optional[List[Any]],
        names: Tuple[str],
        expected_types: Tuple[Any],
    ):
        if value is None:
            if not self._optional:
                raise TypeError(f"{owner_str} is not optional")
            return

        if self._repeated:
            if not isinstance(value, (list, tuple)):
                raise TypeError(
                    f"{owner_str} expects an iterable of {' or '.join(names)}, instead got "
                    f"non-iterable {type(value).__name__} ({value})"
                )
            bad_values = [v for v in value if not self._is_valid(v, expected_types)]

            if bad_values:
                bad_types = set(type(v).__name__ for v in bad_values)
                raise TypeError(
                    f"{owner_str} expects an iterable of {' or '.join(names)}, instead got "
                    f"iterable containing {' and '.join(bad_types)}"
                )

        elif not self._is_valid(value, expected_types):
            raise TypeError(
                f"{owner_str} expects {' or '.join(names)}, instead got {type(value).__name__} "
                f"({value}))"
            )

    def _make_type_docstring(self, names: List[str]) -> str:
        if self._repeated:
            return make_docstring_seq(make_docstring(names))
        else:
            return make_docstring(names)

    def _make_docstring(self, key: str, names: List[str]) -> str:
        return (
            f"{{description: {self._description or ''}, name: {key}, "
            f"type: {repr(self._make_type_docstring(names))}}}"
        )

    @staticmethod
    def _is_valid(value: Any, expected_types: Tuple[Any]) -> bool:
        # Return whether value is valid for at least one of the expected types
        return any(
            expected_type._is_valid_value(value)  # noqa:SLF001
            if hasattr(expected_type, "_is_valid_value")
            else isinstance(value, expected_type)
            for expected_type in expected_types
        )

    def make_spec(self) -> Dict[str, Any]:
        return {
            "type": self.make_type_docstring(),
            "optional": self._optional,
            "repeated": self._repeated,
            "deprecated": self._deprecated,
            "description": dedent_and_strip(self._description or ""),
        }


class TypeFixed(TypeQualifier):
    def __init__(
        self,
        name: str,
        *,
        optional: bool = False,
        repeated: bool = False,
        deprecated: bool = False,
        description: Optional[str] = None,
    ):
        super().__init__(optional, repeated, deprecated, description)
        self._name = name

    def check(self, owner_str: str, type_registry: Any, value: Optional[List[Any]]):
        self._check(owner_str, value, (self._name,), (type_registry.resolve(self._name),))

    def make_docstring(self, key: str):
        return self._make_docstring(key, [self._name])

    def make_type_docstring(self):
        return self._make_type_docstring([self._name])


def TypedList(item_type: type):
    class _TypedList(list):
        def __init__(self, iterable: Optional[Iterable[Any]] = None, _from_proto: bool = False):
            attrsetter = super().__setattr__
            attrsetter("_from_proto_list", _from_proto)
            self.extend(iterable or ())
            # Override the value of `_from_proto_list` so that any updates in the list are
            # validated based on the spec.
            attrsetter("_from_proto_list", False)

        def append(self, item: Any):
            self._registry.assert_type_name(item_type, item, f"{self.__class__.__name__} item")
            list.append(self, item)

        def extend(self, iterable: Iterable[Any]):
            items = list(iterable)
            if not self._from_proto_list:
                for i, item in enumerate(items):
                    self._registry.assert_type_name(
                        item_type, item, f"{self.__class__.__name__} item[{i}]"
                    )
            list.extend(self, items)

        def __setitem__(self, key, value):
            if isinstance(key, int):
                if not self._from_proto_list:
                    self._registry.assert_type_name(
                        item_type, value, f"{ self.__class__.__name__} item"
                    )
            elif isinstance(key, slice):
                value = list(value)
                if not self._from_proto_list:
                    for v in value:
                        self._registry.assert_type_name(
                            item_type, v, f"{self.__class__.__name__} item"
                        )
            # else: Fall through and let list handle the key error
            list.__setitem__(self, key, value)

        def __add__(self, other):
            result = self.__class__(self)  # Copy self
            result.extend(other)
            return result

        def __iadd__(self, other):
            self.extend(other)
            return self

        @classmethod
        @lru_cache()
        def _spec(cls, language_code=symbols.Languages.ENGLISH) -> ClassSpec:
            if language_code != symbols.Languages.ENGLISH:
                raise ValueError("Language not supported")

            return ClassSpec(
                name="TypedList",
                docstring="A list that enforces the type of members.",
                public_attributes=[],
                constructor=ConstructorSpec(
                    docstring="",
                    args=[
                        ValueSpec(
                            name="iterable",
                            type=f"Optional[List[{item_type}]]",
                            docstring="An optional iterable of initial items to be added.",
                        )
                    ],
                ),
                public_methods=[],
            )

    return _TypedList


def TypedDefaultDict(dict_type: type):
    class _TypedDefaultDict(dict):
        def __init__(
            self,
            default_factory: Optional[Any] = None,
            mapping: Optional[Dict[Any, Any]] = None,
            _from_proto: bool = False,
        ):
            self.default_factory = default_factory
            if mapping is not None and not isinstance(mapping, Mapping):
                raise TypeError("TypedDict init expects Mapping object")
            if mapping:
                # Bypass initial checks if the dict populated from proto
                if not _from_proto:
                    self._registry.assert_type_name(
                        dict_type, mapping, f"{self.__class__.__name__} key: value"
                    )
            else:
                mapping = {}
            super(_TypedDefaultDict, self).__init__(mapping)

        def __missing__(self, key):
            if self.default_factory is None:
                raise KeyError(key)
            value = self.default_factory(key)
            temp_dict = {key: value}
            # Always check the type of new key value pair set by end user
            self._registry.assert_type_name(
                dict_type, temp_dict, f"{self.__class__.__name__} key: value"
            )
            self[key] = value
            return value

        def __getitem__(self, key):
            try:
                return dict.__getitem__(self, key)
            except KeyError:
                return self.__missing__(key)

        def __setitem__(self, key, value):
            temp_dict = {key: value}
            # Always check the type of new key value pair set by end user
            self._registry.assert_type_name(
                dict_type, temp_dict, f"{self.__class__.__name__} key: value"
            )
            super(_TypedDefaultDict, self).__setitem__(key, value)

        # Used in private Contracts API library
        def _set_item_custom(self, key, value, _from_proto=False):
            temp_dict = {key: value}
            # Bypass initial checks of new key value pairs if populated from proto
            if not _from_proto:
                self._registry.assert_type_name(
                    dict_type, temp_dict, f"{self.__class__.__name__} key: value"
                )
            super(_TypedDefaultDict, self).__setitem__(key, value)

        def update(self, other_dict: Dict[Any, Any] = None, **kwargs):  # type: ignore
            _from_proto = kwargs.pop("_from_proto", False)
            # Bypass initial checks of the other dict if populated from proto
            if other_dict and not _from_proto:
                self._registry.assert_type_name(
                    dict_type, other_dict, f"{self.__class__.__name__} key: value"
                )
            # Bypass initial checks of new key value pairs if populated from proto
            if kwargs and not _from_proto:
                self._registry.assert_type_name(
                    dict_type, kwargs, f"{self.__class__.__name__} key: value"
                )
            super(_TypedDefaultDict, self).update(other_dict, **kwargs)  # type: ignore

        def setdefault(self, key: Any, default: Any = None):
            if key in self:
                return self[key]
            temp_dict = {key: default}
            # Always check the type of new key value pair set by end user
            self._registry.assert_type_name(
                dict_type, temp_dict, f"{self.__class__.__name__} key: value"
            )
            super(_TypedDefaultDict, self).setdefault(key, default)

        def copy(self):
            return type(self)(self.default_factory, self, _from_proto=True)

    return _TypedDefaultDict


class NativeObjectSpec:
    """
    A NativeObjectSpec is an object that is defined by Python or an included third party library.
    If specified, the docs field links to the appropriate third party webpage, otherwise the link
    is inferred from the object and package.
    """

    def __init__(
        self,
        *,
        name: str,
        object: Any,
        package: Optional[Any] = None,
        docs: Optional[str] = None,
        description: str = "",
    ):
        self.name = name
        self.object = object
        self.package = package
        self.docs = docs
        self.description = description


class ValueSpec:
    """A Specification defining an exposed value."""

    def __init__(self, *, name: str, type: str, docstring: str):
        self.name = name
        self.docstring = docstring
        self.type = type


class FixedValueSpec:
    """A Specification defining a fixed value."""

    def __init__(self, *, name: str, type: str, fixed_value: Any, docstring: str):
        self.name = name
        self.docstring = docstring
        self.fixed_value = fixed_value
        self.type = type


class ReturnValueSpec:
    """A Specification defining an exposed value."""

    def __init__(self, *, type: str, docstring: str):
        self.docstring = docstring
        self.type = type


class EnumSpec:
    """A Specification defining a custom enum."""

    def __init__(self, *, name: str, docstring: str, members: List[Any], show_values: bool = False):
        self.name = name
        self.docstring = docstring
        self.members = members
        self.show_values = show_values


class Example:
    def __init__(self, *, title: str, code: str):
        self.title = title
        self.code = code


class MethodSpec:
    """A Specification defining a custom method."""

    def __init__(
        self,
        *,
        name: str,
        docstring: str,
        args: List[ValueSpec] = None,
        return_value: Optional[Union[ReturnValueSpec, ValueSpec]] = None,
        examples: List[Example] = None,
    ):
        self.name = name
        self.docstring = docstring
        self.args = {arg.name: arg for arg in (args or [])}
        self.return_value = return_value
        self.examples = examples or []

    def assert_args(self, type_registry: Any, cls_name, args: Dict[str, ValueSpec]):
        for arg_name, arg_value in args.items():
            arg_spec = self.args.get(arg_name)
            if not arg_spec:
                raise ValueError(
                    f"ArgSpec missing on class {cls_name} for method {self.name} arg "
                    f"{repr(arg_name)}"
                )
            type_registry.assert_type_name(
                arg_spec.type,
                arg_value,
                f"{cls_name}.{self.name} arg {repr(arg_name)}",
            )

    def arg_names(self):
        return self.args.keys()


class ExceptionSpec:
    """A Specification defining a custom Exception"""

    def __init__(self, name: str, docstring: str, constructor_args: List[ValueSpec] = None):
        self.name = name
        self.docstring = docstring
        self.constructor_args = constructor_args or []


class ConstructorSpec(MethodSpec):
    """A Specification defining a constructor"""

    def __init__(self, docstring: str, args: List[ValueSpec]):
        self.docstring = docstring
        self.args = {arg.name: arg for arg in args}

    def assert_args(self, type_registry: Any, cls_name: str, args: Dict[str, ValueSpec]):
        for arg_name, arg_value in args.items():
            arg_spec = self.args.get(arg_name)
            if not arg_spec:
                raise ValueError(
                    f"ArgSpec missing on class {cls_name} for constructor arg {repr(arg_name)}"
                )
            type_registry.assert_type_name(
                arg_spec.type, arg_value, f"{cls_name}.__init__ arg {repr(arg_name)}"
            )


class ClassSpec:
    """A Specification defined a custom defined class."""

    def __init__(
        self,
        *,
        name: str,
        docstring: str,
        public_attributes: Optional[List[ValueSpec]] = None,
        constructor: Optional[Any] = None,
        public_methods: Optional[List[MethodSpec]] = None,
    ):
        self.name = name
        self.docstring = docstring
        self.public_attributes: Dict[Any, ValueSpec] = (
            {public_attribute.name: public_attribute for public_attribute in public_attributes}
            if public_attributes is not None
            else {}
        )
        self.constructor = constructor
        self.public_methods: Dict[str, MethodSpec] = (
            {public_method.name: public_method for public_method in public_methods}
            if public_methods is not None
            else {}
        )

    def assert_constructor_args(self, type_registry, method_args):
        if not self.constructor:
            raise ValueError(f"ConstructorSpec missing on class {self.name}")
        self.constructor.assert_args(type_registry, self.name, method_args)

    def assert_method_args(self, type_registry, method_name, method_args):
        method_spec = self.public_methods.get(method_name)
        if not method_spec:
            raise ValueError(
                f"MethodSpec missing on class {self.name} for method {repr(method_name)}"
            )
        method_spec.assert_args(type_registry, self.name, method_args)

    def assert_attribute_value(self, type_registry, name, value):
        attribute_spec = self.public_attributes.get(name)
        if not attribute_spec:
            raise exceptions.StrongTypingError(
                f"ValueSpec missing on class {self.name} for attribute {name}"
            )
        type_registry.assert_type_name(attribute_spec.type, value, f"{self.name}.{name}")


class DecoratorSpec:
    """Specification for custom defined decorators."""

    def __init__(
        self,
        *,
        name,
        object,
        docstring="",
        args=None,
        smart_contract_args=None,
        supervisor_args=None,
    ):
        self.name = name
        self.object = object
        self.docstring = docstring
        self.args = args or []
        self.smart_contract_args = smart_contract_args or []
        self.supervisor_args = supervisor_args or []

    def __call__(self, *args, **kwargs):
        return self.object(*args, **kwargs)


class _IntWithValueProperty(int):
    @property
    def value(self):
        return self


class _StrWithValueProperty(str):
    @property
    def value(self):
        return self


_WITH_VALUE_PROPERTY_CLASSES = {int: _IntWithValueProperty, str: _StrWithValueProperty}


def Enum(
    *,
    name: str,
    key_value_dict: Dict[str, Any],
    docstring: Optional[str] = None,
    show_values: bool = False,
) -> type:

    valid_values = set(v for v in key_value_dict.values())

    def _type_check(value) -> bool:
        return value in valid_values

    key_value_dict = {
        key: _WITH_VALUE_PROPERTY_CLASSES[type(value)](value)
        for key, value in key_value_dict.items()
    }
    for k, v in key_value_dict.items():
        v.name = k

    @lru_cache()
    def _spec() -> EnumSpec:
        return EnumSpec(
            name=name,
            docstring=docstring or "",
            members=[
                {"name": name, "value": value}
                for name, value in sorted(key_value_dict.items())
                if "UNKNOWN" not in name
            ],
            show_values=show_values,
        )

    members = dict(key_value_dict)
    members["_spec"] = _spec
    members["_type_check"] = _type_check

    return type(name, (), members)


def Timeseries(_item_type, _item_desc, _return_on_empty=None):

    base_class = TypedList(f"Tuple[datetime, {_item_type}]")

    class _Timeseries(base_class):
        item_type = _item_type
        item_desc = _item_desc
        return_on_empty = _return_on_empty

        def __init__(self, *args, **kwargs):
            self._from_proto_list = kwargs.get("_from_proto", False)
            super().__init__(*args, **kwargs)
            self._from_proto_list = False

        @staticmethod
        def _select_timestamp_or_date(
            timestamp: Optional[datetime] = None, date: Optional[datetime] = None
        ):
            if timestamp and not date:
                return timestamp
            elif date and not timestamp:
                return date
            else:
                raise exceptions.StrongTypingError("Specify date or timestamp, not both")

        def at(
            self,
            *,
            timestamp: Optional[datetime] = None,
            date: Optional[datetime] = None,
            inclusive: bool = True,
        ):
            real_timestamp = self._select_timestamp_or_date(timestamp, date)
            self._spec().assert_method_args(self._registry, "at", {"timestamp": real_timestamp})
            start_timestamps = [self._timestamp_from_item(entry) for entry in self]
            if inclusive:
                # bisect_right gives the index of the first entry strictly exceeding the timestamp
                index = bisect.bisect_right(start_timestamps, real_timestamp) - 1
            else:
                # bisect_left gives the index of the first entry exceeding or equal to the timestamp
                index = bisect.bisect_left(start_timestamps, real_timestamp) - 1
            if index >= 0:
                return self._value_from_item(self[index])
            if self.return_on_empty is not None:
                return self.return_on_empty()
            raise exceptions.StrongTypingError(f"No values provided as of date {real_timestamp}")

        def before(self, *, timestamp: Optional[datetime] = None, date: Optional[datetime] = None):
            real_timestamp = self._select_timestamp_or_date(timestamp, date)
            self._spec().assert_method_args(self._registry, "before", {"timestamp": real_timestamp})
            return self.at(date=real_timestamp, inclusive=False)

        def latest(self):
            if not self:
                if self.return_on_empty is not None:
                    return self.return_on_empty()
                raise exceptions.StrongTypingError("No values provided")
            return self._value_from_item(self[-1])

        def all(self):
            return [(self._timestamp_from_item(item), self._value_from_item(item)) for item in self]

        def _timestamp_from_item(self, item) -> datetime:
            return item[0]

        def _value_from_item(self, item) -> _item_type:
            return item[1]

        @classmethod
        @lru_cache()
        def _spec(cls, language_code=symbols.Languages.ENGLISH) -> ClassSpec:
            if language_code != symbols.Languages.ENGLISH:
                raise ValueError("Language not supported")

            item_desc = cls.item_desc
            return merge_class_specs(
                derived_spec=ClassSpec(
                    name="Timeseries",
                    docstring="A generic timeseries.",
                    public_attributes=[],
                    public_methods=[
                        MethodSpec(
                            name="at",
                            docstring=(
                                f" Returns the latest available {item_desc} as of the given "
                                "timestamp."
                            ),
                            args=[
                                ValueSpec(
                                    name="timestamp",
                                    type="datetime",
                                    docstring=(
                                        "The timestamp as of which to fetch the "
                                        f"latest {item_desc}."
                                    ),
                                ),
                            ],
                            return_value=ReturnValueSpec(
                                type=cls.item_type,
                                docstring=(f"The latest {item_desc} as of the timestamp provided."),
                            ),
                        ),
                        MethodSpec(
                            name="before",
                            docstring=(
                                f"Returns the latest available {item_desc} as of just before the "
                                "given timestamp."
                            ),
                            args=[
                                ValueSpec(
                                    name="timestamp",
                                    type="datetime",
                                    docstring=(
                                        "The timestamp just before which to fetch the "
                                        f"latest {item_desc}."
                                    ),
                                ),
                            ],
                            return_value=ReturnValueSpec(
                                type=cls.item_type,
                                docstring=(
                                    f"The latest {item_desc} as of just before the timestamp "
                                    "provided."
                                ),
                            ),
                        ),
                        MethodSpec(
                            name="latest",
                            docstring=f"Returns the latest available {item_desc}.",
                            args=[],
                            return_value=ReturnValueSpec(
                                type=cls.item_type,
                                docstring=f"The latest available {item_desc}.",
                            ),
                        ),
                        MethodSpec(
                            name="all",
                            docstring=(
                                f"Returns a list of all available {item_desc} values across time."
                            ),
                            args=[],
                            return_value=ReturnValueSpec(
                                type=f"List[Tuple[datetime, {cls.item_type}]]",
                                docstring=f"All available {item_desc} values and their timestamps.",
                            ),
                        ),
                    ],
                ),
                base_spec=base_class._spec(language_code),  # noqa: SLF001
            )

    return _Timeseries


def merge_class_specs(*, derived_spec: ClassSpec, base_spec: ClassSpec) -> ClassSpec:
    """
    Generates a new ClassSpec object by overriding base_spec values with derived_spec
    values where appropriate.
    """
    return ClassSpec(
        name=derived_spec.name,
        docstring=derived_spec.docstring or base_spec.docstring,
        public_attributes=list(
            dict(base_spec.public_attributes, **derived_spec.public_attributes).values()
        ),
        constructor=derived_spec.constructor or base_spec.constructor,
        public_methods=list(dict(base_spec.public_methods, **derived_spec.public_methods).values()),
    )


def transform_const_enum(
    *,
    name: str,
    const_enum: Any,
    docstring: str = None,
    show_values: bool = False,
    hide_keys: Tuple = (),
) -> type:
    """
    Factory creating Enum representation of public.utils.symbols classes that shadow proto enums
    :param const_enum: The class from public.utils.symbols
    """
    key_value_dict = {
        key: value
        for key, value in const_enum.__dict__.items()
        if not key.startswith("__") and key not in hide_keys
    }
    return Enum(
        name=name, key_value_dict=key_value_dict, docstring=docstring, show_values=show_values
    )


class _EnumMember:
    def __init__(self, name, value):
        self.name = name
        self.value = value.value

    def __getitem__(self, key):
        if key == "name":
            return self.name
        if key == "value":
            return self.value
        raise KeyError(f"{key} not found")


def enum_members(cls):
    "Helper function for Language v4+ to enable documentation generator to work with Python Enums"
    return [
        _EnumMember(k, v)
        for k, v in sorted(cls.__dict__.items())
        if not k.startswith("_") and "UNKNOWN" not in k
    ]


class EnumRepr:
    "Mixin for Python enums in Language v4+ to provide shorter representation in messages"

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


def make_docstring(names: List[str]) -> str:
    if len(names) == 1:
        return names[0]
    elif len(names) > 1:
        return f"Union[{', '.join(names)}]"
    else:
        raise ValueError("len(names) must be >= 1")


def make_docstring_seq(name: str) -> str:
    return f"Sequence[{name}]"


def dedent_and_strip(string: str) -> str:
    return dedent(string).strip()


def get_iterator(items: Iterable, hint: str, name, check_empty=False):
    exception_message = f"Expected list of {hint} objects for '{name}', got '{items}'"
    if isinstance(items, str):
        raise exceptions.StrongTypingError(exception_message)
    if check_empty and not items:
        raise exceptions.InvalidSmartContractError(
            f"'{name}' must be a non empty list, got {items}"
        )
    try:
        iterator = iter(items)
    except TypeError:
        raise exceptions.StrongTypingError(exception_message)
    return iterator


def validate_type(
    item: Any,
    expected: Any,
    *,
    check_empty: bool = False,
    is_optional: bool = False,
    hint: Optional[str] = "",
    prefix: Optional[str] = "",
):
    if is_optional and item is None:
        return

    if (
        (
            # handle case where expected contains int and not bool but item is bool
            isinstance(expected, tuple)
            and int in expected
            and bool not in expected
            and type(item) == bool
        )
        or (expected == int and type(item) == bool)
        or (not isinstance(item, expected))
    ):
        if not hint:
            hint = (
                "Union[" + ", ".join([e.__name__ for e in expected]) + "]"
                if isinstance(expected, tuple)
                else str(expected.__name__)
            )
        if is_optional:
            hint += " if populated"

        if item is None:
            item_of_type = "None"
        else:
            item_of_type = (
                f"'{item}'"
                if isclass(item) or repr(item) == type(item).__name__
                else f"'{item}' of type {type(item).__name__}"
            )

        if prefix:
            message = f"'{prefix}' expected {hint}, got {item_of_type}"
        else:
            message = f"Expected {hint}, got {item_of_type}"
        raise exceptions.StrongTypingError(message)

    if check_empty:
        if expected == str and item.strip() == "":
            message = (
                f"'{prefix}' must be a non-empty string" if prefix else "Expected non empty string"
            )
            raise exceptions.InvalidSmartContractError(message)
