# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
from library.loan.test import accounts, files, parameters
from library.loan.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationTestScenario,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase


class LoanTestBase(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = str(files.LOAN_CONTRACT)
        cls.input_data_filename = "library/loan/test/simulation/input_data.json"
        cls.expected_output_filename = "library/loan/test/simulation/expected_output.json"
        super().setUpClass()

    loan_account_id = accounts.LOAN
    contract_filepaths = [str(files.LOAN_CONTRACT)]
    internal_accounts = default_internal_accounts
    loan_instance_params = parameters.loan_instance_params
    loan_template_params = parameters.loan_template_params
    default_simulation_start_datetime = datetime(year=2023, month=1, day=1, tzinfo=ZoneInfo("UTC"))

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
            contract_content=self.smart_contract_path_to_content[self.contract_filepath],
            template_params=template_params or self.loan_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.loan_instance_params,
                    account_id_base=self.loan_account_id,
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

    def create_deposit_events(
        self,
        num_payments: int,
        repayment_amount: str,
        repayment_day: int,
        repayment_hour: int,
        start_year: int,
        start_month: int,
    ):
        """
        Generates inbound hard settlement events for loan repayments. Datetime of the repayment
        event is fixed at minute = 0, second = 0
        """
        events = []
        for i in range(num_payments):
            month = (i + start_month - 1) % 12 + 1
            year = start_year + int((i + start_month + 1 - month) / 12)

            event_date = datetime(
                year=year,
                month=month,
                day=repayment_day,
                hour=repayment_hour,
                minute=0,
                second=0,
                tzinfo=ZoneInfo("UTC"),
            )
            events.append(
                create_inbound_hard_settlement_instruction(
                    target_account_id=self.loan_account_id,
                    amount=repayment_amount,
                    event_datetime=event_date,
                    internal_account_id=accounts.DEPOSIT,
                )
            )

        return events
