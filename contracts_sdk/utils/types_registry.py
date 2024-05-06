import builtins
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Generic, List, Set, Tuple, TypeVar, Union, Optional

from .exceptions import InvalidSmartContractError, StrongTypingError
from .types_utils import (
    ClassSpec,
    DecoratorSpec,
    EnumSpec,
    FixedValueSpec,
    MethodSpec,
    NativeObjectSpec,
    ValueSpec,
)


class TypeRegistry(dict):
    """
    The TypeRegistry hold all types that a particular Smart Contract API defines.

    A TypeRegistry instance is itself usable as a dict, meaning that it can be used
    as a sandbox for contract execution via instructions like:
        exec(contract_code, type_registry, type_registry)

    It also contains the member _check_dict, which consists of the builtins, custom types,
    and the type annotation types that are needed to verify a type that any custom type
    or method may wish to assert.
    """

    def __init__(
        self, *, builtins: Dict[str, Any], custom: List[Any], disable_type_checking: bool = False
    ):
        if not isinstance(builtins, dict):
            raise ValueError("builtins must be a dict")
        if not isinstance(custom, list):
            raise ValueError("custom must be a list")

        self["__builtins__"] = builtins
        self._specs: Dict[
            str,
            Union[
                ClassSpec, DecoratorSpec, FixedValueSpec, MethodSpec, NativeObjectSpec, ValueSpec
            ],
        ] = {}
        self.disable_type_checking = disable_type_checking

        for item in custom:
            if isinstance(item, NativeObjectSpec) or isinstance(item, DecoratorSpec):
                name, object, spec = item.name, item.object, item
            elif isinstance(item, FixedValueSpec):
                name, object, spec = item.name, item.fixed_value, item  # type: ignore
            elif hasattr(item, "_spec"):
                name, object, spec = item._spec().name, item, item._spec()  # noqa:SLF001
            else:
                raise ValueError(f"Invalid item {item} inserted into TypeRegistry")

            if not isinstance(name, str):
                raise ValueError(f"TypeRegistry could not infer name for object {repr(item)}")
            if name in self:
                raise ValueError(f"Name {repr(name)} is multiply defined in TypeRegistry")

            self[name] = object
            self._specs[name] = spec

        # Build the dictionary to check all the types used within Smart Contracts
        # that contain custom types and typing classes.
        self._check_dict: Dict[str, Any] = dict(self)
        self._check_dict["Any"] = TypeCheckingAny
        self._check_dict["Dict"] = _TypeCheckingDict()
        self._check_dict["List"] = _TypeCheckingList()
        self._check_dict["Optional"] = _TypeCheckingOptional()
        self._check_dict["Tuple"] = _TypeCheckingTupleCls()
        self._check_dict["Union"] = _TypeCheckingUnionCls()

        # Attach the type registry to every class in the check dict;
        # each class in there may need to check the registry for recursive types.
        for cls in self._check_dict.values():
            try:
                cls._registry = self  # noqa:SF01
            except (AttributeError, TypeError):
                pass

    def assert_type_name(self, type_name: str, obj: Any, location: str):
        if self.disable_type_checking:
            return
        # Use the Python interpreter to parse the type_name string,
        # which may be arbitrarily nested, e.g. 'List[Dict[int, SomeType]].
        type_obj = eval(type_name, self._check_dict)
        if not self.is_valid_type(type_obj, obj):
            raise StrongTypingError(f"{location} expected {type_name} but got value {repr(obj)}")

    @staticmethod
    def is_valid_type(type_obj: Any, obj: Any):
        if hasattr(type_obj, "_type_check"):
            return type_obj._type_check(obj)  # noqa:SLF001
        else:
            return isinstance(obj, type_obj)


class RegistrySpecsSanityCheckResults:
    def __init__(self):
        # Each item is a class name.
        self.classes_without_constructor_specs: Set[str] = set()

        # Each item is attr identifier.
        self.missing_attributes: Set[str] = set()

        # Each item is (attr identifier, expected type name, actual type obj).
        self.invalid_attributes: Set[Tuple[str, str, type]] = set()

        # Each item is a method identifier.
        self.missing_methods: Set[str] = set()

        # Each item is (method identifier, exception).
        self.invalid_methods: Set[Tuple[str, Union[TypeError, StrongTypingError]]] = set()

        # Each item is (method identifier, expected type name, actual type obj).
        self.invalid_method_return_values: Set[Tuple[str, type, type]] = set()

    def __str__(self):
        lines = []
        if self.classes_without_constructor_specs:
            lines.append(
                f"Classes without constructor specs: "
                f"{', '.join(sorted(self.classes_without_constructor_specs))}"
            )

        if self.missing_attributes:
            lines.append(f"Missing attributes: {' ,'.join(sorted(self.missing_attributes))}")

        if self.invalid_attributes:
            lines.append("Invalid attributes:")
            lines.extend(
                f"{item} expected {repr(item)} but got {item}"
                for item in sorted(self.invalid_attributes)
            )

        if self.missing_methods:
            lines.append(f"Missing methods: {', '.join(sorted(self.missing_methods))}")

        if self.invalid_methods:
            lines.append("Invalid methods:")
            lines.extend(f"{item} raised {item}" for item in sorted(self.invalid_methods))

        return "\n".join(lines or ["All specs satisfied"])


