# standard libs
import logging
import os
import sys

# inception sdk
from inception_sdk.common.python.flag_utils import FLAGS, flags, parse_flags
from inception_sdk.tools.git_source_finder.source_finder import GitSourceFinder

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

flags.DEFINE_string(
    name="file_hash",
    short_name="h",
    default=None,
    required=True,
    help="file hash to find",
)

flags.DEFINE_string(
    name="git_commit_hash",
    short_name="g",
    default=None,
    required=False,
    help="specific Git commit hash to check against, providing a commit hash will greatly speed "
    "up file retrieval if cache is not populated",
)

flags.DEFINE_string(
    name="hashing_algorithm",
    short_name="alg",
    default="md5",
    required=False,
    help="hashing algorithm used to calculate and compare the checksum of Git source files with the"
    "checksum provided",
)

flags.DEFINE_string(
    name="filepath",
    short_name="f",
    required=False,
    default=None,
    help="specific filepath within the repo used to search revisions for provided checksum match",
)

flags.DEFINE_string(
    name="cache_filepath",
    required=False,
    default=".gsfcache",
    help="path to save the cache to/read existing cache from. Mandatory if `save_cache` is True",
)

flags.DEFINE_boolean(
    name="save_cache", default=True, required=False, help="write the cache to disk"
)

flags.DEFINE_boolean(
    name="print_hashes",
    default=True,
    required=False,
    help="optionally disable printing the checksum and Git commit hash after the file source code",
)


def main(argv: list[str]):
    parse_flags(argv)
    gsf = GitSourceFinder(
        cache_filepath=FLAGS.cache_filepath,
        hashing_algorithm=FLAGS.hashing_algorithm,
        save_cache=FLAGS.save_cache,
        git_repo_root=FLAGS.git_repo_root,
    )
    gsf_result = gsf.get_source(
        file_hash=FLAGS.file_hash,
        git_commit_hash=FLAGS.git_commit_hash,
        filepath=FLAGS.filepath,
    )

    log.info(gsf_result.source_code)

    if FLAGS.print_hashes:
        log.info(f"File hash ({gsf.hashing_algorithm}): {gsf_result.file_hash}")
        log.info(f"Git commit hash: {gsf_result.git_commit_hash}")


if __name__ == "__main__":
    main(sys.argv)
