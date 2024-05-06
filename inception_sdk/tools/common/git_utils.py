# standard libs
import logging
import os

# third party
import git
from git.exc import GitCommandError
from git.repo import Repo
from pydriller import ModificationType, Repository

# inception sdk
from inception_sdk.common.python.flag_utils import flags
from inception_sdk.tools.common.tools_utils import (
    get_file_checksum,
    get_hash,
    override_logging_level,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

FLAG_GIT_REPO_ROOT = "git_repo_root"
flags.DEFINE_string(
    name=FLAG_GIT_REPO_ROOT,
    default=".",
    required=False,
    help="path to the root of the Git repo. Repos in parent directories are also considered",
)


class BareRepoException(Exception):
    def __init__(self) -> None:
        super().__init__("Repo has no working dir - this is the sign of a bare repo")


class GitException(Exception):
    pass


def load_repo(path: str | os.PathLike | None = None, **kwargs) -> Repo:
    log.info(f"Looking for repo at or above `{path}`")
    try:
        repo = Repo(path, search_parent_directories=True, **kwargs)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
        log.exception(f"Could not find git repository using path `{path}`")
        raise e

    if repo.git.working_dir is None:
        raise BareRepoException()

    log.info(f"Using repo at `{repo.working_tree_dir}`")
    return repo


def get_relative_filepath(filepath: str, repo: Repo) -> str:
    if repo.git.working_dir is None:
        raise BareRepoException()
    return filepath.removeprefix(str(repo.git.working_dir) + "/").removeprefix("./")


def get_file_checksum_from_commit_hash(
    filepath: str,
    commit_hash: str,
    repo: Repo,
    hashing_algorithm: str = "md5",
) -> str:
    """
    Given a filepath, return the file checksum after validating that the file exists in the
    specified commit.

    :param filepath: this must be the absolute filepath of the file being evaluated
    """
    if repo.git.working_dir is None:
        raise BareRepoException()
    with override_logging_level(logging.WARNING):
        # Due to the high frequency of logging messages from pydriller we fully evaluate the
        # generator returned by traverse_commits() before iterating over them with a reduced
        # logging level.
        commits = list(Repository(str(repo.git.working_dir), single=commit_hash).traverse_commits())
    for commit in commits:
        for modified_file in commit.modified_files:
            # as filepath is absolute, we can reliably use endswith() to find a file match
            if modified_file.new_path and filepath.endswith(modified_file.new_path):
                if modified_file.source_code:
                    return get_hash(hashing_algorithm, modified_file.source_code)
                elif modified_file.change_type == ModificationType.RENAME:
                    return get_file_checksum(filepath, hashing_algorithm)
    raise GitException(
        f"Unable to find the file {get_relative_filepath(filepath, repo)} in commit {commit_hash}. "
        "Ensure that remote is up-to-date."
    )


def get_current_commit_hash(filepath: str, repo: Repo) -> str:
    try:
        return repo.git.log("-n", "1", "--pretty=format:%H", filepath)
    except GitCommandError as e:
        log.exception(e)
        raise GitException(
            f"Unable to find file {get_relative_filepath(filepath, repo)} in the Git repo."
        )


def get_validated_commit_hash_for_file_checksum(
    filepath: str,
    checksum: str,
    repo: Repo,
    hashing_algorithm: str = "md5",
) -> str:
    commit_hash = get_current_commit_hash(filepath=filepath, repo=repo)
    committed_file_checksum = get_file_checksum_from_commit_hash(
        filepath=filepath,
        commit_hash=commit_hash,
        repo=repo,
        hashing_algorithm=hashing_algorithm,
    )
    if checksum == committed_file_checksum:
        return commit_hash
    else:
        raise GitException(
            f"The checksum of {get_relative_filepath(filepath, repo)} does not match the latest "
            "checksum in the Git repo. Ensure that all changes are committed."
        )
