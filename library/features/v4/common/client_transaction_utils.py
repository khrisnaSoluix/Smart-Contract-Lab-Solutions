# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Iterable, Optional

# features
import library.features.v4.common.utils as utils

# contracts api
from contracts_api import ClientTransaction, PostingInstructionType


def sum_client_transactions(
    *,
    cutoff_datetime: datetime,
    client_transactions: dict[str, ClientTransaction],
    denomination: str,
) -> tuple[Decimal, Decimal]:
    """
    Sum the net amount credited to and debited from an account by the given client_transactions
    since a given cut off point in a specific denomination. The impact of chainable instructions is
    considered in the Auth, unless the subsequent instructions increase the auth'd amount.
    For example:
    - an inbound auth before cut off and settlement for same amount X after cut off will result in 0
      credit and debit.
    - an inbound auth and settlement for same amount X, both after cut off will result in the amount
      in credit = X and debit = 0
    - an inbound auth before cut off for amount X and settlement after cut off for Y, where Y > X,
      will result in credit = Y - X and debit = 0

    :param cutoff_datetime: postings value timestamped before this datetime are excluded from the
    totals.
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param denomination: denomination for which the sums are being calculated, client transactions
    in other denomination will be ignored
    :return: Sum of credits, sum of debits for given client transactions since the cut-off in the
    specified denomination. Both values are >= 0
    """
    amount_debited = Decimal(0)
    amount_credited = Decimal(0)

    for transaction in client_transactions.values():
        if transaction.denomination == denomination:
            transaction_amount = _get_total_transaction_impact(transaction=transaction)

            # We can't do `.before()` on transaction effects, so we get 'at' the latest timestamp
            # before the cutoff timestamp instead (max granularity is 1 us)
            cutoff_datetime -= relativedelta(microseconds=1)

            amount_before_cutoff = _get_total_transaction_impact(
                transaction=transaction, effective_datetime=cutoff_datetime
            )

            amount = transaction_amount - amount_before_cutoff

            # ClientTransactionEffects are always computed on a LIABILITY basis, so this logic
            # works for ASSET and LIABILITY contracts
            if amount > 0:
                amount_credited += amount
            else:
                amount_debited += abs(amount)

    return amount_credited, amount_debited


def sum_debits_by_instruction_details_key(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    cutoff_datetime: datetime,
    key: str,
    value: str,
    client_transaction_ids_to_ignore: Optional[list[str]] = None,
) -> Decimal:
    """
    Determines the net debit amount for a given transaction type since the cut off:
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - type is determined by the specified key-value pair on the first posting instruction of a
    given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to consider
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param cutoff_datetime: datetime from which to include client transaction postings, inclusive
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :param client_transaction_ids_to_ignore: list of client transaction ids to ignore (e.g. the
    current posting being processed)
    :return: the net withdrawal amount, filtered according to the arguments. This number is <= 0
    """

    in_scope_transactions = filter_client_transactions(
        client_transactions=client_transactions,
        denomination=denomination,
        client_transaction_ids_to_ignore=client_transaction_ids_to_ignore,
        key=key,
        value=value,
    )

    return sum_client_transactions(
        cutoff_datetime=cutoff_datetime,
        client_transactions=in_scope_transactions,
        denomination=denomination,
    )[1]


