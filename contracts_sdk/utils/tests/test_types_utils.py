from abc import abstractmethod
import builtins
from datetime import datetime
from decimal import Decimal
import unittest

from .. import exceptions, symbols, types_registry, types_utils


class ListOfInts(types_utils.TypedList("int")):  # type:ignore
    @classmethod
    def _spec(cls, *_, **__):
        return types_utils.ClassSpec(name="ListOfInts", docstring="")


class IntDefaultDict(types_utils.TypedDefaultDict("Dict[int, int]")):  # type:ignore
    @classmethod
    def _spec(cls, *_, **__):
        return types_utils.ClassSpec(name="IntDefaultDict", docstring="")


IntTimeseries = types_utils.Timeseries("int", "bunch of ints")

registry = types_registry.TypeRegistry(
    builtins={name: getattr(builtins, name) for name in dir(builtins)} | {"datetime": datetime},
    custom=[ListOfInts, IntDefaultDict, IntTimeseries],
)


class PublicTypesUtilsTest(unittest.TestCase):
    def test_hidden_keys_key_not_in_symbol(self):
        ContractParameterLevel = types_utils.transform_const_enum(
            name="Level",
            const_enum=symbols.ContractParameterLevel,
            docstring="Different levels of visibility for Parameter objects.",
            hide_keys=("SIMULATION"),
        )
        self.assertRaises(AttributeError, getattr, ContractParameterLevel, "SIMULATION")

    def test_hidden_keys_key_in_symbol(self):
        ContractParameterLevel = types_utils.transform_const_enum(
            name="Level",
            const_enum=symbols.ContractParameterLevel,
            docstring="Different levels of visibility for Parameter objects.",
            hide_keys=("INSTANCE"),
        )
        self.assertRaises(AttributeError, getattr, ContractParameterLevel, "INSTANCE")

    def test_typed_lists(self):

        x = ListOfInts()
        self.assertEqual(len(x), 0)
        self.assertTrue(not x)

        x = ListOfInts([1, 2, 3])
        self.assertEqual(len(x), 3)
        self.assertEqual(x, [1, 2, 3])
        self.assertNotEqual(x, [1, 2])

        def generator():
            yield 1
            yield "hello"

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"ListOfInts item\[1\] expected int but got value 'hello'"
        ):
            ListOfInts(generator())

        def generator():
            yield 1
            yield 2
            yield 3

        x = ListOfInts(generator())
        self.assertEqual(x, [1, 2, 3])
        x.extend((4, 5, 6))
        x.append(7)
        self.assertEqual(x, [1, 2, 3, 4, 5, 6, 7])

        self.assertEqual(x[2], 3)
        self.assertEqual(x[2:5], [3, 4, 5])
        self.assertEqual(x[4:], [5, 6, 7])
        self.assertEqual(x[:3], [1, 2, 3])

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"ListOfInts item expected int but got value 'hello'"
        ):
            x.append("hello")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"ListOfInts item\[1\] expected int but got value 'world'"
        ):
            x.extend([8, "world"])

        self.assertEqual(x, [1, 2, 3, 4, 5, 6, 7])

        x_plus_extras = x + [8]
        self.assertEqual(x, [1, 2, 3, 4, 5, 6, 7])
        self.assertIsInstance(x_plus_extras, ListOfInts)
        self.assertEqual(x_plus_extras, [1, 2, 3, 4, 5, 6, 7, 8])

        x_plus_extras += ListOfInts([9])
        self.assertEqual(x_plus_extras, [1, 2, 3, 4, 5, 6, 7, 8, 9])

        rhs_added = [1, 2] + ListOfInts([3, 4])
        self.assertIsInstance(rhs_added, list)
        self.assertNotIsInstance(rhs_added, ListOfInts)
        self.assertEqual(rhs_added, [1, 2, 3, 4])

        x[3] = 123
        self.assertEqual(x, [1, 2, 3, 123, 5, 6, 7])

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"ListOfInts item expected int but got value '123'"
        ):
            x[3] = "123"

        x[3:5] = [123]
        self.assertEqual(x, [1, 2, 3, 123, 6, 7])

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"ListOfInts item expected int but got value 'hmm'"
        ):
            x[3:5] = [55555, 0, -323, "hmm", 7]

    def test_typed_list_type_check(self):
        list_of_ints = ListOfInts()
        with self.assertRaises(exceptions.StrongTypingError):
            list_of_ints.append("not_an_int")

    def test_typed_list_from_proto(self):
        data = [1, 2, "not_an_int"]
        list_bypass_type_check = ListOfInts(data, _from_proto=True)
        self.assertEqual(len(list_bypass_type_check), 3)

    def test_type_annotation_any(self):
        for obj in 123, None, "hello", {(1, 2): ListOfInts([4, 5, 6])}:
            registry.assert_type_name("Any", obj, "")

    def test_type_annotation_dict(self):
        registry.assert_type_name(
            "Dict[int, ListOfInts]", {1: ListOfInts(), 2: ListOfInts([1, 2])}, ""
        )
        registry.assert_type_name("Dict[int, ListOfInts]", {}, "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Dict\[int, ListOfInts\] but got value 'hello'"
        ):
            registry.assert_type_name("Dict[int, ListOfInts]", "hello", "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Dict\[int, str\] but got value {'5': '5'}"
        ):
            registry.assert_type_name("Dict[int, str]", {"5": "5"}, "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError,
            r"expected Dict\[int, ListOfInts\] but got value {1: \[\], 2: \[1, 2\]}",
        ):
            registry.assert_type_name("Dict[int, ListOfInts]", {1: ListOfInts(), 2: [1, 2]}, "")

    def test_type_annotation_list(self):
        registry.assert_type_name("List[str]", [], "")
        registry.assert_type_name("List[str]", ["hello", "world"], "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected List\[str\] but got value 123"
        ):
            registry.assert_type_name("List[str]", 123, "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected List\[str\] but got value \[123, '456'\]"
        ):
            registry.assert_type_name("List[str]", [123, "456"], "")

        registry.assert_type_name("List[int]", ListOfInts([123, 456]), "")

    def test_type_annotation_optional(self):
        registry.assert_type_name("Optional[int]", 123, "")
        registry.assert_type_name("Optional[int]", None, "")
        registry.assert_type_name("Optional[ListOfInts]", None, "")
        registry.assert_type_name("Optional[ListOfInts]", ListOfInts([1, 2, 3]), "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Optional\[int\] but got value 'some string'"
        ):
            registry.assert_type_name("Optional[int]", "some string", "")

    def test_type_annotation_tuple(self):
        registry.assert_type_name("Tuple[int, str]", (123, "456"), "")
        registry.assert_type_name("Tuple[int, str, List[int]]", (123, "456", [789]), "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Tuple\[int, str\] but got value \[123, '456'\]"
        ):
            registry.assert_type_name("Tuple[int, str]", [123, "456"], "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Tuple\[int, str\] but got value 123"
        ):
            registry.assert_type_name("Tuple[int, str]", 123, "")

    def test_type_annotation_union(self):
        registry.assert_type_name("Union[int, str]", 123, "")
        registry.assert_type_name("Union[int, str]", "123", "")

        with self.assertRaisesRegex(
            exceptions.StrongTypingError, r"expected Union\[int, str\] but got value 1.23"
        ):
            registry.assert_type_name("Union[int, str]", 1.23, "")


