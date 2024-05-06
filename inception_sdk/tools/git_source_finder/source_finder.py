# standard libs
import hashlib
import logging
import os
import pathlib
import pickle
from dataclasses import dataclass
from os import path
from time import time
from typing import Generator

# third party
from pydriller import Repository
from pydriller.domain.commit import Commit

# inception sdk
from inception_sdk.tools.common.git_utils import BareRepoException, load_repo
from inception_sdk.tools.common.tools_utils import override_logging_level

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class GitSourceFinderResult:
    source_code: str
    file_hash: str
    git_commit_hash: str


class GitSourceFinderCache:
    # the algorithm used to generate file hashes (not commit hashes)
    alg: str
    commit_hashes: set[str]
    # map of file hashes to the commit hash they are found in
    hash_map: dict[str, str]

    def __init__(self) -> None:
        """
        Initialise an empty cache object using default values.
        """
        defaults = self._default_values()
        self.alg = defaults["alg"]
        self.commit_hashes = defaults["commit_hashes"]
        self.hash_map = defaults["hash_map"]

    def _default_values(self) -> dict:
        return {"alg": "md5", "commit_hashes": set(), "hash_map": {}}


class SourceNotFound(Exception):
    pass


class GitSourceFinder:
    """
    GitSourceFinder defines methods to retrieve source files from a Git repo based on the file
    checksum. It will detect a local Git repo and traverse every historic commit made to the repo
    to find an associated source file that matches the checksum provided.
    """

    def __init__(
        self,
        cache_filepath: str | os.PathLike | None = None,
        hashing_algorithm: str = "md5",
        git_repo_root: str | os.PathLike = ".",
        save_cache: bool = True,
    ) -> None:
        """
        Discover the local Git repo and attempt to load the cache file.
        :param cache_filepath: path to a cache to attempt to load and save to (see `save_cache`)
        :param hashing_algorithm: algorithm used to calculate file checksums, can be any
        supported by hashlib https://docs.python.org/3/library/hashlib.html
        :param git_repo_root: path to the git repo root
        :param save_cache: write the cache file to disk to allow speedy loading of commits
        """
        self._save_cache_to_disk = save_cache
        if hashing_algorithm not in hashlib.algorithms_available:
            raise ValueError(f"Unsupported hash type {hashing_algorithm}")
        else:
            self.hashing_algorithm = hashing_algorithm
        repo = load_repo(git_repo_root)
        if repo.git.working_dir is None:
            raise BareRepoException()
        self._git_root = str(repo.git.working_dir)
        self._cache_filepath = cache_filepath or pathlib.Path(".gsfcache")
        self._app_cache = self._load_cache() or GitSourceFinderCache()
        if not self._validate_cache():
            self._app_cache = GitSourceFinderCache()
            self._app_cache.alg = self.hashing_algorithm

    def get_source(
        self,
        file_hash: str,
        git_commit_hash: str | None = None,
        filepath: str | None = None,
    ) -> GitSourceFinderResult:
        """
        Calculate checksums against all source files associated with every commit in the local Git
        repo and return the first match against the hash_digest.
        """
        if not file_hash.strip():
            raise ValueError("hash_digest is not a valid non-empty string")

        if not git_commit_hash and not filepath:
            git_commit_hash = self.get_commit_hash(file_hash)

        if git_commit_hash or filepath:
            with override_logging_level(logging.WARNING):
                commits = Repository(
                    self._git_root, single=git_commit_hash, filepath=filepath
                ).traverse_commits()
            source = self._find_source_from_hash(commits, file_hash)
            if source:
                return source

        raise SourceNotFound(f'No file exists for {self.hashing_algorithm} hash "{file_hash}"')

    def get_commit_hash(self, file_hash: str) -> str | None:
        """
        Return the Git commit hash that contains the source file checksum hash_digest.
        """
        if file_hash in self._app_cache.hash_map:
            return self._app_cache.hash_map[file_hash]
        else:
            self._populate_cache()
            return self._app_cache.hash_map.get(file_hash)

    def _hash(self, data: str) -> str:
        return hashlib.new(self.hashing_algorithm, data.encode("utf-8")).hexdigest()

    def _find_source_from_hash(
        self, commits: Generator[Commit, None, None], file_hash: str
    ) -> GitSourceFinderResult | None:
        for commit in commits:
            for modified_file in commit.modified_files:
                if modified_file.source_code:
                    modified_file_hash = self._hash(modified_file.source_code)
                    if modified_file_hash == file_hash:
                        return GitSourceFinderResult(
                            source_code=modified_file.source_code,
                            file_hash=file_hash,
                            git_commit_hash=commit.hash,
                        )

    def _load_cache(self) -> GitSourceFinderCache | None:
        log.info(f"Loading cache from `{self._cache_filepath}`")
        if path.isfile(self._cache_filepath):
            with open(self._cache_filepath, "rb") as file:
                cache = pickle.load(file)
                if isinstance(cache, GitSourceFinderCache):
                    return cache
        else:
            log.warning("Cache path does not point to a file")

    def _validate_cache(self) -> bool:
        if not self._app_cache:
            return False
        if (
            self._app_cache.commit_hashes is None
            or self._app_cache.hash_map is None
            or self._app_cache.alg != self.hashing_algorithm
        ):
            log.warning(
                f"Cache file {self._cache_filepath} is empty or invalid (algorithm mismatch)"
            )
            return False
        else:
            return True

    def _clean_cache(self, all_git_commit_hashes: list[str]) -> None:
        invalid_hashes = [
            cached_hash
            for cached_hash in self._app_cache.commit_hashes
            if cached_hash not in all_git_commit_hashes
        ]
        invalid_checksums = [
            checksum
            for checksum, git_commit_hash in self._app_cache.hash_map.items()
            if git_commit_hash in invalid_hashes
        ]
        if invalid_hashes or invalid_checksums:
            log.info("Removing stale commit hashes from cache")
            for invalid_hash in invalid_hashes:
                self._app_cache.commit_hashes.remove(invalid_hash)
            for checksum in invalid_checksums:
                self._app_cache.hash_map.pop(checksum)

    def _save_cache(self):
        if self._save_cache_to_disk:
            with open(self._cache_filepath, "wb+") as file:
                log.info(f"Writing cache file {self._cache_filepath}")
                pickle.dump(self._app_cache, file)

    def _populate_cache(self):
        self._t_start = time()
        log.info("Populating the cache, this may take several minutes...")
        with override_logging_level(logging.WARNING):
            commits = list(Repository(self._git_root, num_workers=8).traverse_commits())
        commit_hashes = [commit.hash for commit in commits]
        self._clean_cache(commit_hashes)
        update_made = False
        for i, commit in enumerate(commits):
            self._report_status(i, len(commits))
            if commit.hash not in self._app_cache.commit_hashes:
                self._app_cache.hash_map.update(self._get_source_file_hash_map(commit))
                self._app_cache.commit_hashes.add(commit.hash)
                update_made = True
        if update_made:
            self._save_cache()

    def _get_source_file_hash_map(self, commit: Commit) -> dict[str, str]:
        hash_map = {}
        if commit.hash not in self._app_cache.commit_hashes:
            for modified_file in commit.modified_files:
                if modified_file.source_code:
                    hash_map.update({self._hash(modified_file.source_code): commit.hash})
        return hash_map

    def _report_status(self, current_iteration: int, total_interations: int):
        if time() - self._t_start > 10:
            self._t_start = time()
            percent_complete = f"{current_iteration/total_interations*100:2.0f}%"
            log.info(f"{current_iteration}/{total_interations} ({percent_complete}) complete.")
