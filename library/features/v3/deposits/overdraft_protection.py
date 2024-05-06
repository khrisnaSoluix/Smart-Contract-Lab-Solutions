# standard libs
from datetime import datetime
from decimal import Decimal

# features
import library.features.v3.common.supervisor_utils as supervisor_utils
import library.features.v3.common.utils as utils

# inception sdk
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    PostingInstruction,
    Rejected,
    RejectedReason,
    SupervisorVault,
    Vault,
)

# The fee_free_overdraft_limit is used in this feature and should be defined here. It's hasn't been
# because it's currently defined in a contract which hasn't been templated yet and it needs to be
# included in this feature as the supervisor (which has been templated) uses it.


def _check_for_savings_coverage(
    vault: SupervisorVault,
    checking_account: Vault,
    savings_account: Vault,
) -> None:
    """
    This function is checking that there is enough balance across
    the linked savings and checking accounts to cover the proposed
    transaction
    """
    standard_overdraft_limit = 0
    standard_overdraft_limit = utils.get_parameter(
        name="standard_overdraft_limit", vault=checking_account
    )

    denomination = utils.get_parameter(name="denomination", vault=checking_account)
    new_checking_account_postings = vault.get_posting_instructions_by_supervisee()[
        checking_account.account_id
    ]
    new_checking_account_postings_balance = utils.get_available_balance(
        new_checking_account_postings.balances(), denomination
    )

    combined_balance = supervisor_utils.sum_available_balances_across_supervisees(
        [checking_account, savings_account],
        denomination=denomination,
        observation_fetcher_id="live_balance",
        rounding_precision=2,
    )
    # Check to see if the posting will bring the checking balance below the standard overdraft
    # limit, even if we sweep from savings
    if (combined_balance + new_checking_account_postings_balance + standard_overdraft_limit) < 0:
        raise Rejected(
            f"Combined checking and savings account balance {combined_balance} "
            f"insufficient to cover net transaction amount {new_checking_account_postings_balance}",
            reason_code=RejectedReason.INSUFFICIENT_FUNDS,
        )


def validate(
    vault: SupervisorVault,
    checking_account: Vault,
    savings_accounts: list[Vault],
) -> None:
    """
    In this function we are checking to see if the proposed transaction is covered by ODP,
    this includes ensuring that the rejection raised on the checking is due to insufficient funds
    and we have a linked savings account with enough balance to cover the net transaction

    :param: vault: Vault object
    :param: checking_account:
    :param: checking_account:
    :raises: Rejected: Can raise the rejection fetched from the checking account, unless it is of
    type INSUFFICIENT_FUNDS and we have a linked savings account. If we have more than one linked
    savings account we will raise a separate rejection of type AGAINST_TNC
    :return: None
    """
    # If checking account accepts the posting no additional ODP balance checks necessary
    account_rejection = checking_account.get_hook_return_data()
    if not account_rejection:
        return

    # ODP doesn't override rejections that weren't caused by insufficient funds on checking account
    if account_rejection.reason_code != RejectedReason.INSUFFICIENT_FUNDS:
        raise account_rejection

    # If no linked savings account, raise the original insufficient funds rejection from checking
    if len(savings_accounts) == 0:
        raise account_rejection
    elif len(savings_accounts) > 1:
        raise Rejected(
            f"Requested 1 us_savings accounts but found {len(savings_accounts)}.",
            reason_code=RejectedReason.AGAINST_TNC,
        )

    savings_account = savings_accounts.pop()
    _check_for_savings_coverage(vault, checking_account, savings_account)


