from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from .postings import CustomInstruction
from .enums import PostingInstructionType

from .....utils import symbols, types_utils, exceptions
from .....utils.timezone_utils import validate_timezone_is_utc


class PostingInstructionsDirective:
    def __init__(
        self,
        *,
        posting_instructions: List[CustomInstruction],
        client_batch_id: Optional[str] = None,
        value_datetime: Optional[datetime] = None,
        _from_proto=False,
    ):
        self.posting_instructions = posting_instructions
        self.client_batch_id = client_batch_id
        self.value_datetime = value_datetime
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        iterator = types_utils.get_iterator(
            self.posting_instructions, "CustomInstruction", "posting_instructions", check_empty=True
        )
        if len(self.posting_instructions) > 64:
            raise exceptions.InvalidSmartContractError(
                "Too many posting instructions submitted in the Posting Instructions Directive. "
                f"Number submitted: {len(self.posting_instructions)}. Limit: 64.",
            )
        for pi in iterator:
            types_utils.validate_type(pi, CustomInstruction, hint="List[CustomInstruction]")
            if pi.type != PostingInstructionType.CUSTOM_INSTRUCTION:
                raise exceptions.InvalidSmartContractError(
                    f"Posting instruction of type {pi.type} cannot be instructed from a Contract."
                )
            pi._validate_postings_and_zero_net_sum()  # noqa: SLF001
        if self.value_datetime is not None:
            types_utils.validate_type(self.value_datetime, datetime)
            validate_timezone_is_utc(
                self.value_datetime,
                "value_datetime",
                "PostingInstructionsDirective",
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="PostingInstructionsDirective",
            docstring="""
                A hook directive that instructs a list of posting instructions. Currently only
                [CustomInstruction](#classes-CustomInstruction)s are supported as hook directives.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PostingInstructionsDirective",
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
                name="posting_instructions",
                type="List[CustomInstruction]",
                docstring="""
                    A list of posting instructions that will be atomically accepted or rejected.
                """,
            ),
            types_utils.ValueSpec(
                name="client_batch_id",
                type="Optional[str]",
                docstring="""
                    An ID that can be used as a correlation ID across different posting instruction
                    batches. If not provided, defaults to a unique auto-generated UUID.
                """,
            ),
            types_utils.ValueSpec(
                name="value_datetime",
                type="Optional[datetime]",
                docstring="""
                    Specifies the datetime at which all committed postings of all posting
                    instructions in this directive will affect balances. For most cases,
                    this should not be set and will default to the generated `insertion_datetime`.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                """,
            ),
        ]