def sum_debits_by_type(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    cutoff_datetime: datetime,
    key: str,
    values: Iterable[str],
    client_transaction_ids_to_ignore: Optional[Iterable[str]] = None,
) -> dict[str, Decimal]:
    """
    Determines the total debit amount for the specified transaction types since the cut off:
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - transaction type is determined by the value of the specified key in the instruction_details
    of first posting instruction of a given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to match
    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param cutoff_datetime: datetime from which to include client transaction postings, inclusive
    :param key: key to look up in the instruction details
    :param values: values against the key in the instruction details to include
    :param client_transaction_ids_to_ignore: client transaction ids to exclude (e.g. the
    current posting being processed)
    :return: the net withdrawal amount per transaction type, filtered according to the arguments.
    This number is >= 0
    """

    in_scope_transactions = filter_client_transactions_by_type(
        client_transactions=client_transactions,
        denomination=denomination,
        client_transaction_ids_to_ignore=client_transaction_ids_to_ignore,
        key=key,
        values=values,
    )

    return {
        transaction_type: sum_client_transactions(
            cutoff_datetime=cutoff_datetime,
            client_transactions=transactions,
            denomination=denomination,
        )[1]
        for transaction_type, transactions in in_scope_transactions.items()
    }


def filter_client_transactions(
    *,
    client_transactions: dict[str, ClientTransaction],
    denomination: str,
    key: str,
    value: str,
    client_transaction_ids_to_ignore: Optional[list[str]] = None,
) -> dict[str, ClientTransaction]:
    """
    Filters client transactions to only include client transactions with:
    - the specified denomination
    - no custom instructions
    - non-released status
    - the specified key-value pair on the first posting instruction

    :param client_transactions: the client transactions to filter
    :param denomination: the denomination to match
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :param client_transaction_ids_to_ignore: list of specific client transaction ids to filter out
    :return: the filtered client transactions. Could be empty
    """
    if client_transaction_ids_to_ignore is None:
        client_transaction_ids_to_ignore = []

    return {
        client_transaction_id: client_transaction
        for client_transaction_id, client_transaction in client_transactions.items()
        if client_transaction_id not in client_transaction_ids_to_ignore
        and client_transaction.denomination == denomination
        and not client_transaction.released()
        # custom instructions aren't chainable so we only need to check the first posting
        and client_transaction.posting_instructions[0].type
        != PostingInstructionType.CUSTOM_INSTRUCTION
        and client_transaction.posting_instructions[0].instruction_details.get(key) == value
    }


def filter_client_transactions_by_type(
    *,
    client_transactions: dict[str, ClientTransaction],
    denomination: str,
    key: str,
    values: Iterable[str],
    client_transaction_ids_to_ignore: Optional[Iterable[str]] = None,
) -> dict[str, dict[str, ClientTransaction]]:
    """
    Filters client transactions to only include the desired client transactions:
    - transaction type is determined by the value of the specified key in the instruction_details
    of first posting instruction of a given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param client_transactions: ClientTransaction dictionary, keyed by unique client transaction id
    :param denomination: the denomination to match
    :param key: key to lookup in the instruction details
    :param values: values against the key in the instruction details to include
    :param client_transaction_ids_to_ignore: client transaction ids to exclude (e.g. the
    current posting being processed)
    :return: mapping of type to dict of in-scope client transactions
    """
    if client_transaction_ids_to_ignore is None:
        client_transaction_ids_to_ignore = []

    in_scope_transactions: dict[str, dict[str, ClientTransaction]] = {value: {} for value in values}

    for client_transaction_id, client_transaction in client_transactions.items():
        transaction_type = client_transaction.posting_instructions[0].instruction_details.get(
            key, ""
        )
        if (
            client_transaction_id not in client_transaction_ids_to_ignore
            and client_transaction.denomination == denomination
            and not client_transaction.released()
            # custom instructions aren't chainable so we only need to check the first posting
            and client_transaction.posting_instructions[0].type
            != PostingInstructionType.CUSTOM_INSTRUCTION
            and transaction_type in values
        ):
            in_scope_transactions[transaction_type][client_transaction_id] = client_transaction

    return in_scope_transactions


