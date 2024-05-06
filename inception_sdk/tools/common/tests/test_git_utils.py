# standard libs
import unittest
from unittest import TestCase
from unittest.mock import Mock, patch

# third party
from git.repo import Repo

# inception sdk
import inception_sdk.tools.common.git_utils as git_utils


class TestGitUtils(TestCase):
    def test_get_relative_filepath(self):
        mock_git = Mock(working_dir="/my/home/directory/repo_root")
        mock_repo = Mock(git=mock_git)
        rf = git_utils.get_relative_filepath(
            "/my/home/directory/repo_root/library/new_file.py", repo=mock_repo
        )
        self.assertEqual(rf, "library/new_file.py")

    @patch.object(git_utils, "Repository")
    @patch.object(git_utils, "get_hash")
    def test_get_file_checksum_from_commit_hash(self, mock_get_hash: Mock, mock_Repository: Mock):
        filepath = "path/file.py"
        mock_get_hash.return_value = "checksum"
        mock_modified_files = [Mock(source_code="source_code", new_path=filepath)]
        mock_commit = Mock(modified_files=mock_modified_files, hash="commit_hash")
        mock_Repository.return_value = Mock(traverse_commits=Mock(return_value=[mock_commit]))
        checksum = git_utils.get_file_checksum_from_commit_hash(
            filepath=filepath, commit_hash="commit_hash", repo=Mock()
        )
        self.assertEqual(checksum, "checksum")

    @patch.object(git_utils, "get_relative_filepath")
    def test_get_file_checksum_from_commit_hash_hash_doesnt_exist(
        self, mock_get_relative_filepath: Mock
    ):
        mock_get_relative_filepath.return_value = "file.py"
        with self.assertRaises(Exception) as test:
            git_utils.get_file_checksum_from_commit_hash(
                filepath="path/file.py",
                commit_hash="commit_hash",
                repo=Repo.init(),
            )
        self.assertEqual(
            test.exception.args[0],
            "The commit commit_hash defined in the 'single' filtered does not exist",
        )

    @patch.object(git_utils, "Repository")
    @patch.object(git_utils, "get_hash")
    @patch.object(git_utils, "get_relative_filepath")
    def test_get_file_checksum_from_commit_hash_no_file(
        self, mock_get_relative_filepath: Mock, mock_get_hash: Mock, mock_Repository: Mock
    ):
        filepath = "path/file.py"
        mock_get_hash.return_value = "checksum"
        mock_modified_files = [Mock(source_code="source_code", new_path="not_found")]
        mock_commit = Mock(modified_files=mock_modified_files, hash="commit_hash")
        mock_Repository.return_value = Mock(traverse_commits=Mock(return_value=[mock_commit]))
        mock_get_relative_filepath.return_value = "file.py"
        with self.assertRaises(git_utils.GitException) as test:
            git_utils.get_file_checksum_from_commit_hash(
                filepath=filepath, commit_hash="commit_hash", repo=Mock()
            )
        self.assertEqual(
            test.exception.args[0],
            "Unable to find the file file.py in commit commit_hash. Ensure that remote is "
            "up-to-date.",
        )

    @patch.object(git_utils, "get_current_commit_hash")
    @patch.object(git_utils, "get_file_checksum_from_commit_hash")
    def test_get_validated_commit_hash_for_file_checksum(
        self, mock_get_file_checksum_from_commit_hash: Mock, mock_get_current_commit_hash: Mock
    ):
        mock_get_current_commit_hash.return_value = "commit_hash"
        mock_get_file_checksum_from_commit_hash.return_value = "checksum"
        commit_hash = git_utils.get_validated_commit_hash_for_file_checksum(
            filepath="path/file.py", checksum="checksum", repo=Mock()
        )
        self.assertEqual(commit_hash, "commit_hash")

    @patch.object(git_utils, "get_current_commit_hash")
    @patch.object(git_utils, "get_file_checksum_from_commit_hash")
    @patch.object(git_utils, "get_relative_filepath")
    def test_get_validated_commit_hash_for_file_checksum_invalid(
        self,
        mock_get_relative_filepath: Mock,
        mock_get_file_checksum_from_commit_hash: Mock,
        mock_get_current_commit_hash: Mock,
    ):
        mock_get_current_commit_hash.return_value = "commit_hash"
        mock_get_file_checksum_from_commit_hash.return_value = "muskcehc"
        mock_get_relative_filepath.return_value = "file.py"
        with self.assertRaises(git_utils.GitException) as test:
            git_utils.get_validated_commit_hash_for_file_checksum(
                filepath="path/file.py", checksum="checksum", repo=Mock()
            )
        self.assertEqual(
            test.exception.args[0],
            "The checksum of file.py does not match the latest checksum in the Git repo. Ensure "
            "that all changes are committed.",
        )


if __name__ == "__main__":
    unittest.main()