def _check_class_spec(
    results: RegistrySpecsSanityCheckResults,
    registry: TypeRegistry,
    prebuilt_instances: Dict[str, Any],
    class_spec: ClassSpec,
):
    if class_spec.name not in prebuilt_instances and not class_spec.constructor:
        # If the ClassSpec doesn't have a constructor, ignore it.
        # There are some types where the class itself may be used
        # as opposed to constructing an instance, e.g. Parameter types.
        results.classes_without_constructor_specs.add(class_spec.name)
        return

    try:
        instance = _try_to_construct(registry, prebuilt_instances, class_spec.name)
    except (TypeError, StrongTypingError) as e:
        # The arguments within the constructor were of the wrong types
        # with respect to the specification.
        results.invalid_methods.add((f"{class_spec.name}.__init__", e))
        return
    except:  # noqa: E722
        return

    # Check that all the public attributes match the Class specification.
    for attr_spec in class_spec.public_attributes.values():
        if attr_spec.name:
            try:
                attr = getattr(instance, attr_spec.name)
            except AttributeError:
                results.missing_attributes.add(f"{class_spec.name}.{attr_spec.name}")
                continue
            except Exception:
                # The attribute exists, but there was a different problem:
                # potentially, one of the attributes was a property whose method threw an exception.
                continue
            try:
                registry.assert_type_name(attr_spec.type, attr, "")
            except StrongTypingError:
                results.invalid_attributes.add(
                    (f"{class_spec.name}.{attr_spec.name}", attr_spec.type, type(attr))
                )

    # Check all the public methods match the specification.
    for method_spec in class_spec.public_methods.values():
        identifier = f"{class_spec.name}.{method_spec.name}"
        try:
            method = getattr(instance, method_spec.name)
        except:  # noqa: E722
            results.missing_methods.add(identifier)
            return
        _check_method_spec(results, registry, prebuilt_instances, identifier, method, method_spec)


def _check_method_spec(
    results: RegistrySpecsSanityCheckResults,
    registry: TypeRegistry,
    prebuilt_instances: Dict[str, Any],
    identifier: str,
    method: Any,
    method_spec: MethodSpec,
):
    args = {
        name: _try_to_construct(registry, prebuilt_instances, spec_of_arg.type)
        for name, spec_of_arg in method_spec.args.items()
    }

    try:
        return_value = method(**args)
    except (TypeError, StrongTypingError) as e:  # TypeError: invalid argument count.
        results.invalid_methods.add((identifier, e))
        return
    except:  # noqa: E722
        return

    # Check the return value.
    if method_spec.return_value:
        try:
            registry.assert_type_name(method_spec.return_value.type, return_value, "")
        except StrongTypingError:
            results.invalid_method_return_values.add(
                (identifier, method_spec.type, type(return_value))
            )


def _try_to_construct(registry: TypeRegistry, prebuilt_instances: Dict[str, Any], type_str: str):
    prebuilt_instance = prebuilt_instances.get(type_str)
    if prebuilt_instance is not None:
        return prebuilt_instance

    type_obj = eval(type_str, registry._check_dict, registry._check_dict)  # noqa: SLF001
    spec = registry._specs.get(type_str)  # noqa: SLF001

    if spec:
        if isinstance(spec, ClassSpec) and spec.constructor:
            return type_obj(
                **{
                    name: _try_to_construct(registry, prebuilt_instances, spec_of_arg.type)
                    for name, spec_of_arg in spec.constructor.args.items()
                }
            )
        elif isinstance(spec, ValueSpec):
            return _try_to_construct(registry, prebuilt_instances, spec.type)
        elif isinstance(spec, NativeObjectSpec):
            if type_obj == Decimal:
                return Decimal(123)
            elif type_obj == datetime:
                return datetime(2019, 1, 1)
            else:
                raise ValueError(f"Dont know how to construct NativeObject of type {type_obj}")
        elif isinstance(spec, EnumSpec):
            return spec.members[0]["value"]
        else:
            raise ValueError(f"Cant construct specification of type {spec.__class__}")
    else:
        if type_obj == str:
            return "Hello"
        elif type_obj.__bases__ == (_TypeCheckingOptional,):
            return None
        elif type_obj.__bases__ == (_TypeCheckingList,):
            return []
        elif type_obj.__bases__ == (_TypeCheckingDict,):
            return {}
        instance = type_obj()
        return instance


def _builtin_not_supported(*args):
    raise InvalidSmartContractError("Unsupported builtin used")


def check_registry_specs_sanity(registry: TypeRegistry, prebuilt_instances: Dict[str, Any]):
    # Start with an empty results object.
    results = RegistrySpecsSanityCheckResults()

    # For each object in the registry with a spec, check that the specification is valid.
    for _, spec in registry._specs.items():  # noqa: SLF001
        if isinstance(spec, ClassSpec):
            _check_class_spec(results, registry, prebuilt_instances, spec)

    return results


