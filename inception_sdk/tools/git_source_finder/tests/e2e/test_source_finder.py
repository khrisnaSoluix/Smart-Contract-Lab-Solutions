# standard libs
import unittest
from unittest import TestCase

# inception sdk
from inception_sdk.tools.git_source_finder.source_finder import (
    GitSourceFinder,
    GitSourceFinderResult,
    SourceNotFound,
)

INPUT_CHECKSUM = "ae0dca24c020ff7731877973df4b6a11"
INPUT_GIT_HASH = "a108021b8436907d2b2d6f8e3676f06229ff16c9"

EXPECTED_OUTPUT = GitSourceFinderResult(
    source_code="Self-service banking layer components for Inception\n",
    file_hash=INPUT_CHECKSUM,
    git_commit_hash=INPUT_GIT_HASH,
)


class TestSourceFinder(TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def test_checksum_only(self):
        gsf_output = GitSourceFinder(save_cache=False).get_source(file_hash=INPUT_CHECKSUM)
        self.assertEqual(gsf_output, EXPECTED_OUTPUT)

    def test_checksum_doesnt_exist(self):
        with self.assertRaises(SourceNotFound) as test:
            GitSourceFinder(save_cache=False).get_source("unknown")
        self.assertEqual(
            test.exception.args[0],
            'No file exists for md5 hash "unknown"',
        )

    def test_get_source_from_commit(self):
        gsf_output = GitSourceFinder(save_cache=False).get_source(
            file_hash=INPUT_CHECKSUM,
            git_commit_hash=INPUT_GIT_HASH,
        )
        self.assertEqual(gsf_output, EXPECTED_OUTPUT)

    def test_get_source_from_commit_commit_doesnt_exist(self):
        with self.assertRaises(Exception) as test:
            GitSourceFinder(save_cache=False).get_source(
                file_hash=INPUT_CHECKSUM,
                git_commit_hash="unknown",
            )
        self.assertEqual(
            test.exception.args[0],
            "The commit unknown defined in the 'single' filtered does not exist",
        )

    def test_get_source_from_filepath(self):
        gsf_output = GitSourceFinder(save_cache=False).get_source(
            file_hash=INPUT_CHECKSUM, filepath="README.md"
        )
        self.assertEqual(gsf_output, EXPECTED_OUTPUT)

    def test_get_source_from_filepath_filepath_doesnt_exist(self):
        with self.assertRaises(SourceNotFound) as test:
            GitSourceFinder(save_cache=False).get_source(
                file_hash=INPUT_CHECKSUM,
                filepath="unknown",
            )
        self.assertEqual(
            test.exception.args[0],
            'No file exists for md5 hash "ae0dca24c020ff7731877973df4b6a11"',
        )


if __name__ == "__main__":
    unittest.main()
