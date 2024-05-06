from .symbols import VaultRejectionReasonCode


class ContractException(Exception):
    """
    Exception subclass used in contract exceptions - supports
    documentation attributes.
    """

    pass


class InvalidSmartContractError(ContractException):
    """
    A special exception thrown when a smart contract is invalid. These errors should not be logged
    at error level.
    """

    pass


class AmbiguousDatetimeProvided(ContractException):
    """
    An exception to be raised when provided `start_date` or `end_date` in Execution Schedule is
    ambiguous in the Events Timezone. For example 2019-11-03T01:30:00 in `US/Pacific` timezone is an
    ambiguous datetime, as it happens during daylight savings time transition. It could be
    interpreted as both 8:30AM and 9:30AM UTC.
    """

    pass


class InvalidPostingInstructionException(Exception):
    """
    An exception raised when PostingInstruction or PostingInstructionBatch is invalid
    or fail ClientTransaction validation rules.
    """

    pass


class InvalidContractParameter(ContractException):
    """
    An exception to be raised when there is a logical error in the content of a hook argument
    or one or more ``[../types/ContractParameter]`` objects.
    """

    pass


class Rejected(ContractException):
    """
    An exception raised by the ``[../hooks/pre_posting_code]`` hook to reject a
    ``[../types/PostingInstruction]``, and raised by the ``[../hooks/pre_parameter_change_code]``
    hook to reject a ``[../types/Parameter]``. The attribute `reason_code` defines the rejection
    reason; see ``[../types/VaultRejectionReasonCode]``.
    """

    def __init__(self, message, reason_code=VaultRejectionReasonCode.UNKNOWN_REASON):
        super().__init__(message)
        # An int64 value representing failure reason.
        self.reason_code = reason_code


class IllegalPython(Exception):
    """
    A special exception thrown when running the ast contract parse.
    The exception wrapper uses this to return a stack trace showing the error
    in the user's contract.
    """

    pass


class UnsupportedApiVersion(Exception):
    """
    A special exception thrown when running or parsing a contract that uses an unsupported
    Contracts Language library version. The exception wrapper returns a corresponding error
    message.
     e.g `UnsupportedApiVersion: (9, 9, 9)`.
    """

    pass


class InDevelopmentApiVersion(UnsupportedApiVersion):
    """
    An exception thrown when parsing a contract that uses a Contracts Language library version,
    which is currently in development. The exception wrapper returns a corresponding error
    message. e.g `InDevelopmentApiVersion: (9, 9, 9)`.
    """

    pass


class StrongTypingError(ValueError):
    """
    This defines our own Exception class so that inside contract execution,
    we can get to the top level and build an UnexpectedError object.
    For v4+, this error is raised in native to proto conversion if there is a type error.
    If possible, the stack trace is adjusted to show that the error is raised in the user code.
    """

    pass
