# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from json import dumps

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_template_parameter_change_event,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
)

from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    ContractModuleConfig,
    AccountConfig,
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


class MortgageRepaymentHolidayTest(SimulationTestCase):
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

    def test_monthly_interest_accrual_fixed(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=9, day=21, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + relativedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(
            _set_up_deposit_events(1, str(Decimal("3140.01")), 20, payment_hour, start_year, 2)
        )
        events.extend(
            _set_up_deposit_events(2, str(Decimal("2910.69")), 20, payment_hour, start_year, 3)
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_2_instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
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

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_interest_accrual_fixed"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
                (PRINCIPAL_DIMENSION, values[2]),
                (CAPITALISED_INTEREST_DIMENSION, values[3]),
                (ACCRUED_INTEREST_DIMENSION, values[4]),
                (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, values[5]),
                (EMI_ADDRESS_DIMENSION, values[6]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_monthly_interest_accrual_variable(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=6, day=13, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=6, day=12, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=12, day=12, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + relativedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=mortgage_1_instance_params,
            template_params=mortgage_1_template_params,
            contract_file_path=self.contract_filepath,
        )

        for event in self.input_data["repayment_holiday_test_monthly_interest_accrual_variable"]:
            if event[0] == "variable_rate_change":
                # Rate changes occuring just after repayment
                events.append(
                    create_template_parameter_change_event(
                        timestamp=datetime(
                            year=int(event[1]),
                            month=int(event[2]),
                            day=int(event[3]),
                            tzinfo=timezone.utc,
                        ),
                        smart_contract_version_id=main_account["smart_contract_version_id"],
                        variable_interest_rate=str(event[4]),
                    )
                )
            else:
                # Repayments occur on repayment day
                events.extend(
                    _set_up_deposit_events(
                        int(event[1]),
                        event[2],
                        12,
                        payment_hour,
                        int(event[3]),
                        int(event[4]),
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

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=12,
            hour=0,
            minute=1,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["repayment_holiday_test_monthly_interest_accrual_variable"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DUE_DIMENSION, values[0]),
                (INTEREST_DUE_DIMENSION, values[1]),
                (CAPITALISED_INTEREST_DIMENSION, values[2]),
                (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, values[3]),
                (EMI_ADDRESS_DIMENSION, values[4]),
            ]

        self.check_balances(expected_balances=expected_balances, actual_balances=balances)

    def test_1_year_fixed_with_full_repayment(self):
        start = default_simulation_start_date
        end = datetime(year=2021, month=1, day=21, minute=1, tzinfo=timezone.utc)

        instance_params = mortgage_2_instance_params.copy()
        instance_params["total_term"] = "12"
        instance_params["principal"] = "18000"
        main_account = account_to_simulate(
            timestamp=start,
            account_id=MORTGAGE_ACCOUNT,
            instance_params=instance_params,
            template_params=mortgage_2_template_params,
            contract_file_path=self.contract_filepath,
        )

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=7, day=20, hour=0, minute=2, tzinfo=timezone.utc
        )

        events = [_set_up_repayment_holiday_flag(start)]

        events.append(
            create_flag_event(
                timestamp=start + timedelta(seconds=2),
                flag_definition_id="REPAYMENT_HOLIDAY",
                account_id=MORTGAGE_ACCOUNT,
                effective_timestamp=payment_holiday_start,
                expiry_timestamp=payment_holiday_end,
            )
        )

        events.extend(_set_up_deposit_events(1, "1539.07", 20, payment_hour, 2020, 2))
        events.extend(_set_up_deposit_events(2, "1525.31", 20, payment_hour, 2020, 3))

        # after repayment holiday
        events.extend(_set_up_deposit_events(5, "2296.69", 20, payment_hour, 2020, 8))

        # Final repayment
        events.extend(_set_up_deposit_events(1, "2297.9", 20, payment_hour, 2021, 1))

        res = self.client.simulate_smart_contract(
            account_creation_events=[main_account],
            contract_config=self._get_contract_config(
                contract_version_id=main_account["smart_contract_version_id"],
                instance_params=instance_params,
                template_params=mortgage_2_template_params,
            ),
            internal_account_ids=default_internal_accounts,
            start_timestamp=start,
            end_timestamp=end,
            events=events,
        )

        repayment_date = datetime(
            year=start_year,
            month=2,
            day=20,
            hour=0,
            minute=2,
            second=0,
            microsecond=2,
            tzinfo=timezone.utc,
        )
        expected_balances = defaultdict(lambda: defaultdict(lambda: list))
        for i, values in enumerate(
            self.expected_output["repayment_holiday_1year_fixed_with_full_repayment"]
        ):
            expected_balances[MORTGAGE_ACCOUNT][repayment_date + relativedelta(months=i)] = [
                (PRINCIPAL_DIMENSION, values[0]),
                (PRINCIPAL_DUE_DIMENSION, values[1]),
                (INTEREST_DUE_DIMENSION, values[2]),
                (CAPITALISED_INTEREST_DIMENSION, values[3]),
                (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, values[4]),
            ]
        expected_balances[MORTGAGE_ACCOUNT][end] = [
            (PRINCIPAL_DIMENSION, "-104.65"),
            (PRINCIPAL_DUE_DIMENSION, "0"),
            (INTEREST_DUE_DIMENSION, "0"),
            (CAPITALISED_INTEREST_DIMENSION, "0"),
            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "104.65"),
        ]

        self.check_balances(expected_balances=expected_balances, actual_balances=get_balances(res))

    def test_daily_penalty_accrual_and_blocking(self):
        start = default_simulation_start_date
        end = datetime(year=2020, month=8, day=21, minute=1, tzinfo=timezone.utc)

        payment_holiday_start = datetime(
            year=2020, month=4, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )
        payment_holiday_end = datetime(
            year=2020, month=6, day=20, hour=20, minute=2, tzinfo=timezone.utc
        )

        first_repayment_date = datetime(year=2020, month=2, day=20, minute=2, tzinfo=timezone.utc)
        before_first_repayment_date = first_repayment_date - relativedelta(hours=1)
        after_first_repayment_due = first_repayment_date + relativedelta(hours=1)

        sub_tests = [
            SubTest(
                description="create flag definition and flag event",
                events=[
                    _set_up_repayment_holiday_flag(start),
                    create_flag_event(
                        timestamp=start + timedelta(seconds=2),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=MORTGAGE_ACCOUNT,
                        effective_timestamp=payment_holiday_start,
                        expiry_timestamp=payment_holiday_end,
                    ),
                ],
            ),
            SubTest(
                description="first EMI due",
                expected_balances_at_ts={
                    first_repayment_date: {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2120.83"),
                            (INTEREST_DUE_DIMENSION, "1019.18"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "0"),
                            (INTEREST_OVERDUE_DIMENSION, "0"),
                            (CAPITALISED_INTEREST_DIMENSION, "0"),
                        ]
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=before_first_repayment_date,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="120",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_first_repayment_due,
                        account_id=MORTGAGE_ACCOUNT,
                        name="remaining_term",
                        value="119",
                    ),
                ],
            ),
            SubTest(
                description="first EMI overdue, second EMI due, fee applied",
                expected_balances_at_ts={
                    datetime(year=2020, month=3, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2177.01"),
                            (INTEREST_DUE_DIMENSION, "733.68"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "2120.83"),
                            (INTEREST_OVERDUE_DIMENSION, "1019.18"),
                            (CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PENALTIES_DIMENSION, "15"),
                        ]
                    }
                },
            ),
            SubTest(
                description="second EMI overdue, third EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2132.14"),
                            (INTEREST_DUE_DIMENSION, "778.55"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "4297.84"),
                            (INTEREST_OVERDUE_DIMENSION, "1752.86"),
                            (CAPITALISED_INTEREST_DIMENSION, "0"),
                            # 15 + (2120.83+1019.18)*(0.24+0.031)/365 * 31 + 15 = 102.27
                            (PENALTIES_DIMENSION, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday starts, third EMI remains due, no overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=4, day=30, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2132.14"),
                            (INTEREST_DUE_DIMENSION, "778.55"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "4297.84"),
                            (INTEREST_OVERDUE_DIMENSION, "1752.86"),
                            (PRINCIPAL_DIMENSION, "293570.02"),
                            # 293570.02 * 0.031/365 * 10 = 249.3
                            (CAPITALISED_INTEREST_DIMENSION, "249.3"),
                            (PENALTIES_DIMENSION, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, third EMI remains due",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2132.14"),
                            (INTEREST_DUE_DIMENSION, "778.55"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "4297.84"),
                            (INTEREST_OVERDUE_DIMENSION, "1752.86"),
                            (PRINCIPAL_DIMENSION, "293570.02"),
                            # 249.3 + 293570.02 * 0.031/365 * 20 = 747.9
                            (CAPITALISED_INTEREST_DIMENSION, "747.9"),
                            (PENALTIES_DIMENSION, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further overdue from check overdue",
                expected_balances_at_ts={
                    datetime(year=2020, month=5, day=30, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2132.14"),
                            (INTEREST_DUE_DIMENSION, "778.55"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "4297.84"),
                            (INTEREST_OVERDUE_DIMENSION, "1752.86"),
                            (PRINCIPAL_DIMENSION, "293570.02"),
                            # 747.9 + 293570.02 * 0.031/365 * 10 = 997.2
                            (CAPITALISED_INTEREST_DIMENSION, "997.2"),
                            (PENALTIES_DIMENSION, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ongoing, no further due",
                expected_balances_at_ts={
                    datetime(year=2020, month=6, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2132.14"),
                            (INTEREST_DUE_DIMENSION, "778.55"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "0"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "4297.84"),
                            (INTEREST_OVERDUE_DIMENSION, "1752.86"),
                            (PRINCIPAL_DIMENSION, "293570.02"),
                            # 997.2+ 293570.02 * 0.031/365 * 21 = 1520.73
                            (CAPITALISED_INTEREST_DIMENSION, "1520.73"),
                            (PENALTIES_DIMENSION, "102.23"),
                        ]
                    }
                },
            ),
            SubTest(
                description="repayment holiday ended, third EMI overdue, fourth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=7, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            # EMI increased from 2910.69 to 2969.3
                            # due to capitalised interest added to principal
                            (PRINCIPAL_DUE_DIMENSION, "2217.42"),
                            (INTEREST_DUE_DIMENSION, "751.88"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "1520.73"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "6429.98"),
                            (INTEREST_OVERDUE_DIMENSION, "2531.41"),
                            (CAPITALISED_INTEREST_DIMENSION, "0"),
                            # 102.23 + 15 + (4297.84+1752.86)*(0.24+0.031)/365 * 30 = 252.01
                            (PENALTIES_DIMENSION, "251.93"),
                        ]
                    }
                },
            ),
            SubTest(
                description="fourth EMI overdue, fifth EMI due",
                expected_balances_at_ts={
                    datetime(year=2020, month=8, day=20, minute=2, tzinfo=timezone.utc): {
                        MORTGAGE_ACCOUNT: [
                            (PRINCIPAL_DUE_DIMENSION, "2198.2"),
                            (INTEREST_DUE_DIMENSION, "771.1"),
                            (PRINCIPAL_CAPITALISED_INTEREST_DIMENSION, "1520.73"),
                            (PRINCIPAL_OVERDUE_DIMENSION, "8647.4"),
                            (INTEREST_OVERDUE_DIMENSION, "3283.29"),
                            (CAPITALISED_INTEREST_DIMENSION, "0"),
                            # 251.93 + (8647.53+3283.29)*(0.24+0.031)/365*21 = 437.95
                            (PENALTIES_DIMENSION, "473.08"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=mortgage_2_template_params,
            instance_params=mortgage_2_instance_params,
            internal_accounts=default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)


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


def _set_up_repayment_holiday_flag(start):
    return create_flag_definition_event(timestamp=start, flag_definition_id="REPAYMENT_HOLIDAY")


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
                if dimension == ACCRUED_INTEREST_DIMENSION:
                    daily_accrued_interest = balance.net - prev_accrued_interest
                    prev_accrued_interest = balance.net
                    print(
                        f"{value_datetime} - {dimension[0]}: {balance.net} |"
                        f" increase: {daily_accrued_interest}"
                    )
