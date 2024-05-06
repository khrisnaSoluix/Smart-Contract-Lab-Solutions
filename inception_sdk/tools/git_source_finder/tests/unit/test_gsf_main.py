# standard libs
from unittest import TestCase
from unittest.mock import Mock, call, patch

# inception sdk
import inception_sdk.tools.git_source_finder.main as main_module
from inception_sdk.common.python.flag_utils import FLAGS
from inception_sdk.tools.git_source_finder.main import main
from inception_sdk.tools.git_source_finder.source_finder import GitSourceFinderResult

EXPECTED_LOG_CALLS = [
    call("source_code"),
    call("File hash (md5): file_hash"),
    call("Git commit hash: commit_hash"),
]


@patch.object(main_module.log, "info")
@patch.object(main_module, "GitSourceFinder")
class TestSourceFinder(TestCase):
    def setUp(self) -> None:
        FLAGS.unparse_flags()
        return super().setUp()

    def set_gsf_mock_properties(self, mock_gsf) -> Mock:
        mock_result = GitSourceFinderResult(
            source_code="source_code", file_hash="file_hash", git_commit_hash="commit_hash"
        )
        mock_get_results = Mock(return_value=mock_result)
        mock_gsf.return_value = Mock(
            get_source=mock_get_results,
            get_source_from_commit=mock_get_results,
            get_source_from_filepath=mock_get_results,
            hashing_algorithm="md5",
        )
        return mock_gsf

    def test_file_hash_only(self, mock_GitSourceFinder: Mock, mock_log: Mock):
        mock_GitSourceFinder = self.set_gsf_mock_properties(mock_GitSourceFinder)
        cli_args = ["/path/to/main.py", "--file_hash", "ae0dca24c020ff7731877973df4b6a11"]
        main(cli_args)
        mock_GitSourceFinder.assert_has_calls(
            [
                call(
                    cache_filepath=".gsfcache",
                    hashing_algorithm="md5",
                    save_cache=True,
                    git_repo_root=".",
                ),
                call().get_source(
                    file_hash="ae0dca24c020ff7731877973df4b6a11",
                    git_commit_hash=None,
                    filepath=None,
                ),
            ]
        )
        mock_log.assert_has_calls(EXPECTED_LOG_CALLS)

    def test_custom_cache_path(self, mock_GitSourceFinder: Mock, mock_log: Mock):
        mock_GitSourceFinder = self.set_gsf_mock_properties(mock_GitSourceFinder)
        cli_args = [
            "/path/to/main.py",
            "--file_hash",
            "ae0dca24c020ff7731877973df4b6a11",
            "--cache_filepath",
            "abc",
        ]
        main(cli_args)
        mock_GitSourceFinder.assert_has_calls(
            [
                call(
                    cache_filepath="abc",
                    hashing_algorithm="md5",
                    save_cache=True,
                    git_repo_root=".",
                ),
                call().get_source(
                    file_hash="ae0dca24c020ff7731877973df4b6a11",
                    git_commit_hash=None,
                    filepath=None,
                ),
            ]
        )
        mock_log.assert_has_calls(EXPECTED_LOG_CALLS)

    def test_file_hash_and_commit_hash(self, mock_GitSourceFinder: Mock, mock_log: Mock):
        mock_GitSourceFinder = self.set_gsf_mock_properties(mock_GitSourceFinder)
        cli_args = [
            "/path/to/main.py",
            "--file_hash",
            "ae0dca24c020ff7731877973df4b6a11",
            "--git_commit_hash",
            "a108021b8436907d2b2d6f8e3676f06229ff16c9",
        ]
        main(cli_args)
        mock_GitSourceFinder.assert_has_calls(
            [
                call(
                    cache_filepath=".gsfcache",
                    hashing_algorithm="md5",
                    save_cache=True,
                    git_repo_root=".",
                ),
                call().get_source(
                    file_hash="ae0dca24c020ff7731877973df4b6a11",
                    git_commit_hash="a108021b8436907d2b2d6f8e3676f06229ff16c9",
                    filepath=None,
                ),
            ]
        )
        mock_log.assert_has_calls(EXPECTED_LOG_CALLS)

    def test_file_hash_and_filepath(self, mock_GitSourceFinder: Mock, mock_log: Mock):
        mock_GitSourceFinder = self.set_gsf_mock_properties(mock_GitSourceFinder)
        cli_args = [
            "/path/to/main.py",
            "--file_hash",
            "ae0dca24c020ff7731877973df4b6a11",
            "--filepath",
            "/path/to/loan.py",
        ]
        main(cli_args)
        mock_GitSourceFinder.assert_has_calls(
            [
                call(
                    cache_filepath=".gsfcache",
                    git_repo_root=".",
                    hashing_algorithm="md5",
                    save_cache=True,
                ),
                call().get_source(
                    file_hash="ae0dca24c020ff7731877973df4b6a11",
                    git_commit_hash=None,
                    filepath="/path/to/loan.py",
                ),
            ]
        )
        mock_log.assert_has_calls(EXPECTED_LOG_CALLS)

    def test_print_source_code_only(self, mock_GitSourceFinder: Mock, mock_log: Mock):
        mock_GitSourceFinder = self.set_gsf_mock_properties(mock_GitSourceFinder)
        cli_args = [
            "/path/to/main.py",
            "--file_hash",
            "ae0dca24c020ff7731877973df4b6a11",
            "--git_commit_hash",
            "a108021b8436907d2b2d6f8e3676f06229ff16c9",
            "--print_hashes=false",
        ]
        main(cli_args)
        mock_GitSourceFinder.assert_has_calls(
            [
                call(
                    cache_filepath=".gsfcache",
                    git_repo_root=".",
                    hashing_algorithm="md5",
                    save_cache=True,
                ),
                call().get_source(
                    file_hash="ae0dca24c020ff7731877973df4b6a11",
                    git_commit_hash="a108021b8436907d2b2d6f8e3676f06229ff16c9",
                    filepath=None,
                ),
            ]
        )
        mock_log.assert_has_calls([call("source_code")])
