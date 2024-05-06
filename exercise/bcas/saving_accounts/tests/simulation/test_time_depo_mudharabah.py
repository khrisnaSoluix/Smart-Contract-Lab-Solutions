# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from library.features.v4.shariah import fixed_profit_accrual, profit_application

# library
from projects.gundala_s.time_deposit.contracts.template import time_depo_mudharabah
from projects.gundala_s.time_deposit.tests import accounts, files
from projects.gundala_s.time_deposit.tests.accounts import default_internal_accounts
from projects.gundala_s.time_deposit.tests import parameters

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationTestScenario,
    SubTest,
)
from contracts_api import(
    NumberShape
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_global_parameter_value_instruction,
    create_global_parameter_instruction,
    update_account_status_pending_closure
)

from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)

time_deposit_instance_params = parameters.time_deposit_instance_params
time_deposit_template_params = parameters.time_deposit_template_params

DEFAULT_SIMULATION_START_DATETIME = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))
PUBLIC_HOLIDAYS = "PUBLIC_HOLIDAYS"

class TimeDepositTest(SimulationTestCase):
    account_id_base = accounts.TIME_DEPOSIT_MDH
    contract_filepaths = [str(files.TIME_DEPOSIT_CONTRACT)]
    internal_accounts = default_internal_accounts

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=False,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[str(files.TIME_DEPOSIT_CONTRACT)],
            template_params=template_params or time_deposit_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or time_deposit_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=self.internal_accounts or internal_accounts,
            debug=debug,
        )

    def test_pre_posting_hook_rejections(self):
        start = DEFAULT_SIMULATION_START_DATETIME
        end = start + relativedelta(months=7)

        sub_tests = [
            SubTest(
                description="Credit account with 1000IDR and apply flag",
                events=[
                    create_global_parameter_instruction(
                        timestamp=start,
                        global_parameter_id=profit_application.PARAM_TAX_RATE,
                        initial_value="0.2",
                        display_name="Global tax rate",
                        description="Global tax rate",
                        number=NumberShape(),
                    ),
                    create_global_parameter_value_instruction(
                        timestamp=start,
                        global_parameter_id=profit_application.PARAM_TAX_RATE,
                        value="0.2",
                        effective_timestamp=start + relativedelta(hours=1),
                    ),
                    create_global_parameter_instruction(
                        timestamp=start,
                        global_parameter_id=fixed_profit_accrual.PARAM_GROSS_DISTRIBUTION_RATE,
                        initial_value="0.2",
                        display_name="Global Gross Distribution rate",
                        description="Global Gross Distribution rate",
                        number=NumberShape(),
                    ),
                    create_global_parameter_value_instruction(
                        timestamp=start,
                        global_parameter_id=fixed_profit_accrual.PARAM_GROSS_DISTRIBUTION_RATE,
                        value="0.2",
                        effective_timestamp=start + relativedelta(hours=1),
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="8000000",
                        event_datetime=start + relativedelta(days=1),
                        denomination=parameters.TEST_DENOMINATION,
                        target_account_id=accounts.TIME_DEPOSIT_MDH,
                        internal_account_id=accounts.INTERNAL_SUSPENSE_ACOCUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="8004756.17",
                        event_datetime=start + relativedelta(months=1, day=7, hour=3),
                        denomination=parameters.TEST_DENOMINATION,
                        target_account_id=accounts.TIME_DEPOSIT_MDH,
                        internal_account_id=accounts.INTERNAL_SUSPENSE_ACOCUNT,
                    ),
                    update_account_status_pending_closure(start + relativedelta(months=1, day=7, hour=4), accounts.TIME_DEPOSIT_MDH)
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)