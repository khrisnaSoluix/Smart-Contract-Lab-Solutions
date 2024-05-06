# standard libs
import os
import sys
import unittest
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

# inception sdk
import inception_sdk.tools.common.tools_utils as tools_utils

TEST_MODULE_FILEPATH = "inception_sdk/tools/common/tests/module.py"


class TestToolsUtils(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="data")
    def test_get_file_checksum(self, mock_open: Mock):
        checksum = tools_utils.get_file_checksum(filepath="path/file.py", hashing_algorithm="md5")
        self.assertEqual(checksum, "8d777f385d3dfec8815d20f7496026dc")
        mock_open.assert_called_once_with("path/file.py", "r")

    def test_get_hash(self):
        hashed_data = tools_utils.get_hash(hashing_algorithm="md5", data="data")
        self.assertEqual(hashed_data, "8d777f385d3dfec8815d20f7496026dc")

    def test_add_to_path(self):
        with tools_utils.add_to_path("test_add_to_path"):
            self.assertIn("test_add_to_path", sys.path)
        self.assertNotIn("test_add_to_path", sys.path)

    def test_path_import(self):
        test_module = tools_utils.path_import(TEST_MODULE_FILEPATH, "test_module")
        self.assertEqual(test_module.test, "test")

    def test_get_relative_filepath_from_cwd(self):
        absolute_test_fp = os.getcwd() + "/" + TEST_MODULE_FILEPATH
        relative_fp = tools_utils.get_relative_filepath_from_cwd(absolute_test_fp)
        self.assertEqual(relative_fp, TEST_MODULE_FILEPATH)


if __name__ == "__main__":
    unittest.main()