def extract_debits_by_instruction_details_key(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    cutoff_datetime: datetime,
    key: str,
    value: str,
    client_transaction_ids_to_ignore: Optional[list[str]] = None,
) -> utils.PostingInstructionListAlias:
    """
    Extracts all posting instructions in the client transactions that resulted in a net debit
    since the cutoff
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - type is determined by the specified key-value pair on the first posting instruction of a
    given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to consider
    :param client_transactions: historic and new client transactions to consider
    :param cutoff_datetime: datetime from which to include client transaction postings, inclusive
    :param key: key to reference in the instruction details
    :param value: value to lookup against the key in the instruction details
    :param client_transaction_ids_to_ignore: list of specific client transaction ids to filter out
    :return the list of instructions
    """

    debit_instructions: utils.PostingInstructionListAlias = []

    in_scope_transactions = filter_client_transactions(
        client_transactions=client_transactions,
        denomination=denomination,
        client_transaction_ids_to_ignore=client_transaction_ids_to_ignore,
        key=key,
        value=value,
    )

    for transaction in in_scope_transactions.values():
        amount_before_posting = _get_total_transaction_impact(
            transaction=transaction,
            # We can't do `.before()` on transaction effects, so we get 'at' the latest timestamp
            # before the posting's value_timestamp instead (max granularity is 1 us). This relies
            # on postings API not allowing postings within a transaction having the same value
            # timestamp
            # using cutoff_datetime ensures we calculate the net w.r.t all postings before cutoff
            effective_datetime=cutoff_datetime - relativedelta(microseconds=1),
        )
        for posting_instruction in transaction.posting_instructions:
            # this will always be non-None on hook args/fetched posting instructions and any
            # corresponding ClientTransaction instances, but the API type hint is Optional for
            # instantiations during hook execution, which won't be the case here
            if posting_instruction.value_datetime < cutoff_datetime:  # type: ignore
                continue

            # We only consider a posting to be a net debit if the transaction impact after the
            # posting decreases (e.g. -10 to -12 or 10 to 8)
            amount_after_posting = _get_total_transaction_impact(
                transaction=transaction, effective_datetime=posting_instruction.value_datetime
            )
            if amount_after_posting < amount_before_posting:
                debit_instructions.append(posting_instruction)
            # this helps us avoid having to calculate a before/after for each posting
            amount_before_posting = amount_after_posting
    return debit_instructions


def extract_debits_by_type(
    *,
    denomination: str,
    client_transactions: dict[str, ClientTransaction],
    cutoff_datetime: datetime,
    key: str,
    values: Iterable[str],
    client_transaction_ids_to_ignore: Optional[Iterable[str]] = None,
) -> dict[str, utils.PostingInstructionListAlias]:
    """
    Extracts all posting instructions in the client transactions that resulted in a net debit
    since the cutoff:
    - debit amount includes any debit impact to the available balance at the DEFAULT address and
    specified denomination, which includes unsettled authorisations.
    - type is determined by the specified key-value pair on the first posting instruction of a
    given client transaction.
    - Released client transactions are ignored.
    - Client transactions with a CustomInstruction are ignored.

    :param denomination: denomination to consider
    :param client_transactions: historic and new client transactions to consider
    :param cutoff_datetime: datetime from which to include client transaction postings, inclusive
    :param key: key to lookup in the instruction details
    :param values: values against the key in the instruction details to include
    :param client_transaction_ids_to_ignore: client transaction ids to exclude (e.g. the
    current posting being processed)
    :return a dictionary of type to the list of relevant posting instructions. Missing types are
    equivalent to an empty list of posting instructions.
    """

    debit_instructions: dict[str, utils.PostingInstructionListAlias] = {}

    in_scope_transactions = filter_client_transactions_by_type(
        client_transactions=client_transactions,
        denomination=denomination,
        client_transaction_ids_to_ignore=client_transaction_ids_to_ignore,
        key=key,
        values=values,
    )

    for transaction_type, transaction_dict in in_scope_transactions.items():
        debit_instructions[transaction_type] = []
        for transaction in transaction_dict.values():
            amount_before_posting = _get_total_transaction_impact(
                transaction=transaction,
                # We can't do `.before()` on transaction effects, so we get 'at' the latest
                # timestamp before the posting's value_timestamp instead (max granularity is 1 us).
                # This relies on postings API not allowing postings within a transaction having the
                # same value timestamp.
                # Using cutoff_datetime yields the net w.r.t all postings before cutoff
                effective_datetime=cutoff_datetime - relativedelta(microseconds=1),
            )
            for posting_instruction in transaction.posting_instructions:
                # value_datetime will always be non-None on hook args/fetched posting instructions.
                # The API type hint is Optional for instantiations during hook execution, which
                # aren't in scope here, so we can ignore this scenario
                if posting_instruction.value_datetime < cutoff_datetime:  # type: ignore
                    continue

                # We only consider a posting to be a net debit if the transaction impact after the
                # posting decreases (e.g. -10 to -12 or 10 to 8)
                amount_after_posting = _get_total_transaction_impact(
                    transaction=transaction, effective_datetime=posting_instruction.value_datetime
                )
                if amount_after_posting < amount_before_posting:
                    debit_instructions[transaction_type].append(posting_instruction)
                # this helps us avoid having to calculate a before/after for each posting
                amount_before_posting = amount_after_posting
    return debit_instructions