def make_contract_version_sandbox(
    contract_lib: Any, disable_type_checking: bool = False
) -> Dict[str, Any]:
    # The _builtin_not_supported method provides a more accurate error message when unsupported
    # builtin methods are used, e.g. if python has a C implementation which is calling a Python
    # function such as `__import__`.
    types_dict = TypeRegistry(
        builtins={
            k: v if k in contract_lib.ALLOWED_BUILTINS else _builtin_not_supported
            for k, v in builtins.__dict__.items()
        },
        custom=list(contract_lib.types_registry().values()),
        disable_type_checking=disable_type_checking,
    )
    return types_dict


def make_contract_version_sandbox_with_imports(
    contract_lib: Any,
    imported_native_modules: Optional[set] = None,
    imported_contract_modules: Optional[dict] = None,
    contracts_api_imports: Optional[set[str]] = None,
    contracts_api_import_all: Optional[bool] = False,
    native_modules_import_all: Optional[bool] = False,
) -> dict[str, Any]:
    # The _builtin_not_supported method provides a more accurate error message when unsupported
    # builtin methods are used, e.g. if python has a C implementation which is calling a Python
    # function such as `__import__`.

    # We cannot define the same type twice, therefore, we need use a set here.
    contracts_api_imports = contracts_api_imports or set()
    if contracts_api_import_all:
        custom_types = set(contract_lib.types_registry().values())
    else:
        custom_types = set(
            [
                custom_type
                for name, custom_type in contract_lib.types_registry().items()
                if name in contracts_api_imports
            ]
        )
    if native_modules_import_all:
        native_module_list = []
        for function_dict in contract_lib.ALLOWED_NATIVES.values():
            for module_object in function_dict.values():
                native_module_list.append(module_object)

        custom_types.update(native_module_list)
    elif imported_native_modules:
        custom_types.update(imported_native_modules)
    types_dict = TypeRegistry(
        builtins={
            k: v if k in contract_lib.ALLOWED_BUILTINS else _builtin_not_supported
            for k, v in builtins.__dict__.items()
        },
        # Custom needs to be a list for the TypeRegistry.
        custom=list(custom_types),
    )

    # Inject the imported modules into the sandbox as well
    types_dict.update(imported_contract_modules or {})
    return types_dict


DictKeyType = TypeVar("DictKeyType")
DictValueType = TypeVar("DictValueType")
ListItemType = TypeVar("ListItemType")
OptionalItemType = TypeVar("OptionalItemType")


class TypeCheckingAny:
    """
    A type that matches the signature of typing.Any but
    implements the _type_check method.
    """

    @classmethod
    def _type_check(cls, obj):
        return True


class _TypeCheckingDict:
    def __getitem__(self, types):
        class TypeCheckingDict(Generic[DictKeyType, DictValueType]):
            """
            A type that matches the signature of typing.Dict but
            implements the _type_check method.
            """

            @staticmethod
            def _type_check(obj: Any):
                return isinstance(obj, dict) and all(
                    self._registry.is_valid_type(types[0], key)
                    and self._registry.is_valid_type(  # noqa: SLF001
                        types[1], value
                    )  # noqa: SLF001
                    for key, value in obj.items()
                )

        return TypeCheckingDict


class _TypeCheckingList:
    def __getitem__(self, type):
        class TypeCheckingList(Generic[ListItemType]):
            """
            A type that matches the signature of typing.List but
            implements the _type_check method.
            """

            @staticmethod
            def _type_check(obj):
                return isinstance(obj, list) and all(
                    self._registry.is_valid_type(type, item) for item in obj  # noqa: SLF001
                )

        return TypeCheckingList


class _TypeCheckingOptional:
    def __getitem__(self, type):
        class TypeCheckingOptional(Generic[OptionalItemType]):
            """
            A type that matches the signature of typing.Optional but
            implements the _type_check method.
            """

            @staticmethod
            def _type_check(obj):
                return obj is None or self._registry.is_valid_type(type, obj)

        return TypeCheckingOptional


class _TypeCheckingTupleCls:
    """
    The pattern of inheriting from typing.Generic does not work
    for tuples, because typing.Generic will not accept an Ellipsis.
    """

    def __getitem__(self, types):
        class TypeCheckingTupleWithArgs:
            @staticmethod
            def _type_check(obj):
                return (
                    isinstance(obj, tuple)
                    and len(obj) == len(types)
                    and all(
                        self._registry.is_valid_type(_type, item) for _type, item in zip(types, obj)
                    )
                )

        return TypeCheckingTupleWithArgs


class _TypeCheckingUnionCls:
    """
    The pattern of inheriting from typing.Generic does not work
    for unions, because typing.Generic will not accept an Ellipsis.
    """

    def __getitem__(self, types):
        class TypeCheckingUnionWithArgs:
            @staticmethod
            def _type_check(obj):
                return any(self._registry.is_valid_type(_type, obj) for _type in types)

        return TypeCheckingUnionWithArgs
