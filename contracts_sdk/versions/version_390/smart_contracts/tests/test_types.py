from ..types import ContractModule, SharedFunction, SharedFunctionArg
from ...common.tests.test_types import PublicCommonV390TypesTestCase
from ....version_380.smart_contracts.tests import test_types
from .....utils.exceptions import StrongTypingError
from .....utils.tools import SmartContracts390TestCase


class PublicSmartContractsV390TypesTestCase(
    SmartContracts390TestCase,
    PublicCommonV390TypesTestCase,
    test_types.PublicSmartContractsV380TypesTestCase,
):
    def test_shared_function_arg(self):
        arg = SharedFunctionArg(name="some_arg", type="str")
        self.assertEqual("some_arg", arg.name)
        self.assertEqual("str", arg.type)

    def test_shared_function_arg_no_type(self):
        arg = SharedFunctionArg(name="some_arg")
        self.assertEqual("some_arg", arg.name)
        self.assertIsNone(arg.type)

    def test_shared_function_invalid_arg_name_type(self):
        with self.assertRaises(StrongTypingError):
            SharedFunctionArg(name=27, type="int")

    def test_shared_function_no_args_no_return_type(self):
        func = SharedFunction(name="some_func", args=[])
        self.assertEqual("some_func", func.name)
        self.assertEqual([], func.args)
        self.assertEqual(None, func.return_type)

    def test_shared_function_no_args(self):
        func = SharedFunction(name="some_func", args=[], return_type="int")
        self.assertEqual("some_func", func.name)
        self.assertEqual([], func.args)
        self.assertEqual("int", func.return_type)

    def test_shared_function(self):
        arg_1 = SharedFunctionArg(name="arg_1", type="int")
        arg_2 = SharedFunctionArg(name="arg_2", type="str")
        func = SharedFunction(name="some_func", args=[arg_1, arg_2], return_type="bool")
        self.assertEqual("some_func", func.name)
        self.assertEqual(len(func.args), 2)
        self.assertEqual("arg_1", func.args[0].name)
        self.assertEqual("int", func.args[0].type)
        self.assertEqual("arg_2", func.args[1].name)
        self.assertEqual("str", func.args[1].type)
        self.assertEqual("bool", func.return_type)

    def test_shared_function_args_without_types(self):
        arg_1 = SharedFunctionArg(name="arg_1")
        arg_2 = SharedFunctionArg(name="arg_2")
        func = SharedFunction(name="some_func", args=[arg_1, arg_2], return_type="str")
        self.assertEqual("some_func", func.name)
        self.assertEqual(len(func.args), 2)
        self.assertEqual("arg_1", func.args[0].name)
        self.assertEqual("arg_2", func.args[1].name)
        self.assertEqual("str", func.return_type)

    def test_shared_function_invalid_name_type(self):
        with self.assertRaises(StrongTypingError):
            SharedFunction(name=54)

    def test_contract_module_no_functions(self):
        module = ContractModule(alias="my_module", expected_interface=[])
        self.assertEqual("my_module", module.alias)
        self.assertEqual([], module.expected_interface)

    def test_contract_module(self):
        arg_1 = SharedFunctionArg(name="arg_1", type="int")
        arg_2 = SharedFunctionArg(name="arg_2", type="str")
        func_1 = SharedFunction(name="func_1", args=[arg_1, arg_2], return_type="bool")
        func_2 = SharedFunction(name="func_2", args=[], return_type="int")
        module = ContractModule(alias="my_module", expected_interface=[func_1, func_2])
        self.assertEqual("my_module", module.alias)
        self.assertEqual(2, len(module.expected_interface))
        self.assertEqual("func_1", module.expected_interface[0].name)
        self.assertEqual("func_2", module.expected_interface[1].name)

    def test_contract_module_invalid_alias_type(self):
        with self.assertRaises(StrongTypingError):
            ContractModule(alias=71, expected_interface=[])

    def test_contract_module_invalid_expected_interface_type(self):
        with self.assertRaises(StrongTypingError):
            ContractModule(alias="foo", expected_interface=27)