def _get_total_transaction_impact(
    *,
    transaction: ClientTransaction,
    effective_datetime: Optional[datetime] = None,
) -> Decimal:
    """
    For any financial movement, the total effect a ClientTransaction has had on the balances can be
    represented by the sum of settled and unsettled effects.
    WARNING: ClientTransaction effects are always None in the platform if they are based on a
    CustomInstruction. This method will return Decimal(0) if such a ClientTransaction is provided

    1. HardSettlement (-10):
        authorised: 0, settled: -10, unsettled: 0
        sum = -10
    2. Authorisation (-10)
        authorised: -10, settled: 0, unsettled: -10
        sum = -10
    3. Authorisation (-10) + Adjustment (-5)
        authorisation:  authorised: -10, settled: 0, unsettled: -10
        adjustment:     authorised: -15, settled: 0, unsettled: -15
        sum = -15
    4. Authorisation (-10) + Total Settlement (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -10, unsettled: 0
        sum = -10
    5. Authorisation (-10) + Partial Settlement Non-final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -5, unsettled: -5
        # if the settlement was not final, then the total effect of the transaction
        # is the value of the initial auth.
        sum = -10
    6. Authorisation (-10) + Partial Settlement Final (-5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -5, settled: -5, unsettled: 0
        # as the settlement was final, the remaining funds were released. The impact
        # of this transaction is therefore only -5, i.e. even though the original auth
        # was -10, -5 of that was returned.
        sum = -5
    7. Authorisation (-10) + Oversettlement (auth -10 & an additional -5)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        settlement:    authorised: -10, settled: -15, unsettled: 0
        # as an oversettlement has occurred, the impact on the account is the
        # the settlement amount of -15
        sum = -15
    8. Authorisation (-10) + Release (-10)
        authorisation: authorised: -10, settled: 0, unsettled: -10
        release:       authorised: -10, settled: 0, unsettled: 0
        # as we have released all funds then this is expected to be 0, i.e. the
        # transaction has no overall impact on an account,
        sum = 0

    :param transaction: client transaction to process
    :param effective_datetime: effective datetime to determine which point of time to
    :return: The net of settled and unsettled effects.
    """
    # This is required to circumvent TM-80295 whereby the contracts_api wrongly raises an exception
    # instead of returning 0 if effects are queried before the start_datetime
    if (
        effective_datetime is not None
        and transaction.start_datetime is not None
        and effective_datetime < transaction.start_datetime
    ):
        return Decimal(0)

    transaction_effects = transaction.effects(effective_datetime=effective_datetime)
    if transaction_effects is None:
        return Decimal(0)

    return transaction_effects.settled + transaction_effects.unsettled
