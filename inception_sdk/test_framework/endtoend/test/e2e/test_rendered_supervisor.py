# standard libs
import logging
import os
from typing import cast

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

endtoend.testhandle.CONTRACTS = {
    "test_contract": {
        "path": "inception_sdk/test_framework/endtoend/test/e2e/input/template/"
        "contract_template.py",
        "template_params": {},
    },
}

endtoend.testhandle.SUPERVISORCONTRACTS = {
    "test_supervisor": {
        "path": "inception_sdk/test_framework/endtoend/test/e2e/input/template/"
        "supervisor_template.py"
    }
}


class TestRenderedSupervisor(endtoend.AcceleratedEnd2EndTest):
    # "ACCRUE_FEES" will have a default paused tag
    @endtoend.AcceleratedEnd2EndTest.Decorators.control_schedules(
        {"test_supervisor": ["ACCRUE_OFFSET_INTEREST"]}
    )
    def test_rendered_supervisor_schedules_are_controlled(self):
        endtoend.standard_setup()
        cust_id = endtoend.core_api_helper.create_customer()
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="test_contract",
            status="ACCOUNT_STATUS_OPEN",
        )

        plan_id = endtoend.supervisors_helper.link_accounts_to_supervisor(
            "test_supervisor", [account["id"]]
        )

        plan_schedules = endtoend.schedule_helper.get_plan_schedules(plan_id=plan_id)

        # we've defined schedules as dict[str, str] but for tags specifically we get list[str]
        # fixing the return type hint causes more issues than it solves and this is only really
        # addressed by using proper classes for vault types, which is on the to-do list for SDK v2
        accrue_offset_tags = cast(list[str], plan_schedules["ACCRUE_OFFSET_INTEREST"]["tags"])
        accrue_fees_tags = cast(list[str], plan_schedules["ACCRUE_FEES"]["tags"])

        # Accrue offset is explicitly controlled and has its own tag, whereas accrue fees is
        # implicitly controlled and uses the default paused tag id
        self.assertListEqual(
            accrue_offset_tags,
            [
                endtoend.testhandle.controlled_schedule_tags["test_supervisor"][
                    "ACCRUE_OFFSET_INTEREST"
                ]
            ],
        )
        self.assertListEqual(accrue_fees_tags, [endtoend.testhandle.default_paused_tag_id])

        endtoend.schedule_helper.trigger_next_schedule_job_and_wait(
            schedule_name="ACCRUE_OFFSET_INTEREST",
            plan_id=plan_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            account["id"],
            expected_balances=[
                (BalanceDimensions(address="TEST_ADDRESS_1", denomination="GBP"), "2"),
                (BalanceDimensions(address="TEST_ADDRESS_2", denomination="GBP"), "-2"),
            ],
        )
