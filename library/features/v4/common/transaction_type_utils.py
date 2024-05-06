# standard libs
from typing import Iterable

# features
import library.features.v4.common.utils as utils


def match_transaction_type(
    *,
    posting_instruction: utils.PostingInstructionTypeAlias,
    values: Iterable[str],
    key: str = "type",
) -> bool:
    """
    Checks if the Posting Instruction matches a given type

    :param posting_instruction: A single Posting Instruction type.
    :param values: a list of values to match against.
    :param key: the key where the transaction type is stored in the posting instruction details.
        Defaults to `type`
    :return: returns a Boolean on if the transaction type falls in the checklist.
    """
    return posting_instruction.instruction_details.get(key, "") in values
