"""Common utilities for command line flag parsing."""

# standard libs
import logging
import os
import sys
from typing import Callable

# third party
from absl import flags

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

flags.DEFINE_boolean("help", False, help="Print usage and exit")
flags.DEFINE_enum(
    "log_level",
    "INFO",
    ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"],
    "Level to set root logger to",
)

FLAGS = flags.FLAGS


def _parse_argument_list(
    argv: list[str] | None = None, positional_only=False, allow_unknown: bool = False
):
    remaining = FLAGS(argv, known_only=allow_unknown)[1:]  # First one is the binary name
    if allow_unknown:
        logger.warning(f"Ignoring unrecognised flags {remaining}")
        return remaining
    if positional_only:
        if any(x.startswith("-") and x != "-" for x in remaining):
            raise ValueError("Unknown flags passed: %s" % " ".join(remaining))
    elif any(remaining):
        raise ValueError("Unknown flags passed: %s" % " ".join(remaining))
    return remaining


def parse_flags(
    argv: list[str] | None = None, positional: bool = True, allow_unknown: bool = False
):
    """Parses incoming command-line flags.

    :param argv: Command line given to the app. Will use sys.argv if not passed.
    :param positional: If true, only positional arguments are allowed (cannot start
     with `-` unless equal to `-`)
    :param allow_unknown: If true, known flags. Unknown/undefined
      arguments are allowed, but will be logged as a warning. Note: this maps 1-2-1 with absl's
      known_only flag, which is named a little confusingly
    :raise ValueError: if unknown and/or positional flags are passed in and known_only and/or
      positional are not set to True, respectively
    SystemExit: if help flag was set
    :return: The remainder of the command line, excluding the initial argument (i.e. the first param
      passed to exec(), typically the path to this binary).
    """
    try:
        args = _parse_argument_list(
            argv or sys.argv, positional_only=positional, allow_unknown=allow_unknown
        )
        if FLAGS.help:
            logger.info(str(FLAGS))
            sys.exit(0)
        return args
    except flags.Error as err:
        if FLAGS.is_parsed() and FLAGS.help:
            logger.info(str(FLAGS))
            sys.exit(0)
        logger.exception(err)
        raise err


def apply_flag_modifiers(flag_modifiers: dict[str, Callable]):
    """
    Updates the values of flags by assigning the return value of Callable to the flag.

    :param flag_modifiers: dict key is the flag name, dict value is a Callable object that is
    called with the current flag value as an argument.
    """
    for flag_name, modifier in flag_modifiers.items():
        current_flag_value = FLAGS.get_flag_value(flag_name, None)
        setattr(FLAGS, flag_name, modifier(current_flag_value))
