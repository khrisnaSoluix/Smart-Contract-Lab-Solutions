from .....utils import symbols
from .....utils import types_utils


transaction_reference_field_name = types_utils.FixedValueSpec(
    name='TRANSACTION_REFERENCE_FIELD_NAME',
    type='str',
    fixed_value=symbols.TRANSACTION_REFERENCE_FIELD_NAME,
    docstring='If this field is present in the instruction details for a posting instruction, '
              'the value will be used as the reference on any corresponding Experience Layer '
              'transactions. Available on versions 3.2.0+.',
)
