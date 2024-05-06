import importlib
from types import FunctionType
from typing import Any, Dict, List
from unittest import mock, TestCase

from .types_registry import make_contract_version_sandbox


# For v3.x ONLY
# These Test Case classes are only required for Contracts Language version 3.x
# If you are targetting Contracts Language v4+, use the standard Python TestCase from unittest


class ContractsTestCase(TestCase):
    supported_hook_names: List[str] = []

    @classmethod
    def setUpClass(cls):
        versions_package = ".".join(__package__.split(".")[:-1]) + ".versions"
        path = f".version_{cls.version}.{cls.executor_type}.lib"
        cls._contract_lib = importlib.import_module(path, versions_package)
        cls._registry = make_contract_version_sandbox(cls._contract_lib)
        cls.builtins = cls._contract_lib.ALLOWED_BUILTINS

    @staticmethod
    def load_contract_code(filepath: str) -> str:
        with open(filepath, "r") as f:
            contract_code = f.read()
        return contract_code

    def create_sandbox(self, types: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "__builtins__": {name: self._registry["__builtins__"][name] for name in self.builtins},
            **types,
        }

    def create_sandbox_with_imports(self, types: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        importBuiltin = {"__import__": __import__}
        allowedBuiltins = {name: self._registry["__builtins__"][name] for name in self.builtins}
        allowedNatives = {name: name for name in self._contract_lib.ALLOWED_NATIVES}
        return {"__builtins__": {**importBuiltin, **allowedBuiltins, **allowedNatives, **types}}

    def _execute_function_in_sandbox(
        self, contract_code: str, function_name: str, sandbox: Dict[str, Any], *args, **kwargs
    ) -> FunctionType:
        exec(contract_code, sandbox, sandbox)
        func = sandbox.get(function_name)
        if func is None:
            raise ValueError(
                f'Function "{function_name}" does not exist in provided {self.module_desc} code'
            )

        function_globals = {**sandbox}
        if function_name in self.supported_hook_names:
            function_globals["vault"] = self.vault
        func = FunctionType(
            func.__code__, function_globals, func.__name__, func.__defaults__, func.__closure__
        )
        return func(*args, **kwargs)

    def run_contract_function(
        self, contract_code: str, function_name: str, *args, **kwargs
    ) -> FunctionType:
        types = {name: func for name, func in self._registry.items() if name != "__builtins__"}
        sandbox = self.create_sandbox(types)

        return self._execute_function_in_sandbox(
            contract_code, function_name, sandbox, *args, **kwargs
        )

    def run_contract_function_with_imports(
        self, contract_code: str, function_name: str, *args, **kwargs
    ) -> FunctionType:
        types = {name: func for name, func in self._registry.items() if name != "__builtins__"}
        sandbox = self.create_sandbox_with_imports(types)

        return self._execute_function_in_sandbox(
            contract_code, function_name, sandbox, *args, **kwargs
        )


class SmartContractsTestCase(ContractsTestCase):
    version = ""
    executor_type = "smart_contracts"
    module_desc = "Smart Contract"
    supported_hook_names = [
        "pre_posting_code",
        "post_posting_code",
        "post_activate_code",
        "execution_schedules",
        "close_code",
        "upgrade_code",
        "pre_parameter_change_code",
        "post_parameter_change_code",
        "derived_parameters",
        "scheduled_code",
    ]

    def create_sandbox(self, types: Dict[str, Any]) -> Dict[str, Any]:
        sandbox = super().create_sandbox(types)
        sandbox["requires"] = self.requires
        sandbox["fetch_account_data"] = self.fetch_account_data
        return sandbox

    def setUp(self, *args, **kwargs):
        def _mock_requires_decorator(
            parameters=None,
            balances=None,
            flags=None,
            postings=None,
            last_execution_time=None,
            event_type=None,
            calendar=None,
            modules=None,
        ):
            def inner(func):
                return func

            return inner

        def _mock_fetch_account_data(
            balances=None,
            event_type=None,
            postings=None,
        ):
            def inner(func):
                return func

            return inner

        self.requires = _mock_requires_decorator
        self.fetch_account_data = _mock_fetch_account_data
        self.vault = mock.create_autospec(self._contract_lib.VaultFunctionsABC)
        super().setUp(*args, **kwargs)


class SupervisorContractsTestCase(ContractsTestCase):
    version = ""
    executor_type = "supervisor_contracts"
    module_desc = "Supervisor Contract"
    supervisee_executor_type = "smart_contracts"
    supported_hook_names = ["post_posting_code", "execution_schedules", "scheduled_code"]

    def create_sandbox(self, types: Dict[str, Any]) -> Dict[str, Any]:
        sandbox = super().create_sandbox(types)
        sandbox["requires"] = self.requires
        return sandbox

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        versions_package = ".".join(__package__.split(".")[:-1]) + ".versions"
        supervisee_path = f".version_{cls.version}.{cls.supervisee_executor_type}.lib"
        cls._supervisee_contract_lib = importlib.import_module(supervisee_path, versions_package)

    def setUp(self, *args, **kwargs):
        def _mock_requires_decorator(
            parameters=None,
            balances=None,
            flags=None,
            postings=None,
            last_execution_time=None,
            event_type=None,
            data_scope=None,
            supervisee_hook_directives=None,
            calendar=None,
        ):
            def inner(func):
                return func

            return inner

        self.requires = _mock_requires_decorator
        self.vault = mock.create_autospec(self._contract_lib.VaultFunctionsABC)
        super().setUp(*args, **kwargs)

    def create_supervisee_vault(self):
        return mock.create_autospec(self._supervisee_contract_lib.VaultFunctionsABC)


class ContractModulesTestCase(ContractsTestCase):
    version = ""
    executor_type = "contract_modules"
    module_desc = "Contract Module"


class SmartContracts300TestCase(SmartContractsTestCase):
    version = "300"


class SmartContracts310TestCase(SmartContractsTestCase):
    version = "310"


class SmartContracts320TestCase(SmartContractsTestCase):
    version = "320"


class SmartContracts330TestCase(SmartContractsTestCase):
    version = "330"


class SmartContracts340TestCase(SmartContractsTestCase):
    version = "340"


class SmartContracts350TestCase(SmartContractsTestCase):
    version = "350"


class SmartContracts360TestCase(SmartContractsTestCase):
    version = "360"


class SmartContracts370TestCase(SmartContractsTestCase):
    version = "370"


class SmartContracts380TestCase(SmartContractsTestCase):
    version = "380"


class SmartContracts390TestCase(SmartContractsTestCase):
    version = "390"


class SmartContracts3100TestCase(SmartContractsTestCase):
    version = "3100"


class SmartContracts3110TestCase(SmartContractsTestCase):
    version = "3110"


class SmartContracts3120TestCase(SmartContractsTestCase):
    version = "3120"


class SupervisorContracts340TestCase(SupervisorContractsTestCase):
    version = "340"


class SupervisorContracts350TestCase(SupervisorContractsTestCase):
    version = "350"


class SupervisorContracts360TestCase(SupervisorContractsTestCase):
    version = "360"


class SupervisorContracts370TestCase(SupervisorContractsTestCase):
    version = "370"


class SupervisorContracts380TestCase(SupervisorContractsTestCase):
    version = "380"


class SupervisorContracts390TestCase(SupervisorContractsTestCase):
    version = "390"


class SupervisorContracts3100TestCase(SupervisorContractsTestCase):
    version = "3100"


class SupervisorContracts3110TestCase(SupervisorContractsTestCase):
    version = "3110"


class SupervisorContracts3120TestCase(SupervisorContractsTestCase):
    version = "3120"


class ContractModules390TestCase(ContractModulesTestCase):
    version = "390"


class ContractModules3100TestCase(ContractModulesTestCase):
    version = "3100"


class ContractModules3110TestCase(ContractModulesTestCase):
    version = "3110"


class ContractModules3120TestCase(ContractModulesTestCase):
    version = "3120"
