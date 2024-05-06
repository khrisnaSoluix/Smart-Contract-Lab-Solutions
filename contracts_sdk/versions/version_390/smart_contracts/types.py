from functools import lru_cache

from ...version_380.smart_contracts.types import *  # noqa: F401, F403
from ...version_380.smart_contracts import types as types380
from ....utils import symbols, types_utils


class ContractModule:
    def __init__(self, *, alias, expected_interface=None, _from_proto=False):
        self._from_proto = _from_proto
        if not self._from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "alias": alias,
                    "expected_interface": expected_interface,
                },
            )
        self.alias = alias
        self.expected_interface = expected_interface

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ContractModule",
            docstring="""
                **Only available in version 3.9+**
                A Smart Contract must declare any Contract Modules needed for it to run.
                Using the ContractModule object, the Smart Contract must provide an 'alias' that
                will be used to reference the Contract Module code and can optionally define the
                expected interfaces of function names, arguments and return types within the
                SharedFunction object.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="alias",
                type="str",
                docstring="The alias for the ContractModule as referenced in the Smart Contract.",
            ),
            types_utils.ValueSpec(
                name="expected_interface",
                type="Optional[List[SharedFunction]]",
                docstring="The list of functions expected in the ContractModule.",
            ),
        ]


class SharedFunction:
    def __init__(self, *, name, args=None, return_type=None, _from_proto=False):
        self._from_proto = _from_proto
        if not self._from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "name": name,
                    "args": args,
                    "return_type": return_type,
                },
            )
        self.name = name
        self.args = args
        self.return_type = return_type

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SharedFunction",
            docstring="""
                **Only available in version 3.9+**
                A SharedFunction defines a function from a ContractModule that may be used in the
                Smart Contract.
                It defines the expected arguments as SharedFunctionArg objects and also defines the
                return type.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="name",
                type="str",
                docstring="The name of the SharedFunction as defined in the ContractModule.",
            ),
            types_utils.ValueSpec(
                name="args",
                type="Optional[List[SharedFunctionArg]]",
                docstring="The list of arguments to the function in the ContractModule.",
            ),
            types_utils.ValueSpec(
                name="return_type",
                type="Optional[str]",
                docstring="""
                    Type annotation of the return value of the function in the ContractModule.
                """,
            ),
        ]


class SharedFunctionArg:
    def __init__(self, *, name, type=None, _from_proto=False):
        self._from_proto = _from_proto
        if not self._from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "name": name,
                    "type": type,
                },
            )
        self.name = name
        self.type = type

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SharedFunctionArg",
            docstring="""
                **Only available in version 3.9+**
                An argument to a SharedFunction in a ContractModule.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="name",
                type="str",
                docstring="The name of the function argument as defined in the Contract Module.",
            ),
            types_utils.ValueSpec(
                name="type",
                type="Optional[str]",
                docstring="The type annotation for the argument to the function.",
            ),
        ]


def types_registry():
    TYPES = types380.types_registry()
    TYPES["ContractModule"] = ContractModule
    TYPES["SharedFunction"] = SharedFunction
    TYPES["SharedFunctionArg"] = SharedFunctionArg
    return TYPES
