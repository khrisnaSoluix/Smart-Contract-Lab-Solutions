"""Module for loading static files, either from within a .pex or from outside.

Note that this module has been rewritten to use zipfile instead of zipimport.
This is to work around a bug in zipimport which is not threadsafe (it produces the dreaded
"zlib not available" error) due to some code in C. That's triggered by pkg_resources
which uses import underneath, but zipimport just parses the zipfile (and is often faster).
This is all a bit vexing since import is *supposed* to be threadsafe but c'est la vie.
"""

# standard libs
import atexit
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from functools import partial
from io import BytesIO, StringIO
from pathlib import PurePath

_temp_resources = set()

# Determine if we're in a zipfile. If so get a handle on it we can use later.
# If it's not a zip-safe pex we've already been exploded and we don't need this.
_zf = None
if zipfile.is_zipfile(sys.argv[0]):
    _zf = zipfile.ZipFile(sys.argv[0])


def resource_stream(filename, module=None, return_string=False, seekable=False):
    """Provides access to a resource as a file-like object.

    If seekable is True, the returned object will support seek(). If not passed
    it's not guaranteed that it will.
    """
    filename = _filename_and_module(filename, module)
    if _zf:
        try:
            if return_string:
                return StringIO(_zf.read(filename).decode("utf-8"))
            elif seekable:
                return BytesIO(_zf.read(filename))
            return _zf.open(filename)
        except KeyError as err:
            # Getting a KeyError for an unknown file is a bit unintuitive (and definitely
            # breaks some existing code). Convert to something more obvious.
            raise IOError(err)
    return open(filename, "r" if return_string else "rb")


# Provided for compatibility with the above; this used to be a class and many
# things use it under this name.
ResourceStream = resource_stream


def resource_string(filename, module=None, utf8=False):
    """Simpler form where we just want the contents of a file."""
    filename = _filename_and_module(filename, module)
    if _zf:
        if utf8:
            return _zf.read(filename).decode("utf-8")
        return _zf.read(filename)
    with open(filename, "r" if utf8 else "rb") as f:
        contents = f.read()
    return contents


def resource_or_file_string(filename, module=None, utf8=False):
    """As above, but falls back to attempting to load an external file."""
    try:
        if not filename.startswith("/") and resource_exists(filename, module):
            return resource_string(filename, module, utf8)
    except (ValueError, KeyError):
        pass  # Fall back to opening file
    with open(_normalise_platform_path(filename), encoding="utf-8" if utf8 else None) as f:
        return f.read()


def resource_folder(folder, module=None):
    """Extracts a resource folder to an external temporary folder."""
    dest = tempfile.mkdtemp(prefix=folder)
    _temp_resources.add(dest)
    folder = _filename_and_module(folder, module)
    if not _zf:
        # Not in zip, can just copy the directory.
        shutil.copytree(folder, dest)
        return dest
    # Must extract relevant items from the zipfile.
    _zf.extractall(dest, [name for name in _zf.namelist() if name.startswith(folder + "/")])
    # ZipFile.extractall extracts with the full path
    return os.path.join(dest, folder)


def resource_filename(filename, suffix="", prefix=""):
    """Extracts a resource to an external file with an actual name in the filesystem.

    Returns the name of the new file. It will be cleaned up at program exit.
    If you want it removed sooner, or want to be sure it is gone, use cleanup_resource
    to get rid of it. You shouldn't delete it yourself.
    """
    with tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, delete=False) as f:
        _temp_resources.add(f.name)
        f.write(resource_string(filename))
        return f.name


def resource_executable(filename, suffix="", prefix=""):
    """As resource_filename, but makes the resulting file executable."""
    tmp_filename = resource_filename(filename, suffix, prefix)
    os.chmod(tmp_filename, stat.S_IRWXU)
    return tmp_filename


def resource_exists(filename, module=None):
    """Returns true if the given path exists."""
    filename = _filename_and_module(filename, module)
    if not _zf:
        return os.path.exists(filename)
    try:
        _zf.getinfo(filename)
        return True
    except KeyError:
        return False


def resource_isdir(filename, module=None):
    filename = _filename_and_module(filename, module)
    if not _zf:
        return os.path.isdir(filename)

    try:
        info = _zf.getinfo(filename)
    except KeyError:
        return False

    return info.is_dir()


def cleanup_resources(tmp_resources=None):
    """Deletes any temporary files and folders created by resource_filename or resource_folder."""
    # This is a workaround for the fact that when packaged in a pex, this function seems to have no
    # context: that is, no module variable, no imports, nothing. So here we reimport the needed
    # libraries to make it work and clean up everything.
    # standard libs
    import os
    import shutil

    for resource in tmp_resources or _temp_resources:
        if os.path.isdir(resource):
            shutil.rmtree(resource)
        else:
            os.unlink(resource)
    _temp_resources.clear()


def cleanup_resource(resource):
    """Deletes a single temporary file or folder created by resource_filename or resource_folder."""
    if os.path.isdir(resource):
        shutil.rmtree(resource)
    else:
        os.unlink(resource)
    _temp_resources.remove(resource)


def listdir(filename, module=None, fullnames=False):
    """lists the contents of a directory."""
    filename = _filename_and_module(filename, module)
    if not _zf:
        return os.listdir(filename)
    files = [name for name in _zf.namelist() if name.startswith(filename + "/")]
    if fullnames:
        return files  # For compatibility with older usages of the function.
    n = len(filename) + 1
    return sorted(set(name[n:].partition("/")[0] for name in files))


def _filename_and_module(filename, module):
    """Utility to handle our many functions that take both filename and module."""
    # Normalise path by OS
    filename = _normalise_platform_path(filename)
    if module:
        return os.path.join(module.replace(".", os.path.sep), filename)
    return filename


def _normalise_platform_path(filename) -> str:
    """
    Normalises the path based on the platform. This will convert all POSIX and WIN separators to the
    platform.
    """
    # PurePath will attempt to process the path based on the underlying os platform.
    return str(PurePath(filename))


# Clean up any lurking files on exit.
atexit.register(partial(cleanup_resources, _temp_resources))
