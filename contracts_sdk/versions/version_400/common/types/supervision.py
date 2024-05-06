from functools import lru_cache

from .....utils import exceptions, symbols, types_utils
from typing import Optional
from .enums import SupervisionExecutionMode


class SupervisedHooks:
    def __init__(self, *, pre_posting_hook: SupervisionExecutionMode = None):
        self.pre_posting_hook = pre_posting_hook
        self._validate_attributes()

    def _validate_attributes(self):
        # This can be extended later to check that at least one hook
        # supervision is specified.
        if not self.pre_posting_hook:
            raise exceptions.InvalidSmartContractError(
                "At least one hook supervision must be specified."
            )

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
                Currently only configures pre_posting_hook hook supervision.
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
                name="pre_posting_hook",
                type="SupervisionExecutionMode",
                docstring="""
                    If specified, defines the
                    [SupervisionExecutionMode](#enums-SupervisionExecutionMode).
                    for the supervisee's pre_posting_hook.
                """,
            ),
        ]


class SmartContractDescriptor:
    def __init__(
        self,
        *,
        alias: str,
        smart_contract_version_id: str,
        supervise_post_posting_hook: bool = False,
        supervised_hooks: Optional[SupervisedHooks] = None,
    ):
        self.alias = alias
        self.smart_contract_version_id = smart_contract_version_id
        self.supervise_post_posting_hook = supervise_post_posting_hook
        self.supervised_hooks = supervised_hooks
        self._validate_attributes()

    def _validate_attributes(self):
        if self.alias is None:
            raise exceptions.StrongTypingError("SmartContractDescriptor 'alias' must be populated")

        if self.smart_contract_version_id is None:
            raise exceptions.StrongTypingError(
                "SmartContractDescriptor 'smart_contract_version_id' must be populated"
            )

        types_utils.validate_type(
            self.supervised_hooks,
            SupervisedHooks,
            hint="SupervisedHooks",
            is_optional=True,
            prefix="SmartContractDescriptor.supervised_hooks",
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SmartContractDescriptor",
            docstring="""
                Each Supervisor Contract must declare the Smart Contracts that it supervises. Using
                the Smart Contract Descriptor object, a Product Version Id is declared with an alias
                that is used throughout the Supervisor Contract to refer to this Smart Contract
                Product Version.
                An optional flag can be used to declare that a supervisee will have
                its post_posting_hook supervised.
                The supervised_hooks attribute can be populated to declare that a supervisee will
                have additional hooks supervised, with specific
                [SupervisionExecutionModes](#enums-SupervisionExecutionMode).
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SmartContractDescriptor",
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
                name="alias",
                type="str",
                docstring="""
                    An alias for the Product Version to use throughout the Supervisor Contract.
                """,
            ),
            types_utils.ValueSpec(
                name="smart_contract_version_id",
                type="str",
                docstring="""
                    A string ID for the Product Version of a Smart Contract that will be supervised
                    by this Supervisor Contract.
                """,
            ),
            types_utils.ValueSpec(
                name="supervise_post_posting_hook",
                type="bool",
                docstring="""
                    A bool to denote whether this supervisee's post_posting_hook should be
                    supervised.
                """,
            ),
            types_utils.ValueSpec(
                name="supervised_hooks",
                type="Optional[SupervisedHooks]",
                docstring="""
                    This attribute can be populated with a
                    [SupervisedHooks](#classes-SupervisedHooks)
                    value to specify which hooks are supervised, and with which execution mode.
                """,
            ),
        ]
