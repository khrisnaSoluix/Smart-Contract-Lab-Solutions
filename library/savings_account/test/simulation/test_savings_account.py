# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.savings_account.contracts.template import savings_account
from library.savings_account.test import accounts, dimensions, files, parameters
from library.savings_account.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.errors import generic_error
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_settlement_event,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundAuthorisation,
)

DORMANCY_FLAG = parameters.DORMANCY_FLAG
PAYMENT_ATM_INSTRUCTION_DETAILS = {"TRANSACTION_TYPE": "ATM"}

default_template_params: dict[str, str] = {
    **parameters.default_template,
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
}
template_parameters_annual_interest = {
    **default_template_params,
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "annually",
}
template_parameters_partial_inactivity_fee = {
    **template_parameters_annual_interest,
    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
    savings_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0",
}
template_parameters_partial_minimum_balance_fee = {
    **template_parameters_annual_interest,
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
    savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",
    savings_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0",
}
default_instance_params: dict[str, str] = {
    **parameters.default_instance,
    savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "1",
}
default_simulation_start_date = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))
maximum_daily_withdrawal_by_txn_type = savings_account.maximum_daily_withdrawal_by_transaction_type


class SavingsAccountBaseTest(SimulationTestCase):
    account_id_base = accounts.SAVINGS_ACCOUNT
    contract_filepaths = [files.SAVINGS_ACCOUNT_CONTRACT]

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
            contract_content=self.smart_contract_path_to_content[self.contract_filepaths[0]],
            template_params=template_params or default_template_params.copy(),
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params.copy(),
                    account_id_base=self.account_id_base,
                )
            ],
        )

        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or default_internal_accounts,
            debug=debug,
        )


