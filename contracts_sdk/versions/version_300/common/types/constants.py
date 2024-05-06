from .....utils import symbols
from .....utils import types_utils


defaultAddress = types_utils.FixedValueSpec(
    name="DEFAULT_ADDRESS",
    type="str",
    fixed_value=symbols.DEFAULT_ADDRESS,
    docstring="The default address to which Vault makes Postings.",
)

defaultAsset = types_utils.FixedValueSpec(
    name="DEFAULT_ASSET",
    type="str",
    fixed_value=symbols.DEFAULT_ASSET,
    docstring="The default asset on all non-custom Postings.",
)
