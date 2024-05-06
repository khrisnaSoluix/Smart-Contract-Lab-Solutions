from .....utils import symbols
from .....utils import types_utils


defaultAddress = types_utils.FixedValueSpec(
    name="DEFAULT_ADDRESS",
    type="str",
    fixed_value=symbols.DEFAULT_ADDRESS,
    docstring="The default address to which Vault makes Postings.",
)
DEFAULT_ADDRESS = defaultAddress.fixed_value


defaultAsset = types_utils.FixedValueSpec(
    name="DEFAULT_ASSET",
    type="str",
    fixed_value=symbols.DEFAULT_ASSET,
    docstring="The default asset on all non-custom Postings.",
)
DEFAULT_ASSET = defaultAsset.fixed_value


transaction_reference_field_name = types_utils.FixedValueSpec(
    name="TRANSACTION_REFERENCE_FIELD_NAME",
    type="str",
    fixed_value=symbols.TRANSACTION_REFERENCE_FIELD_NAME,
    docstring="If this field is present in the instruction details for a posting instruction, "
    "the value will be used as the reference on any corresponding Experience Layer "
    "transactions. Available on versions 3.2.0+.",
)
TRANSACTION_REFERENCE_FIELD_NAME = transaction_reference_field_name.fixed_value
