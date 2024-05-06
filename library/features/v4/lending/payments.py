# standard libs
from decimal import Decimal
from typing import NamedTuple, Optional

# features
import library.features.common.common_parameters as common_parameters
import library.features.common.fetchers as fetchers
import library.features.v4.common.supervisor_utils as supervisor_utils
import library.features.v4.common.utils as utils
import library.features.v4.lending.early_repayment as early_repayment
import library.features.v4.lending.interest_capitalisation as interest_capitalisation
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_interfaces as lending_interfaces

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    BalanceCoordinate,
    BalanceDefaultDict,
    CustomInstruction,
    Phase,
    Posting,
    PostPostingHookArguments,
    SupervisorPostPostingHookArguments,
)

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import (
    SmartContractVault,
    SuperviseeContractVault,
)

RepaymentAmounts = NamedTuple(
    "RepaymentAmounts",
    [
        ("unrounded_amount", Decimal),
        ("rounded_amount", Decimal),
    ],
)


def redistribute_postings(
    debit_account: str,
    denomination: str,
    amount: Decimal,
    credit_account: str,
    credit_address: str,
    debit_address: str = DEFAULT_ADDRESS,
) -> list[Posting]:
    """
    Redistribute a lump sum of payment into another account / address
    :param debit_account: the account id that receives initial sum and initiates the redistribution
    :param denomination: the denomination of the application
    :param amount: the amount to pay. If <= 0 an empty list is returned
    :param credit_account: the account id that receives the redistributed amount
    :param credit_address: the address to receive the redistributed amount in the credit_account
    :param debit_address: the address from which to move the amount
    :return: the payment postings, in credit-debit pair
    """
    if amount <= Decimal("0"):
        return []
    return [
        Posting(
            credit=True,
            amount=amount,
            denomination=denomination,
            account_id=credit_account,
            account_address=credit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=False,
            amount=amount,
            denomination=denomination,
            account_id=debit_account,
            account_address=debit_address,
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ]


def distribute_repayment_for_single_target(
    balances: BalanceDefaultDict,
    repayment_amount: Decimal,
    denomination: str,
    repayment_hierarchy: Optional[list[str]] = None,
    phase: Phase = Phase.COMMITTED,
) -> tuple[dict[str, RepaymentAmounts], Decimal]:
    """
    Determines how a repayment amount is distributed across balances based on the repayment
    hierarchy and the outstanding balances. Each repayment hierarchy address' balance is
    rounded to 2 decimal points for repayment purposes. Both rounded and unrounded amounts are
    returned so that the consumer can decide how to handle remainders. For example, a repayment of
    0.01 distributed to a balance of 0.0052 or to a balance of 0.0012

    :param balances: The balances to distribute the repayment amount across
    :param repayment_amount: The 2 decimal point repayment amount to distribute
    :param denomination: The denomination of the repayment
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across addresses. Defaults to standard lending repayment hierarchy
    :param phase: The balance phase of the balances fetched to get amounts from
    :return: A dictionary of addresses to repayment amounts to be repaid and the remaining
    repayment amount
    """
    remaining_repayment_amount = repayment_amount
    if repayment_hierarchy is None:
        repayment_hierarchy = lending_addresses.REPAYMENT_HIERARCHY
    repayment_per_address: dict[str, RepaymentAmounts] = {}

    for repayment_address in repayment_hierarchy:
        balance_address = BalanceCoordinate(repayment_address, DEFAULT_ASSET, denomination, phase)
        unrounded_address_amount = balances[balance_address].net
        rounded_address_amount = utils.round_decimal(unrounded_address_amount, 2)
        rounded_address_repayment_amount = min(rounded_address_amount, remaining_repayment_amount)
        # can't repay a balance that is < 2 decimal points - this should be dealt with in
        # close_code for early repayments
        if rounded_address_repayment_amount == Decimal(0):
            continue

        # ensure that the unrounded repayment amount is <= unrounded address amount
        # rounded repayment amount can be >, =, or < unrounded address amount
        unrounded_address_repayment_amount = (
            unrounded_address_amount
            if rounded_address_amount <= remaining_repayment_amount
            else remaining_repayment_amount
        )
        repayment_per_address[repayment_address] = RepaymentAmounts(
            unrounded_amount=unrounded_address_repayment_amount,
            rounded_amount=rounded_address_repayment_amount,
        )

        remaining_repayment_amount -= rounded_address_repayment_amount

    return repayment_per_address, remaining_repayment_amount


def distribute_repayment_for_multiple_targets(
    balances_per_target: dict[str, BalanceDefaultDict],
    repayment_amount: Decimal,
    denomination: str,
    repayment_hierarchy: list[list[str]],
) -> tuple[dict[str, dict[str, RepaymentAmounts]], Decimal]:
    """
    Determines how a repayment amount should be distributed across a number of repayment targets
    (loans), based on the repayment hierarchy and the outstanding balances. This is intended to
    only be used by a supervisor.
    :param balances_per_target: a dictionary where the key is the repayment target account id and
    the value is its balances. This should be sorted in order of which target should be repaid
    first.
    :param repayment_amount: repayment amount to distribute
    :param denomination: the denomination of the repayment
    :param repayment_hierarchy: The order in which a repayment amount is to be distributed across
    addresses for one or more targets. The outer list represents ordering across accounts and the
    the inner lists represent ordering within an account.
    For example, the hierarchy [[ADDRESS_1],[ADDRESS_2, ADDRESS_3]] would result in a distribution
    in this order, assuming two loans loan_1 and loan_2:
    # ADDRESS_1 paid on loan_1 and then loan_2
    ADDRESS_1 loan_1
    ADDRESS_1 loan_2
    # ADDRESS_2 and ADDRESS_3 paid on loan 1 and then loan 2
    ADDRESS_2 loan_1
    ADDRESS_3 loan_1
    ADDRESS_2 loan_2
    ADDRESS_3 loan_2
    :return: A tuple containing
        - a dictionary where the key is the target account id and the value is the repayment
    amounts for each address.
        - the remaining repayment amount.
    """

    remaining_repayment_amount = repayment_amount
    repayments_per_target: dict[str, dict[str, RepaymentAmounts]] = {
        target: {} for target in balances_per_target.keys()
    }

    for address_list in repayment_hierarchy:
        for target_account_id in balances_per_target.keys():
            (
                repayment_per_address,
                remaining_repayment_amount,
            ) = distribute_repayment_for_single_target(
                balances=balances_per_target[target_account_id],
                repayment_amount=remaining_repayment_amount,
                denomination=denomination,
                repayment_hierarchy=address_list,
            )

            repayments_per_target[target_account_id].update(repayment_per_address)

            if remaining_repayment_amount == Decimal("0"):
                return repayments_per_target, Decimal("0")

    return repayments_per_target, remaining_repayment_amount


def generate_repayment_postings(
    vault: SmartContractVault,
    hook_arguments: PostPostingHookArguments,
    repayment_hierarchy: Optional[list[str]] = None,
    overpayment_features: Optional[list[lending_interfaces.Overpayment]] = None,
    early_repayment_fees: Optional[list[lending_interfaces.EarlyRepaymentFee]] = None,
) -> list[CustomInstruction]:
    """
    A top level wrapper that generates a list of custom instructions to spread a regular payment
    across different balance addresses based on the repayment hierarchy and debit addresses.
    Optionally handles overpayments if any overpayment features are passed in.

    :param vault: Vault object used for data extraction
    :param hook_arguments: The post posting hook arguments
    :param repayment_hierarchy: Order in which a repayment amount is to be
    distributed across addresses. Defaults to standard lending repayment hierarchy
    :param overpayment_features: List of features responsible for handling any excess
    overpayment amount after all repayments have been made. This can be omitted if
    overpayments can be disregarded. Note that handle_overpayment will be called for
    each feature passed into the list.
    :param early_repayment_fees: List of early repayment fee features for handling the amounts of
    early repayment fees that are being charged, but only applicable if the repayment amount is
    correct for making an early repayment to fully pay off and close the account.
    """
    denomination: str = utils.get_parameter(vault=vault, name="denomination")
    if repayment_hierarchy is None:
        repayment_hierarchy = lending_addresses.REPAYMENT_HIERARCHY

    # here it is assumed that the repayment amount will always be in the DEFAULT balance address
    # associated with the first posting instruction, which should be enforced in the pre_posting
    # hook
    repayment_amount: Decimal = (
        hook_arguments.posting_instructions[0]
        .balances()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination, Phase.COMMITTED)]
        .net
    )
    balances = vault.get_balances_observation(fetcher_id=fetchers.LIVE_BALANCES_BOF_ID).balances

    posting_instructions: list[CustomInstruction] = []

    # Run the core logic
    repayment_postings: list[Posting] = []
    overpayment_amount = Decimal("0")
    if repayment_amount < 0:
        (repayment_per_address, overpayment_amount) = distribute_repayment_for_single_target(
            balances=balances,
            repayment_amount=abs(repayment_amount),
            denomination=denomination,
            repayment_hierarchy=repayment_hierarchy,
        )
        for repayment_address, repayment_address_amount in repayment_per_address.items():
            # no postings are required when due balance is 0 or rounds to 0
            if repayment_address_amount[1] == Decimal(0):
                continue

            repayment_postings += redistribute_postings(
                debit_account=vault.account_id,
                amount=repayment_address_amount[1],
                denomination=denomination,
                credit_account=vault.account_id,
                credit_address=repayment_address,
            )

        # Data transformation
        if repayment_postings:
            posting_instructions += [
                CustomInstruction(
                    postings=repayment_postings,
                    instruction_details={
                        "description": "Process a repayment",
                        "event": "PROCESS_REPAYMENTS",
                    },
                )
            ]
    # run overpayment feature logic
    if overpayment_amount > 0 and overpayment_features is not None:
        for overpayment_feature in overpayment_features:
            overpayment_postings = overpayment_feature.handle_overpayment(
                vault=vault,
                overpayment_amount=overpayment_amount,
                balances=balances,
                denomination=denomination,
            )

            # Data transformation
            if overpayment_postings:
                posting_instructions += [
                    CustomInstruction(
                        postings=overpayment_postings,
                        instruction_details={
                            "description": "Process repayment overpayment",
                            "event": "PROCESS_REPAYMENTS",
                        },
                    )
                ]

    if early_repayment.is_posting_an_early_repayment(
        vault=vault,
        repayment_amount=repayment_amount,
        early_repayment_fees=early_repayment_fees,
        balances=balances,
        denomination=denomination,
    ):
        posting_instructions.extend(
            interest_capitalisation.handle_overpayments_to_penalties_pending_capitalisation(
                vault=vault,
                denomination=denomination,
                balances=balances,
            )
        )
        if early_repayment_fees:
            for early_repayment_fee in early_repayment_fees:
                amount_to_charge = early_repayment_fee.get_early_repayment_fee_amount(
                    vault=vault,
                    balances=balances,
                    denomination=denomination,
                )
                posting_instructions.extend(
                    early_repayment_fee.charge_early_repayment_fee(
                        vault=vault,
                        account_id=vault.account_id,
                        amount_to_charge=amount_to_charge,
                        fee_name=early_repayment_fee.fee_name,
                        denomination=denomination,
                    )
                )

    return posting_instructions


