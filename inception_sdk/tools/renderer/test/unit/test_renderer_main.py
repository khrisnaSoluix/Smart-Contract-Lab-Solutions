# standard libs
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

# inception sdk
from inception_sdk.tools.renderer import main


class RendererMainTest(TestCase):
    @patch.object(main, "FLAGS")
    def test_build_config_from_flags(self, mock_FLAGS: MagicMock):
        test_output_filepath = "test/filepath/output.py"
        mock_FLAGS.output_filepath = test_output_filepath
        config = main.build_config_from_flags()
        self.assertEqual(config.output_filepath, test_output_filepath)

    @patch("builtins.input", lambda *args: "y")
    @patch.object(main, "FLAGS")
    def test_confirm_overwrite_yes(self, mock_FLAGS: MagicMock):
        mock_FLAGS.force = False
        result = main.confirm_overwrite(__file__)
        self.assertTrue(result)

    @patch("builtins.input", lambda *args: "n")
    @patch.object(main, "FLAGS")
    def test_confirm_overwrite_no(self, mock_FLAGS: MagicMock):
        mock_FLAGS.force = False
        result = main.confirm_overwrite(__file__)
        self.assertFalse(result)

    @patch("builtins.input", lambda *args: "")
    @patch.object(main, "FLAGS")
    def test_confirm_overwrite_no_input(self, mock_FLAGS: MagicMock):
        mock_FLAGS.force = False
        result = main.confirm_overwrite(__file__)
        self.assertFalse(result)

    @patch.object(main, "FLAGS")
    def test_confirm_overwritewith_flag(self, mock_FLAGS: MagicMock):
        mock_FLAGS.force = True
        result = main.confirm_overwrite(__file__)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
