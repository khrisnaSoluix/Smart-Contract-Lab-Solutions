# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from json import dumps

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
    ExpectedWorkflow,
    ExpectedDerivedParameter,
    ExpectedRejection,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
    get_postings,
    get_processed_scheduled_events,
    get_logs,
    get_workflows_by_id,
)

CONTRACT_FILE = "library/mortgage/contracts/mortgage.py"
CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "amortisation": "library/common/contract_modules/amortisation.py",
}

INPUT_DATA = "library/mortgage/contracts/tests/simulation/input_data.json"
EXPECTED_OUTPUT = "library/mortgage/contracts/tests/simulation/expected_output.json"

DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"
DEFAULT_DENOMINATION = "GBP"

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

DEFAULT_PENALTY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_DELINQUENCY_FLAG = dumps(["ACCOUNT_DELINQUENT"])
DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])
DEFAULT_REPAYMENT_BLOCKING_FLAG = dumps(["REPAYMENT_HOLIDAY"])

INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECEIVED"
INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_RECEIVED"
INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE_INCOME"

ASSET = "ASSET"
LIABILITY = "LIABILITY"

default_internal_accounts = {
    DEPOSIT_ACCOUNT: LIABILITY,
    INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: ASSET,
    INTERNAL_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT: LIABILITY,
    INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: LIABILITY,
    INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT: LIABILITY,
}

PRINCIPAL = "PRINCIPAL"
PRINCIPAL_CAPITALISED_INTEREST = "PRINCIPAL_CAPITALISED_INTEREST"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL_DUE = "PRINCIPAL_DUE"
OVERPAYMENT = "OVERPAYMENT"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

PRINCIPAL_DIMENSION = BalanceDimensions(address=PRINCIPAL)
PRINCIPAL_CAPITALISED_INTEREST_DIMENSION = BalanceDimensions(address=PRINCIPAL_CAPITALISED_INTEREST)
ACCRUED_EXPECTED_INTEREST_DIMENSION = BalanceDimensions(address=ACCRUED_EXPECTED_INTEREST)
ACCRUED_INTEREST_DIMENSION = BalanceDimensions(address=ACCRUED_INTEREST)
CAPITALISED_INTEREST_DIMENSION = BalanceDimensions(address=CAPITALISED_INTEREST)
INTEREST_DUE_DIMENSION = BalanceDimensions(address=INTEREST_DUE)
PRINCIPAL_DUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_DUE)
OVERPAYMENT_DIMENSION = BalanceDimensions(address=OVERPAYMENT)
EMI_PRINCIPAL_EXCESS_DIMENSION = BalanceDimensions(address=EMI_PRINCIPAL_EXCESS)
INTEREST_OVERDUE_DIMENSION = BalanceDimensions(address=INTEREST_OVERDUE)
PRINCIPAL_OVERDUE_DIMENSION = BalanceDimensions(address=PRINCIPAL_OVERDUE)
PENALTIES_DIMENSION = BalanceDimensions(address=PENALTIES)
EMI_ADDRESS_DIMENSION = BalanceDimensions(address=EMI_ADDRESS)
INTERNAL_CONTRA_DIMENSION = BalanceDimensions(address=INTERNAL_CONTRA)
DEFAULT_DIMENSION = BalanceDimensions()

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
num_payments = 1
repayment_day = 28
payment_hour = 12
start_year = 2020
start_month = 1
mortgage_1_expected_monthly_repayment = "2275.16"
mortgage_1_expected_remaining_balance = "-46.67"
mortgage_2_first_month_payment = str(Decimal("2910.69") + Decimal("229.32"))
mortgage_2_EMI = "2910.69"
mortgage_2_expected_fee = "35.0"

