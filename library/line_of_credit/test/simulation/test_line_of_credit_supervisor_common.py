# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

DEFAULT_PLAN_ID = "1"


class LineOfCreditSupervisorCommonTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [
            contract_files.LOC_SUPERVISOR,
            contract_files.LOC_CONTRACT,
            contract_files.DRAWDOWN_LOAN_CONTRACT,
        ]
        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            "line_of_credit": "1000",
            "drawdown_loan": "1001",
        }

        super().setUpClass()

    def _get_default_supervisor_config(
        self,
        loc_instance_params=test_parameters.loc_instance_params,
        loc_template_params=test_parameters.loc_template_params,
        drawdown_loan_instance_params=test_parameters.drawdown_loan_instance_params,
        drawdown_loan_template_params=test_parameters.drawdown_loan_template_params,
        loc_instances=1,
        drawdown_loan_instances=1,
    ):
        loc_supervisee = ContractConfig(
            template_params=loc_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=loc_instance_params,
                    account_id_base=f"{accounts.LOC_ACCOUNT}_",
                    number_of_accounts=loc_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.LOC_CONTRACT],
            clu_resource_id="line_of_credit",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["line_of_credit"],
        )
        drawdown_loan_supervisee = ContractConfig(
            template_params=drawdown_loan_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=drawdown_loan_instance_params,
                    account_id_base=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_",
                    number_of_accounts=drawdown_loan_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[
                contract_files.DRAWDOWN_LOAN_CONTRACT
            ],
            clu_resource_id="drawdown_loan",
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["drawdown_loan"],
        )

        supervisor_config = SupervisorConfig(
            supervisor_contract=self.smart_contract_path_to_content[contract_files.LOC_SUPERVISOR],
            supervisee_contracts=[
                loc_supervisee,
                drawdown_loan_supervisee,
            ],
            supervisor_contract_version_id="supervisor version 1",
            plan_id=DEFAULT_PLAN_ID,
        )

        return supervisor_config


def get_mimic_loan_creation_subtest(
    start: datetime,
    amount: str,
    drawdown_loan_instances: int = 1,
) -> SubTest:
    events = []
    expected_balances = {}
    for i in range(drawdown_loan_instances):
        events.append(
            create_outbound_hard_settlement_instruction(
                target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                amount=amount,
                event_datetime=start,
                internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
            ),
        )
        expected_balances.update(
            {f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_{i}": [(dimensions.PRINCIPAL, amount)]}
        )
    total_amount = str(drawdown_loan_instances * int(amount))
    expected_balances.update(
        {
            f"{accounts.LOC_ACCOUNT}_0": [(dimensions.DEFAULT, total_amount)],
            accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, total_amount)],
        },
    )

    return SubTest(
        description="Check balances when account opens",
        # we need to mimic the creation of the outbound hard settlement
        # instructions used to create the drawdown loans
        events=events,
        expected_balances_at_ts={start + relativedelta(seconds=1): expected_balances},
    )
