import importlib
import os
import sys


def init():
    """Registers import hook to handle binary modules."""
    # Hack for operating outside a pex; if Please hasn't adjusted the import path then
    # we do so here to get third-party modules.
    # Add the path correctly even if e.g. it is in site-packages.
    third_party_path = "third_party" + os.sep + "python3"
    if not any(third_party_path in x for x in sys.path):
        for p in sys.path:
            if os.path.isdir(os.path.join(p, third_party_path)):
                sys.path.insert(1, os.path.join(p, third_party_path))
                sys.meta_path.insert(0, ModuleDirImport("third_party.python3"))
                break


class ModuleDirImport(object):
    """Handles imports to a directory equivalently to them being at the top level.

    This is a copy of Please's builtin hook which gets added here if we are not within
    a pex so third_party imports continue to work.
    """

    def __init__(self, module_dir):
        self.prefix = module_dir + "."

    def find_module(self, fullname, path=None):
        """Attempt to locate module. Returns self if found, None if not."""
        if fullname.startswith(self.prefix):
            return self

    def load_module(self, fullname):
        """Actually load a module that we said we'd handle in find_module."""
        module = importlib.import_module(fullname[len(self.prefix) :])
        sys.modules[fullname] = module
        return module