class SavingsAccountTest(SavingsAccountBaseTest):
    def test_account_activation_no_fees(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=1)
        template_params = {
            **default_template_params,
            savings_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {
                    "0.00": "0.01",
                    "1000.00": "-0.02",
                    "3000.00": "-0.035",
                }
            ),
        }

        sub_tests = [
            SubTest(
                description="Check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                    }
                },
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_dormancy_scenarios(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=5, seconds=1)
        template_params = {
            **template_parameters_annual_interest,
            savings_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {
                    "0.00": "0.01",
                }
            ),
        }
        instance_params = {
            **default_instance_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "5",
        }

        first_interest_application = datetime(
            year=2023, month=1, day=5, minute=1, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Postings accepted when dormancy flag off",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                    },
                },
            ),
            SubTest(
                description="Postings rejected when dormancy flag on",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=2, minutes=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=3),
                        account_id=self.account_id_base,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Account flagged 'Dormant' does "
                        "not accept external transactions.",
                    )
                ],
            ),
            SubTest(
                description="Inactivity fees applied when dormancy flag on",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("80"))],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Dormancy flag has expired and inactivity fee is not charged",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=5, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("80"))],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Will not apply minimum balance fee when dormancy flag is on",
                events=[
                    create_flag_event(
                        timestamp=start + relativedelta(months=6),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(years=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("20"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("80"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.64849"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Customer interest application with an annual interval",
                expected_balances_at_ts={
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.65069"),
                        ],
                        # This amount is based on the default amount through time.
                        # Daily interest accrued = 0.01/365 * DEFAULT
                        #
                        # Jan                DEFAULT 100 - daily accrual 0.00274
                        # Feb                DEFAULT 90 - daily accrual 0.00247
                        # Mar, Apr, May, Jun DEFAULT 80 - daily accrual 0.00219
                        # Jul                DEFAULT 70 - daily accrual 0.00192
                        # Aug                DEFAULT 60 - daily accrual 0.00164
                        # Sep                DEFAULT 50 - daily accrual 0.00137
                        # Oct                DEFAULT 40 - daily accrual 0.00110
                        # Nov                DEFAULT 30 - daily accrual 0.00082
                        # Dec                DEFAULT 20 - daily accrual 0.00055
                        # (0.00274 * 31) + (0.00247 * 28) + (0.00219 * (31+30+31+30))
                        #  + (0.00192 * 31) + (0.00164 * 31) + (0.00137 * 30)
                        #  + (0.00110 * 31) + (0.00082 * 30) + (0.00055 * (31+4)) = 0.65069
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.65069")
                        ],
                    },
                    first_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "20.65"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0.65")],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC12"])
    def test_application_of_inactivity_fee_for_non_existent_day(self):
        # AC010
        # When the application day is 29, 30, or 31, and this day is not present
        # in the current month, the application should happen on the last day of the month.
        start = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = start.replace(month=2, day=28, hour=23, minute=59)
        template_params = {
            **template_parameters_annual_interest,
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "23",
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "59",
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
        }

        instance_params = {
            **default_instance_params,
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Fund the account below the inactivity fee threshold",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("40"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fee is applied on the 28th of February",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=3),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=end + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("30"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id="APPLY_INACTIVITY_FEE",
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC05", "CPP-2031-AC06", "CPP-2031-AC08"])
    def test_application_of_inactivity_fee(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=1)

        first_inactivity_fee = datetime(year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))
        second_inactivity_fee = first_inactivity_fee + relativedelta(months=1)
        third_inactivity_fee = second_inactivity_fee + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("15"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fee applied with sufficient funds - month 1",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=5),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=5),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=second_inactivity_fee + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_inactivity_fee: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_inactivity_fee],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fee applied with insufficient funds - month 2",
                expected_balances_at_ts={
                    second_inactivity_fee: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_inactivity_fee],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fee not applied to active account - month 3",
                expected_balances_at_ts={
                    third_inactivity_fee: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[third_inactivity_fee],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=3,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters_annual_interest,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC04", "CPP-2031-AC09", "CPP-2031-AC10", "CPP-2031-AC11"])
    def test_inactivity_fee_with_partial_payment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, minutes=10)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=2,
            day=int(
                parameters.default_instance[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )
        expected_schedule_month_2 = expected_schedule_month_1 + relativedelta(months=1)

        sub_tests = [
            SubTest(
                description="Initial deposit of 15",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("15")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    # dormancy flag to expire just before account is re-funded
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=expected_schedule_month_2 + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on - month 1",
                expected_balances_at_ts={
                    # Inactivity fee applied: 10 (1 month)
                    expected_schedule_month_1: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_1,
                        ],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on with insufficient "
                "funds - month 2",
                expected_balances_at_ts={
                    # Inactivity fee applied: 20 (2 months)
                    expected_schedule_month_2: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("5")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("15"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_2,
                        ],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=2,
                    ),
                ],
            ),
            SubTest(
                description="Partial fee deducted when account is funded partially ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=expected_schedule_month_2 + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    expected_schedule_month_2
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("2")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("18"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Partial Fee cleared when account is funded sufficiently",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=expected_schedule_month_2 + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    expected_schedule_month_2
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("13")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters_partial_inactivity_fee,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC13"])
    def test_outstanding_inactivity_fee_prevents_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, minutes=10)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=2,
            day=int(
                parameters.default_instance[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Initial deposit of 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    # dormancy flag to expire just before account is re-funded
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=expected_schedule_month_1 + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Verify outstanding inactivity fee fee prevents closure",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end, account_id=accounts.SAVINGS_ACCOUNT
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters_partial_inactivity_fee,
        )
        self.run_test_scenario(
            test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    def test_dormant_account_reactivation(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=5, seconds=1)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fees charged after dormant account reactivation",
                events=[
                    # account flagged as dormant
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    # account is going to reactivate when flag expires
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=2, minutes=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    # credit savings account after reactivation
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(months=2, minutes=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    # debit savings account after reactivation
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(months=2, minutes=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    # check balances before monthly schedule and after flag expires
                    # 20 is charged from savings account related of two inactivity months
                    + relativedelta(months=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("30"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                    start
                    # check savings account one month after reactivation
                    # 45 is charged from savings account related to fees
                    + relativedelta(months=3, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("10"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, minutes=1, seconds=1)
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.32877")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.32877")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                },
            ),
            SubTest(
                description="Corresponding interest rate when balance moves",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5500",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                    # 0.32877 + 0.32877 = 0.65754
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.65754")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.65754")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.65754")
                        ],
                    },
                    # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365))
                    # + (5000 * (0.05/365)) + (500 * (0.06/365)) = 1.09589
                    # 0.65754 + 1.09589 = 1.75343
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-1.75343")
                        ],
                    },
                },
            ),
            SubTest(
                description="No interest accrued for a 0 GBP or negative account balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10500",
                        event_datetime=start + relativedelta(days=3, seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-1.75343")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Apply accrued interest after 1 month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "1.75"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "1.75")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_interest_application_annually(self):
        start = datetime(year=2022, month=1, day=15, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(years=1, days=5, minutes=1, seconds=1)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
        }
        instance_params = {
            **default_instance_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "5",
        }

        first_interest_application = datetime(
            year=2023, month=1, day=5, minute=1, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Check daily interest calculation before application",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "116.71335"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-116.71335")
                        ],
                    },
                },
            ),
            SubTest(
                description="Customer interest application with an annual interval",
                expected_balances_at_ts={
                    first_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5116.71"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "116.71")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_application_annually_on_leap_year(self):
        start = datetime(year=2018, month=2, day=28, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(years=3, days=1, minutes=1, seconds=1)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {"0.00": "0.01"}
            ),
        }
        instance_params = {
            **default_instance_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "29",
        }

        first_interest_application = datetime(
            year=2019, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC")
        )
        second_interest_application = datetime(
            year=2020, month=2, day=29, minute=1, tzinfo=ZoneInfo("UTC")
        )
        third_interest_application = datetime(
            year=2021, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Check daily interest calculation before annual application",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # 5000 * (0.01/365) = 0.13699
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.13699"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.13699")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "50.00135"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-50.00135")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Interest application with an annual interval - non leap year - Y1",
                expected_balances_at_ts={
                    first_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5050"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "50")],
                    },
                },
            ),
            SubTest(
                description="Interest application with an annual interval - leap year - Y2",
                expected_balances_at_ts={
                    # 5050 * (0.01/365) = 0.13836 daily
                    second_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5050"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "50.63976"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-50.63976")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "50")],
                    },
                    second_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5100.64"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "100.64")],
                    },
                },
            ),
            SubTest(
                description="Interest application with an annual interval - non leap year - Y3",
                expected_balances_at_ts={
                    # 5100.64 * (0.01/365) = 0.13974 daily
                    third_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5100.64"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "51.0051"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-51.0051")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "100.64")],
                    },
                    third_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5151.65"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "151.65")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_application_monthly_positive(self):
        start = datetime(year=2022, month=1, day=15, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=2, minutes=1, seconds=1)
        template_params = {
            **default_template_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "22",
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "30",
        }
        instance_params = {
            **default_instance_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }

        first_interest_application = datetime(
            year=2022, month=1, day=28, hour=22, minute=30, tzinfo=ZoneInfo("UTC")
        )
        second_interest_application = datetime(
            year=2022, month=2, day=28, hour=22, minute=30, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Check daily interest calculation before monthly application",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "4.27401"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-4.27401")
                        ],
                    },
                },
            ),
            SubTest(
                description="First interest application with a monthly interval",
                expected_balances_at_ts={
                    first_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5004.27"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "4.27")],
                    },
                },
            ),
            SubTest(
                description="Second interest application with a monthly interval",
                expected_balances_at_ts={
                    second_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5004.27"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "10.20985"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-10.20985")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "4.27")],
                    },
                    second_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5014.48"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "14.48")],
                    },
                },
            ),
            SubTest(
                description="Account closure before interest application",
                events=[update_account_status_pending_closure(end, accounts.SAVINGS_ACCOUNT)],
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5014.48"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "4.96125"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-4.96125")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "14.48")],
                    },
                    end: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5014.48"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "14.48")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_interest_application_quarterly(self):
        start = datetime(year=2022, month=1, day=18, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=4, minutes=1, seconds=1)
        template_params = {
            **default_template_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "quarterly",
        }
        instance_params = {
            **default_instance_params,
            savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
        }

        first_interest_application = datetime(
            year=2022, month=4, day=28, minute=1, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Check daily interest calculation before quarterly application",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "32.877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-32.877")
                        ],
                    },
                },
            ),
            SubTest(
                description="Interest application with a quarterly interval",
                expected_balances_at_ts={
                    first_interest_application: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5032.88"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "32.88")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_negative_interest_accrual(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, minutes=1, seconds=1)
        template_params = {
            **default_template_params,
            savings_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {
                    "0.00": "-0.01",
                    "1000.00": "-0.02",
                    "3000.00": "-0.035",
                    "5000.00": "-0.05",
                    "10000.00": "-0.06",
                }
            ),
        }

        sub_tests = [
            SubTest(
                description="Check daily negative interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (-0.01/365)) + (2000 * (-0.02/365)) + (2000 * (-0.035/365)) = -0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-0.32877")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.32877")),
                        ],
                    },
                },
            ),
            # -0.32877 * 31 = -10.19187
            SubTest(
                description="Application of negative interest after 1 month",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "4989.81"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "10.19")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_accepted_denominations(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=7)

        sub_tests = [
            SubTest(
                description="Outbound authorization in unsupported denomination - rejected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="JPY",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP']",
                    )
                ],
            ),
            SubTest(
                description="Inbound authorization in unsupported denomination - rejected",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="PHP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP']",
                    )
                ],
            ),
            SubTest(
                description="Inbound hard settlement in default denomination - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1499",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1499")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement in primary denomination - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="199",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1300")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_postings_exceeding_balance_supported_denomination(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        template_params = {
            **default_template_params,
        }

        sub_tests = [
            SubTest(
                description="Outbound authorization exceeding balance - rejected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting amount of 10 GBP is exceeding available "
                        "balance of 0 GBP",
                    )
                ],
            ),
            SubTest(
                description="Inbound hard settlement - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement GBP accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement GBP denomination - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000.01",
                        event_datetime=start + relativedelta(seconds=3, microseconds=30),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=3, microseconds=30),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting amount of 1000.01 GBP is exceeding available "
                        "balance of 1000 GBP",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_deposit_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Deposit below minimum deposit amount - rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction amount 4 GBP is less than the minimum "
                        "deposit amount 5 GBP.",
                    )
                ],
            ),
            SubTest(
                description="Deposit funds - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1499",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1499")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_daily_deposit_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1, seconds=3)

        template_params = {
            **default_template_params,
            savings_account.maximum_daily_deposit_limit.PARAM_MAX_DAILY_DEPOSIT: "2000",
            savings_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0.01",
        }

        sub_tests = [
            # Daily deposit limit spent:
            # Before :    0
            # After  :  500
            SubTest(
                description="Client transaction 0 - Inbound Hard Settlement - Accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  500
            # After  :  1000
            SubTest(
                description="Client transaction 1 - Inbound Auth - Accepted",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=1, microseconds=10),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_1",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=10): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500"),
                            (dimensions.PENDING_IN, "500"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  1000
            # After  :  800
            SubTest(
                description="Client transaction 1 - Auth Adjustment -200 - Accepted",
                events=[
                    create_auth_adjustment_instruction(
                        amount="-200",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=11),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=11): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "500"),
                            (dimensions.PENDING_IN, "300"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  800
            # After  :  800
            SubTest(
                description="Client transaction 1 - Partial settlement 150 - Accepted",
                events=[
                    create_settlement_event(
                        amount="150.00",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=25),
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=25): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "650"),
                            (dimensions.PENDING_IN, "150"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  800
            # After  :  850
            SubTest(
                description="Client transaction 1 - Final settlement 200 - Accepted",
                events=[
                    create_settlement_event(
                        amount="200.00",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=35),
                        final=True,
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=35): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "850"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  850
            # After  :  850 due to the rejection of the 1150.01 hard settlement
            SubTest(
                description="Client transaction 2 - Inbound Hard Settle 1150.01 GBP - rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1150.01",
                        client_transaction_id="CT_ID_2",
                        event_datetime=start + relativedelta(seconds=2, microseconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "850"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2, microseconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily deposit limit"
                        " of 2000 GBP to be exceeded.",
                    )
                ],
            ),
            # Daily deposit limit spent:
            # Before :  850
            # After  : 2000
            SubTest(
                description="Client transaction 3 - Inbound Hard Settle 1150 GBP - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1150",
                        client_transaction_id="CT_ID_3",
                        event_datetime=start + relativedelta(seconds=3, microseconds=20),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3, microseconds=20): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
            ),
            # Daily deposit limit spent:
            # Before :  2000
            # After  :  2000 due to the rejection of the 0.01 Auth
            SubTest(
                description="Client transaction 4 - Inbound Auth 0.01 GBP before EOD - rejected",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="5.01",
                        client_transaction_id="CT_ID_4",
                        event_datetime=start
                        + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily deposit limit"
                        " of 2000 GBP to be exceeded.",
                    )
                ],
            ),
            # Daily deposit limit spent:
            # Before :     0 due to start of new day
            # After  :  0.01
            SubTest(
                description="Client transaction 5 - Inbound Auth 0.01 GBP after EOD - accepted",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="0.01",
                        client_transaction_id="CT_ID_5",
                        event_datetime=start + relativedelta(days=1, microseconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.PENDING_IN, "0.01"),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_withdrawal_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
            ),
            SubTest(
                description="Withdrawal below minimum withdrawal amount - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction amount 4 GBP is less than the minimum "
                        "withdrawal amount 5 GBP.",
                    )
                ],
            ),
            SubTest(
                description="Withdrawal above minimum withdrawal amount - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "1100")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_daily_withdrawal_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1, seconds=5)
        template_params = {
            **default_template_params,
            savings_account.maximum_daily_withdrawal.PARAM_MAX_DAILY_WITHDRAWAL: "2000",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :    0
            # After  :  500
            SubTest(
                description="Client transaction 1 - Outbound Auth - Accepted",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=1, microseconds=10),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_1",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=10): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.PENDING_OUT, "-500"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :  500
            # After  :  300
            SubTest(
                description="Client transaction 1 - Auth Adjustment -200 - Accepted",
                events=[
                    create_auth_adjustment_instruction(
                        amount="-200",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=11),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=11): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.PENDING_OUT, "-300"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :  300
            # After  :  300
            SubTest(
                description="Client transaction 1 - Partial settlement 150 - Accepted",
                events=[
                    create_settlement_event(
                        amount="150.00",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=25),
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=25): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "4850"),
                            (dimensions.PENDING_OUT, "-150"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :  300
            # After  :  350
            SubTest(
                description="Client transaction 1 - Final settlement 200 - Accepted",
                events=[
                    create_settlement_event(
                        amount="200.00",
                        client_transaction_id="CT_ID_1",
                        event_datetime=start + relativedelta(seconds=1, microseconds=35),
                        final=True,
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=35): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "4650"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :  350
            # After  : 1750
            SubTest(
                description="Client transaction 2 - Outbound Hard settlement - Accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1400",
                        event_datetime=start + relativedelta(hours=15, seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_2",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=15, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3250"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before : 1750
            # After  : 1750 - due to rejection of 250.01 Auth
            # Note: The rejection causes both posting instructions to be rejected
            SubTest(
                description="PIB with transactions 3 and 4, Outbound Auth over limit - Rejected",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundAuthorisation(
                                amount="250.01",
                                target_account_id=accounts.SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                            InboundHardSettlement(
                                amount="75",
                                target_account_id=accounts.SAVINGS_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                        ],
                        event_datetime=start + relativedelta(hours=23, seconds=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3250"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily withdrawal "
                        "limit of 2000 GBP to be exceeded.",
                    )
                ],
            ),
            # Spent Daily Withdrawal limit:
            # Before : 1750
            # After  : 2000
            SubTest(
                description="Client transaction 5 - Outbound Auth at exactly the limit - accepted",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="250",
                        event_datetime=start + relativedelta(hours=23, seconds=20),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_5",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, seconds=20): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3250"),
                            (dimensions.PENDING_OUT, "-250"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before : 2000
            # After  : 2000
            SubTest(
                description="Client transaction 5 - Outbound settlement 245 - Accepted",
                events=[
                    create_settlement_event(
                        amount="245",
                        client_transaction_id="CT_ID_5",
                        event_datetime=start + relativedelta(hours=23, seconds=25, microseconds=2),
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, seconds=25, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3005"),
                            (dimensions.PENDING_OUT, "-5"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before : 2000
            # After  : 2000 - Due to rejection of 15 Auth
            SubTest(
                description="Client transaction 5 - Outbound Auth 15 GBP - rejected",
                events=[
                    create_settlement_event(
                        amount="15",
                        client_transaction_id="CT_ID_5",
                        event_datetime=start
                        + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "3005"),
                            (dimensions.PENDING_OUT, "-5"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily withdrawal "
                        "limit of 2000 GBP to be exceeded.",
                    )
                ],
            ),
            # Spent Daily Withdrawal limit:
            # Before :     0 - Reset due to day change
            # After  :    10 - Settlement of 15 when the remaining Auth was just 5
            SubTest(
                description="Client transaction 5 - Outbound Auth 15 GBP next day - accepted",
                events=[
                    create_settlement_event(
                        amount="15",
                        client_transaction_id="CT_ID_5",
                        event_datetime=start + relativedelta(days=1, seconds=1, microseconds=2),
                        require_pre_posting_hook_execution=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=1, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "2990"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
            # Spent Daily Withdrawal limit:
            # Before :    10
            # After  :    10 - due to rejection of hard settlement 1990.01
            SubTest(
                description="Client transaction 6 - Outbound Hard Settle 1990.01 GBP - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1990.01",
                        client_transaction_id="CT_ID_6",
                        event_datetime=start + relativedelta(days=1, seconds=3, microseconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=3, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "2990"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=1, seconds=3, microseconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily withdrawal "
                        "limit of 2000 GBP to be exceeded.",
                    )
                ],
            ),
            # Spent Daily Withdrawal limit:
            # Before :   10
            # After  : 2000
            SubTest(
                description="Client transaction 7 - Outbound Hard Settle 1990 GBP - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1990",
                        client_transaction_id="CT_ID_7",
                        event_datetime=start + relativedelta(days=1, seconds=4, microseconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=4, microseconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "1000"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_maximum_balance_limit(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=3)

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "30000")],
                    },
                },
            ),
            SubTest(
                description="Reject inbound over balance limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000.01",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "30000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would exceed maximum permitted balance 50000"
                        " GBP.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_specific_day_and_time(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        schedule_date = datetime(year=2022, month=2, day=15, tzinfo=ZoneInfo("UTC"))
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "6",
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "30",
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "45",
        }
        instance_params = {
            **default_instance_params,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "15",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="LOWER_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="LOWER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="70",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("70"))],
                    },
                },
            ),
            SubTest(
                description="Check account at defined fee schedule",
                expected_balances_at_ts={
                    schedule_date
                    + relativedelta(hours=6, minutes=30, second=45): {
                        # Minimum balance Fee is debited from savings account and
                        # credited into minimum balance fee income account
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "50.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[schedule_date + relativedelta(hours=6, minutes=30, second=45)],
                        event_id="APPLY_MINIMUM_BALANCE_FEE",
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_mean_balance_below_threshold(self):
        start = default_simulation_start_date
        last_day = datetime(year=2022, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        end = last_day + relativedelta(hours=1)
        before_last_day = datetime(year=2022, month=1, day=31, tzinfo=ZoneInfo("UTC"))

        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Create Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="LOWER_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="LOWER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Debit account the day before last day of period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=before_last_day,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Debit the last day of period, mean balance is lower than threshold
                expected_balances_at_ts={
                    before_last_day
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "50")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Credit money the last day of period ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=last_day,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Monthly mean balance is lower than threshold ((100 * 30) + 50)/31 = 98.38
                expected_balances_at_ts={
                    last_day: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "100")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        # Fees is charged because monthly balance is lower than threshold
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "80.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minutes=1)],
                        event_id="APPLY_INACTIVITY_FEE",
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC13"])
    def test_minimum_balance_fee_not_charged_when_balance_equal_threshold(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="LOWER_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="LOWER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        # Minimum balance Fee is not charged
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "100.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minutes=1)],
                        event_id="APPLY_INACTIVITY_FEE",
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_fee_middle_tier_charged(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1, hours=2)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to MIDDLE TIER so if the monthly average balance
                    # is lower than 75 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="MIDDLE_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="MIDDLE_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("150"))],
                    },
                },
            ),
            SubTest(
                description="Spend money",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="75.01",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Monthly average balance is lower than 75 so
                # the minimum balance fee is going to be charged in the next fee schedule
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "74.99")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        # Minimum balance Fee is debited from savings account and
                        # credited into minimum balance fee income account
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "54.99")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC09"])
    def test_minimum_balance_limit_fee_with_insufficient_funds_makes_account_balance_negative(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=2)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to UPPER TIER so if the monthly average balance
                    # is lower than 25 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="UPPER_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="UPPER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    # Savings balance is lower than 25 so the fee is going to apply
                    + relativedelta(hours=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("15"))],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        # Minimum balance Fee is debited from savings account
                        # savings account is insufficient, the balance becomes negative
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "-5")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_defaults_to_lower_no_tier_defined(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # No tier is defined, so it will default to LOWER_TIER
                    create_inbound_hard_settlement_instruction(
                        amount="80",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "80")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        # Minimum balance Fee is debited from savings account and
                        # credited into minimum balance fee income account
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "60.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC14"])
    def test_minimum_balance_limit_fee_ignores_current_day_in_average(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=4)
        template_params = {
            # Set to annual interest to not interfere with the test
            **template_parameters_annual_interest,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to UPPER TIER so if the monthly balance
                    # is lower than 25 the minimum balance fee is charged
                    create_flag_definition_event(timestamp=start, flag_definition_id="UPPER_TIER"),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="UPPER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="25.01",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "25.01")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Outbound is on day of fee schedule so should not be included "
                "in the average - no fee applied",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="25",
                        event_datetime=start + relativedelta(months=1, seconds=30),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=35): {
                        # Check balance after outbound hard settlement
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
                    },
                    start
                    + relativedelta(months=1, minutes=2): {
                        # Check balance after minimum monthly balance fee schedule
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC10", "CPP-1922-AC12"])
    def test_minimum_balance_limit_fee_partial_fee_collection(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=1)

        # Schedule run times
        first_schedule_run = datetime(year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, Decimal("10"))],
                    },
                },
            ),
            SubTest(
                description="Fee charged with insufficient funds is partially applied",
                expected_balances_at_ts={
                    first_schedule_run: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "10"),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "10"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account partially to check some outstanding fee is collected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=first_schedule_run + relativedelta(minutes=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "7"),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "13"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account fully to check outstanding fee is collected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=first_schedule_run + relativedelta(minutes=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "13"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "0"),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters_partial_minimum_balance_fee,
        )
        self.run_test_scenario(test_scenario)

    def test_partial_payment_fee_hierarchy(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        template_params = {
            **template_parameters_partial_inactivity_fee,
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",  # noqa: E501
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "10",
            savings_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "0",
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE: "15",
            savings_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "1",
        }

        minimum_balance_schedule_datetime = datetime(
            year=2022, month=2, day=1, minute=0, tzinfo=ZoneInfo("UTC")
        )
        inactivity_fee_schedule_datetime = datetime(
            year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )

        instance_params = {
            **parameters.default_instance,
        }

        sub_tests = [
            SubTest(
                description="Fund account without sufficient balance to collect fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Partially apply minimum balance fee.",
                expected_balances_at_ts={
                    minimum_balance_schedule_datetime: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("7"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[minimum_balance_schedule_datetime],
                        event_id=savings_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,  # noqa: E501
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Apply dormancy flag and partially apply inactivity fee.",
                events=[
                    create_flag_definition_event(
                        timestamp=inactivity_fee_schedule_datetime - relativedelta(seconds=1),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=inactivity_fee_schedule_datetime - relativedelta(seconds=1),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=inactivity_fee_schedule_datetime
                        + relativedelta(seconds=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("7"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("15"),
                            ),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[inactivity_fee_schedule_datetime],
                        event_id=savings_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Fund account to pay outstanding minimum balance fee fee and partially "
                "pay outstanding inactivity fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=inactivity_fee_schedule_datetime + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("12"),
                            ),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Fund account to pay outstanding inactivity fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=inactivity_fee_schedule_datetime + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("15"))
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC18"])
    def test_outstanding_minimum_balance_fee_prevents_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=1)

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Verify outstanding minimum balance fee prevents closure",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end, account_id=accounts.SAVINGS_ACCOUNT
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters_partial_minimum_balance_fee,
        )
        self.run_test_scenario(
            test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    def test_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1, hours=23, minutes=59, seconds=59)
        template_params = {
            **default_template_params,
        }

        first_interest_accrual = start + relativedelta(
            days=1,
            hour=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Fund the account: EOD balance 5000 GBP",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start,
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(microseconds=10): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Check balances after interest accrual",
                # Accrued interest = (1000 * (0.01/365))
                #                  + (2000 * (0.02/365))
                #                  + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    first_interest_accrual
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Clear off account balance to close the account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=end - relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    update_account_status_pending_closure(end, accounts.SAVINGS_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    end: {
                        accounts.SAVINGS_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_excess_withdrawal_fee(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, seconds=10)

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Withdrawals below the Number of Withdrawals Permitted per Month",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=7),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=7): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4940")],
                        accounts.EXCESS_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Withdrawals over the Number of Withdrawals Permitted per Month",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=start + relativedelta(seconds=8),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=start + relativedelta(seconds=9),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=11),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Only 3 excess withdrawal fees will be applied 3 * 2.50 = 7.50
                # Because the other operation is not a ATM withdrawal
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=12): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4792.50")],
                        accounts.EXCESS_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "7.50")],
                    },
                },
            ),
            SubTest(
                description="Once calendar month changes the previous transactions are not counted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start + relativedelta(months=1, seconds=5),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start + relativedelta(months=1, seconds=6),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=7): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4292.50")],
                        accounts.EXCESS_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "7.50")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_withdrawal_limit_by_transaction_type(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=3, minutes=1)
        instance_params = {
            **default_instance_params,
            maximum_daily_withdrawal_by_txn_type.PARAM_DAILY_WITHDRAWAL_LIMIT_BY_TRANSACTION: (
                dumps({"ATM": "1000"})
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Exceeds daily ATM withdrawal limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM "
                        "withdrawal limit of 1000 GBP to be exceeded.",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Within the daily ATM withdrawal limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4500")],
                    },
                    start
                    + relativedelta(seconds=4): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4000")],
                    },
                },
            ),
            SubTest(
                description="No more ATM withdrawal for the day",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "4000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=5),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM "
                        "withdrawal limit of 1000 GBP to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="Daily ATM withdrawal limit not defined at instance level - accepted",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=1),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps({"XXX": "0"}),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=start + relativedelta(days=1, seconds=1),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "2500")],
                    },
                },
            ),
            SubTest(
                description="Daily ATM withdrawal limit not defined at instance level - rejected",
                events=[
                    # minimum withdrawal is 5
                    create_outbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(days=1, seconds=3),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=3): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "2500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=1, seconds=3),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM "
                        "withdrawal limit of 1500 GBP to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="Fund Account and set upper tier",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(days=1, seconds=4),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=1, seconds=4),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps({"ATM": "6000"}),
                    ),
                    # Tier set to UPPER TIER so if the daily withdrawal amount
                    # is above 5000 the rejection is raised
                    create_flag_definition_event(
                        timestamp=start + relativedelta(days=1, seconds=5),
                        flag_definition_id="UPPER_TIER",
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(days=1, seconds=5),
                        flag_definition_id="UPPER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.SAVINGS_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, seconds=1): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "7500")],
                    },
                },
            ),
            SubTest(
                description="Instance daily withdrawal ATM limit above tiered limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + relativedelta(days=2, seconds=2),
                        target_account_id=accounts.SAVINGS_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "7500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=2, seconds=2),
                        account_id=accounts.SAVINGS_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM "
                        "withdrawal limit of 5000 GBP to be exceeded.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_account_conversion_daily_and_monthly_schedules_are_preserved(self):
        """
        Test ~ a month's worth of schedules running as expected after two account conversions:
        - the first on account opening day
        - the second at mid month
        """
        # relativedelta here is to avoid seeing first application happening on account opening date
        start = default_simulation_start_date + relativedelta(hours=2)
        end = start + relativedelta(months=1)

        # Define the conversion timings
        conversion_1 = start + relativedelta(hours=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.SAVINGS_ACCOUNT_CONTRACT],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=default_template_params,
            account_configs=[],
        )
        conversion_2 = conversion_1 + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.SAVINGS_ACCOUNT_CONTRACT],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=default_template_params,
            account_configs=[],
        )

        # Get interest accrual schedules
        run_times_accrue_interest = []
        accrue_interest_date = start + relativedelta(days=1)
        accrue_interest_date = accrue_interest_date.replace(
            hour=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                default_template_params[
                    savings_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )
        run_times_accrue_interest.append(accrue_interest_date)
        for _ in range(30):
            accrue_interest_date = accrue_interest_date + relativedelta(days=1)
            run_times_accrue_interest.append(accrue_interest_date)

        first_application_date = (start + relativedelta(months=1)).replace(
            day=int(
                default_instance_params[
                    savings_account.interest_application.PARAM_INTEREST_APPLICATION_DAY
                ]
            ),
            hour=int(
                default_template_params[
                    savings_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                default_template_params[
                    savings_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                default_template_params[
                    savings_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversions and Check Schedules at EoM",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.SAVINGS_ACCOUNT,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.SAVINGS_ACCOUNT,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_interest,
                        event_id="ACCRUE_INTEREST",
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=31,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            first_application_date,
                        ],
                        event_id="APPLY_INTEREST",
                        account_id=accounts.SAVINGS_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )
