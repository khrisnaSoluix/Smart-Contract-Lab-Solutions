# standard libs
import hashlib
import logging
import os
import pathlib
import platform
import re
import sys
from collections import OrderedDict
from contextlib import contextmanager
from importlib import util
from types import ModuleType

# third party
import yaml

markers = ["library"]


def check_banking_layer_repo() -> None:
    for testpath in markers:
        if not os.path.exists(testpath):
            raise Exception(
                "This doesn't look like a valid Banking Layer repo. "
                "Please rerun at the root of the repo"
            )


def init_logger(name: str, log_levels: list[str]) -> logging.Logger:
    """
    :param log_level: logging level name.
    :return:
    """
    logger = logging.getLogger(name)
    logging.basicConfig(format="%(levelname)s - %(message)s")
    for level in log_levels:
        logger.setLevel(level)
    return logger


def check_if_plz() -> bool:
    """
    Check the tests are being run by plz or via Python unittest
    """
    if "plz-out" not in os.getcwd():
        return False
    return True


def get_clu_path_by_system() -> str:
    """
    Determine correct CLU path to use based on architecture
    :return clu_path: path the correct clu binary
    """

    current_system = platform.system()
    if current_system == "Linux":
        clu_path = "tools/clu-linux-amd64"
        return clu_path
    elif current_system == "Darwin":
        clu_path = "tools/clu-darwin-amd64"
        return clu_path
    else:
        raise Exception(f"Unsupported system {current_system}")


def parse_product_manifests(
    product_manifest_file_paths: list[str],
) -> dict[str, dict[str, list[str]]]:
    """
    Takes the list of filepaths relating to the product manifests and parses
    them using the metadata contained in the comments for each section of the
    file and returns a dict containing the product name and the associated
    resources named.

    :param product_manifest_file_paths: list of filepaths
    :return: dict of product_manifests. Each key is a product id and each value is a dict
    of resource type to list of corresponding resource ids
    """
    regex = r"\#\s[-]{9}\s(\w.+)\n"
    product_manifests = {}
    for product_manifest_file_path in product_manifest_file_paths:
        product = pathlib.Path(product_manifest_file_path).stem.split("_manifest")[0]
        product_manifest = OrderedDict()
        with open(product_manifest_file_path, "r", encoding="utf-8") as product_manifest_file:
            product_manifest_yaml = product_manifest_file.read()
        # Retrieve all lines between headers and associate with that RESOURCE header,
        # wherever they are in manifest
        resources = re.findall(regex, product_manifest_yaml)
        base = "# --------- "
        for resource in resources[:-1]:
            search_term = base + resource
            split_start = product_manifest_yaml.split(search_term)
            split_end = split_start[1].split(base)
            product_manifest[resource] = yaml.safe_load(split_end[0])
        # last resource has no closing header
        product_manifest[resources[-1]] = yaml.safe_load(
            product_manifest_yaml.split(base + resources[-1])[1]
        )
        product_manifests[product] = product_manifest
    return product_manifests


def get_hash(hashing_algorithm: str, data: str) -> str:
    return hashlib.new(hashing_algorithm, data.encode("utf-8")).hexdigest()


def get_file_checksum(filepath: str, hashing_algorithm: str) -> str:
    with open(filepath, "r") as f:
        hash_digest = get_hash(hashing_algorithm=hashing_algorithm, data=str(f.read()))
        return hash_digest


def get_file_name(filepath: str) -> str:
    return os.path.basename(filepath)


def get_relative_filepath_from_cwd(filepath: str) -> str:
    fp = pathlib.Path(filepath)
    cwd = pathlib.Path(os.getcwd())
    return str(fp.relative_to(cwd))


@contextmanager
def add_to_path(var: str):
    """
    Temporarily add to the system path variable.
    """
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, var)
    try:
        yield
    finally:
        sys.path = old_path


def path_import(absolute_path, module_name) -> ModuleType | None:
    """implementation taken from
    https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly"""
    with add_to_path(os.path.dirname(absolute_path)):
        spec = util.spec_from_file_location(module_name, absolute_path)
        if spec and spec.loader:
            module = util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        else:
            return None


@contextmanager
def override_logging_level(level: int, logger: str = ""):
    """
    Context manager to temporarily override the logging level set by the logging module.
    This is primarily used to reduce noise when calling third-party modules, of which we have no
    control over their use of the logging module.
    """
    current_logging_level = logging.getLogger(logger).level
    logging.getLogger(logger).setLevel(level)
    try:
        yield
    finally:
        logging.getLogger(logger).setLevel(current_logging_level)
