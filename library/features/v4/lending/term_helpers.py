# standard libs
from datetime import datetime
from typing import Optional

# features
import library.features.common.fetchers as fetchers
import library.features.v4.common.utils as utils
import library.features.v4.lending.lending_addresses as lending_addresses
import library.features.v4.lending.lending_parameters as lending_parameters

# contracts api
from contracts_api import BalanceDefaultDict

# inception sdk
from inception_sdk.vault.contracts.extensions.contracts_api_extensions import SmartContractVault


def calculate_elapsed_term(balances: BalanceDefaultDict, denomination: str) -> int:
    return int(
        utils.balance_at_coordinates(
            balances=balances,
            address=lending_addresses.DUE_CALCULATION_EVENT_COUNTER,
            denomination=denomination,
        )
    )


def calculate_term_details_from_counter(
    vault: SmartContractVault,
    effective_datetime: datetime,
    balances: Optional[BalanceDefaultDict] = None,
    denomination: Optional[str] = None,
) -> tuple[int, int]:
    original_total_term = int(
        utils.get_parameter(vault=vault, name=lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT)
    )

    # this allows us to avoid fetching balances in activation hook
    if effective_datetime == vault.get_account_creation_datetime():
        # in account activation, elapsed is 0 and the remaining term is the parameter value
        return 0, original_total_term

    if balances is None:
        balances = vault.get_balances_observation(
            fetcher_id=fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID
        ).balances
    if denomination is None:
        denomination = utils.get_parameter(vault=vault, name="denomination")

    elapsed = calculate_elapsed_term(balances=balances, denomination=denomination)
    expected_remaining_term = original_total_term - elapsed

    return elapsed, expected_remaining_term
