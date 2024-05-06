# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from typing import List, Dict

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    SimulationTestScenario,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_instance_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    get_processed_scheduled_events,
    SimulationTestCase,
)

CONTRACT_FILE = "library/time_deposit/contracts/time_deposit.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"

CONTRACT_FILES = [CONTRACT_FILE]

DEFAULT_DENOMINATION = "GBP"
TD_ACCOUNT = "TIME_DEPOSIT_ACCOUNT"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
TIME_DEPOSIT_BANK_HOLIDAY = "PUBLIC_HOLIDAYS"

ASSET = "ASSET"
LIABILITY = "LIABILITY"

default_internal_accounts = [
    # generic account used for external postings
    "1",
    ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    INTEREST_PAID_ACCOUNT,
]

default_template_params = {
    "denomination": "GBP",
    "maximum_balance": "1000",
    "minimum_first_deposit": "50",
    "single_deposit": "unlimited",
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "interest_application_hour": "23",
    "interest_application_minute": "59",
    "interest_application_second": "59",
    "interest_accrual_hour": "23",
    "interest_accrual_minute": "58",
    "interest_accrual_second": "59",
}
default_instance_params = {
    "gross_interest_rate": "0.149",
    "interest_application_frequency": "monthly",
    "interest_application_day": "31",
    "deposit_period": "28",
    "grace_period": "0",
    "cool_off_period": "0",
    "term_unit": "months",
    "term": "60",
    "fee_free_percentage_limit": "0",
    "withdrawal_fee": "10",
    "withdrawal_percentage_fee": "0",
    "account_closure_period": "7",
    "period_end_hour": "0",
    "auto_rollover_type": "no_rollover",
    "partial_principal_amount": "0",
    "rollover_term_unit": "months",
    "rollover_term": "60",
    "rollover_gross_interest_rate": "0.149",
    "rollover_interest_application_day": "31",
    "rollover_interest_application_frequency": "monthly",
    "rollover_grace_period": "7",
    "rollover_period_end_hour": "0",
    "rollover_account_closure_period": "7",
}

GBP_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="GBP")
GBP_CAPITALISED_INTEREST = BalanceDimensions(address="CAPITALISED_INTEREST", denomination="GBP")
GBP_ACCRUED_INTEREST_PAYABLE = BalanceDimensions(
    address="ACCRUED_INTEREST_PAYABLE", denomination="GBP"
)
GBP_INTERNAL_CONTRA = BalanceDimensions(address="INTERNAL_CONTRA", denomination="GBP")
GBP_COMMITTED = BalanceDimensions(phase="POSTING_PHASE_COMMITTED", denomination="GBP")
GBP_PENDING_OUTGOING = BalanceDimensions(phase="POSTING_PHASE_PENDING_OUTGOING", denomination="GBP")
GBP_PENDING_INCOMING = BalanceDimensions(phase="POSTING_PHASE_PENDING_INCOMING", denomination="GBP")
DEFAULT_DIM = BalanceDimensions(
    address="DEFAULT",
    asset="COMMERCIAL_BANK_MONEY",
    denomination="GBP",
    phase="POSTING_PHASE_COMMITTED",
)


class TimeDepositTestBase(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = CONTRACT_FILES
        cls.contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def default_simulate_account_event(self, start, instance_params=None):
        return create_account_instruction(
            timestamp=start,
            account_id=TD_ACCOUNT,
            product_id="0",
            instance_param_vals=instance_params or default_instance_params,
        )

    def run_test(
        self,
        start: datetime,
        end: datetime,
        events: List,
        template_parameters: Dict[str, str] = None,
        output_account_ids=None,
        output_timestamps=None,
    ):

        return self.client.simulate_smart_contract(
            contract_codes=self.smart_contract_contents.copy(),
            smart_contract_version_ids=["0"],
            templates_parameters=[
                template_parameters or default_template_params,
            ],
            internal_account_ids=default_internal_accounts,
            output_account_ids=output_account_ids,
            output_timestamps=output_timestamps,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            contract_config=self._get_contract_config(template_params=template_parameters),
        )

    def _get_contract_config(self, template_params=None, instance_params=None):
        contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]

        return ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=TD_ACCOUNT,
                )
            ],
            linked_contract_modules=contract_modules,
        )

    def _get_simulation_test_scenario(
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
            contract_config=self._get_contract_config(template_params, instance_params),
            internal_accounts=internal_accounts,
            debug=debug,
        )


class TimeDepositPeriodTest(TimeDepositTestBase):
    def test_change_interest_day_monthly_updates_schedule(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 4, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        instance_params["interest_application_frequency"] = "monthly"
        events = [
            self.default_simulate_account_event(start, instance_params),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2020, 1, 6, tzinfo=timezone.utc),
                interest_application_day="3",
            ),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2020, 3, 2, tzinfo=timezone.utc),
                interest_application_day="1",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        interest_application_events = get_processed_scheduled_events(
            res, "APPLY_ACCRUED_INTEREST", TD_ACCOUNT
        )
        self.assertEqual(
            interest_application_events,
            ["2020-01-05T23:59:59Z", "2020-02-03T23:59:59Z", "2020-04-01T23:59:59Z"],
        )

    def test_change_interest_day_quarterly_updates_schedule(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        instance_params["interest_application_frequency"] = "quarterly"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2020, 4, 6, tzinfo=timezone.utc),
                interest_application_day="3",
            ),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2020, 10, 2, tzinfo=timezone.utc),
                interest_application_day="1",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        interest_application_events = get_processed_scheduled_events(
            res, "APPLY_ACCRUED_INTEREST", TD_ACCOUNT
        )
        self.assertEqual(
            interest_application_events,
            ["2020-04-05T23:59:59Z", "2020-07-03T23:59:59Z", "2021-01-01T23:59:59Z"],
        )

    def test_change_interest_day_semi_annually_updates_schedule(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        instance_params["interest_application_frequency"] = "semi_annually"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2021, 1, 6, tzinfo=timezone.utc),
                interest_application_day="3",
            ),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2023, 1, 2, tzinfo=timezone.utc),
                interest_application_day="1",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        interest_application_events = get_processed_scheduled_events(
            res, "APPLY_ACCRUED_INTEREST", TD_ACCOUNT
        )
        self.assertEqual(
            interest_application_events,
            [
                "2020-07-05T23:59:59Z",
                "2021-01-05T23:59:59Z",
                "2021-07-03T23:59:59Z",
                "2022-01-03T23:59:59Z",
                "2022-07-03T23:59:59Z",
                "2023-07-01T23:59:59Z",
                "2024-01-01T23:59:59Z",
            ],
        )

    def test_change_interest_day_annually_updates_schedule(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        instance_params["interest_application_frequency"] = "annually"

        events = [
            self.default_simulate_account_event(start, instance_params),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2021, 1, 6, tzinfo=timezone.utc),
                interest_application_day="3",
            ),
            create_instance_parameter_change_event(
                account_id=TD_ACCOUNT,
                timestamp=datetime(2023, 1, 2, tzinfo=timezone.utc),
                interest_application_day="1",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        interest_application_events = get_processed_scheduled_events(
            res, "APPLY_ACCRUED_INTEREST", TD_ACCOUNT
        )
        self.assertEqual(
            interest_application_events,
            ["2021-01-05T23:59:59Z", "2022-01-03T23:59:59Z", "2024-01-01T23:59:59Z"],
        )