class TestTimeseries(unittest.TestCase):
    def test_timeseries_append_checks_types(self):
        ts = IntTimeseries()
        ts.append((datetime(year=2020, month=10, day=1), 1))
        ts.append((datetime(year=2020, month=10, day=1), 2))
        with self.assertRaises(exceptions.StrongTypingError):
            ts.append((datetime(year=2020, month=10, day=3), "Wrong type"))

    def test_timeseries_from_proto(self):
        proto_series = [
            (datetime(year=2020, month=10, day=1), 1),
            (datetime(year=2020, month=10, day=1), 2),
            (datetime(year=2020, month=10, day=3), "No Type Checking"),
        ]
        ts = IntTimeseries(proto_series, _from_proto=True)
        self.assertEqual(proto_series, ts.all())

    def test_timeseries_at_within_interval(self):
        proto_series = [
            (datetime.fromtimestamp(1), 1),
            (datetime.fromtimestamp(11), 2),
            (datetime.fromtimestamp(21), 3),
        ]
        ts = IntTimeseries(proto_series)
        self.assertEqual(1, ts.at(timestamp=datetime.fromtimestamp(5)))
        self.assertEqual(2, ts.at(timestamp=datetime.fromtimestamp(15)))

    def test_timeseries_at_before_start_raises_error(self):
        proto_series = [(datetime.fromtimestamp(2), 1)]
        ts = IntTimeseries(proto_series)
        with self.assertRaises(expected_exception=exceptions.StrongTypingError):
            ts.at(timestamp=datetime.fromtimestamp(1))

    def test_timeseries_at_after_end_returns_last_value(self):
        proto_series = [
            (datetime.fromtimestamp(1), 1),
            (datetime.fromtimestamp(2), 2),
        ]
        ts = IntTimeseries(proto_series)
        self.assertEqual(2, ts.at(timestamp=datetime.fromtimestamp(10)))

    def test_timeseries_at_inclusive_on_boundary_returns_subsequent_value(self):
        proto_series = [
            (datetime.fromtimestamp(1), 1),
            (datetime.fromtimestamp(10), 2),
        ]
        ts = IntTimeseries(proto_series)
        self.assertEqual(1, ts.at(timestamp=datetime.fromtimestamp(1)))
        self.assertEqual(2, ts.at(timestamp=datetime.fromtimestamp(10)))

    def test_timeseries_not_inclusive_on_boundary_returns_previous_value(self):
        proto_series = [
            (datetime.fromtimestamp(1), 1),
            (datetime.fromtimestamp(10), 2),
        ]
        ts = IntTimeseries(proto_series)
        with self.assertRaises(expected_exception=exceptions.StrongTypingError):
            ts.at(inclusive=False, timestamp=datetime.fromtimestamp(1))
        self.assertEqual(1, ts.at(inclusive=False, timestamp=datetime.fromtimestamp(10)))

    def test_timeseries_empty_at_raises_error(self):
        ts = IntTimeseries(None)
        with self.assertRaises(expected_exception=exceptions.StrongTypingError):
            ts.at(timestamp=datetime.fromtimestamp(1))

    def test_timeseries_at_and_before(self):
        ts = IntTimeseries()

        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500008), 1))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500009), 2))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500010), 3))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500010), 4))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500010), 5))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500011), 6))
        ts.append((datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500012), 7))

        at_idx = ts.at(
            timestamp=datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500010)
        )
        before_id = ts.before(
            timestamp=datetime(year=2020, month=1, day=1, hour=12, minute=0, microsecond=500010)
        )

        self.assertEqual(at_idx, 5)
        self.assertEqual(before_id, 2)


