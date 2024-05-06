# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# library
from library.mortgage.test import accounts, files, parameters
from library.mortgage.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationTestScenario,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

INPUT_DATA = Path("library/mortgage/test/simulation/input_data.json")
EXPECTED_OUTPUT = Path("library/mortgage/test/simulation/expected_output.json")


class MortgageTestBase(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = str(files.MORTGAGE_CONTRACT)
        cls.input_data_filename = INPUT_DATA
        cls.expected_output_filename = EXPECTED_OUTPUT
        super().setUpClass()

    account_id_base = accounts.MORTGAGE_ACCOUNT
    contract_filepaths = [str(files.MORTGAGE_CONTRACT)]
    internal_accounts = default_internal_accounts
    mortgage_instance_params = parameters.mortgage_instance_params
    mortgage_template_params = parameters.mortgage_template_params
    default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=ZoneInfo("UTC"))

    def get_contract_config(
        self,
        contract_version_id=None,
        instance_params=None,
        template_params=None,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            template_params=template_params or self.mortgage_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.mortgage_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
        )
        if contract_version_id:
            contract_config.smart_contract_version_id = contract_version_id
        return contract_config

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
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self.get_contract_config(
                instance_params=instance_params,
                template_params=template_params,
            ),
            internal_accounts=internal_accounts or self.internal_accounts,
            debug=debug,
        )
