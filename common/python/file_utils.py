import common.python.resources as resources


def load_file_contents(path) -> str:
    """
    Try to read the resource file path, which may be given either as a "data"
    under the specific test's BUILD, or loaded as a "resource" under helper.py's BUILD
    """
    try:
        # If the file is given as a "data" under the specific test's BUILD,
        # then we can just read the file path.
        with open(path, encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        # If the file is given as a default "resource" under helper.py's BUILD,
        # we need to invoke common.python.resources.resource_stream to read the data
        # from the built .pex file.
        with resources.resource_stream(path, return_string=True) as resource_file:
            return resource_file.read()