mortgage_1_instance_params = {
    "fixed_interest_rate": "0.129971",
    "fixed_interest_term": "0",
    "total_term": "120",
    "overpayment_fee_percentage": "0.05",
    "interest_only_term": "0",
    "principal": "300000",
    "repayment_day": "12",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "-0.001",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

mortgage_1_template_params = {
    "variable_interest_rate": "0.032",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    "interest_received_account": INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_allowance_fee_income_account": INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}

mortgage_2_instance_params = {
    "fixed_interest_rate": "0.031",
    "fixed_interest_term": "120",
    "total_term": "120",
    "interest_only_term": "0",
    "overpayment_fee_percentage": "0.05",
    "principal": "300000",
    "repayment_day": "20",
    "deposit_account": DEPOSIT_ACCOUNT,
    "overpayment_percentage": "0.1",
    "variable_rate_adjustment": "0.00",
    "mortgage_start_date": str(default_simulation_start_date.date()),
}

mortgage_2_template_params = {
    "variable_interest_rate": "0.189965",
    "denomination": "GBP",
    "late_repayment_fee": "15",
    "penalty_interest_rate": "0.24",
    "penalty_includes_base_rate": "True",
    "grace_period": "5",
    "penalty_blocking_flags": DEFAULT_PENALTY_BLOCKING_FLAG,
    "due_amount_blocking_flags": DEFAULT_DUE_AMOUNT_BLOCKING_FLAG,
    "delinquency_blocking_flags": DEFAULT_DELINQUENCY_BLOCKING_FLAG,
    "delinquency_flags": DEFAULT_DELINQUENCY_FLAG,
    "overdue_amount_blocking_flags": DEFAULT_OVERDUE_AMOUNT_BLOCKING_FLAG,
    "repayment_blocking_flags": DEFAULT_REPAYMENT_BLOCKING_FLAG,
    "accrued_interest_receivable_account": INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "capitalised_interest_received_account": INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT,
    "interest_received_account": INTERNAL_INTEREST_RECEIVED_ACCOUNT,
    "penalty_interest_received_account": INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT,
    "late_repayment_fee_income_account": INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT,
    "overpayment_allowance_fee_income_account": INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT,
    "accrual_precision": "5",
    "fulfillment_precision": "2",
    "overpayment_impact_preference": "reduce_term",
    "accrue_interest_hour": "0",
    "accrue_interest_minute": "0",
    "accrue_interest_second": "1",
    "check_delinquency_hour": "0",
    "check_delinquency_minute": "0",
    "check_delinquency_second": "2",
    "repayment_hour": "0",
    "repayment_minute": "1",
    "repayment_second": "0",
    "overpayment_hour": "0",
    "overpayment_minute": "0",
    "overpayment_second": "0",
}


class MortgageTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepath = CONTRACT_FILE
        cls.input_data_filename = INPUT_DATA
        cls.expected_output_filename = EXPECTED_OUTPUT
        cls.linked_contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def _get_contract_config(
        self,
        contract_version_id=None,
        instance_params=None,
        template_params=None,
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=MORTGAGE_ACCOUNT,
                )
            ],
            linked_contract_modules=self.linked_contract_modules,
        )
        if contract_version_id:
            contract_config.smart_contract_version_id = contract_version_id
        return contract_config

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self._get_contract_config(
                instance_params=instance_params,
                template_params=template_params,
            ),
            internal_accounts=internal_accounts,
        )

    def test_switch_mortgage(self):
        start = datetime(year=2021, month=3, day=8, tzinfo=timezone.utc)
        end = start + relativedelta(days=3, hours=1)
        remortgage_date = start + relativedelta(days=2, hours=1)
        before_remortgage = remortgage_date - relativedelta(days=1)
        after_remortgage = remortgage_date + relativedelta(minutes=1)

        template_params = mortgage_1_template_params.copy()
        instance_params = mortgage_1_instance_params.copy()
        instance_params["mortgage_start_date"] = str(start.date())

        sub_tests = [
            SubTest(
                description="setup overpayment before remortgage",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "10000",
                        start + relativedelta(hours=1),
                        internal_account_id=DEPOSIT_ACCOUNT,
                        target_account_id=MORTGAGE_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    before_remortgage: {
                        # expected principal 300000
                        # variable rate 0.032
                        # variable rate offset -0.001
                        # days in year 365
                        # 300000*(0.032-0.001)/365 = 25.47945
                        MORTGAGE_ACCOUNT: [
                            (DEFAULT_DIMENSION, "0"),
                            (PRINCIPAL_DIMENSION, "300000"),
                            (OVERPAYMENT_DIMENSION, "-10000"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "25.47945"),
                        ]
                    }
                },
            ),
            SubTest(
                description="balance clearance after remortgaging",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=remortgage_date,
                        account_id=MORTGAGE_ACCOUNT,
                        mortgage_start_date=str(remortgage_date.date()),
                        fixed_interest_rate="0.021",
                        fixed_interest_term="10",
                        interest_only_term="0",
                        total_term="240",
                        principal="290000",
                    )
                ],
                expected_balances_at_ts={
                    after_remortgage: {
                        MORTGAGE_ACCOUNT: [
                            (DEFAULT_DIMENSION, "0"),
                            (PRINCIPAL_DIMENSION, "290000"),
                            (OVERPAYMENT_DIMENSION, "0"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "0"),
                        ]
                    }
                },
            ),
            SubTest(
                description="interest accrued using updated principal and rates",
                expected_balances_at_ts={
                    # expected principal 290000
                    # fixed rate 0.021
                    # days in year 365
                    # 290000*0.021/365 = 16.68492
                    end: {
                        MORTGAGE_ACCOUNT: [
                            (DEFAULT_DIMENSION, "0"),
                            (PRINCIPAL_DIMENSION, "290000"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "16.68492"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_interest_accrual(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=3, seconds=1)

        events = []
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount="100000",
                event_datetime=start + relativedelta(days=2),
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount="100000",
                event_datetime=start + relativedelta(days=3),
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_1_instance_params,
            template_params=mortgage_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_1_instance_params,
                template_params=mortgage_1_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        mortgage_balances = get_balances(res)[MORTGAGE_ACCOUNT]
        self.assertEqual(
            mortgage_balances.at(start + relativedelta(days=1, seconds=1))[
                ACCRUED_INTEREST,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                "POSTING_PHASE_COMMITTED",
            ].net,
            Decimal("25.47945"),
        )
        self.assertEqual(
            mortgage_balances.at(start + relativedelta(days=2, seconds=1))[
                ACCRUED_INTEREST,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                "POSTING_PHASE_COMMITTED",
            ].net,
            Decimal("42.46575"),
        )
        self.assertEqual(
            mortgage_balances.at(start + relativedelta(days=3, seconds=1))[
                ACCRUED_INTEREST,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                "POSTING_PHASE_COMMITTED",
            ].net,
            Decimal("50.95890"),
        )

        schedules = get_processed_scheduled_events(
            res, event_id="ACCRUE_INTEREST", account_id=MORTGAGE_ACCOUNT
        )
        self.assertEqual(len(schedules), 3)
        self.assertEqual("2020-01-12T00:00:01Z", schedules[0])
        self.assertEqual("2020-01-13T00:00:01Z", schedules[1])
        self.assertEqual("2020-01-14T00:00:01Z", schedules[2])

    def test_daily_penalty_accrual(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=19, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        principal_overdues = [
            posting
            for posting in get_postings(res, MORTGAGE_ACCOUNT, PRINCIPAL_OVERDUE_DIMENSION)
            if posting["credit"]
        ]
        interest_overdues = [
            posting
            for posting in get_postings(res, MORTGAGE_ACCOUNT, INTEREST_OVERDUE_DIMENSION)
            if posting["credit"]
        ]
        penalties = [
            posting
            for posting in get_postings(res, MORTGAGE_ACCOUNT, PENALTIES_DIMENSION)
            if posting["credit"]
        ]

        for index, amount_due in enumerate(zip(principal_overdues, interest_overdues)):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][0]),
                Decimal(amount_due[0]["amount"]),
            )
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["overdue"][index][1]),
                Decimal(amount_due[1]["amount"]),
            )

        for index, amount_due in enumerate(penalties):
            self.assertEquals(
                Decimal(self.expected_output["late_payment"]["penalties"][index]),
                Decimal(amount_due["amount"]),
            )

    def test_zero_interest_rate(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2)

        template_params = mortgage_1_template_params.copy()
        template_params["variable_interest_rate"] = "0.001"

        sub_tests = [
            SubTest(
                description="0 interest accrual",
                expected_balances_at_ts={
                    datetime(year=2020, month=2, day=12, hour=1, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            # 300000/120 = 2500
                            (PRINCIPAL_DUE_DIMENSION, "2500"),
                            (INTEREST_DUE_DIMENSION, "0"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                        ]
                    }
                },
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=mortgage_1_instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_change_repayment_day_after(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=1, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )
        events = []
        for event in self.input_data["change_repayment_day_after"]:
            if event[0] == "repayment_day_change":
                events.append(
                    create_instance_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        account_id=MORTGAGE_ACCOUNT,
                        repayment_day=str(event[4]),
                    )
                )
            elif event[0] == "repayment_postings":
                events.extend(
                    _set_up_deposit_events(
                        num_payments=int(event[1]),
                        repayment_amount=event[2],
                        repayment_day=int(event[5]),
                        repayment_hour=payment_hour,
                        start_year=int(event[3]),
                        start_month=int(event[4]),
                    )
                )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_day_schedules = get_processed_scheduled_events(
            res, event_id="REPAYMENT_DAY_SCHEDULE", account_id=MORTGAGE_ACCOUNT
        )
        self.assertEqual(len(repayment_day_schedules), 11)
        self.assertEqual("2020-02-20T00:01:00Z", repayment_day_schedules[0])
        self.assertEqual("2020-03-20T00:01:00Z", repayment_day_schedules[1])
        self.assertEqual("2020-04-22T00:01:00Z", repayment_day_schedules[2])
        self.assertEqual("2020-05-22T00:01:00Z", repayment_day_schedules[3])
        self.assertEqual("2020-06-26T00:01:00Z", repayment_day_schedules[4])
        self.assertEqual("2020-07-26T00:01:00Z", repayment_day_schedules[5])
        self.assertEqual("2020-08-26T00:01:00Z", repayment_day_schedules[6])
        self.assertEqual("2020-09-26T00:01:00Z", repayment_day_schedules[7])
        self.assertEqual("2020-10-26T00:01:00Z", repayment_day_schedules[8])
        self.assertEqual("2020-11-26T00:01:00Z", repayment_day_schedules[9])
        self.assertEqual("2020-12-26T00:01:00Z", repayment_day_schedules[10])

        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        expected_output = self.expected_output["change_repayment_day_after"]
        for i, values in enumerate(expected_output):
            repayment_date = datetime(
                year=start_year,
                month=2,
                day=int(values[2]),
                hour=1,
                tzinfo=timezone.utc,
            )
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]

        self.check_balances(expected_balances, get_balances(res))

    def test_change_repayment_day_before(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=2, day=1, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []
        for event in self.input_data["change_repayment_day_before"]:
            if event[0] == "repayment_day_change":
                events.append(
                    create_instance_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        account_id=MORTGAGE_ACCOUNT,
                        repayment_day=str(event[4]),
                    )
                )
            elif event[0] == "repayment_postings":
                events.extend(
                    _set_up_deposit_events(
                        num_payments=int(event[1]),
                        repayment_amount=event[2],
                        repayment_day=int(event[5]),
                        repayment_hour=payment_hour,
                        start_year=int(event[3]),
                        start_month=int(event[4]),
                    )
                )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_day_schedules = get_processed_scheduled_events(
            res, event_id="REPAYMENT_DAY_SCHEDULE", account_id=MORTGAGE_ACCOUNT
        )
        self.assertEqual(len(repayment_day_schedules), 10)
        self.assertEqual("2020-02-20T00:01:00Z", repayment_day_schedules[0])
        self.assertEqual("2020-03-20T00:01:00Z", repayment_day_schedules[1])
        self.assertEqual("2020-05-18T00:01:00Z", repayment_day_schedules[2])
        self.assertEqual("2020-06-18T00:01:00Z", repayment_day_schedules[3])
        self.assertEqual("2020-07-18T00:01:00Z", repayment_day_schedules[4])
        self.assertEqual("2020-08-18T00:01:00Z", repayment_day_schedules[5])
        self.assertEqual("2020-09-18T00:01:00Z", repayment_day_schedules[6])
        self.assertEqual("2020-11-10T00:01:00Z", repayment_day_schedules[7])
        self.assertEqual("2020-12-10T00:01:00Z", repayment_day_schedules[8])

        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        expected_output = self.expected_output["change_repayment_day_before"]
        previous_repayment_date = None
        months_delta = 0
        for _i, values in enumerate(expected_output):
            repayment_date = datetime(
                year=start_year,
                month=2,
                day=int(values[2]),
                hour=1,
                tzinfo=timezone.utc,
            )
            if previous_repayment_date and previous_repayment_date > values[2]:
                months_delta = months_delta + 1
            expected_balances[MORTGAGE_ACCOUNT][
                repayment_date + relativedelta(months=months_delta)
            ] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
            ]
            previous_repayment_date = values[2]
            months_delta += 1

        self.check_balances(expected_balances, get_balances(res))

    def test_check_delinquency_schedule(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=10, minute=1, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        day_of_repayment_day_change = datetime(year=2020, month=6, day=15, tzinfo=timezone.utc)

        events = []

        repayment_with_overpayment = str(Decimal(mortgage_2_EMI) + Decimal("10000"))
        events.extend(
            _set_up_deposit_events(
                2,
                repayment_with_overpayment,
                repayment_day,
                payment_hour,
                start_year,
                3,
            )
        )

        events.append(
            create_instance_parameter_change_event(
                timestamp=day_of_repayment_day_change,
                account_id=MORTGAGE_ACCOUNT,
                repayment_day="25",
            )
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        check_delinquency_schedules = get_processed_scheduled_events(
            res, "CHECK_DELINQUENCY", account_id=MORTGAGE_ACCOUNT
        )

        self.assertEqual(len(check_delinquency_schedules), 8)
        self.assertEqual("2020-03-25T00:00:02Z", check_delinquency_schedules[0])
        self.assertEqual("2020-06-30T00:00:02Z", check_delinquency_schedules[1])
        self.assertEqual("2020-07-30T00:00:02Z", check_delinquency_schedules[2])
        self.assertEqual("2020-08-30T00:00:02Z", check_delinquency_schedules[3])
        self.assertEqual("2020-09-30T00:00:02Z", check_delinquency_schedules[4])
        self.assertEqual("2020-10-30T00:00:02Z", check_delinquency_schedules[5])
        self.assertEqual("2020-11-30T00:00:02Z", check_delinquency_schedules[6])
        self.assertEqual("2020-12-30T00:00:02Z", check_delinquency_schedules[7])

    def test_early_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=29, hour=3, tzinfo=timezone.utc)

        template_params = mortgage_1_template_params.copy()

        early_repayment_time = datetime(year=2020, month=3, day=28, tzinfo=timezone.utc)
        before_early_repayment = early_repayment_time - relativedelta(seconds=1)
        after_early_repayment = early_repayment_time + relativedelta(seconds=1)

        sub_tests = [
            SubTest(
                description="early repayment triggers close mortgage workflow",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "301973.44",
                        early_repayment_time,
                        target_account_id=MORTGAGE_ACCOUNT,
                        internal_account_id=DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    before_early_repayment: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DIMENSION, "295702.16"),
                            (ACCRUED_INTEREST_DIMENSION, "376.71645"),
                            (INTERNAL_CONTRA_DIMENSION, "-3664.1229"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "376.71645"),
                            (INTEREST_DUE_DIMENSION, "733.68"),
                            (PRINCIPAL_DUE_DIMENSION, "2177.01"),
                            (EMI_ADDRESS_DIMENSION, "2910.69"),
                            (PENALTIES_DIMENSION, "47.7"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "2120.83"),
                            (INTEREST_OVERDUE_DIMENSION, "815.34"),
                            (DEFAULT_DIMENSION, "0"),
                            (OVERPAYMENT_DIMENSION, "0"),
                        ]
                    },
                    # residual balances not cleared until close account
                    # workflow is complete
                    after_early_repayment: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DIMENSION, "295702.16"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (INTERNAL_CONTRA_DIMENSION, "-3312.52088"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "401.83088"),
                            (INTEREST_DUE_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (EMI_ADDRESS_DIMENSION, "2910.69"),
                            (PENALTIES_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                            (INTEREST_OVERDUE_DIMENSION, "0"),
                            # from backdated posting in withdrawal override subtest
                            (DEFAULT_DIMENSION, "-10000"),
                            (OVERPAYMENT_DIMENSION, "-295702.16"),
                        ]
                    },
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="MORTGAGE_CLOSURE",
                        account_id=MORTGAGE_ACCOUNT,
                        count=1,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_early_repayment,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="118",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_early_repayment,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="0",
                    ),
                ],
            ),
            SubTest(
                description="back dated overpayment is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        amount="301973.44",
                        event_datetime=early_repayment_time + relativedelta(hours=1),
                        internal_account_id=DEPOSIT_ACCOUNT,
                        value_timestamp=early_repayment_time - relativedelta(hours=1),
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_time
                    + relativedelta(hours=1): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DIMENSION, "295702.16"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (INTERNAL_CONTRA_DIMENSION, "-3312.52088"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "401.83088"),
                            (INTEREST_DUE_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (EMI_ADDRESS_DIMENSION, "2910.69"),
                            (PENALTIES_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                            (INTEREST_OVERDUE_DIMENSION, "0"),
                            # from backdated posting in withdrawal override subtest
                            (DEFAULT_DIMENSION, "-10000"),
                            (OVERPAYMENT_DIMENSION, "-295702.16"),
                        ]
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=early_repayment_time + relativedelta(hours=1),
                        account_id=MORTGAGE_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than is owed",
                    )
                ],
            ),
            SubTest(
                description="back dated posting with withdrawal override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=MORTGAGE_ACCOUNT,
                        amount="10000",
                        event_datetime=early_repayment_time + relativedelta(hours=2),
                        internal_account_id=DEPOSIT_ACCOUNT,
                        value_timestamp=early_repayment_time - relativedelta(hours=2),
                        batch_details={"withdrawal_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_time
                    + relativedelta(hours=2): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DIMENSION, "295702.16"),
                            (ACCRUED_INTEREST_DIMENSION, "0"),
                            (INTERNAL_CONTRA_DIMENSION, "-3312.52088"),
                            (ACCRUED_EXPECTED_INTEREST_DIMENSION, "401.83088"),
                            (INTEREST_DUE_DIMENSION, "0"),
                            (PRINCIPAL_DUE_DIMENSION, "0"),
                            (EMI_ADDRESS_DIMENSION, "2910.69"),
                            (PENALTIES_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                            (INTEREST_OVERDUE_DIMENSION, "0"),
                            (DEFAULT_DIMENSION, "-10000"),
                            (OVERPAYMENT_DIMENSION, "-295702.16"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=mortgage_1_instance_params,
            internal_accounts=default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_overpayment_backdated_posting_is_rejected(self):
        """
        Ensure smart contract refers the live balances and rejects
        when backdated repayment postings are received with an amount exceeding
        the current outstanding debt balances
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=28, minute=1, tzinfo=timezone.utc)

        instance_params = mortgage_1_instance_params.copy()
        instance_params["overpayment_percentage"] = "1"

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (PRINCIPAL_DIMENSION, "295702.16"),
                    (ACCRUED_INTEREST_DIMENSION, "0"),
                    (INTERNAL_CONTRA_DIMENSION, "-3312.52088"),
                    (ACCRUED_EXPECTED_INTEREST_DIMENSION, "401.83088"),
                    (INTEREST_DUE_DIMENSION, "0"),
                    (PRINCIPAL_DUE_DIMENSION, "0"),
                    (EMI_ADDRESS_DIMENSION, "2910.69"),
                    (PENALTIES_DIMENSION, "0"),
                    (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                    (INTEREST_OVERDUE_DIMENSION, "0"),
                    (DEFAULT_DIMENSION, "0"),
                    (OVERPAYMENT_DIMENSION, "-295702.16"),
                ]
            }
        }

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_1_instance_params,
            template_params=mortgage_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = _set_up_deposit_events(1, "301973.44", 27, 10, 2020, 3)
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount="301973.44",
                event_datetime=datetime(year=2020, month=3, day=27, hour=11, tzinfo=timezone.utc),
                internal_account_id=DEPOSIT_ACCOUNT,
                value_timestamp=datetime(year=2020, month=3, day=27, hour=9, tzinfo=timezone.utc),
            )
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_1_instance_params,
                template_params=mortgage_1_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)

        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

        self.assertIn("Cannot pay more than is owed", get_logs(res))

    def test_overpayment_backdated_posting_with_withdrawal_override(self):
        """
        Ensure smart contract refers the live balances and accepts
        when backdated repayment postings are received with an amount exceeding
        the current outstanding debt balances and posting batch is set to
        override withdrawal
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=28, minute=1, tzinfo=timezone.utc)

        instance_params = mortgage_1_instance_params.copy()
        instance_params["overpayment_percentage"] = "1"

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (PRINCIPAL_DIMENSION, "295702.16"),
                    (ACCRUED_INTEREST_DIMENSION, "0"),
                    (INTERNAL_CONTRA_DIMENSION, "-3312.52088"),
                    (ACCRUED_EXPECTED_INTEREST_DIMENSION, "401.83088"),
                    (INTEREST_DUE_DIMENSION, "0"),
                    (PRINCIPAL_DUE_DIMENSION, "0"),
                    (EMI_ADDRESS_DIMENSION, "2910.69"),
                    (PENALTIES_DIMENSION, "0"),
                    (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                    (INTEREST_OVERDUE_DIMENSION, "0"),
                    (DEFAULT_DIMENSION, "-10000"),
                    (OVERPAYMENT_DIMENSION, "-295702.16"),
                ]
            }
        }

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_1_instance_params,
            template_params=mortgage_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = _set_up_deposit_events(1, "301973.44", 27, 10, 2020, 3)
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount="10000",
                event_datetime=datetime(year=2020, month=3, day=27, hour=11, tzinfo=timezone.utc),
                internal_account_id=DEPOSIT_ACCOUNT,
                value_timestamp=datetime(year=2020, month=3, day=27, hour=9, tzinfo=timezone.utc),
                batch_details={"withdrawal_override": "true"},
            )
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_1_instance_params,
                template_params=mortgage_1_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        balances = get_balances(res)
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_check_delinquency_instantiated_when_backdated_payment_received_after_graceperiod(
        self,
    ):
        """
        When a repayment is made during the grace period but received after the grace period,
        ensure repayment amount is applied to live overdue balances first,
        followed repayment hierarchy and
        MORTGAGE_MARK_DELINQUENT workflow is instantiated at the end of the grace period.
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=26, hour=2, minute=1, tzinfo=timezone.utc)

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (INTEREST_DUE_DIMENSION, "733.68"),
                    (PRINCIPAL_DUE_DIMENSION, "2177.01"),
                    (PENALTIES_DIMENSION, "26.65"),
                    (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                    (INTEREST_OVERDUE_DIMENSION, "0"),
                ]
            }
        }

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount=mortgage_2_first_month_payment,
                event_datetime=datetime(year=2020, month=3, day=25, hour=1, tzinfo=timezone.utc),
                internal_account_id=DEPOSIT_ACCOUNT,
                value_timestamp=datetime(year=2020, month=3, day=19, hour=1, tzinfo=timezone.utc),
            )
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        workflow_delinquent = get_workflows_by_id(
            res=res,
            workflow_definition_id="MORTGAGE_MARK_DELINQUENT",
            account_id=MORTGAGE_ACCOUNT,
        )

        check_repayment_schedules = get_processed_scheduled_events(
            res, "REPAYMENT_DAY_SCHEDULE", account_id=MORTGAGE_ACCOUNT
        )
        check_delinquency_schedules = get_processed_scheduled_events(
            res, "CHECK_DELINQUENCY", account_id=MORTGAGE_ACCOUNT
        )

        self.assertEqual("2020-02-20T00:01:00Z", check_repayment_schedules[0])
        self.assertEqual("2020-03-20T00:01:00Z", check_repayment_schedules[1])
        self.assertEqual(1, len(check_delinquency_schedules))
        self.assertEqual("2020-03-25T00:00:02Z", check_delinquency_schedules[0])
        self.assertEqual(1, len(workflow_delinquent))

        balances = get_balances(res)
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_check_delinquency_disabled_when_backdated_payment_received_during_graceperiod(
        self,
    ):
        """
        When a repayment is made before the grace period but vault received
        during the grace period, ensure repayment amount is applied to live overdue
        balances first, followed repayment hierarchy and
        CHECK_DELINQUENCY schedule has not instantiated the MORTGAGE_MARK_DELINQUENT workflow.
        """
        start = default_simulation_start_date
        end = datetime(year=2020, month=3, day=26, hour=2, minute=1, tzinfo=timezone.utc)

        expected_balances = {
            MORTGAGE_ACCOUNT: {
                end: [
                    (INTEREST_DUE_DIMENSION, "733.68"),
                    # reduced principal due to overpayment
                    (PRINCIPAL_DUE_DIMENSION, "2176.34"),
                    (PENALTIES_DIMENSION, "0"),
                    (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                    (INTEREST_OVERDUE_DIMENSION, "0"),
                ]
            }
        }

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        events = []
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount=str(Decimal(mortgage_2_first_month_payment) + Decimal("18")),
                event_datetime=datetime(year=2020, month=3, day=22, hour=0, tzinfo=timezone.utc),
                internal_account_id=DEPOSIT_ACCOUNT,
                value_timestamp=datetime(year=2020, month=3, day=20, hour=1, tzinfo=timezone.utc),
            )
        )

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=mortgage_2_instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        workflow_delinquent = get_workflows_by_id(
            res=res,
            workflow_definition_id="MORTGAGE_MARK_DELINQUENT",
            account_id=MORTGAGE_ACCOUNT,
        )

        check_repayment_schedules = get_processed_scheduled_events(
            res, "REPAYMENT_DAY_SCHEDULE", account_id=MORTGAGE_ACCOUNT
        )
        check_delinquency_schedules = get_processed_scheduled_events(
            res, "CHECK_DELINQUENCY", account_id=MORTGAGE_ACCOUNT
        )

        self.assertEqual("2020-02-20T00:01:00Z", check_repayment_schedules[0])
        self.assertEqual("2020-03-20T00:01:00Z", check_repayment_schedules[1])
        self.assertEqual(1, len(check_delinquency_schedules))
        self.assertEqual("2020-03-25T00:00:02Z", check_delinquency_schedules[0])
        self.assertEqual(0, len(workflow_delinquent))

        balances = get_balances(res)
        self.check_balances(expected_balances=expected_balances, actual_balances=balances)


def _set_up_deposit_events(
    num_payments,
    repayment_amount,
    repayment_day,
    repayment_hour,
    start_year,
    start_month,
):
    events = []
    for i in range(num_payments):
        month = (i + start_month - 1) % 12 + 1
        year = start_year + int((i + start_month + 1 - month) / 12)

        event_date = datetime(
            year=year,
            month=month,
            day=repayment_day,
            hour=repayment_hour,
            tzinfo=timezone.utc,
        )
        events.append(
            create_inbound_hard_settlement_instruction(
                target_account_id=MORTGAGE_ACCOUNT,
                amount=repayment_amount,
                event_datetime=event_date,
                internal_account_id=DEPOSIT_ACCOUNT,
            )
        )

    return events


# Helper debug functions for printing out balances
def _debug_print_repayment_day_balances(balances):
    repayment_day_dimensions = [
        PRINCIPAL_DIMENSION,
        INTEREST_DUE_DIMENSION,
        PRINCIPAL_DUE_DIMENSION,
        EMI_ADDRESS_DIMENSION,
        OVERPAYMENT_DIMENSION,
    ]
    for value_datetime, balance_ts in balances[MORTGAGE_ACCOUNT]:
        if (
            value_datetime.hour == 0
            and value_datetime.minute == 1
            and value_datetime.microsecond == 2
        ):
            for dimension, balance in balance_ts.items():
                if dimension in repayment_day_dimensions:
                    print(f"{value_datetime} - {dimension[0]}: {balance.net}")


def _debug_print_accrue_interest_balances(balances, accrual_year, accrual_months):
    prev_accrued_interest = Decimal(0)
    for value_datetime, balance_ts in balances[MORTGAGE_ACCOUNT]:
        if (
            value_datetime.year == accrual_year
            and value_datetime.month in accrual_months
            and value_datetime.second == 1
        ):
            for dimension, balance in balance_ts.items():
                if dimension == ACCRUED_INTEREST_DIMENSION or dimension == PENALTIES_DIMENSION:
                    daily_accrued_interest = balance.net - prev_accrued_interest
                    prev_accrued_interest = balance.net
                    print(
                        f"{value_datetime} - {dimension[0]}: {balance.net} |"
                        f" increase: {daily_accrued_interest}"
                    )
