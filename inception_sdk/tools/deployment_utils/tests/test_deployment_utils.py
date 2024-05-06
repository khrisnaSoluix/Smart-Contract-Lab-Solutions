# standard libs
from unittest import TestCase, main

# inception sdk
import inception_sdk.tools.deployment_utils.deployment_utils as deployment_utils
from inception_sdk.common.python.flag_utils import FLAGS, flags, parse_flags


class FlagParsingTest(TestCase):
    def tearDown(self) -> None:
        FLAGS.unparse_flags()
        return super().tearDown()

    def test_standard_validate(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
            "--validate_manifest",
        ]
        parse_flags(args)
        self.assertTrue(FLAGS.validate_manifest)

    def test_standard_import(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
            "--import_manifest",
            "--auth_cookie=abc",
            "--activate_workflows",
            "--update_workflows_inst_config",
        ]
        parse_flags(args)
        self.assertTrue(FLAGS.import_manifest)
        self.assertTrue(FLAGS.activate_workflows)
        self.assertTrue(FLAGS.update_workflows_inst_config)
        self.assertEqual(FLAGS.auth_cookie, "abc")

    def test_additional_positional_args_passed_through(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
            "--import_manifest",
            "bla",
        ]
        unknown_args = parse_flags(args)
        self.assertTrue(FLAGS.import_manifest)
        self.assertListEqual(unknown_args, ["bla"])

    def test_additional_kwargs_rejected(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
            "--import_manifest",
            "--bla",
        ]
        with self.assertRaises(flags.UnrecognizedFlagError):
            parse_flags(args)

    def test_validate_manifest_and_import_manifest_are_mutually_exclusive(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
            "--validate_manifest",
            "--import_manifest",
        ]
        with self.assertRaisesRegex(
            flags.IllegalFlagValueError,
            r"Exactly one of \(import_manifest, validate_manifest\) must be True",
        ):
            parse_flags(args)

    def test_one_of_validate_manifest_and_import_manifest_is_required(self):

        args = [
            "binary",  # dummy arg to represent the binary in normal CLI command
        ]
        with self.assertRaisesRegex(
            flags.IllegalFlagValueError,
            r"Exactly one of \(import_manifest, validate_manifest\) must be True",
        ):
            parse_flags(args)

    def test_additional_flags_only_accepted_for_import_manifest(self):
        additional_args = [
            "--activate_workflows",
            "--update_workflows_inst_config",
            "--auth_cookie=abc",
        ]
        for additional_arg in additional_args:
            args = [
                "binary",  # dummy arg to represent the binary in normal CLI command
                "--validate_manifest",
                additional_arg,
            ]
            with self.assertRaisesRegex(flags.IllegalFlagValueError, ".*"):
                parse_flags(args)


class DeploymentUtilsTest(TestCase):
    def test_extract_xsrf_token_from_cookie(self):
        good_cookie = (
            'ABC; _xsrf=1|1a2bc345|d6efgh78901ijk1234l567m890123n45|6789012345; tm_ops_auth_token="'
        )
        short_cookie = (
            'ABC; _xsrf=|1a2bc345|d6efgh78901ijk1234l567m890123n45|6789012345; tm_ops_auth_token="'
        )
        long_cookie = (
            "ABC; _xsrf=11|1a2bc345|d6efgh78901ijk1234l567m890123n45|6789012345; "
            + 'tm_ops_auth_token="'
        )
        empty_token = 'ABC; _xsrf=; tm_ops_auth_token="'
        no_header = (
            'ABC; 1|1a2bc345|d6efgh78901ijk1234l567m890123n45|6789012345; tm_ops_auth_token="'
        )
        no_token_no_header = 'ABC; tm_ops_auth_token="'

        self.assertEqual(
            deployment_utils.extract_xsrf_token_from_cookie(good_cookie),
            "1|1a2bc345|d6efgh78901ijk1234l567m890123n45|6789012345",
        )
        with self.assertRaises(ValueError):
            deployment_utils.extract_xsrf_token_from_cookie(short_cookie)

        with self.assertRaises(ValueError):
            deployment_utils.extract_xsrf_token_from_cookie(long_cookie)

        with self.assertRaises(ValueError):
            deployment_utils.extract_xsrf_token_from_cookie(empty_token)

        with self.assertRaises(ValueError):
            deployment_utils.extract_xsrf_token_from_cookie(no_header)

        with self.assertRaises(ValueError):
            deployment_utils.extract_xsrf_token_from_cookie(no_token_no_header)

    def test_workflow_deployment_status_successful(self):
        clu_output_1 = """2022-01-28 13:57:34.112 - INFO: WORKFLOW_DEFINITION_VERSION with ID
        CASA_APPLICATION was IMPORTED successfully using a create action. ID in Vault: '1.0.4
        ,CASA_APPLICATION'"""
        clu_output_2 = """2022-01-28 13:57:35.893 - INFO: WORKFLOW_DEFINITION_VERSION with ID
        OVERDRAFT_PROTECTION_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION was NOT IMPORTED successfully
        using a create action. Error message: received error response code 409: A Workflow
        Definition with ID {OVERDRAFT_PROTECTION_CHECKING_AND_SAVINGS_ACCOUNT_APPLICATION}
        and version {1.0.1} already exists. Duplicate IDs and versions are not allowed"""

        self.assertTrue(deployment_utils.deployment_status_successful(clu_output_1))
        self.assertFalse(deployment_utils.deployment_status_successful(clu_output_2))


if __name__ == "__main__":
    main(DeploymentUtilsTest)
