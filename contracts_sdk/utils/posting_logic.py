from datetime import datetime
from decimal import Decimal
from typing import Dict, List, NamedTuple, Optional, Tuple

from .exceptions import InvalidPostingInstructionException
from .symbols import DEFAULT_ADDRESS, DEFAULT_ASSET, PostingInstructionType

SECONDARY_POSTING_INSTRUCTIONS = [
    PostingInstructionType.AUTHORISATION_ADJUSTMENT,
    PostingInstructionType.SETTLEMENT,
    PostingInstructionType.RELEASE,
]
PRIMARY_POSTING_INSTRUCTIONS = [
    PostingInstructionType.INBOUND_AUTHORISATION,
    PostingInstructionType.OUTBOUND_AUTHORISATION,
]
NON_CHAINABLE_INSTRUCTIONS = [
    PostingInstructionType.INBOUND_HARD_SETTLEMENT,
    PostingInstructionType.OUTBOUND_HARD_SETTLEMENT,
    PostingInstructionType.TRANSFER,
]

CUSTOM_INSTRUCTIONS = PostingInstructionType.CUSTOM_INSTRUCTION


# Below data classes are internal data types used only in the scope of this posting logic
# module. Final results will be converted to a versioned
# public data types defined in the Contracts API.
class CommittedPosting(NamedTuple):
    account_id: str
    amount: Decimal
    denomination: str
    credit: bool
    phase: int
    account_address: str = DEFAULT_ADDRESS
    asset: str = DEFAULT_ASSET


class BalanceKey(NamedTuple):
    account_address: str
    asset: str
    denomination: str
    phase: int


class BalanceValue(NamedTuple):
    debit: Decimal
    credit: Decimal


class ClientTransactionUpdate(NamedTuple):
    at_datetime: datetime
    committed_postings: List[CommittedPosting]
    balances: Dict[BalanceKey, BalanceValue]
    completed: bool
    released: bool


