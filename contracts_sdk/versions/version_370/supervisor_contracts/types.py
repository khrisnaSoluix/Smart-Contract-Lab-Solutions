from functools import lru_cache

from ...version_360.supervisor_contracts.types import *  # noqa: F401, F403
from ..common.types import (
    CalendarEvent,
    CalendarEvents,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionBatchDirective,
    HookDirectives,
    TransactionCode,
)
from ...version_360.supervisor_contracts import types as types360
from ....utils import types_utils, symbols


class SmartContractDescriptor(types360.SmartContractDescriptor):
    def __init__(self, *, alias, smart_contract_version_id, supervise_post_posting_hook=False):
        self._spec().assert_constructor_args(
            self._registry, {"supervise_post_posting_hook": supervise_post_posting_hook}
        )
        super().__init__(alias=alias, smart_contract_version_id=smart_contract_version_id)
        self.supervise_post_posting_hook = supervise_post_posting_hook

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SmartContractDescriptor",
            docstring="""
                **Only available in version 3.4+.**
                Each Supervisor Contract must declare the Smart Contracts that it supervises. Using
                the Smart Contract Descriptor object, a Product Version Id is declared with an alias
                that is used throughout the Supervisor Contract to refer to this Smart Contract
                Product Version. An optional flag can be used to declare that a supervisee will have
                its post_posting_code hook supervised (**only available in version 3.7+**).
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

        super_public_attr = super()._public_attributes(language_code)
        super_public_attr.append(
            types_utils.ValueSpec(
                name="supervise_post_posting_hook",
                type="bool",
                docstring="""
                    A bool to denote whether this supervisee's post_posting_code hook should be
                    supervised.
                """,
            ),
        )
        return super_public_attr


def types_registry():
    TYPES = types360.types_registry()
    TYPES["SmartContractDescriptor"] = SmartContractDescriptor
    TYPES["CalendarEvent"] = CalendarEvent
    TYPES["CalendarEvents"] = CalendarEvents
    TYPES["PostingInstruction"] = PostingInstruction
    TYPES["PostingInstructionBatch"] = PostingInstructionBatch
    TYPES["PostingInstructionBatchDirective"] = PostingInstructionBatchDirective
    TYPES["HookDirectives"] = HookDirectives
    TYPES["TransactionCode"] = TransactionCode

    return TYPES