def sweep_funds(
    vault: SupervisorVault,
    effective_date: datetime,
) -> tuple[Decimal, list[PostingInstruction]]:
    """
    sweep_funds is used to generate a posting that sweeps funds from a savings
    account to a checking account to avoid potential overdraft fees
    As we are making use of the .latest() balances we need to ensure that the
    balances provided are live.
    """
    savings_sweep_transfer_amount: Decimal = Decimal("0")
    posting_instructions = []

    savings_accounts = supervisor_utils.get_supervisees_for_alias(vault, "us_savings", 1)

    savings_account = savings_accounts.pop()

    checking_account = supervisor_utils.get_supervisees_for_alias(vault, "us_checking", 1).pop()

    denomination = utils.get_parameter(name="denomination", vault=checking_account)

    # Check if savings sweep is necessary
    balances = checking_account.get_balance_timeseries().latest()
    checking_account_committed_balance = Decimal(
        balances[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)].net
    )

    if checking_account_committed_balance < 0:
        savings_available_balance = utils.get_available_balance(
            savings_account.get_balance_timeseries().latest(),
            denomination,
        )
        savings_sweep_transfer_amount = min(
            abs(checking_account_committed_balance), savings_available_balance
        )

        if savings_sweep_transfer_amount > Decimal("0"):

            posting_instructions.extend(
                checking_account.make_internal_transfer_instructions(
                    amount=savings_sweep_transfer_amount,
                    denomination=denomination,
                    client_transaction_id=f"INTERNAL_POSTING_"
                    f"SWEEP_WITHDRAWAL_FROM_"
                    f"{savings_account.account_id}_"
                    f"{checking_account.get_hook_execution_id()}",
                    from_account_id=savings_account.account_id,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=checking_account.account_id,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    pics=[],
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Sweep from savings account",
                        "event": "SWEEP",
                    },
                )
            )
    return savings_sweep_transfer_amount, posting_instructions


def remove_unnecessary_overdraft_fees(
    vault: SupervisorVault,
    postings: list[PostingInstruction],
    offset_amount: Decimal,
    denomination: str,
    effective_date: datetime,
    standard_overdraft_instructions: list[PostingInstruction],
) -> list[PostingInstruction]:

    balances = vault.get_balance_timeseries().before(timestamp=effective_date)
    fee_free_overdraft_limit = vault.get_parameter_timeseries(
        name="fee_free_overdraft_limit"
    ).latest()

    balance_before = balances[DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED].net
    proposed_amount = postings.balances()[
        DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
    ].net
    latest_balance = balance_before + proposed_amount
    effective_balance = latest_balance + offset_amount

    posting_instructions = []
    counter = 0

    for posting in sorted(
        postings,
        key=lambda posting: posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net,
    ):
        if effective_balance < -fee_free_overdraft_limit:
            counter += 1
        effective_balance += posting.balances()[
            DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED
        ].net

    # a list of STANDARD_OVERDRAFT posting instructions was created in supervisee.
    # in the supervisor, when funds are transferred into checking account
    # from the savings, it would no longer be in overdraft.
    # based on the counter above (the expected number of
    # STANDARD_OVERDRAFT posting instructions from all posting),
    # add only that number of STANDARD_OVERDRAFT posting instructions from
    # supervisee to the final list of posting instructions.
    for instruction in standard_overdraft_instructions:
        client_transaction_id = instruction.client_transaction_id.split("_")
        if int(client_transaction_id[-1]) < counter:
            posting_instructions.append(instruction)

    return posting_instructions


def get_odp_sweep_schedule(checking_account: Vault) -> dict[str, str]:
    """
    Sets up dictionary of odp_sweep schedule based on parameters

    :param vault: Vault object
    :return: dict, representation of odp_sweep schedule
    """
    overdraft_protection_sweep_hour = utils.get_parameter(
        checking_account, name="overdraft_protection_sweep_hour"
    )

    overdraft_protection_sweep_minute = utils.get_parameter(
        checking_account, name="overdraft_protection_sweep_minute"
    )

    overdraft_protection_sweep_second = utils.get_parameter(
        checking_account, name="overdraft_protection_sweep_second"
    )

    overdraft_protection_sweep_schedule = utils.create_schedule_dict(
        hour=overdraft_protection_sweep_hour,
        minute=overdraft_protection_sweep_minute,
        second=overdraft_protection_sweep_second,
    )

    return overdraft_protection_sweep_schedule