def generate_repayment_postings_for_multiple_targets(
    main_vault: SuperviseeContractVault,
    sorted_repayment_targets: list[SuperviseeContractVault],
    hook_arguments: SupervisorPostPostingHookArguments,
    repayment_hierarchy: Optional[list[list[str]]] = None,
    overpayment_features: Optional[list[lending_interfaces.MultiTargetOverpayment]] = None,
    early_repayment_fees: Optional[list[lending_interfaces.EarlyRepaymentFee]] = None,
) -> dict[str, list[CustomInstruction]]:
    """
    A top level wrapper that generates a list of custom instructions per repayment target to spread
    a regular payment across different targets and balance addresses based on the repayment
    hierarchy and debit addresses. Optionally handles overpayments if any overpayment features are
    passed in.

    It is assumed that the repayment amount will always be in the DEFAULT balance address
    associated with the first posting instruction, which should be enforced in the pre_posting hook

    :param main_vault: The supervisee vault object to instruct the repayment instructions from
    :param sorted_repayment_targets: The repayment targets sorted by the required order of repayment
    :param hook_arguments: The post posting hook arguments
    :param repayment_hierarchy: The order in which a repayment amount is to be distributed across
    addresses for one or more targets. The outer list represents ordering across accounts and the
    the inner lists represent ordering within an account.
    :param overpayment_features: List of features responsible for handling any excess
    overpayment amount after all repayments have been made. This can be omitted if
    overpayments can be disregarded. Note that handle_overpayment will be called for
    each feature passed into the list.
    :param early_repayment_fees: List of early repayment fee features for handling the amounts of
    early repayment fees that are being charged, but only applicable if the repayment amount is
    correct for making an early repayment to fully pay off one or more loans.
    :return: The repayment instructions for each repayment target
    """
    denomination: str = common_parameters.get_denomination_parameter(vault=main_vault)
    if repayment_hierarchy is None:
        repayment_hierarchy = [[address] for address in lending_addresses.REPAYMENT_HIERARCHY]

    posting_instructions_per_target: dict[str, list[CustomInstruction]] = {
        target.account_id: [] for target in sorted_repayment_targets
    }

    # here it is assumed that the repayment amount will always be in the DEFAULT balance address
    # associated with the first posting instruction, which should be enforced in the pre_posting
    # hook
    if (
        repayment_amount := utils.balance_at_coordinates(
            balances=hook_arguments.supervisee_posting_instructions[main_vault.account_id][
                0
            ].balances(),
            denomination=denomination,
        )
    ) >= 0:
        return posting_instructions_per_target

    balances_per_target = supervisor_utils.get_balances_default_dicts_from_timeseries(
        supervisees=sorted_repayment_targets,
        effective_datetime=hook_arguments.effective_datetime,
    )

    repayments_per_target, overpayment_amount = distribute_repayment_for_multiple_targets(
        balances_per_target=balances_per_target,
        repayment_amount=abs(repayment_amount),
        denomination=denomination,
        repayment_hierarchy=repayment_hierarchy,
    )

    for target_account_id, repayment_amounts_per_address in repayments_per_target.items():
        repayment_postings: list[Posting] = []
        for address, repayment_amounts in repayment_amounts_per_address.items():
            if repayment_amounts.rounded_amount == Decimal(0):
                # No postings required
                continue

            repayment_postings += redistribute_postings(
                debit_account=target_account_id,
                amount=repayment_amounts.rounded_amount,
                denomination=denomination,
                credit_account=target_account_id,
                credit_address=address,
                debit_address=DEFAULT_ADDRESS
                if target_account_id == main_vault.account_id
                else lending_addresses.INTERNAL_CONTRA,
            )

        if repayment_postings:
            posting_instructions_per_target[target_account_id] += [
                CustomInstruction(
                    postings=repayment_postings,
                    instruction_details={
                        "description": "Process a repayment",
                        "event": "PROCESS_REPAYMENTS",
                    },
                )
            ]

    # Handle overpayment
    if overpayment_amount > 0 and overpayment_features is not None:
        overpayment_postings_per_target: dict[str, list[Posting]] = {
            target.account_id: [] for target in sorted_repayment_targets
        }
        for overpayment_feature in overpayment_features:
            for target_account_id, postings in overpayment_feature.handle_overpayment(
                main_vault=main_vault,
                overpayment_amount=overpayment_amount,
                denomination=denomination,
                balances_per_target_vault={
                    target: balances_per_target[target.account_id]
                    for target in sorted_repayment_targets
                },
            ).items():
                overpayment_postings_per_target[target_account_id] += postings

        for target_account_id, postings in overpayment_postings_per_target.items():
            if postings:
                posting_instructions_per_target[target_account_id] += [
                    CustomInstruction(
                        postings=postings,
                        instruction_details={
                            "description": "Process repayment overpayment",
                            "event": "PROCESS_REPAYMENTS",
                        },
                    )
                ]

    # TODO: Handle early repayment

    return posting_instructions_per_target
