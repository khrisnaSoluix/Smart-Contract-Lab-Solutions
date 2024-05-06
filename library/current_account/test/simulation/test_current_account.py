# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.current_account.contracts.template import current_account
from library.current_account.test import accounts, dimensions, files, parameters
from library.current_account.test.parameters import TEST_DENOMINATION
from library.current_account.test.simulation.accounts import default_internal_accounts

# features
import library.features.v4.deposit.fees.maintenance_fees as maintenance_fees

# inception sdk
from inception_sdk.test_framework.common.utils import ac_coverage
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedDerivedParameter,
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
    OutboundHardSettlement,
)

DORMANCY_FLAG = parameters.DORMANCY_FLAG
PAYMENT_ATM_INSTRUCTION_DETAILS = {"TRANSACTION_TYPE": "ATM"}

default_simulation_start_date = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))


class CurrentAccountBaseTest(SimulationTestCase):
    account_id_base = accounts.CURRENT_ACCOUNT
    contract_filepaths = [files.CURRENT_ACCOUNT_CONTRACT]

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
            template_params=template_params or parameters.default_template.copy(),
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or parameters.default_instance.copy(),
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


class CurrentAccountTest(CurrentAccountBaseTest):
    def test_account_activation_no_fees(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=1)
        template_params = {
            **parameters.default_template,
            current_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
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
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.template_parameters_annual_interest,
            current_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {"0.00": "0.01"}
            ),
        }
        instance_params = {
            **parameters.default_instance,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "5",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
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
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
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
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("80"))],
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
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("80"))],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Will not apply yearly maintenance fees when dormancy flag on",
                events=[
                    create_flag_event(
                        timestamp=start + relativedelta(months=6),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(years=1, minutes=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("10"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("90"))
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "10"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.64957"),
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
                        # Jan                DEFAULT 10 - daily accrual 0.00027
                        # (0.00274 * 31) + (0.00247 * 28) + (0.00219 * (31+30+31+30))
                        #  + (0.00192 * 31) + (0.00164 * 31) + (0.00137 * 30)
                        #  + (0.00110 * 31) + (0.00082 * 30) + (0.00055 * 31) + (0.00027*4) =
                        # 0.64957
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.64957")
                        ],
                    },
                    first_interest_application: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "10.65"),
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
        # When Application day is 29, 30 or 31 and not exist in current month.
        # Application should happen on the last day of the month.
        start = datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end = start.replace(month=2, day=28, hour=23, minute=59)
        template_params = {
            **parameters.template_parameters_annual_interest,
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "23",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "59",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
        }

        instance_params = {
            **parameters.default_instance,
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Fund the account but its less than inactivity fee amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="7",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("7"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fee applied on end of Feb",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=3),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=end + relativedelta(seconds=1),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-3"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id="APPLY_INACTIVITY_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
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

    @ac_coverage(["CPP-2031-AC08"])
    def test_application_of_inactivity_fee(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=5, seconds=1)

        first_inactivity_fee = datetime(year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund the account but its less than inactivity fee amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="7",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("7"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fee applied overdrawing the account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=5),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=5),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=1, minutes=5),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-3"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_inactivity_fee],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=parameters.template_parameters_annual_interest,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC04", "CPP-2031-AC09", "CPP-2031-AC10", "CPP-2031-AC11"])
    def test_inactivity_fee_with_partial_payment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, minutes=10)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=2,
            day=int(
                parameters.default_instance[
                    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )
        expected_schedule_month_2 = expected_schedule_month_1 + relativedelta(months=1)
        expected_schedule_month_3 = expected_schedule_month_2 + relativedelta(months=1)
        template_params = {
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
                {"UPPER_TIER": "0", "MIDDLE_TIER": "0", "LOWER_TIER": "0"}
            ),
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 15",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
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
                        expiry_timestamp=start + relativedelta(months=3, minutes=7),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on - month 1",
                expected_balances_at_ts={
                    # Inactivity fee applied: 10 (1 month)
                    expected_schedule_month_1: {
                        accounts.CURRENT_ACCOUNT: [
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
                        event_id=current_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on uses overdraft limit "
                "- month 2",
                expected_balances_at_ts={
                    # Inactivity fee applied: 20 (2 months)
                    expected_schedule_month_2: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20.00"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_2,
                        ],
                        event_id=current_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on becomes pending when "
                "insufficient overdraft limit - month 3",
                expected_balances_at_ts={
                    # Inactivity fee applied: 30 (3 months)
                    # Insufficient overdraft to charge entire fee amount
                    expected_schedule_month_3: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("10")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_3,
                        ],
                        event_id=current_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=3,
                    ),
                ],
            ),
            SubTest(
                description="Partial fee deducted when account is funded partially ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(months=3, minutes=8),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, minutes=8): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("5")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Partial Fee cleared when account is funded sufficiently",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start + relativedelta(months=3, minutes=9),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, minutes=9): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("30"))
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.instance_parameters_small_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-2031-AC13"])
    def test_inactivity_fee_closure_with_outstanding_fees(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, seconds=2)

        template_params = {
            **parameters.default_template,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
                dumps(
                    {
                        parameters.UPPER_TIER: "0",
                        parameters.MIDDLE_TIER: "0",
                        parameters.LOWER_TIER: "0",
                    }
                )
            ),
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Create and apply dormancy flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    # Create flag to expire just before the account closure event is made
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=1, seconds=1),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Account closure rejected while outstanding fees have not been paid",
                events=[
                    update_account_status_pending_closure(
                        start + relativedelta(months=1, seconds=2),
                        accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.instance_parameters_no_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario=test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    @ac_coverage(["CPP-2031-AC05", "CPP-2031-AC06"])
    def test_dormant_account_reactivation(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, minutes=2)

        template_params = {
            **parameters.template_parameters_annual_interest,
            **parameters.maintenance_fees_enabled,
            **parameters.minimum_balance_fee_enabled,
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
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    # credit current account after reactivation
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(months=2, minutes=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    # debit current account after reactivation
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(months=2, minutes=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    # check balances before monthly schedule and after flag expires
                    # 20 is charged from current account related of two inactivity months
                    + relativedelta(months=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("30"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                    start
                    # check current account one month after reactivation
                    # 45 is charged from current account related to fees
                    + relativedelta(months=3, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
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
            **parameters.default_template,
        }

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                    # 0.32877 + 0.32877 = 0.65754
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.template_parameters_annual_interest,
        }
        instance_params = {
            **parameters.default_instance,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "5",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.template_parameters_annual_interest,
            current_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {"0.00": "0.01"}
            ),
        }
        instance_params = {
            **parameters.default_instance,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "29",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # 5000 * (0.01/365) = 0.13699
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.13699"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.13699")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5050"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "50.63976"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-50.63976")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "50")],
                    },
                    second_interest_application: {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5100.64"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "51.0051"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-51.0051")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "100.64")],
                    },
                    third_interest_application: {
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.default_template,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR: "22",
            current_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE: "30",
        }
        instance_params = {
            **parameters.default_instance,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5004.27"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "10.20985"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-10.20985")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "4.27")],
                    },
                    second_interest_application: {
                        accounts.CURRENT_ACCOUNT: [
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
                events=[update_account_status_pending_closure(end, accounts.CURRENT_ACCOUNT)],
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5014.48"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "4.96125"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-4.96125")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "14.48")],
                    },
                    end: {
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.default_template,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "quarterly",
        }
        instance_params = {
            **parameters.default_instance,
            current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "28",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (0.01/365)) + (2000 * (0.02/365)) + (2000 * (0.035/365)) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                    },
                    first_interest_application
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
            **parameters.default_template,
            current_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # (1000 * (-0.01/365)) + (2000 * (-0.02/365)) + (2000 * (-0.035/365)) = -0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="JPY",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP', 'USD']",
                    )
                ],
            ),
            SubTest(
                description="Inbound authorization in unsupported denomination - rejected",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="PHP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['GBP', 'USD']",
                    )
                ],
            ),
            SubTest(
                description="Inbound hard settlement in default denomination - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1499",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1499")],
                    },
                },
            ),
            SubTest(
                description="Inbound hard settlement in supported denomination - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "500")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement in supported denomination - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "400")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement in primary denomination - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="199",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1300")],
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
            **parameters.default_template,
            current_account.PARAM_ADDITIONAL_DENOMINATIONS: dumps(["EUR", "USD"]),
        }

        sub_tests = [
            SubTest(
                description="Outbound authorization exceeding balance - rejected",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting amount of 10 USD is exceeding available "
                        "balance of 0 USD",
                    )
                ],
            ),
            SubTest(
                description="Inbound hard settlement - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "1500")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement USD, inbound hard settlement EUR - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="EUR",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "1000")],
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_EUR, "500")],
                    },
                },
            ),
            SubTest(
                description="Outbound hard settlement EUR denomination - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=3, microseconds=30),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="EUR",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=3, microseconds=30),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting amount of 1000 EUR is exceeding available "
                        "balance of 500 EUR",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1499")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_daily_deposit_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1, seconds=3)

        template_parameters = {
            **parameters.default_template,
            current_account.maximum_daily_deposit_limit.PARAM_MAX_DAILY_DEPOSIT: "2000",
            current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0.01",
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_1",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=10): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2, microseconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "850"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2, microseconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3, microseconds=20): {
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.PENDING_IN, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, microseconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "2000"),
                            (dimensions.PENDING_IN, "0.01"),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_parameters
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
            ),
            SubTest(
                description="Withdrawal below minimum withdrawal amount - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="4",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "1100")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_daily_withdrawal_limits(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1, seconds=5)
        template_parameters = {
            **parameters.default_template,
            current_account.maximum_daily_withdrawal.PARAM_MAX_DAILY_WITHDRAWAL: "2000",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_0",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_1",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1, microseconds=10): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_2",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=15, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
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
                                target_account_id=accounts.CURRENT_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                            InboundHardSettlement(
                                amount="75",
                                target_account_id=accounts.CURRENT_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                        ],
                        event_datetime=start + relativedelta(hours=23, seconds=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "3250"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        client_transaction_id="CT_ID_5",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=23, seconds=20): {
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "3005"),
                            (dimensions.PENDING_OUT, "-5"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(hours=23, minutes=59, seconds=59, microseconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        accounts.CURRENT_ACCOUNT: [
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=3, microseconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "2990"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=1, seconds=3, microseconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=4, microseconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "1000"),
                            (dimensions.PENDING_OUT, "0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_parameters
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "30000")],
                    },
                },
            ),
            SubTest(
                description="Reject inbound over balance limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000.01",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "30000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would exceed maximum permitted balance 50000"
                        " GBP.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_overdraft_limit_arranged_not_set_unarranged_not_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        instance_parameters = {
            **parameters.default_instance,
            current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "",
            current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3500",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -3500, which exceeds the available "
                        "balance of GBP 3000.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "500")],
                    },
                },
            ),
            SubTest(
                description="Accept outbound over current balance due to credit in PIB",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="1000",
                                target_account_id=accounts.CURRENT_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                            InboundHardSettlement(
                                amount="750",
                                target_account_id=accounts.CURRENT_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=4),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "250")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_limit_arranged_set_unarranged_not_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=14)
        instance_parameters = {
            **parameters.default_instance,
            current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100",
            current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3150",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -3150, which exceeds the available "
                        "balance of GBP 3100.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3050",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                },
            ),
            SubTest(
                description="Pay overdraft, Change arranged overdraft: 100 to 50, reject -100 Deb",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=5),
                        account_id=accounts.CURRENT_ACCOUNT,
                        **{current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "50"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=6),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -100, which exceeds the available "
                        "balance of GBP 50.",
                    )
                ],
            ),
            SubTest(
                description="Change arranged overdraft: 50 to 0, reject -100 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=7),
                        account_id=accounts.CURRENT_ACCOUNT,
                        **{current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=8),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=8): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=8),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -100, which exceeds the available "
                        "balance of GBP 0.",
                    )
                ],
            ),
            SubTest(
                description="Change arranged overdraft: 0 to 100, Accept -100 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=9),
                        account_id=accounts.CURRENT_ACCOUNT,
                        **{current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=10): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-100")],
                    },
                },
            ),
            SubTest(
                description="Change arranged overdraft: 100 to 50, Reject -0.01 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=11),
                        account_id=accounts.CURRENT_ACCOUNT,
                        **{current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "50"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="0.01",
                        event_datetime=start + relativedelta(seconds=12),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=12): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-100")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=12),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -0.01, which exceeds the available "
                        "balance of GBP -50.",
                    )
                ],
            ),
            SubTest(
                description="Change arranged overdraft: 50 to 150, Accept -10 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=13),
                        account_id=accounts.CURRENT_ACCOUNT,
                        **{current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "150"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=14),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=14): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-110")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_limit_arranged_not_set_unarranged_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        instance_parameters = {
            **parameters.default_instance,
            current_account.overdraft_limit.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "",
            current_account.overdraft_limit.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "50",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3100",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -3100, which exceeds the available "
                        "balance of GBP 3050.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3050",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_limit_arranged_set_unarranged_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        instance_parameters = {**parameters.default_instance}

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3155",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -3155, which exceeds the available "
                        "balance of GBP 3150.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3145",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-145")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_maintenance_monthly_fees_not_charged(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1, minutes=1)

        sub_tests = [
            SubTest(
                description="Monthly maintenance fees not applied when dormancy flag on",
                events=[
                    # Setting dormancy flag on so the fee is not going to be charged
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=6),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        # Debit 10 from current account and credit 10 to inactivity fee income
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-10"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        # monthly maintenance fee is not charged because account is dormant
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=parameters.template_parameters_fees_enabled,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(
        ["CPP-1921-AC05", "CPP-1921-AC06", "CPP-1921-AC08", "CPP-1921-AC09", "CPP-1921-AC10"]
    )
    def test_maintenance_monthly_fees_charged_specific_day_and_time(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=1, minutes=1)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest_maintenance_fees_enabled,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_HOUR: "6",
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE: "30",
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_SECOND: "15",
        }
        instance_parameters = {
            **parameters.default_instance,
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "30",
        }

        # First schedule should run on 28th Feb as we require 1 month between account opening
        # and the application event and the schedule should run in the first valid day before
        # if the day does not exist in the current month
        first_schedule_datetime = datetime(
            year=2022, month=2, day=28, hour=6, minute=30, second=15, tzinfo=ZoneInfo("UTC")
        )

        second_schedule_datetime = datetime(
            year=2022, month=3, day=30, hour=6, minute=30, second=15, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Credit money in current account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="6",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("6"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Check fee is applied on specific day and time",
                expected_balances_at_ts={
                    first_schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_datetime],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check fee is applied on the next schedule day and time",
                expected_balances_at_ts={
                    second_schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-4"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_schedule_datetime],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_maintenance_monthly_and_annual_fees_charged(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=2, minutes=2)
        template_parameters = {
            **parameters.template_parameters_annual_interest_maintenance_fees_enabled,
            # Overdraft interest rate is set to 0 to not impact the test
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Setup Flags",
                events=[
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.UPPER_TIER
                    ),
                ],
            ),
            SubTest(
                description="Monthly maintenance fees applied as scheduled",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        # Debit 5 from current account and
                        # credit 5 to monthly maintenance fee
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Annual maintenance fee applied as scheduled",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=1): {
                        # After 1 Year monthly maintenance fee is 5 * 12 = 60
                        # Annual maintenance fees for lower tier is 150
                        # Credit 60 into Monthly maintenance fee account
                        # Credit 150 into annual maintenance fee account
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-210"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("60")),
                        ],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("150")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Changing current account tier, from LOWER_TIER to UPPER_TIER",
                events=[
                    # Tier set to UPPER TIER so when the annual maintenance fee is charged
                    # the value should be different
                    create_flag_event(
                        timestamp=start + relativedelta(years=1, minutes=2),
                        flag_definition_id=parameters.UPPER_TIER,
                        account_id=accounts.CURRENT_ACCOUNT,
                        expiry_timestamp=end,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(years=2, minutes=1): {
                        # 12*20=240 monthly maintenance fees for UPPER_TIER
                        # 200 annual maintenance fees for UPPER_TIER
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-650"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("300")),
                        ],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("350")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_maintenance_annual_fees_non_existing_day(self):
        start = datetime(year=2022, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(years=3, months=1, minutes=2)
        first_year_schedule = datetime(year=2023, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))
        second_year_schedule = datetime(
            year=2024, month=2, day=29, minute=1, tzinfo=ZoneInfo("UTC")
        )
        third_year_schedule = datetime(year=2025, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))
        template_parameters = {
            **parameters.default_template,
            current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER: dumps(
                parameters.ANNUAL_MAINTENANCE_FEE_BY_TIER
            ),
            # Overdraft interest rate is set to 0 to not impact the test
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE: "0",
        }
        instance_parameters = {
            **parameters.default_instance,
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "29",
        }

        sub_tests = [
            SubTest(
                description="Annual maintenance fee applied in first year schedule",
                expected_balances_at_ts={
                    first_year_schedule: {
                        # The maintenance fee application day defined does not exist for
                        # february in the first year, so it is applied the first valid day before
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-150"))],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("150")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_year_schedule],
                        event_id=maintenance_fees.APPLY_ANNUAL_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Annual maintenance fee applied in second year schedule",
                expected_balances_at_ts={
                    second_year_schedule: {
                        # The maintenance fee application day defined exist in the second year
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-300"))],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("300")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_year_schedule],
                        event_id=maintenance_fees.APPLY_ANNUAL_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Third Annual maintenance in third year schedule",
                expected_balances_at_ts={
                    third_year_schedule: {
                        # The maintenance fee application day defined does not exist for
                        # february in the third year, so it is applied the first valid day before
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-450"))],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("450")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[third_year_schedule],
                        event_id=maintenance_fees.APPLY_ANNUAL_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_maintenance_monthly_fee_by_tier(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=1, minutes=1)

        sub_tests = [
            SubTest(
                description="Fund the account so it has a positive balance",
                # The account will use LOWER_TIER by default
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("90"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Checking monthly maintenance fee applied corresponds to LOWER_TIER",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("85"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minutes=1)],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Changing current account tier, from LOWER_TIER to UPPER_TIER",
                events=[
                    # Tier set to UPPER TIER so when the monthly maintenance monthly fee is charged
                    # the value should be different
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.UPPER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(months=1, days=1),
                        flag_definition_id=parameters.UPPER_TIER,
                        expiry_timestamp=start + relativedelta(months=2, minutes=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Checking monthly maintenance fee applied corresponds to UPPER_TIER",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("65"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=2, minutes=1)],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Changing current account tier, from UPPER_TIER to MIDDLE_TIER",
                events=[
                    # Tier set to MIDDLE_TIER so when the monthly maintenance monthly fee is charged
                    # the value should be different
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.MIDDLE_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(months=2, days=1),
                        flag_definition_id=parameters.MIDDLE_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Checking monthly maintenance fee applied corresponds to MIDDLE_TIER",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("55"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("35")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=3, minutes=1)],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=parameters.template_parameters_annual_interest_maintenance_fees_enabled,
        )
        self.run_test_scenario(test_scenario)

    def test_zero_maintenance_fees_charged(self):
        start = default_simulation_start_date
        end = start + relativedelta(years=1, days=1, minutes=1)
        template_parameters = parameters.default_template.copy()
        monthly_schedule_event = start + relativedelta(months=1, minutes=1)
        annually_schedule_event = start + relativedelta(years=1, minutes=1)

        # Both maintenance fees set to 0 so they won't be charged
        template_parameters = {
            **parameters.default_template,
            current_account.maintenance_fees.PARAM_ANNUAL_MAINTENANCE_FEE_BY_TIER: dumps(
                parameters.ZERO_MAINTENANCE_FEE_BY_TIER
            ),
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
                parameters.ZERO_MAINTENANCE_FEE_BY_TIER
            ),
        }

        sub_tests = [
            SubTest(
                description="Monthly maintenance fees not applied",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[monthly_schedule_event],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Annual maintenance fees not applied",
                expected_balances_at_ts={
                    start
                    + relativedelta(years=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                        accounts.ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[annually_schedule_event],
                        event_id=maintenance_fees.APPLY_ANNUAL_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1921-AC07", "CPP-1921-AC11", "CPP-1921-AC12", "CPP-1921-AC13"])
    def test_maintenance_monthly_fee_application_allow_partial_fee(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1)

        # Schedule run times
        expected_schedule_1 = datetime(year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))
        expected_schedule_2 = expected_schedule_1 + relativedelta(months=1)

        template_params = {
            **parameters.default_template,
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            current_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: "annually",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0",
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (
                "True"
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund account to have just enough for a partial payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("3"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Apply monthly maintenance with partial funds available uses overdraft "
                "- month 1",
                expected_balances_at_ts={
                    expected_schedule_1: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-2")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_1],
                        event_id=current_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Apply monthly maintenance with partial funds available uses overdraft "
                "- month 2",
                expected_balances_at_ts={
                    expected_schedule_2: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("8"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_2],
                        event_id=current_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=2,
                    )
                ],
            ),
            SubTest(
                description="Fund account partially to check verify the outstanding "
                "maintenance fee is partially collected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=expected_schedule_2 + relativedelta(minutes=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_2
                    + relativedelta(minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("1")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("9"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account fully to check verify remaining outstanding "
                "maintenance fee is collected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=expected_schedule_2 + relativedelta(minutes=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_2
                    + relativedelta(minutes=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("4")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.instance_parameters_small_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1921-AC14"])
    def test_outstanding_maintenance_monthly_fee_prevents_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        # Schedule run times
        schedule_datetime = datetime(year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **parameters.default_template,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa: E501
                "True"
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Account closure rejected while outstanding fees have not been paid",
                events=[
                    update_account_status_pending_closure(
                        schedule_datetime + relativedelta(seconds=1),
                        accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.instance_parameters_no_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario=test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    @ac_coverage(["CPP-1922-AC15", "CPP-1922-AC16", "CPP-1922-AC17"])
    def test_minimum_balance_limit_fee_apply_on_month_end_for_non_existent_day(self):
        # When Application day is 29, 30 or 31 and not exist in current month.
        # Application should happen on the last day of the Month.
        start = default_simulation_start_date
        # Expected application day is 28 Feb
        end = start.replace(month=2, day=28, hour=23, minute=59)

        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "23",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "59",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "0",
        }

        instance_parameters = {
            **parameters.default_instance,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.LOWER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.LOWER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="70",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("70"))],
                    },
                },
            ),
            SubTest(
                description="Check account on end of Feb",
                expected_balances_at_ts={
                    end: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "50.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id="APPLY_MINIMUM_BALANCE_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC16"])
    def test_minimum_balance_limit_fee_apply_skip_first_application_day(self):
        # When account is opened on 15th of Jan and application day is 1st
        # then the first minimum balance fee application should happen only on 1st March.
        start = datetime(year=2022, month=1, day=15, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=2, days=1, hours=1)
        schedule_datetime = datetime(
            year=2022, month=3, day=1, hour=6, minute=30, second=45, tzinfo=ZoneInfo("UTC")
        )

        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "6",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "30",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "45",
        }
        instance_parameters = {
            **parameters.default_instance,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.LOWER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.LOWER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="70",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("70"))],
                    },
                },
            ),
            SubTest(
                description="Check account at defined fee schedule",
                expected_balances_at_ts={
                    schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "50.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[schedule_datetime],
                        event_id="APPLY_MINIMUM_BALANCE_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_specific_day_and_time(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        schedule_date = datetime(year=2022, month=2, day=15, tzinfo=ZoneInfo("UTC"))
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_HOUR: "6",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "30",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_SECOND: "45",
        }
        instance_parameters = {
            **parameters.default_instance,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "15",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.LOWER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.LOWER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="70",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("70"))],
                    },
                },
            ),
            SubTest(
                description="Check account at defined fee schedule",
                expected_balances_at_ts={
                    schedule_date
                    + relativedelta(hours=6, minutes=30, second=45): {
                        # Daily balance since the first day is 70 until the fee schedule day
                        # Mean balance is calculated as Daily balance multiplied and divided
                        # by number of days of period (70 * 31 / 31 = 70)
                        # Mean balance is lower than threshold so Minimum Balance Fee is applied
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "50.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[schedule_date + relativedelta(hours=6, minutes=30, second=45)],
                        event_id="APPLY_MINIMUM_BALANCE_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_mean_balance_below_threshold(self):
        start = default_simulation_start_date
        last_day = datetime(year=2022, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        end = last_day + relativedelta(hours=1)
        before_last_day = datetime(year=2022, month=1, day=31, tzinfo=ZoneInfo("UTC"))

        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Create Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.LOWER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.LOWER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Debit account the day before last day of period",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=before_last_day,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Debit the last day of period, mean balance is lower than threshold
                expected_balances_at_ts={
                    before_last_day
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "50")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Monthly mean balance is lower than threshold ((100 * 30) + 50)/31 = 98.38
                expected_balances_at_ts={
                    last_day: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "100")],
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
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "80.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minutes=1)],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC13"])
    def test_minimum_balance_fee_not_charged_when_balance_equal_threshold(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to LOWER TIER so if the monthly average balance
                    # is lower than 100 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.LOWER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.LOWER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, minutes=1): {
                        # Minimum balance Fee is not charged
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "100.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minutes=1)],
                        event_id=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_fee_middle_tier_charged(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1, hours=2)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to MIDDLE TIER so if the monthly average balance
                    # is lower than 75 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.MIDDLE_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.MIDDLE_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("150"))],
                    },
                },
            ),
            SubTest(
                description="Spend money",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="75.01",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Monthly average balance is lower than 75 so
                # the minimum maintenance fee is going to be charged in the next fee schedule
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "74.99")],
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
                        # Minimum balance Fee is debited from current account and
                        # credited into minimum balance fee income account
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "54.99")],
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
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC09"])
    def test_minimum_balance_limit_fee_with_insufficient_funds_makes_account_balance_negative(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=2)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to UPPER TIER so if the monthly average balance
                    # is lower than 25 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.UPPER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.UPPER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    # Current balance is lower than 25 so the fee is going to apply
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("15"))],
                    },
                },
            ),
            SubTest(
                description="Check account at fee schedule",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, days=1, hours=1): {
                        # Minimum balance Fee is debited from current account
                        # current account is insufficient, the balance becomes negative
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-5")],
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
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_limit_fee_charged_defaults_to_lower_no_tier_defined(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=1)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # No tier is defined, so it will default to LOWER_TIER
                    create_inbound_hard_settlement_instruction(
                        amount="80",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "80")],
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
                        # Minimum balance Fee is debited from current account and
                        # credited into minimum balance fee income account
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "60.00")],
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
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC14"])
    def test_minimum_balance_limit_fee_ignores_current_day_in_average(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1, hours=4)
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # Tier set to UPPER TIER so if the monthly balance
                    # is lower than 25 the minimum balance fee is charged
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=parameters.UPPER_TIER
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.UPPER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="25.01",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "25.01")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=35): {
                        # Check balance after outbound hard settlement
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
                    },
                    start
                    + relativedelta(months=1, minutes=2): {
                        # Check balance after minimum monthly balance fee schedule
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
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
            template_params=template_parameters,
        )
        self.run_test_scenario(test_scenario)

    def test_minimum_balance_fee_not_applied_when_less_than_a_month_since_creation(self):
        start = datetime(year=2022, month=1, day=15, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=2, days=1, hours=1)
        schedule_date = datetime(year=2022, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        next_schedule_date = datetime(year=2022, month=3, day=1, tzinfo=ZoneInfo("UTC"))
        template_parameters = {
            # Set to annual interest to not interfere with the test
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
        }
        instance_parameters = {
            **parameters.default_instance,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "1",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    # LOWER_TIER by default
                    create_inbound_hard_settlement_instruction(
                        amount="70",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("70"))],
                    },
                },
            ),
            SubTest(
                description="Not applying minimum balance fee when less than a month",
                expected_balances_at_ts={
                    schedule_date
                    + relativedelta(minutes=1): {
                        # Less than a month between the account opening day and the
                        # Minimum Balance Fee Application Day.
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "70.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check minimum balance fee charged when more than a month",
                expected_balances_at_ts={
                    next_schedule_date
                    + relativedelta(minutes=1): {
                        # More than a month between the account opening day and the
                        # Minimum Balance Fee Application Day.
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "50.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[next_schedule_date + relativedelta(minutes=1)],
                        event_id="APPLY_MINIMUM_BALANCE_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_parameters,
            instance_params=instance_parameters,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC10", "CPP-1922-AC11", "CPP-1922-AC12"])
    def test_minimum_balance_limit_fee_partial_fee_collection(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, hours=1)

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",  # noqa: E501
            current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0",
        }
        # Schedule run times
        first_schedule_run = datetime(year=2022, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                    },
                },
            ),
            SubTest(
                description="Fee charged with insufficient funds is partially applied and uses "
                "overdraft",
                expected_balances_at_ts={
                    first_schedule_run: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-5.00"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "10.00"),
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-5.00"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "7.00"),
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "8.00"),
                            (dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER, "0.00"),
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
            instance_params=parameters.instance_parameters_small_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_partial_payment_fee_hierarchy(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        template_params = {
            **parameters.template_parameters_annual_interest,
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps({"LOWER_TIER": "5"})
            ),
            current_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa
                "True"
            ),
            current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE: "0",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "10",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: (
                "True"
            ),
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_MINUTE: "1",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE: "15",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "2",
            current_account.minimum_single_deposit_limit.PARAM_MIN_DEPOSIT: "0",
        }

        maintenance_fee_schedule_datetime = datetime(
            year=2022, month=2, day=1, minute=0, tzinfo=ZoneInfo("UTC")
        )
        minimum_balance_schedule_datetime = datetime(
            year=2022, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )
        inactivity_fee_schedule_datetime = datetime(
            year=2022, month=2, day=1, minute=2, tzinfo=ZoneInfo("UTC")
        )

        sub_tests = [
            SubTest(
                description="Fund account without sufficient balance to collect fees",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
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
                description="Partially apply monthly maintenance fee.",
                expected_balances_at_ts={
                    maintenance_fee_schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[maintenance_fee_schedule_datetime],
                        event_id=current_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Partially apply minimum balance fee.",
                expected_balances_at_ts={
                    minimum_balance_schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("10"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[minimum_balance_schedule_datetime],
                        event_id=current_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT,  # noqa: E501
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("10"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("15"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[inactivity_fee_schedule_datetime],
                        event_id=current_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Fund account to pay outstanding maintenance fee and partially pay "
                "outstanding minimum balance fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=inactivity_fee_schedule_datetime + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("7"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("15"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Fund account to pay outstanding minimum balance fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=inactivity_fee_schedule_datetime + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    inactivity_fee_schedule_datetime
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MINIMUM_BALANCE_FEE_TRACKER,
                                Decimal("0"),
                            ),
                            (
                                dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER,
                                Decimal("12"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
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
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=parameters.instance_parameters_no_overdraft,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC18"])
    def test_outstanding_minimum_balance_fee_prevents_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=1)

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.template_parameters_annual_interest,
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "20",
            current_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",  # noqa: E501
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Verify outstanding minimum balance fee prevents closure",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end, account_id=accounts.CURRENT_ACCOUNT
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=parameters.instance_parameters_no_overdraft,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    def test_unarranged_overdraft_fee_accrual_and_apply_time(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=4)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "23",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_HOUR: "23",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_MINUTE: "59",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_SECOND: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: None,
        }

        instance_params = {
            **parameters.default_instance,
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_DAY: "3",
        }

        sub_tests = [
            SubTest(
                description="Overdraft exceeded and no cap - Fee accrued",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-150")],
                    },
                    start
                    + relativedelta(days=1, hours=23): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
                        ],
                    },
                    start
                    + relativedelta(months=1, days=2, hours=23): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-165")],
                    },
                    # Fee Applied on 3nd Jan 23:59.
                    # Accrual for 33 days is 165
                    (start + relativedelta(months=1, days=2, hours=23, minutes=59)): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.DEFAULT, "-315"),
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "165")
                        ],
                    },
                },
            ),
            SubTest(
                description="Unarranged Overdraft fee accrual continues after apply",
                expected_balances_at_ts={
                    (start + relativedelta(months=1, days=3, hours=23)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-5")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-5")
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
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_unarranged_overdraft_fee_application_on_non_existent_day(self):
        # AC 17
        # When Application day is 29, 30 or 31 and not exist in current month.
        # Application should happen on the last day of the Month.
        start = default_simulation_start_date
        end = start.replace(month=2, day=28, hour=23, minute=59)
        template_params = {
            **parameters.default_template,
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: None,
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_HOUR: "23",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_MINUTE: "59",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_SECOND: "0",
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "23",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
        }

        instance_params = {
            **parameters.default_instance,
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Overdraft exceeded and no cap - Fee accrued",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-150")],
                    },
                    start
                    + relativedelta(days=1, hours=23): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
                        ],
                    },
                    # First application happens on 28 Feb so accrual till 28 feb is £290 (58 days)
                    start
                    + relativedelta(month=2, day=28, hour=23): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-290")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-290")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id="APPLY_UNARRANGED_OVERDRAFT_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="Unarranged overdraft fee application run on last day of"
                "the month when application day is not exist in current month",
                expected_balances_at_ts={
                    # Fee should be applied on 28 Feb 23:59.
                    # Fee accrual for 58 days is £290
                    end: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.DEFAULT, "-440"),
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "290")
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
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_unarranged_overdraft_fee_application_on_non_existent_day_jun(self):
        # AC 17
        # When Application day is 31 and the month is June.
        # Application should happen on the 30th June.
        start = datetime(year=2022, month=5, day=1, tzinfo=ZoneInfo("UTC"))
        end = start.replace(month=6, day=30, hour=23, minute=59)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "23",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
            current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "0",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_HOUR: "23",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_MINUTE: "59",
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_SECOND: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: None,
        }

        instance_params = {
            **parameters.default_instance,
            current_account.unarranged_overdraft_fee.PARAM_FEE_APPLICATION_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Overdraft exceeded and no cap - Fee accrued",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-150")],
                    },
                    start
                    + relativedelta(days=1, hours=23): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
                        ],
                    },
                    # First application happens on 30 Jun so accrual till 30 Jun is £300 (60 days)
                    start
                    + relativedelta(month=6, day=30, hour=23): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-300")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-300")
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id="APPLY_UNARRANGED_OVERDRAFT_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
            SubTest(
                description="Unarranged overdraft fee application run on 30 Jun",
                expected_balances_at_ts={
                    # Fee should be applied on 30 Jun 23:59.
                    # Fee accrual for 60 days is £300
                    end: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.DEFAULT, "-450"),
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "300")
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
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_unarranged_overdraft_fee_no_cap(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: None,
        }

        sub_tests = [
            SubTest(
                description="Overdraft exceeded and no cap - Fee accrued",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(days=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                    # Day 1 after first accrual Fee should be 0 as the overdraft not exceeded
                    start
                    + relativedelta(days=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.DEFAULT, "-150"),
                        ],
                    },
                    # After second accrual run fee should be 5 as the overdraft exceeded
                    (start + relativedelta(days=2)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-5")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-5")
                        ],
                    },
                    (start + relativedelta(days=3)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-10")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-10")
                        ],
                    },
                    start
                    + relativedelta(days=31, hours=0): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-150")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-150")
                        ],
                    },
                },
            ),
            SubTest(
                description="Unarranged Overdraft Fee applied",
                expected_balances_at_ts={
                    # End of month Fee accrued should be transferred to main account
                    end
                    - relativedelta(hours=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-300")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "150")
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

    def test_unarranged_overdraft_fee_with_cap(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: "26",
        }

        sub_tests = [
            SubTest(
                description="Overdraft exceeded and no cap - Fee accrued",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(days=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                    # Day 1 after first accrual Fee should be 0 as the overdraft not exceeded
                    start
                    + relativedelta(days=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.DEFAULT, "-150"),
                        ],
                    },
                    # After second accrual run fee should be 5 as the overdraft exceeded
                    (start + relativedelta(days=2)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-5")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-5")
                        ],
                    },
                    (start + relativedelta(days=3)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-10")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-10")
                        ],
                    },
                    (start + relativedelta(days=10)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-26")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-26")
                        ],
                    },
                },
            ),
            SubTest(
                description="Unarranged Overdraft Fee applied",
                expected_balances_at_ts={
                    # End of month Fee accrued should be transferred to main account
                    end
                    - relativedelta(hours=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-176")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "26")
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

    def test_unarranged_overdraft_fee_dormant_scenario(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_RATE: "0",
            current_account.unarranged_overdraft_fee.PARAM_UNARRANGED_OVERDRAFT_FEE_CAP: "26",
            current_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund goes below arranged overdraft limit and account set to dormant",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    # account flagged as dormant
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=DORMANCY_FLAG,
                    ),
                    # account is going to reactivate when flag expires
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=3),
                        flag_definition_id=DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=1, minutes=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "-150")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
                        ],
                    },
                    # After second accrual run fee should be 5 as the overdraft exceeded
                    (start + relativedelta(days=1, hours=23)): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-5")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-5")
                        ],
                    },
                    # Fee accrued capped to 26
                    start
                    + relativedelta(days=30): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.UNARRANGED_OVERDRAFT_FEE, "-26")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-26")
                        ],
                    },
                },
            ),
            SubTest(
                description="Unarranged Overdraft accrued but not applied due to dormancy",
                expected_balances_at_ts={
                    # End of month Fee accrued should be transferred to main account
                    end: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-26"),
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-26")
                        ],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0")
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

    def test_overdraft_interest_accrual_both_buffers_are_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=2, minutes=1, seconds=1)

        overdraft_exit = start + relativedelta(days=10, hours=1)
        second_overdraft = start + relativedelta(days=15, hours=1)

        sub_tests = [
            SubTest(
                description="Overdraw the account leaving it with a balance of -150 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # Day 1 in overdraft buffer applies
                # Final balance = EOD balance -150 + Interest Buffer 50
                # Overdraft accrual = 100 * (0.05/365)) = Round 5 DP(0.013698) = 0.0137
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.0137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.0137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 2 in overdraft buffer applies
                    # Final balance = EOD balance -150 + Interest Buffer 50
                    # Overdraft accrual = 100 * (0.05/365)) = Round 5 DP(0.013698) = 0.0137
                    # Total overdraft Accrual = 0.0137 + 0.0137 = 0.0274
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.0274")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.0274")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 3 in overdraft buffer does not apply
                    # Final balance = EOD balance -150 + Interest Buffer 0
                    # Overdraft accrual = 150 * (0.05/365)) = Round 5 DP(0.020547) = 0.02055
                    # Total overdraft Accrual = 0.0274 + 0.02055 = 0.04795
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.04795")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.04795")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="After 10 days the account is funded taking it out of overdraft",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=overdraft_exit,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # Balances after transfer
                    # Total overdraft accrual = 0.04795 + 0.14385 (7 days * 0.02055) = 0.1918
                    overdraft_exit
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1918")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1918")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 11 no overdraft is calculated
                    start
                    + relativedelta(days=11, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1918")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1918")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Overdraw the account leaving it with a balance of -50 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=second_overdraft,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Day 1 and 2 in overdraft the buffer applies
                    # Final balance = EOD balance -50 + Interest Buffer 50
                    # Total overdraft accrual = 0.1918
                    start
                    + relativedelta(days=17, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1918")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1918")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 3 in overdraft buffer does not apply
                    # Final balance = EOD balance -50 + Interest Buffer 0
                    # Overdraft accrual = 50 * (0.05/365)) = Round 5 DP(0.006849) = 0.00685
                    # Total overdraft Accrual = 0.1918 + 0.00685 = 0.19865
                    start
                    + relativedelta(days=18, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.19865")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.19865")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Apply accrued overdraft interest after 1 month",
                expected_balances_at_ts={
                    # Apply overdraft interest at interest application
                    # Overdraft accrual = 50 * (0.05/365)) = Round 5 DP(0.006849) = 0.00685
                    # Total overdraft Accrual = 0.19865 + 0.08905 (0.00685 * 13 DAYS) = 0.2877
                    # Charged overdraft amount = Round 2 DP(0.2877) = 0.29
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-105.29"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "30")
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.29")
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=parameters.template_parameters_fees_enabled,
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_interest_accrual_only_amount_buffer_is_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=2, minutes=1, seconds=1)
        template_params = {
            **parameters.template_parameters_fees_enabled,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS: "0",
        }

        overdraft_exit = start + relativedelta(days=10, hours=1)
        second_overdraft = start + relativedelta(days=15, hours=1)
        pass_overdraft_buffer_limit = start + relativedelta(days=20, hours=1)

        sub_tests = [
            SubTest(
                description="Overdraw the account leaving it with a balance of -150 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Day 1 in overdraft buffer applies
                    # Final balance = EOD balance -150 + Interest Buffer 50
                    # Overdraft accrual = 100 * (0.05/365)) = Round 5 DP(0.013698) = 0.0137
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.0137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.0137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 10 in overdraft buffer still applies
                    # Final balance = EOD balance -150 + Interest Buffer 50
                    # Overdraft accrual = 100 * (0.05/365)) = Round 5 DP(0.013698) = 0.0137
                    # Total overdraft Accrual = 0.0137 * 10 = 0.137
                    start
                    + relativedelta(days=10): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="After 10 days the account is funded taking it out of overdraft",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=overdraft_exit,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # Balances after transfer
                    # Total overdraft accrual = 0.04795 + 0.14385 (7 days * 0.02055) = 0.1918
                    overdraft_exit
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 11 no overdraft is calculated
                    start
                    + relativedelta(days=11, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Overdraw the account leaving it with a balance of -50 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=second_overdraft,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Overdraft buffer applies
                    # Final balance = EOD balance -50 + Interest Buffer 50 = 0
                    # Total overdraft accrual = 0.137
                    start
                    + relativedelta(days=16, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.137")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.137")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Cause EOD balance to be over the buffer amount of -50 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="25",
                        event_datetime=pass_overdraft_buffer_limit,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Overdraft buffer applies
                    # Final balance = EOD balance -75 + Interest Buffer 50 = -25
                    # Overdraft accrual = 25 * (0.05/365)) = Round 5 DP(0.003424) = 0.00342
                    # Total overdraft accrual = 0.137 + 0.00342
                    start
                    + relativedelta(days=21, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-75")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.14042")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.14042")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Apply accrued overdraft interest after 1 month",
                expected_balances_at_ts={
                    # Apply overdraft interest at interest application
                    # Overdraft accrual = 25 * (0.05/365)) = Round 5 DP(0.003424) = 0.00342
                    # Total overdraft Accrual = 0.14042 + 0.0342 (0.00342 * 10 DAYS) = 0,17462
                    # Charged overdraft amount = Round 2 DP(0.2877) = 0.17
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-130.17"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "30")
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.17")
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_interest_accrual_only_period_buffer_is_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=2, minutes=1, seconds=1)
        template_params = {
            **parameters.template_parameters_fees_enabled,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT: "0",
        }

        overdraft_exit = start + relativedelta(days=10, hours=1)
        second_overdraft = start + relativedelta(days=15, hours=1)
        third_overdraft = start + relativedelta(days=19, hours=1)

        sub_tests = [
            SubTest(
                description="Overdraw the account leaving it with a balance of -150 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Day 1 in overdraft buffer applies
                    # Final balance = EOD balance -150 + Interest Buffer 150
                    # Overdraft accrual = 0
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 2 in overdraft buffer applies
                    # Final balance = EOD balance -150 + Interest Buffer 150
                    # Overdraft accrual = 0
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 3 in overdraft buffer does not apply
                    # Final balance = EOD balance -150 + Interest Buffer 0
                    # Overdraft accrual = 150 * (0.05/365)) = Round 5 DP(0.020547) = 0.02055
                    # Total overdraft Accrual = 0.02055
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.02055")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.02055")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="After 10 days the account is funded taking it out of overdraft",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=overdraft_exit,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # Balances after transfer
                    # Total overdraft accrual = 0.02055 + 0.14385 (7 days * 0.02055) = 0.1644
                    overdraft_exit
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1644")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1644")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 11 no overdraft is calculated
                    start
                    + relativedelta(days=11, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1644")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1644")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Overdraw the account leaving it with a balance of -50 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=second_overdraft,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Overdraft buffer applies for the 2 days
                    # Final balance = EOD balance -50 + Interest Buffer 50 = 0
                    # Total overdraft accrual = 0.1644
                    start
                    + relativedelta(days=17, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1644")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1644")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Fund the account inside buffer period so no interest is accrued",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=second_overdraft + relativedelta(days=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Final balance = EOD balance 100
                    # Total overdraft accrual doesnt change = 0.1644
                    start
                    + relativedelta(days=18, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.1644")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.1644")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Create overdraft and apply accrued overdraft interest after 1 month",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=third_overdraft,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Apply overdraft interest at interest application
                    # Overdraft accrual = 50 * (0.05/365)) = Round 5 DP(0.006849) = 0.00685
                    # Total overdraft Accrual = 0.1644 + 0.06165 (0.00685 * 9 DAYS) = 0.22605
                    # Charged overdraft amount = Round 2 DP(0.22605) = 0.23
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-105.22"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "30")
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.23")
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_interest_accrual_no_buffers_are_set(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=2, minutes=1, seconds=1)
        template_params = {
            **parameters.template_parameters_fees_enabled,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT: "0",
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS: "0",
        }

        overdraft_exit = start + relativedelta(days=10, hours=1)
        second_overdraft = start + relativedelta(days=15, hours=1)

        sub_tests = [
            SubTest(
                description="Overdraw the account leaving it with a balance of -150 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # Day 1 in overdraft no buffers applied
                    # Final balance = EOD balance -150 + Interest Buffer 0
                    # Overdraft accrual = 150 * (0.05/365)) = Round 5 DP(0.020547) = 0.02055
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-150")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.02055")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.02055")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="After 10 days the account is funded taking it out of overdraft",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=overdraft_exit,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # Balances after transfer
                    # Total overdraft accrual = 0.02055 + 0.18495 (9 days * 0.02055) = 0.2055
                    overdraft_exit
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.2055")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.2055")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    # Day 11 no overdraft is calculated
                    start
                    + relativedelta(days=11, seconds=2): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.2055")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.2055")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Overdraw the account leaving it with a balance of -50 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=second_overdraft,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # No interest buffer applies
                    # Final balance = EOD balance -50 + Interest Buffer 0
                    # Overdraft accrual = 50 * (0.05/365)) = Round 5 DP(0.006849) = 0.00685
                    # Total overdraft accrual = 0.2055 + 0.00685 = 0.21235
                    start
                    + relativedelta(days=16, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-50")),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.21235")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.21235")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Apply accrued overdraft interest after 1 month",
                expected_balances_at_ts={
                    # Apply overdraft interest at interest application
                    # Overdraft accrual = 50 * (0.05/365)) = Round 5 DP(0.006849) = 0.00685
                    # Total overdraft Accrual = 0.21235 + 0.10275 (0.00685 * 15 DAYS) = 0.3151
                    # Charged overdraft amount = Round 2 DP(0.3151) = 0.32
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-105.32"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.UNARRANGED_OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "30")
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [
                            (dimensions.DEFAULT, "0.32")
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=2, seconds=5)
        template_params = {
            **parameters.default_template,
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_AMOUNT: "0",
            current_account.overdraft_interest.PARAM_OVERDRAFT_INTEREST_FREE_BUFFER_DAYS: "0",
        }

        first_interest_accrual = start + relativedelta(
            days=1,
            hour=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )
        second_interest_accrual = first_interest_accrual + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="Fund the account: EOD balance 5000 GBP",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(microseconds=10): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
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
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Overdraw the account: EOD balance -150 GBP",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5150",
                        event_datetime=first_interest_accrual + relativedelta(minute=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    first_interest_accrual
                    + relativedelta(minute=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Check balances after second interest and overdraft fee accrual",
                # Overdraft Accrued interest = -150 * (0.05/365) = -0.02055
                expected_balances_at_ts={
                    second_interest_accrual
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "-150"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.02055")),
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.02055")
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Pay-off overdraft balance to close the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="155",
                        event_datetime=end - relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    update_account_status_pending_closure(end, accounts.CURRENT_ACCOUNT),
                ],
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [
                            # 5 GBP left for clearing the unarranged overdraft fee due
                            (dimensions.DEFAULT, "5"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "-5"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0.32877"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("-0.02055")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.32877")
                        ],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-0.02055")
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                    end: {
                        accounts.CURRENT_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.UNARRANGED_OVERDRAFT_FEE, "0"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                            (dimensions.OVERDRAFT_ACCRUED_INTEREST, Decimal("0")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.OVERDRAFT_INTEREST_RECEIVED_ACCOUNT: [(dimensions.DEFAULT, "0")],
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

    def test_roundup_autosave(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=15)
        template_params = {
            **parameters.default_template,
        }

        sub_tests = [
            SubTest(
                description="No Round up Auto save when save account id not set",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        denomination="USD",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    # No round up autosave as saving account id param not set
                    create_outbound_hard_settlement_instruction(
                        amount="10.2",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "39.8")],
                    },
                },
            ),
            SubTest(
                description="Setting optional param to allow round up autosave",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=4),
                        account_id=accounts.CURRENT_ACCOUNT,
                        roundup_autosave_account=accounts.ROUND_UP_SAVINGS_ACCOUNT,
                    ),
                    # Acceptance Criteria 007 auto save for a valid payment type
                    create_outbound_hard_settlement_instruction(
                        amount="10.2",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    # 39.8 - 10.2 - .8(Auto save amount) = 28.8
                    start
                    + relativedelta(seconds=5): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "28.8")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.8")],
                    },
                },
            ),
            SubTest(
                description="No auto save for ATM transaction",
                events=[
                    # No auto save because ATM transaction
                    create_outbound_hard_settlement_instruction(
                        amount="10.2",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "18.6")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.8")],
                    },
                },
            ),
            SubTest(
                description="No auto save for zero balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="18.6",
                        event_datetime=start + relativedelta(seconds=7),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=7): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.8")],
                    },
                },
            ),
            SubTest(
                description="No auto save for non primary currency",
                events=[
                    # Acceptance Criteria 008 Non primary currency.
                    create_outbound_hard_settlement_instruction(
                        amount="10.2",
                        denomination="USD",
                        event_datetime=start + relativedelta(seconds=8),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=8): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT_USD, "39.8")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.8")],
                    },
                },
            ),
            SubTest(
                description="No round up autosave when feature disabled",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=9),
                        account_id=accounts.CURRENT_ACCOUNT,
                        roundup_autosave_active="False",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=start + relativedelta(seconds=9),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5.9",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=10): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "24.1")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.8")],
                    },
                },
            ),
            SubTest(
                description="Turn on the round up autosave feature after being disabled",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=11),
                        account_id=accounts.CURRENT_ACCOUNT,
                        roundup_autosave_active="True",
                    ),
                    # Acceptance Criteria 007 auto save for a valid payment type
                    create_outbound_hard_settlement_instruction(
                        amount="6.9",
                        event_datetime=start + relativedelta(seconds=12),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=12): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "17.1")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.9")],
                    },
                },
            ),
            SubTest(
                description="Un-setting optional param to disallow auto save",
                events=[
                    # Unset round up autosave account param
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=13),
                        account_id=accounts.CURRENT_ACCOUNT,
                        roundup_autosave_account=None,
                    ),
                    # No round up autosave as saving account id param not set
                    create_outbound_hard_settlement_instruction(
                        amount="10.2",
                        event_datetime=end,
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"TRANSACTION_TYPE": "PURCHASE"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "6.9")],
                        accounts.ROUND_UP_SAVINGS_ACCOUNT: [(dimensions.DEFAULT, "0.9")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Withdrawals below the Number of Withdrawals Permitted per Month",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=7),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=7): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4940")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=start + relativedelta(seconds=9),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=11),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                # Only 3 excess withdrawal fees will be applied 3 * 2.50 = 7.50
                # Because the other operation is not a ATM withdrawal
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=12): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4792.50")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="250",
                        event_datetime=start + relativedelta(months=1, seconds=6),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=7): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4292.50")],
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
        maximum_daily_withdrawal_by_txn_type = (
            current_account.maximum_daily_withdrawal_by_transaction_type
        )
        instance_params = {
            **parameters.instance_parameters_no_overdraft,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Exceeds daily ATM withdrawal limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM "
                        "withdrawal limit of 1000 GBP to be exceeded.",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "5000")],
                    },
                },
            ),
            SubTest(
                description="Within the daily ATM withdrawal limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4500")],
                    },
                    start
                    + relativedelta(seconds=4): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4000")],
                    },
                },
            ),
            SubTest(
                description="No more ATM withdrawal for the day",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "4000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=5),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        account_id=accounts.CURRENT_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps({"XXX": "0"}),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=start + relativedelta(days=1, seconds=1),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "2500")],
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=3): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "2500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=1, seconds=3),
                        account_id=accounts.CURRENT_ACCOUNT,
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
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                    # Tier set to UPPER TIER so if the daily withdrawal amount
                    # is above 5000 the rejection is raised
                    create_flag_definition_event(
                        timestamp=start + relativedelta(days=1, seconds=5),
                        flag_definition_id=parameters.UPPER_TIER,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(days=1, seconds=5),
                        flag_definition_id=parameters.UPPER_TIER,
                        expiry_timestamp=end,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2, seconds=1): {
                        accounts.CURRENT_ACCOUNT: [(dimensions.DEFAULT, "7500")],
                    },
                },
            ),
            SubTest(
                description="Daily instance limit set higher than tiered limit - rejected",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=2, seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps({"ATM": "6000"}),
                    ),
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=2, seconds=2),
                        account_id=accounts.CURRENT_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot update ATM transaction type limit for "
                        "Maximum Daily Withdrawal Amount because 6000 GBP exceeds "
                        "tiered limit of 5000 GBP for active UPPER_TIER.",
                    )
                ],
            ),
            SubTest(
                description="Instance daily withdrawal ATM limit above tiered limit - rejected",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(days=2, seconds=3),
                        account_id=accounts.CURRENT_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps({"ATM": "5000"}),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5001",
                        event_datetime=start + relativedelta(days=2, seconds=4),
                        target_account_id=accounts.CURRENT_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details=PAYMENT_ATM_INSTRUCTION_DETAILS,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(days=2, seconds=4),
                        account_id=accounts.CURRENT_ACCOUNT,
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
            template_params=parameters.template_parameters_annual_interest,
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
            contract_content=self.smart_contract_path_to_content[files.CURRENT_ACCOUNT_CONTRACT],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=parameters.default_template,
            account_configs=[],
        )
        conversion_2 = conversion_1 + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CURRENT_ACCOUNT_CONTRACT],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=parameters.default_template,
            account_configs=[],
        )

        # Get interest accrual schedules
        run_times_accrue_interest = []
        accrue_interest_date = start + relativedelta(days=1)
        accrue_interest_date = accrue_interest_date.replace(
            hour=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )
        run_times_accrue_interest.append(accrue_interest_date)
        for _ in range(30):
            accrue_interest_date = accrue_interest_date + relativedelta(days=1)
            run_times_accrue_interest.append(accrue_interest_date)

        first_application_date = (start + relativedelta(months=1)).replace(
            day=int(
                parameters.default_instance[
                    current_account.interest_application.PARAM_INTEREST_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    current_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )

        first_fee_application_date = (start + relativedelta(months=1)).replace(
            day=int(
                parameters.default_instance[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversions and Check Schedules at EoM",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.CURRENT_ACCOUNT,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.CURRENT_ACCOUNT,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=run_times_accrue_interest,
                        event_id="ACCRUE_INTEREST",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=31,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            first_application_date,
                        ],
                        event_id="APPLY_INTEREST",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            first_fee_application_date,
                        ],
                        event_id="APPLY_MONTHLY_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
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

    def test_account_conversion_annual_fee_schedule_is_preserved(self):
        """
        Test the annual fee schedule is running as expected after an account conversion
        """

        # relativedelta here is to avoid seeing first application happening on account opening date
        start = default_simulation_start_date + relativedelta(hours=2)
        end = start + relativedelta(years=1, months=1)

        # Define the conversion timings
        conversion = start + relativedelta(hours=1)
        convert_to_version_id = "5"
        convert_to_contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.CURRENT_ACCOUNT_CONTRACT],
            smart_contract_version_id=convert_to_version_id,
            template_params=parameters.default_template,
            account_configs=[],
        )

        first_annual_fee_application_date = (start + relativedelta(years=1)).replace(
            day=int(
                parameters.default_instance[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.default_template[
                    current_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversion and Check Annual Schedule at EoY",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion,
                        account_id=accounts.CURRENT_ACCOUNT,
                        product_version_id=convert_to_version_id,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_annual_fee_application_date,
                        ],
                        event_id="APPLY_ANNUAL_FEE",
                        account_id=accounts.CURRENT_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario, smart_contracts=[convert_to_contract_config])

    def test_derived_parameters(self):
        start = default_simulation_start_date
        end = start + relativedelta(minutes=5)

        sub_tests = [
            SubTest(
                description="Get account tier name derived parameter",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        start, accounts.CURRENT_ACCOUNT, "account_tier_name", parameters.LOWER_TIER
                    )
                ],
            ),
            SubTest(
                description="Get account tier name derived parameter after flag event",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=30),
                        flag_definition_id=parameters.MIDDLE_TIER,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(minutes=1),
                        expiry_timestamp=end,
                        flag_definition_id=parameters.MIDDLE_TIER,
                        account_id=accounts.CURRENT_ACCOUNT,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        start + relativedelta(minutes=2),
                        accounts.CURRENT_ACCOUNT,
                        "account_tier_name",
                        parameters.MIDDLE_TIER,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)
