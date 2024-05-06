# standard libs
import logging
import os
import sys
from pathlib import Path
from typing import Callable

# inception sdk
from inception_sdk.common.python.flag_utils import FLAGS, apply_flag_modifiers, flags, parse_flags
from inception_sdk.tools.common import git_utils
from inception_sdk.tools.renderer import RendererConfig, render_smart_contract

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

INPUT_TEMPLATE = "input_template"
OUTPUT_FILEPATH = "output_filepath"
USE_GIT = "use_git"
USE_FULL_FILEPATH_IN_HEADERS = "use_full_filepath_in_headers"
FORCE_OVERWRITE = "force"
APPLY_FORMATTING = "apply_formatting"

flags.DEFINE_string(
    name=INPUT_TEMPLATE,
    short_name="in",
    default=None,
    required=True,
    help="filepath to the template file",
)

flags.DEFINE_string(
    name=OUTPUT_FILEPATH,
    short_name="out",
    default=None,
    required=True,
    help="filepath to write the rendered smart contract",
)

flags.DEFINE_bool(
    name=USE_FULL_FILEPATH_IN_HEADERS,
    default=True,
    required=False,
    help="rendered output module headers will contain full filepaths to the modules they were "
    "rendered from",
)

flags.DEFINE_bool(
    name=USE_GIT,
    default=True,
    required=False,
    help="if set, Git commit hashes are added to rendered output module headers. The input "
    "template must be in a valid Git repository for this feature to work.",
)

flags.DEFINE_bool(
    name=FORCE_OVERWRITE,
    default=False,
    required=False,
    help="If set, will overwrite the output without asking.",
)

flags.DEFINE_bool(
    name=APPLY_FORMATTING,
    default=True,
    required=False,
    help="Optionally disable formatting the rendered contract.",
)


def get_absolute_filepath(flag_value: str) -> str:
    path = Path(flag_value)
    return str(path.absolute())


flag_modifiers: dict[str, Callable] = {
    INPUT_TEMPLATE: get_absolute_filepath,
    OUTPUT_FILEPATH: Path,
    git_utils.FLAG_GIT_REPO_ROOT: Path,
}


def build_config_from_flags() -> RendererConfig:
    return RendererConfig(
        output_filepath=getattr(FLAGS, OUTPUT_FILEPATH),
        use_git=getattr(FLAGS, USE_GIT),
        git_repo_root=getattr(FLAGS, git_utils.FLAG_GIT_REPO_ROOT),
        use_full_filepath_in_headers=getattr(FLAGS, USE_FULL_FILEPATH_IN_HEADERS),
        apply_formatting=getattr(FLAGS, APPLY_FORMATTING),
    )


def validate_flags():
    if not confirm_overwrite(getattr(FLAGS, OUTPUT_FILEPATH)):
        sys.exit()
    if not confirm_input_exists(getattr(FLAGS, INPUT_TEMPLATE)):
        sys.exit(f"Input filepath '{getattr(FLAGS, INPUT_TEMPLATE)}' could not be found")


def confirm_overwrite(filepath: str) -> bool:
    if os.path.isfile(filepath):
        if getattr(FLAGS, FORCE_OVERWRITE):
            return True
        return input("File already exists, overwrite? [y/N] ").upper() == "Y"
    elif os.path.exists(filepath):
        sys.exit(f"invalid filepath: '{Path(filepath).absolute()}' is not a file")
    else:
        return True


def confirm_input_exists(filepath: str) -> bool:
    return os.path.isfile(filepath)


def main(argv: list[str]):
    parse_flags(argv, positional=False)
    apply_flag_modifiers(flag_modifiers)
    validate_flags()
    config = build_config_from_flags()
    try:
        render_smart_contract(getattr(FLAGS, INPUT_TEMPLATE), config)
    except ModuleNotFoundError:
        log.exception(
            "Rendering failed due to a ModuleNotFoundError. Does your "
            "PYTHONPATH include all relevant template and feature folders?"
        )


if __name__ == "__main__":
    main(sys.argv)
