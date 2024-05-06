import ast
import unittest
from collections import defaultdict

from common.python.file_utils import load_file_contents
from buildtools.lint.flake8_contracts import (
    ContractLinter,
    ListMetadataVisitor,
    ERRORS_CTR001,
    ERRORS_CTR002,
)

CONTRACT_FILE = "buildtools/lint/test/unit/dummy_contract.py"
NON_CONTRACT_FILE = "buildtools/lint/test/unit/dummy_python.py"


class ContractLinterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(load_file_contents(CONTRACT_FILE))
        cls.linter = ContractLinter(tree)
        cls.outputs = defaultdict(lambda: [])
        for line, col, msg, _ in cls.linter.run():
            cls.outputs[msg].append({"line": line, "col": col})

    def test_ctr001_datetime_now_utcnow(self):

        ctr001_errors = self.outputs[ERRORS_CTR001]
        expected_errors = [
            {"line": 26, "col": 10},
            {"line": 27, "col": 13},
            {"line": 32, "col": 10},
            {"line": 33, "col": 13},
        ]
        self.assertListEqual(ctr001_errors, expected_errors)

    def test_ctr002_event_types(self):
        ctr002_errors = self.outputs[ERRORS_CTR002]
        expected_errors = [
            {"line": 37, "col": 0},  # event_types append
            {"line": 38, "col": 0},  # event_types +=
            {"line": 39, "col": 0},  # event_types list slice
            {"line": 39, "col": 16},  # event_types list slice
            {"line": 44, "col": 4},  # event_types within func
            {"line": 50, "col": 0},  # global_parameters
            {"line": 52, "col": 0},  # parameters
            {"line": 55, "col": 0},  # supported_denoms
            {"line": 58, "col": 0},  # event_types_groups
            {"line": 61, "col": 0},  # contract_module_imports
            {"line": 64, "col": 0},  # data_fetchers
        ]
        self.assertListEqual(ctr002_errors, expected_errors)


class ContractLinterNonContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(load_file_contents(NON_CONTRACT_FILE))
        cls.linter = ContractLinter(tree)
        cls.outputs = defaultdict(lambda: [])
        for line, col, msg, _ in cls.linter.run():
            cls.outputs[msg].append({"line": line, "col": col})

    def test_non_contract_file_ignored_ctr001(self):
        ctr001_errors = self.outputs[ERRORS_CTR001]
        self.assertListEqual(ctr001_errors, [])

    def test_non_contract_file_ignored_ctr002(self):
        ctr002_errors = self.outputs[ERRORS_CTR002]
        self.assertListEqual(ctr002_errors, [])


class ListMetadataVisitorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(load_file_contents(CONTRACT_FILE))
        cls.visitor = ListMetadataVisitor(tree)
        cls.outputs = defaultdict(lambda: [])
        cls.visitor.visit(tree)
        for line, col, msg in cls.visitor.violations:
            cls.outputs[msg].append({"line": line, "col": col})

    def test_get_non_hook_non_helper_funcs(self):
        result = self.visitor.non_hook_non_helper_funcs
        self.assertSetEqual(result, {"extend_event_types"})
        self.assertNotIn("pre_parameter_change_code", result)
        self.assertNotIn("_pre_parameter_change_code_helper_function", result)
