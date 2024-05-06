from functools import lru_cache

from .....utils import exceptions as utils_exceptions
from .....utils import symbols
from .....utils import types_utils


class InvalidContractParameter(utils_exceptions.InvalidContractParameter):

    # (TM-21728): Move full declaration of exception classes into versions
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ExceptionSpec(
            name="InvalidContractParameter",
            docstring="An Exception to be raised when Parameter objects appear malformed.",
            constructor_args=[],
        )


class Rejected(utils_exceptions.Rejected):

    # (TM-21728): Move full declaration of exception classes into versions
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ExceptionSpec(
            name="Rejected",
            docstring=(
                "An Exception raised by the [pre_posting_code](../../smart_contracts_api_reference3XX/hooks/#pre_posting_code) "
                "hook to reject a [PostingInstruction](#classes-PostingInstruction), or raised by "
                "the [pre_parameter_change_code](../../smart_contracts_api_reference3XX/hooks/#pre_parameter_change_code) "  # noqa: E501
                "to reject a [Parameter](#classes-Parameter)."
            ),
            constructor_args=[
                types_utils.ValueSpec(
                    name="message",
                    type="str",
                    docstring=(
                        "The text message describing the reason for the exception. "
                        "Exposed in the `contract_violations` field of the"
                        "[PostingInstructionBatch](/api/core_api/#Posting_instruction_batches-PostingInstructionBatch) in the Core API."  # noqa: E501
                    ),
                ),
                types_utils.ValueSpec(
                    name="reason_code",
                    type="Optional[RejectedReason]",
                    docstring=(
                        "The optional reason code for the rejection; defaults to UNKNOWN_REASON. "
                        "Exposed in the `contract_violations` field of the"
                        "[PostingInstructionBatch](/api/core_api/#Posting_instruction_batches-PostingInstructionBatch) in the Core API."  # noqa: E501
                    ),
                ),
            ],
        )
