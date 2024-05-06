# standard libs
import os
import shutil
import sys

# third party
import json5

# inception sdk
from inception_sdk.common.python.flag_utils import FLAGS, flags, parse_flags

LOCAL_SETTINGS_FOLDER = ".vscode"
LOCAL_SETTINGS_PATH = f"{LOCAL_SETTINGS_FOLDER}/settings.json"
LOCAL_EXTENSIONS_PATH = f"{LOCAL_SETTINGS_FOLDER}/extensions.json"
LOCAL_CSPELL_PATH = f"{LOCAL_SETTINGS_FOLDER}/cspell.json"

INC_SETTINGS_FOLDER = ".inc_vscode"
INC_ENFORCED_SETTINGS_PATH = f"{INC_SETTINGS_FOLDER}/enforced_settings.json"
INC_OPTIONAL_SETTINGS_PATH = f"{INC_SETTINGS_FOLDER}/optional_settings.json"
INC_EXTENSIONS_PATH = f"{INC_SETTINGS_FOLDER}/extensions.json"
INC_CSPELL_PATH = f"{INC_SETTINGS_FOLDER}/cspell.json"

INCLUDE_OPTIONAL = "include_optional"
flags.DEFINE_bool(
    name=INCLUDE_OPTIONAL,
    default=False,
    required=False,
    help="if set, include the optional settings when extending local settings.json",
)


def _extend_json_file_content(local_dict: dict, inc_dict: dict) -> dict:
    for key, inc_value in inc_dict.items():
        # Check if the key already exists in the first dictionary
        if key in local_dict:
            # If the value is a list, extend it instead of overwriting it
            if isinstance(local_dict[key], list) and isinstance(inc_value, list):
                print(f'Extending "{key}" list')
                local_dict[key].extend([item for item in inc_value if item not in local_dict[key]])

            elif local_dict[key] != inc_value:
                print(
                    f'Key "{key}" already exists with value: {local_dict[key]}, '
                    f"and will not be overwritten by {inc_value}"
                )
        else:
            # If the key doesn't exist, add the key-value pair to the first dictionary
            local_dict[key] = inc_value
    return local_dict


def _get_dict_content_of_json_file(filepath: str) -> dict:
    if os.path.isfile(filepath):
        with open(filepath, "r") as f:
            return json5.load(f)
    else:
        return {}


def copy_extension_recommendations():
    print("\nCopying `extensions.json`")
    os.makedirs(os.path.dirname(LOCAL_EXTENSIONS_PATH), exist_ok=True)
    shutil.copy2(INC_EXTENSIONS_PATH, LOCAL_EXTENSIONS_PATH)
    print(f"Recommended extensions updated in file: {LOCAL_EXTENSIONS_PATH}")


def update_cspell():
    print("\nHandling `cspell.json`")

    local_cspell = _get_dict_content_of_json_file(LOCAL_CSPELL_PATH)
    inc_cspell = _get_dict_content_of_json_file(INC_CSPELL_PATH)

    with open(LOCAL_CSPELL_PATH, "w") as f:
        updated_cspell = _extend_json_file_content(local_cspell, inc_cspell)
        json5.dump(updated_cspell, f, indent=4, quote_keys=True, trailing_commas=False)
        print(f"cSpell settings updated in file: {LOCAL_CSPELL_PATH}")


def extend_local_settings():
    print("\nHandling `settings.json`")

    local_settings = _get_dict_content_of_json_file(LOCAL_SETTINGS_PATH)
    inc_enforced_settings = _get_dict_content_of_json_file(INC_ENFORCED_SETTINGS_PATH)

    with open(LOCAL_SETTINGS_PATH, "w") as f:
        updated_settings = _extend_json_file_content(local_settings, inc_enforced_settings)

        if getattr(FLAGS, INCLUDE_OPTIONAL):
            with open(INC_OPTIONAL_SETTINGS_PATH, "r") as optional_f:
                inc_optional_settings = json5.load(optional_f)
            updated_settings = _extend_json_file_content(updated_settings, inc_optional_settings)

        json5.dump(updated_settings, f, indent=4, quote_keys=True, trailing_commas=False)
        print(f"Settings updated in file: {LOCAL_SETTINGS_PATH}")


if __name__ == "__main__":
    parse_flags(sys.argv)
    copy_extension_recommendations()
    update_cspell()
    extend_local_settings()
