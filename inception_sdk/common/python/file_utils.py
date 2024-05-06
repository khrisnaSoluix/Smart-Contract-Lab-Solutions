# standard libs
import importlib.resources
import importlib.util
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import cast

# inception sdk
import inception_sdk.common.python.resources as resources

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def load_file_contents(path: str) -> str:
    """
    Load a file's contents, handling the following scenarios:
    - a user file within the user's filesystem (e.g. a config file)
    - a user file within a plz pex
    - a framework file, running via plz (i.e. within a pex/zip file) as a python_library
    - a framework file, running via plz (i.e. within a pex/zip file) as a python_wheel
    - a framework file, running from source or pip (e.g. somewhere in site-packages)
    :param path: the path to the file to load, relative to the repo/package root
    """
    is_plz = "plz-out" in os.path.abspath(path)
    sdk_resource = path.startswith("inception_sdk" + os.path.sep)

    # in pip or 'from source' scenarios, importlib will find the actual package path for us
    if sdk_resource and not is_plz:
        _path = Path(path)
        return importlib.resources.read_text(
            # convert a path to a package name (e.g. /path/to/module -> path.to.module)
            str(_path.parent).replace(os.path.sep, "."),
            _path.name,
            "utf-8",
        )

    # Python imports from python_wheels in third_party/python3 are handled via plz's moduledir
    # config, but this doesn't handle data file loads. As we can't reliably tell if we are
    # in a third party python_wheel or a regular python_library, we try loading from both
    try:
        # resource_or_file_string handles both files in pex/zip and external files
        return cast(str, resources.resource_or_file_string(path, utf8=True))
    except FileNotFoundError:
        return cast(
            str,
            resources.resource_or_file_string(
                os.path.join("third_party", "python3", path), utf8=True
            ),
        )


def load_module_from_filepath(module_filepath: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(Path(module_filepath).stem, module_filepath)
    if spec and spec.loader:
        template_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(template_module)
        return template_module
    else:
        raise ImportError(f"Unable to load module from {module_filepath}, invalid spec")
