import typing

from .....utils import types_utils


anyObject = types_utils.NativeObjectSpec(
    name='Any',
    object=typing.Any,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Any'
)

callableObject = types_utils.NativeObjectSpec(
    name='Callable',
    object=typing.Callable,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Callable'
)

defaultDictObject = types_utils.NativeObjectSpec(
    name='DefaultDict',
    object=typing.DefaultDict,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.DefaultDict'
)

dictObject = types_utils.NativeObjectSpec(
    name='Dict',
    object=typing.Dict,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Dict'
)

iterableObject = types_utils.NativeObjectSpec(
    name='Iterable',
    object=typing.Iterable,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Iterable'
)

iteratorObject = types_utils.NativeObjectSpec(
    name='Iterator',
    object=typing.Iterator,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Iterator'
)

listObject = types_utils.NativeObjectSpec(
    name='List',
    object=typing.List,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.List'
)

mappingObject = types_utils.NativeObjectSpec(
    name='Mapping',
    object=typing.Mapping,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Mapping'
)

namedTupleObject = types_utils.NativeObjectSpec(
    name='NamedTuple',
    object=typing.NamedTuple,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.NamedTuple'
)

newTypeObject = types_utils.NativeObjectSpec(
    name='NewType',
    object=typing.NewType,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.NewType'
)

noReturnObject = types_utils.NativeObjectSpec(
    name='NoReturn',
    object=typing.NoReturn,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.NoReturn'
)

optionalObject = types_utils.NativeObjectSpec(
    name='Optional',
    object=typing.Optional,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Optional'
)

setObject = types_utils.NativeObjectSpec(
    name='Set',
    object=typing.Set,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Set'
)

typeObject = types_utils.NativeObjectSpec(
    name='Type',
    object=typing.Type,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Type'
)

tupleObject = types_utils.NativeObjectSpec(
    name='Tuple',
    object=typing.Tuple,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Tuple'
)

unionObject = types_utils.NativeObjectSpec(
    name='Union',
    object=typing.Union,
    package=typing,
    docs='https://docs.python.org/3/library/typing.html#typing.Union'
)