class SingleAccountClientTransaction:
    """
    Stores all the CommittedPostings for a given account_id and client_transaction_id.
    Keeps track of the overall balance of the Transaction and its state.
    """

    _client_transaction_id: str
    _account_id: str
    _updates: List[ClientTransactionUpdate]
    _first_type: str

    def __init__(self, client_transaction_id: str, account_id: str) -> None:
        self._client_transaction_id = client_transaction_id
        self._account_id = account_id
        self._updates = []

    @property
    def last_update(self) -> Optional[ClientTransactionUpdate]:
        return self._updates[-1] if self._updates else None

    def balances(self, *, at_datetime: datetime = None) -> Dict[BalanceKey, BalanceValue]:
        """
        Returns the balances state of the client transaction for the provided datetime.
        :param at_datetime:
        :return: the balance state
        """
        if not self.last_update:
            return {}

        if not at_datetime:  # Return latest
            return self.last_update.balances

        index = next(
            (i for i, update in enumerate(self._updates) if update.at_datetime > at_datetime),
            len(self._updates),
        )
        return self._updates[index - 1].balances if index else {}

    def add_committed_postings(
        self,
        at_datetime: datetime,
        committed_postings: List[CommittedPosting],
        instruction_type: str,
        final: bool = False,  # Only used for Settlement PIs
    ) -> None:
        # Validate the committed postings for the Posting Instruction
        self._validate_committed_postings(committed_postings, instruction_type, final=final)
        # Validate that datetime is set - None is not supported
        if not at_datetime:
            raise InvalidPostingInstructionException(
                "All posting instructions within a ClientTransaction have to "
                "have a value_datetime set."
            )

        if self.last_update:
            # We already have at least one instruction for the same client transaction
            self._validate_secondary_instruction(at_datetime, instruction_type)
        else:
            # The committed postings are validated - all their types are the same
            self._first_type = instruction_type
            # First instruction within the Client Transaction
            self._validate_primary_instruction(instruction_type)

        balances_diff, completed, released = self._process_committed_postings(
            committed_postings, instruction_type, final
        )

        self._updates.append(
            ClientTransactionUpdate(
                at_datetime,
                committed_postings,
                balances=self._merge_balances(self.balances(), balances_diff),
                completed=completed,
                released=released,
            )
        )

    def _validate_committed_postings(
        self, committed_postings: List[CommittedPosting], instruction_type: str, final: bool = False
    ):
        if not committed_postings:
            raise InvalidPostingInstructionException("Committed Postings required")
        for committed_posting in committed_postings:
            if committed_posting.account_id != self._account_id:
                raise InvalidPostingInstructionException(
                    "Cannot add this Committed Posting with account ID "
                    f"{committed_posting.account_id} to the Client Transaction "
                    f"for account ID {self._account_id}"
                )

        if final and instruction_type != PostingInstructionType.SETTLEMENT:
            raise InvalidPostingInstructionException(
                "Final flag can only be used with Settlement Posting Instructions"
            )

    @staticmethod
    def _validate_primary_instruction(instruction_type: str) -> None:
        if instruction_type in SECONDARY_POSTING_INSTRUCTIONS:
            raise InvalidPostingInstructionException(
                f"A ClientTransaction cannot start with {instruction_type}"
            )
        elif instruction_type not in (
            PRIMARY_POSTING_INSTRUCTIONS + NON_CHAINABLE_INSTRUCTIONS + [CUSTOM_INSTRUCTIONS]
        ):
            raise InvalidPostingInstructionException(f"Unknown instruction type {instruction_type}")

    def _validate_secondary_instruction(self, at_datetime: datetime, instruction_type: str) -> None:
        last_state = self.last_update
        if not last_state:
            raise InvalidPostingInstructionException(
                "Secondary instruction cannot be added to an empty ClientTransaction"
            )

        if at_datetime < last_state.at_datetime:
            raise InvalidPostingInstructionException(
                "ClientTransaction does not support backdating"
            )

        if last_state.completed or last_state.released:
            raise InvalidPostingInstructionException(
                f"Client Transaction (id {self._client_transaction_id}) has already been finalised"
            )

        if instruction_type in PRIMARY_POSTING_INSTRUCTIONS + NON_CHAINABLE_INSTRUCTIONS:
            raise InvalidPostingInstructionException(
                f"Cannot add {instruction_type} to existing "
                f"ClientTransaction (id {self._client_transaction_id})"
            )
        elif instruction_type in SECONDARY_POSTING_INSTRUCTIONS:
            if self._first_type not in PRIMARY_POSTING_INSTRUCTIONS:
                raise InvalidPostingInstructionException(
                    f"Cannot add {instruction_type} "
                    f"for an existing ClientTransaction (id {self._client_transaction_id}) "
                    f"that did not start with an {PostingInstructionType.INBOUND_AUTHORISATION}"
                    f" or an {PostingInstructionType.OUTBOUND_AUTHORISATION}"
                )
        elif instruction_type == CUSTOM_INSTRUCTIONS:
            if self._first_type != CUSTOM_INSTRUCTIONS:
                raise InvalidPostingInstructionException(
                    f"Cannot add {instruction_type} "
                    f"for an existing ClientTransaction (id {self._client_transaction_id}) "
                    f"that did not start with a {PostingInstructionType.CUSTOM_INSTRUCTION}"
                )
        else:
            raise InvalidPostingInstructionException(f"Unknown instruction type {instruction_type}")

    def _process_committed_postings(
        self, committed_postings: List[CommittedPosting], instruction_type: str, final: bool = False
    ) -> Tuple[Dict[BalanceKey, BalanceValue], bool, bool]:
        # Postings are validated - so the type is consistent
        completed = released = False
        if instruction_type == PostingInstructionType.SETTLEMENT:
            completed = final
        elif instruction_type == PostingInstructionType.RELEASE:
            released = True
        # Get balance diff from the committed postings
        balances_diff = derive_balance_diff_from_committed_postings(committed_postings)

        return balances_diff, completed, released

    @staticmethod
    def _merge_balances(latest_balances, new_balances_diff):
        # Merge current balances with balances changes
        balances = dict(latest_balances)  # Shallow copy
        for key, value in new_balances_diff.items():
            if key in balances:  # Update
                balances[key] = BalanceValue(
                    debit=(balances[key].debit + value.debit),
                    credit=(balances[key].credit + value.credit),
                )
            else:  # Add
                balances[key] = value

        return balances


def derive_balance_diff_from_committed_postings(
    committed_postings: List[CommittedPosting],
) -> Dict[BalanceKey, BalanceValue]:
    balance_diff: Dict[BalanceKey, BalanceValue] = {}
    for committed_posting in committed_postings:
        balance_diff_key = BalanceKey(
            account_address=committed_posting.account_address,
            asset=committed_posting.asset,
            denomination=committed_posting.denomination,
            phase=committed_posting.phase,
        )

        debit, credit = Decimal(0), Decimal(0)
        if balance_diff_key in balance_diff:
            credit = balance_diff[balance_diff_key].credit
            debit = balance_diff[balance_diff_key].debit

        if committed_posting.credit:
            credit += Decimal(committed_posting.amount)
        else:
            debit += Decimal(committed_posting.amount)
        balance_diff[balance_diff_key] = BalanceValue(debit=debit, credit=credit)

    return balance_diff
