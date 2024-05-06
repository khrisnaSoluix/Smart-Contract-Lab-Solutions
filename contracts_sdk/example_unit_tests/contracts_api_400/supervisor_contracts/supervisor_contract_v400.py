from datetime import datetime
from zoneinfo import ZoneInfo

from contracts_api import (  # type: ignore
    SmartContractDescriptor,
    SupervisorPostPostingHookResult,
    AccountNotificationDirective,
    BalanceDefaultDict,
    Balance,
    DEFAULT_ADDRESS,
    BalanceCoordinate,
    DEFAULT_ASSET,
    Phase,
)


api = "4.0.0"
version = "1.0.0"
supported_denominations = ["GBP"]

supervised_smart_contracts = [
    SmartContractDescriptor(
        alias="supervised_contract",
        smart_contract_version_id="contract_version",
    ),
]

notification_types = ["type"]


# This hook demonstrates how to check net balance of new posting instructions per supervisee
# and use python packages (i.e. zoneinfo) within Supervisor Contracts.
def post_posting_hook(vault, hook_arguments):
    timezone = ZoneInfo("America/Los_Angeles")
    example_time = datetime(2022, 1, 2, 1, 1, tzinfo=timezone)
    # merge supervisee posting instructions together
    supervisee_posting_instructions = []
    for ins in hook_arguments.supervisee_posting_instructions.values():
        supervisee_posting_instructions.extend(ins)
    postings_net_balance = sum(
        [instruction.balances() for instruction in supervisee_posting_instructions],
        BalanceDefaultDict(lambda *_: Balance()),
    )
    pending_out_coord = BalanceCoordinate(
        account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        denomination="GBP",
        phase=Phase.PENDING_OUT,
    )
    return SupervisorPostPostingHookResult(
        supervisee_account_notification_directives={
            "test_account_id": [
                AccountNotificationDirective(
                    notification_type="test",
                    notification_details={
                        "tz": example_time.tzname(),
                        "postings_net_balance": str(postings_net_balance[pending_out_coord].net),
                    },
                )
            ]
        }
    )
