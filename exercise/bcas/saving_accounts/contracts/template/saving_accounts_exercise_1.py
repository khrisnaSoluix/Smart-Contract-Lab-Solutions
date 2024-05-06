from contracts_api import (
    BalancesObservationFetcher,
    DefinedDateTime,
    DenominationShape,
    fetch_account_data,
    Parameter,
    ParameterLevel,
    ParameterUpdatePermission,
    PrePostingHookArguments,
    PrePostingHookResult,
    Rejection,
    RejectionReason,
    requires,
    Tside,
)

from inception_sdk.vault.contracts.extensions.contracts_api_extensions.vault_types import SmartContractVault


api = "4.0.0"
version = "1.0.0"
display_name = "Saving Account"
summary = "Personal Savings Account Product"
tside = Tside.LIABILITY
supported_denominations = ["IDR"]

# CONSTANTS
PARAM_DENOMINATION = "denomination"

parameters = [
    Parameter(
        name=PARAM_DENOMINATION,
        shape=DenominationShape(),
        level=ParameterLevel.TEMPLATE,
        display_name="Denomination",
        description="The default denomination of the account.",
        update_permission=ParameterUpdatePermission.USER_EDITABLE,
        default_value="IDR",
    ),
]

data_fetchers = [
    BalancesObservationFetcher(
        fetcher_id="live_balances",
        at=DefinedDateTime.LIVE,
    ),
]

@requires(parameters=True)
@fetch_account_data(balances=["live_balances"])
def pre_posting_hook(vault: SmartContractVault, hook_arguments: PrePostingHookArguments):
    denomination = vault.get_parameter_timeseries(name=PARAM_DENOMINATION).latest()

    # check denomination
    posting_instructions = hook_arguments.posting_instructions

    posting_denominations_used = set(post.denomination for post in posting_instructions)
    disallowed_denominations_used = posting_denominations_used.difference(
        [denomination]
    )
    if disallowed_denominations_used:
        return PrePostingHookResult(
            rejection=Rejection(
                message=f"Postings are not allowed. Only postings in {denomination} are accepted.",
                reason_code=RejectionReason.WRONG_DENOMINATION,
            )
        )