from functools import lru_cache

from .....utils import exceptions, symbols, types_utils


class SupervisedHooks:
    def __init__(self, *, pre_posting_code=None, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "pre_posting_code": pre_posting_code,
                },
            )
        # This can be extended later to check that at least one hook
        # supervision is specified.
        if not pre_posting_code:
            raise exceptions.InvalidSmartContractError(
                "At least one hook supervision must be specified."
            )
        self.pre_posting_code = pre_posting_code

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisedHooks",
            docstring="""
                Contains information of each hook's
                [SupervisionExecutionMode](#enums-SupervisionExecutionMode).
                At least one hook supervision must be specified.
                Currently only configures pre_posting_code hook supervision.
                **Only available in version 3.12+**
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="pre_posting_code",
                type="Optional[SupervisionExecutionMode]",
                docstring="""
                    If specified, defines the
                    [SupervisionExecutionMode](#enums-SupervisionExecutionMode).
                    for the supervisee's pre_posting_code hook.
                """,
            ),
        ]
