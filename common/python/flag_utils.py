"""Common utilities for command line flag parsing."""

import logging
import sys
from absl import flags
from typing import Callable


logger = logging.getLogger(__name__)

flags.DEFINE_boolean("help", False, help="Print usage and exit")
flags.DEFINE_enum(
    "log_level",
    "INFO",
    ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"],
    "Level to set root logger to",
)

FLAGS = flags.FLAGS


def parse_argument_list(argv=None, positional=False):
    remaining = FLAGS(argv)[1:]  # First one is the binary name
    if positional:
        if any(x.startswith("-") and x != "-" for x in remaining):
            raise ValueError("Unknown flags passed: %s" % " ".join(remaining))
    elif any(remaining):
        raise ValueError("Unknown flags passed: %s" % " ".join(remaining))
    return remaining


def parse_flags(argv=None, positional=True):
    """Parses incoming command-line flags.

    Args:
      argv: Command line given to the app. Will use sys.argv if not passed.
      positional: Whether to allow positional arguments. Default does not raise on any extra args.
    Raises:
      SystemExit: if given unregistered flags.
    Returns:
      The remainder of the command line, excluding the initial argument (i.e. the first param
      passed to exec(), typically the path to this binary).
    """
    try:
        args = parse_argument_list(argv or sys.argv, positional=positional)
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
