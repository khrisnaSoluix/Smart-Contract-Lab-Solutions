import decimal
from .....utils import types_utils


ROUND_CEILING = types_utils.NativeObjectSpec(
    name='ROUND_CEILING',
    object=decimal.ROUND_CEILING,
    package=decimal,
    description='**Only available in version 3.3+.**',
)

ROUND_DOWN = types_utils.NativeObjectSpec(
    name='ROUND_DOWN',
    object=decimal.ROUND_DOWN,
    package=decimal,
    description='**Only available in version 3.3+.**',
)

ROUND_HALF_EVEN = types_utils.NativeObjectSpec(
    name='ROUND_HALF_EVEN',
    object=decimal.ROUND_HALF_EVEN,
    package=decimal,
    description='**Only available in version 3.3+.**',
)

ROUND_05UP = types_utils.NativeObjectSpec(
    name='ROUND_05UP',
    object=decimal.ROUND_05UP,
    package=decimal,
    description='**Only available in version 3.3+.**',
)
