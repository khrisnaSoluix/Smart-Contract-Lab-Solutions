# standard libs
import unittest
from unittest.mock import Mock, patch

# inception sdk
import inception_sdk.tools.git_source_finder.source_finder as source_finder
from inception_sdk.tools.git_source_finder.source_finder import (
    GitSourceFinder,
    GitSourceFinderCache,
    GitSourceFinderResult,
    SourceNotFound,
)


class TestGitSourceFinder(unittest.TestCase):
    def create_mock_commit(self, num_modified_files: int = 1) -> Mock:
        def get_source_code(suffix: str):
            return f"source_code{suffix}"

        mock_modified_files = [
            Mock(source_code=get_source_code(str(i))) for i in range(num_modified_files)
        ]
        mock_commit = Mock(modified_files=mock_modified_files, hash="git_commit_hash")
        return mock_commit

    def create_test_cache(self, cache_values: dict) -> GitSourceFinderCache:
        test_cache = GitSourceFinderCache()
        for k, v in cache_values.items():
            setattr(test_cache, k, v)
        return test_cache

    def test_init_unrecognised_hash_alg(self):
        with self.assertRaises(ValueError) as test:
            GitSourceFinder(hashing_algorithm="unknown")
        self.assertEqual(
            test.exception.args[0],
            "Unsupported hash type unknown",
        )

    @patch.object(GitSourceFinder, "_validate_cache")
    @patch.object(source_finder, "load_repo")
    @patch.object(GitSourceFinder, "_load_cache")
    def test_init_recognised_hash_alg(
        self, mock_load_cache: Mock, mock_load_repo: Mock, mock_validate_cache: Mock
    ):
        mock_validate_cache.return_value = False
        gsf = GitSourceFinder(hashing_algorithm="sha1")
        self.assertEqual(gsf._app_cache.alg, "sha1")
        mock_load_cache.assert_called_once()
        mock_load_repo.assert_called_once()
        mock_validate_cache.assert_called_once()

    @patch.object(GitSourceFinder, "_load_cache")
    @patch.object(GitSourceFinder, "_validate_cache")
    @patch.object(source_finder, "load_repo")
    @patch.object(source_finder, "Repository")
    @patch.object(GitSourceFinder, "get_commit_hash")
    def test_get_source(
        self,
        mock_get_commit_hash: Mock,
        mock_Repository: Mock,
        mock_load_repo: Mock,
        mock_validate_cache: Mock,
        mock_load_cache: Mock,
    ):
        source_code = "source_code"
        mock_get_commit_hash.return_value = "commit_hash"
        mock_modified_files = [Mock(source_code=source_code)]
        mock_commit = Mock(modified_files=mock_modified_files, hash="commit_hash")
        mock_Repository.return_value = Mock(traverse_commits=Mock(return_value=[mock_commit]))
        mock_validate_cache.return_value = False
        gsf = GitSourceFinder()
        self.assertEqual(
            gsf.get_source("4828120ab5cdbdfdad1e0fccebdb6622"),
            GitSourceFinderResult(
                source_code=source_code,
                file_hash="4828120ab5cdbdfdad1e0fccebdb6622",
                git_commit_hash="commit_hash",
            ),
        )
        mock_Repository.assert_called_once()
        mock_load_repo.assert_called_once()
        mock_load_cache.assert_called_once()

    @patch.object(GitSourceFinder, "_load_cache")
    @patch.object(GitSourceFinder, "_validate_cache")
    @patch.object(source_finder, "load_repo")
    def test_get_source_no_hash(
        self,
        mock_load_repo: Mock,
        mock_validate_cache: Mock,
        mock_load_cache: Mock,
    ):
        mock_validate_cache.return_value = False
        gsf = GitSourceFinder()
        with self.assertRaises(ValueError) as test:
            gsf.get_source("")
        mock_load_repo.assert_called_once()
        mock_load_cache.assert_called_once()
        self.assertEqual(
            test.exception.args[0],
            "hash_digest is not a valid non-empty string",
        )

    @patch.object(GitSourceFinder, "_validate_cache")
    @patch.object(source_finder, "load_repo")
    @patch.object(source_finder, "Repository")
    @patch.object(source_finder.log, "info")
    def test_get_source_hash_doesnt_exist_in_repo(
        self,
        mock_log_info: Mock,
        mock_Repository: Mock,
        mock_load_repo: Mock,
        mock_validate_cache: Mock,
    ):
        mock_validate_cache.return_value = False
        gsf = GitSourceFinder()
        with self.assertRaises(SourceNotFound) as test:
            gsf.get_source(file_hash="abcdef123456789")
        self.assertEqual(
            test.exception.args[0],
            'No file exists for md5 hash "abcdef123456789"',
        )
        mock_log_info.assert_called_with("Populating the cache, this may take several minutes...")
        mock_Repository.assert_called_once()
        mock_load_repo.assert_called_once()

    def test_get_commit_hash(self):
        mock_app_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"git_commit_hash"},
                "hash_map": {"checksum": "git_commit_hash"},
            }
        )
        mock_gsf = Mock(_app_cache=mock_app_cache)
        commit_hash = GitSourceFinder.get_commit_hash(mock_gsf, "checksum")
        self.assertEqual(commit_hash, "git_commit_hash")

    def test_get_commit_hash_doesnt_exist(self):
        mock_app_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"git_commit_hash"},
                "hash_map": {"checksum": "git_commit_hash"},
            }
        )
        mock_gsf = Mock(_app_cache=mock_app_cache)
        commit_hash = GitSourceFinder.get_commit_hash(mock_gsf, "")
        self.assertEqual(commit_hash, None)

    def test_hash(self):
        mock_gsf = Mock(hashing_algorithm="md5")
        self.assertEqual(
            GitSourceFinder._hash(mock_gsf, "data"), "8d777f385d3dfec8815d20f7496026dc"
        )

    def test_validate_cache_valid(self):
        valid_app_cache = GitSourceFinderCache()
        mock_gsf = Mock(_app_cache=valid_app_cache, hashing_algorithm=valid_app_cache.alg)
        self.assertTrue(GitSourceFinder._validate_cache(mock_gsf))

    @patch.object(source_finder.log, "warning")
    def test_validate_cache_invalid_different_alg(self, mock_log: Mock):
        valid_app_cache = GitSourceFinderCache()
        mock_gsf = Mock(
            _app_cache=valid_app_cache, hashing_algorithm="sha1", _cache_filepath="cache/file"
        )
        self.assertFalse(GitSourceFinder._validate_cache(mock_gsf))
        mock_log.assert_called_with(
            "Cache file cache/file is empty or invalid (algorithm mismatch)"
        )

    @patch.object(source_finder.log, "warning")
    def test_validate_cache_empty_defaults(self, mock_log: Mock):
        empty_cache = GitSourceFinderCache()
        self.assertEqual(empty_cache.alg, "md5")
        self.assertEqual(empty_cache.commit_hashes, set())
        self.assertEqual(empty_cache.hash_map, {})
        mock_log.assert_not_called()

    @patch.object(source_finder.log, "info")
    @patch.object(source_finder, "Repository")
    def test_populate_cache_empty(self, mock_Repository: Mock, mock_log: Mock):
        mock_Repository.return_value = Mock(
            traverse_commits=Mock(return_value=[self.create_mock_commit()])
        )
        expected_hash_map = {"checksum": "commit_hash"}
        mock_get_source_file_hash_map = Mock(return_value=expected_hash_map)
        mock_gsf = Mock(
            _app_cache=GitSourceFinderCache(),
            _get_source_file_hash_map=mock_get_source_file_hash_map,
        )
        GitSourceFinder._populate_cache(mock_gsf)
        self.assertEqual(mock_gsf._app_cache.hash_map, expected_hash_map)
        self.assertEqual(mock_gsf._app_cache.commit_hashes, {"git_commit_hash"})
        mock_log.assert_called_with("Populating the cache, this may take several minutes...")
        mock_Repository.assert_called()
        mock_gsf._report_status.assert_called()
        mock_gsf._save_cache.assert_called()

    @patch.object(source_finder.log, "info")
    @patch.object(source_finder, "Repository")
    def test_populate_cache_not_empty(self, mock_Repository: Mock, mock_log: Mock):
        mock_Repository.return_value = Mock(
            traverse_commits=Mock(return_value=[self.create_mock_commit()])
        )
        initial_hash_map = {"checksum": "git_commit_hash"}
        mock_get_source_file_hash_map = Mock(return_value=initial_hash_map)
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"git_commit_hash_2"},
                "hash_map": {"checksum_2": "git_commit_hash_2"},
            }
        )
        mock_gsf = Mock(
            _app_cache=populated_cache,
            _get_source_file_hash_map=mock_get_source_file_hash_map,
        )
        GitSourceFinder._populate_cache(mock_gsf)
        self.assertEqual(
            mock_gsf._app_cache.hash_map,
            {"checksum_2": "git_commit_hash_2"} | initial_hash_map,
        )
        self.assertEqual(
            mock_gsf._app_cache.commit_hashes, {"git_commit_hash_2", "git_commit_hash"}
        )
        mock_log.assert_called_once_with("Populating the cache, this may take several minutes...")
        mock_Repository.assert_called_once()
        mock_gsf._report_status.assert_called_once()
        mock_gsf._save_cache.assert_called_once()

    @patch.object(source_finder.log, "info")
    @patch.object(source_finder, "Repository")
    def test_populate_cache_already_populated(self, mock_Repository: Mock, mock_log: Mock):
        mock_Repository.return_value = Mock(
            traverse_commits=Mock(return_value=[self.create_mock_commit()])
        )
        initial_hash_map = {"checksum": "git_commit_hash"}
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"git_commit_hash"},
                "hash_map": initial_hash_map,
            }
        )
        mock_gsf = Mock(_app_cache=populated_cache)
        GitSourceFinder._populate_cache(mock_gsf)
        self.assertEqual(
            mock_gsf._app_cache.hash_map,
            initial_hash_map,
        )
        self.assertEqual(mock_gsf._app_cache.commit_hashes, {"git_commit_hash"})
        mock_log.assert_called_once_with("Populating the cache, this may take several minutes...")
        mock_Repository.assert_called()
        mock_gsf._report_status.assert_called()
        mock_gsf._get_source_file_hash_map.assert_not_called()
        mock_gsf._save_cache.assert_not_called()

    @patch.object(source_finder, "Repository")
    def test_get_source_file_hash_map_already_exists(self, mock_Repository: Mock):
        mock_Repository.return_value = Mock(
            traverse_commits=Mock(return_value=[self.create_mock_commit()])
        )
        initial_hash_map = {"checksum": "git_commit_hash"}
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"git_commit_hash"},
                "hash_map": initial_hash_map,
            }
        )
        mock_gsf = Mock(_app_cache=populated_cache)
        hash_map = GitSourceFinder._get_source_file_hash_map(mock_gsf, self.create_mock_commit())
        mock_gsf._hash.assert_not_called()
        self.assertEqual(hash_map, {})

    @patch.object(source_finder, "Repository")
    def test_get_source_file_hash_map_update_required(self, mock_Repository: Mock):
        mock_Repository.return_value = Mock(
            traverse_commits=Mock(return_value=[self.create_mock_commit()])
        )
        initial_hash_map = {"old_checksum": "old_commit_hash"}
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"old_commit_hash"},
                "hash_map": initial_hash_map,
            }
        )
        mock_hash = Mock(return_value="checksum")
        mock_gsf = Mock(_app_cache=populated_cache, _hash=mock_hash)
        hash_map = GitSourceFinder._get_source_file_hash_map(mock_gsf, self.create_mock_commit())
        mock_gsf._hash.assert_called_once_with("source_code0")
        self.assertEqual(hash_map, {"checksum": "git_commit_hash"})

    @patch.object(source_finder.log, "info")
    def test_clean_cache_stale_records(self, mock_log_info: Mock):
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"stale", "a", "b", "c"},
                "hash_map": {
                    "checksum1": "stale",
                    "checksum2": "stale",
                    "checksum3": "a",
                    "checksum4": "b",
                    "checksum5": "c",
                },
            }
        )
        git_commit_hashes = ["a", "b", "c"]
        mock_gsf = Mock(_app_cache=populated_cache)
        GitSourceFinder._clean_cache(mock_gsf, git_commit_hashes)
        mock_log_info.assert_called_with("Removing stale commit hashes from cache")
        self.assertEqual(mock_gsf._app_cache.commit_hashes, {"a", "b", "c"})
        self.assertEqual(
            mock_gsf._app_cache.hash_map,
            {
                "checksum3": "a",
                "checksum4": "b",
                "checksum5": "c",
            },
        )

    @patch.object(source_finder.log, "info")
    def test_clean_cache_no_stale_records(self, mock_log_info: Mock):
        populated_cache = self.create_test_cache(
            {
                "alg": "md5",
                "commit_hashes": {"a", "b", "c"},
                "hash_map": {
                    "checksum1": "a",
                    "checksum2": "b",
                    "checksum3": "c",
                },
            }
        )
        git_commit_hashes = ["a", "b", "c"]
        mock_gsf = Mock(_app_cache=populated_cache)
        GitSourceFinder._clean_cache(mock_gsf, git_commit_hashes)
        mock_log_info.assert_not_called()
        self.assertEqual(mock_gsf._app_cache.commit_hashes, {"a", "b", "c"})
        self.assertEqual(
            mock_gsf._app_cache.hash_map,
            {
                "checksum1": "a",
                "checksum2": "b",
                "checksum3": "c",
            },
        )


if __name__ == "__main__":
    unittest.main()