class TestTypedDefaultDict(unittest.TestCase):
    def test_typed_default_dict_happy_path_no_default(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(KeyError):
            default_dict[0]

    def test_typed_default_dict_wrong_type_init(self):
        data = {1: 2, 3: 4, "wrong": "type"}
        with self.assertRaises(exceptions.StrongTypingError):
            IntDefaultDict(mapping=data)

    def test_typed_default_dict_wrong_type_missing_key(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict["wrong type"]

    def test_typed_default_dict_wrong_type_add(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict["wrong"] = "type"

    def test_typed_default_dict_wrong_type_setdefault(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.setdefault("wrong", "type")

    def test_typed_default_dict_wrong_type_update(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.update({"wrong": "type"})

    def test_typed_default_dict_wrong_type_update_kwargs(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.update(wrong="type")

    def test_typed_default_dict_wrong_type_copy(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(mapping=data)
        self.assertEqual(len(default_dict), 2)
        copied_dict = default_dict.copy()
        with self.assertRaises(exceptions.StrongTypingError):
            copied_dict["wrong"] = "type"

    def test_typed_default_dict_default_factory(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data)
        self.assertEqual(len(default_dict), 2)
        self.assertEqual(default_dict[0], 0)

    def test_typed_default_dict_bypass_checks_init(self):
        data = {1: 2, 3: 4, "wrong": "type"}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        self.assertEqual(len(default_dict), 3)

    def test_typed_default_dict_not_bypass_checks_key(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        with self.assertRaises(exceptions.StrongTypingError):
            self.assertEqual(default_dict["wrong type"], 0)

    def test_typed_default_dict_not_bypass_checks_add(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict["wrong"] = "type"

    def test_typed_default_dict_bypass_checks_custom_method(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data)
        default_dict._set_item_custom(key="wrong", value="type", _from_proto=True)  # noqa: SLF001
        self.assertEqual(len(default_dict), 3)

    def test_typed_default_dict_not_bypass_checks_setdefault(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.setdefault("wrong", "type")

    def test_typed_default_dict_not_bypass_checks_update(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.update({"wrong": "type"})

    def test_typed_default_dict_not_bypass_checks_update_kwargs(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        with self.assertRaises(exceptions.StrongTypingError):
            default_dict.update(wrong="type")

    def test_typed_default_dict_bypass_checks_update(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data)
        default_dict.update({"wrong": "type"}, _from_proto=True)
        self.assertEqual(len(default_dict), 3)

    def test_typed_default_dict_not_bypass_checks_copy(self):
        data = {1: 2, 3: 4}
        default_dict = IntDefaultDict(default_factory=lambda *_: 0, mapping=data, _from_proto=True)
        copied_dict = default_dict.copy()
        with self.assertRaises(exceptions.StrongTypingError):
            copied_dict.setdefault("wrong", "type")


class TestStrictInterface(unittest.TestCase):
    def test_can_instantiate_class_with_all_abstract_methods(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class DerivedClass(BaseClass):
            def base_method_one(self):
                pass

        instance = DerivedClass()
        self.assertIsNotNone(instance)

    def test_can_instantiate_class_with_all_abstract_methods_multiple_inheritance(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class IntermediateClass(BaseClass):
            @abstractmethod
            def base_method_two(self):
                pass

        class DerivedClass(IntermediateClass):
            def base_method_one(self):
                pass

            def base_method_two(self):
                pass

        instance = DerivedClass()
        self.assertIsNotNone(instance)

    def test_cannot_instantiate_class_unless_all_abstract_methods_implemented(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class DerivedClass(BaseClass):
            pass

        with self.assertRaises(TypeError):
            DerivedClass()

    def test_cannot_instantiate_derived_class_unless_all_abstract_methods_implemented(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class IntermediateClass(BaseClass):
            @abstractmethod
            def base_method_two(self):
                pass

        class DerivedClass(IntermediateClass):
            def base_method_two(self):
                pass

        with self.assertRaises(TypeError):
            DerivedClass()

    def test_cannot_instantiate_class_if_method_not_in_base_class(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class DerivedClass(BaseClass):
            def base_method_one(self):
                pass

            def missing_method(self):
                pass

        with self.assertRaises(TypeError):
            DerivedClass()

    def test_private_methods_allowed(self):
        class BaseClass(types_utils.StrictInterface):
            @abstractmethod
            def base_method_one(self):
                pass

        class IntermediateClass(BaseClass):
            @abstractmethod
            def base_method_two(self):
                pass

        class DerivedClass(IntermediateClass):
            def _private_method(self):
                pass

            def base_method_one(self):
                pass

            def base_method_two(self):
                pass

        instance = DerivedClass()
        self.assertIsNotNone(instance)


class PublicTypeValidationHelpersTest(unittest.TestCase):
    def test_iterator_happy_path(self):
        items = (1, 2, 3)
        iterator = types_utils.get_iterator(items, "test", "argument")
        for index, item in enumerate(iterator):
            self.assertEqual(items[index], item)

    def test_iterator_raises_with_str(self):
        items = "not a list"
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.get_iterator(items, "list", "argument")
        self.assertEqual(
            "Expected list of list objects for 'argument', got 'not a list'", str(ex.exception)
        )

    def test_iterator_raises_with_bool(self):
        items = True
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.get_iterator(items, "list", "argument")
        self.assertEqual(
            "Expected list of list objects for 'argument', got 'True'", str(ex.exception)
        )

    def test_iterator_raises_with_empty_check_if_empty(self):
        items = []
        with self.assertRaises(exceptions.InvalidSmartContractError) as ex:
            types_utils.get_iterator(items, "list", "argument", check_empty=True)
        self.assertEqual("'argument' must be a non empty list, got []", str(ex.exception))

    def test_iterator_raises_with_empty_check_if_none(self):
        items = None
        with self.assertRaises(exceptions.InvalidSmartContractError) as ex:
            types_utils.get_iterator(items, "list", "argument", check_empty=True)
        self.assertEqual("'argument' must be a non empty list, got None", str(ex.exception))

    def test_validate_type_happy_path(self):
        item = "a string"
        types_utils.validate_type(item, str, hint="test")
        self.assertEqual("a string", item)

    def test_validate_type_raises_with_hint_and_prefix(self):
        item = "another string"
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, list, hint="my_list", prefix="some_attribute")
        expected = "'some_attribute' expected my_list, got 'another string' of type str"
        self.assertEqual(expected, str(ex.exception))

    def test_validate_type_raises_with_hint_without_prefix(self):
        item = "not an int"
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, int, hint="int")
        self.assertEqual("Expected int, got 'not an int' of type str", str(ex.exception))

    def test_validate_type_raises_without_hint_with_prefix(self):
        item = "another string"
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, list, prefix="some_attribute")
        self.assertEqual(
            "'some_attribute' expected list, got 'another string' of type str",
            str(ex.exception),
        )

    def test_validate_type_raises_without_hint_with_prefix_empty_str(self):
        item = ""
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, list, prefix="some_attribute")
        self.assertEqual(
            "'some_attribute' expected list, got '' of type str",
            str(ex.exception),
        )

    def test_validate_type_raises_without_hint_with_prefix_empty_str_(self):
        item = b""
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, list, prefix="some_attribute")
        self.assertEqual(
            "'some_attribute' expected list, got 'b''' of type bytes",
            str(ex.exception),
        )

    def test_validate_type_raises_without_hint_or_prefix(self):
        item = "not an int"
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, int)
        self.assertEqual("Expected int, got 'not an int' of type str", str(ex.exception))

    def test_validate_type_happy_path_optional(self):
        item = ""
        types_utils.validate_type(item, str, hint="test", is_optional=True)
        self.assertEqual("", item)

    def test_validate_type_happy_path_optional_with_none(self):
        item = None
        types_utils.validate_type(item, str, hint="test", is_optional=True)
        self.assertEqual(None, item)

    def test_validate_type_optional_raises_wrong_type(self):
        item = ""
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, bool, is_optional=True)
        self.assertEqual("Expected bool if populated, got '' of type str", str(ex.exception))

    def test_validate_type_none_raises_wrong_type(self):
        item = None
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, bool, is_optional=False)
        self.assertEqual("Expected bool, got None", str(ex.exception))

    def test_validate_type_int_as_bool(self):
        item = True
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, int, hint="test")
        self.assertEqual("Expected test, got 'True' of type bool", str(ex.exception))

    def test_validate_type_int_as_bool_multiple_types(self):
        item = True
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, (int, str))
        self.assertEqual("Expected Union[int, str], got 'True' of type bool", str(ex.exception))

    def test_validate_type_int_as_bool_multiple_types_optional(self):
        item = True
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, (int, str), is_optional=True)
        self.assertEqual(
            "Expected Union[int, str] if populated, got 'True' of type bool", str(ex.exception)
        )

    def test_validate_type_happy_path_bool_multiple_types(self):
        item = True
        types_utils.validate_type(item, (int, str, bool))
        self.assertEqual(True, item)

    def test_validate_type_value_is_class(self):
        item = Decimal
        with self.assertRaises(exceptions.StrongTypingError) as ex:
            types_utils.validate_type(item, int)
        self.assertEqual("Expected int, got '<class 'decimal.Decimal'>'", str(ex.exception))

    def test_validate_type_check_empty_happy_path(self):
        item = "not empty"
        types_utils.validate_type(item, str, check_empty=True)
        self.assertEqual("not empty", item)

    def test_validate_type_check_empty_raises_for_empty_str(self):
        item = ""
        with self.assertRaises(exceptions.InvalidSmartContractError) as ex:
            types_utils.validate_type(item, str, check_empty=True)
        self.assertEqual("Expected non empty string", str(ex.exception))

    def test_validate_type_check_empty_raises_for_empty_str_with_prefix(self):
        item = ""
        with self.assertRaises(exceptions.InvalidSmartContractError) as ex:
            types_utils.validate_type(item, str, check_empty=True, prefix="Prefix.str")
        self.assertEqual("'Prefix.str' must be a non-empty string", str(ex.exception))
