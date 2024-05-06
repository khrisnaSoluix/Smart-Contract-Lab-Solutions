# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.core_api_helper as core_api_helper
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

DEFAULT_DENOM = "GBP"

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


def standard_teardown(test, closure_flag_definition_id: str) -> None:
    """
    The standard credit card tests will all finish with:
    - Repay Full Outstanding Balance
    - Apply account closure flag
    - Update status to pending closure, which will trigger close code hook
    - Close code hook zeros out balances
    - Test will wait for account update [closure_update] w/ status ACCOUNT_UPDATE_STATUS_COMPLETED.
    - Lastly the parent tearDownClass would clean up the customers, accounts and wf processes used.
    :param test: the test instance we're tearing down
    :param closure_flag_definition_id: the unmapped flag definition id to use when creating the
     account closure flag. This id will be mapped using the e2e testhandle mappings

    """

    if not getattr(test, "account_id", None):
        log.info(
            f"Account has not been created for {test._testMethodName}, skipping account tear down"
        )
        return

    # Uncomment this for timing info.
    # test._elapsed_time = time.time() - test._started_at
    # print('\n{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2)))
    log.info(f"tearing down {test.account_id} ")
    core_api_helper.create_flag(
        endtoend.testhandle.flag_definition_id_mapping[closure_flag_definition_id], test.account_id
    )

    amount_was_cleared = endtoend.contracts_helper.clear_specific_address_balance(
        test.account, "FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
    )

    if amount_was_cleared:
        endtoend.balances_helper.wait_for_account_balances(
            test.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "0",
                )
            ],
        )

    endtoend.core_api_helper.update_account(
        test.account_id, core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE
    )
    endtoend.balances_helper.wait_for_account_balances(
        test.account_id,
        expected_balances=[
            (BalanceDimensions(address="DEFAULT", denomination=DEFAULT_DENOM), "0"),
            (BalanceDimensions(address="DEPOSIT", denomination=DEFAULT_DENOM), "0"),
            (
                BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                "0",
            ),
            (
                BalanceDimensions(
                    address="TOTAL_REPAYMENTS_LAST_STATEMENT",
                    denomination=DEFAULT_DENOM,
                ),
                "0",
            ),
            (
                BalanceDimensions(address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                "0",
            ),
            (
                BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                "0",
            ),
        ],
    )

    endtoend.accounts_helper.wait_for_account_update(test.account_id, "closure_update")
    endtoend.core_api_helper.update_account(
        test.account_id, core_api_helper.AccountStatus.ACCOUNT_STATUS_CLOSED
    )
