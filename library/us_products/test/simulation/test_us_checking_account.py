# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from zoneinfo import ZoneInfo

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test import accounts, dimensions, files, parameters
from library.us_products.test.parameters import TEST_DENOMINATION
from library.us_products.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
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
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

# Aliases
_overdraft_coverage = us_checking_account.overdraft_coverage

# Const
default_simulation_start_date = datetime(2023, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))


class USCheckingAccountTest(SimulationTestCase):
    account_id_base = accounts.CHECKING_ACCOUNT
    contract_filepaths = [files.CHECKING_ACCOUNT_CONTRACT]
    rebatable_fee_metadata = {
        us_checking_account.unlimited_fee_rebate.FEE_TYPE_METADATA_KEY: "out_of_network_ATM"
    }
    non_rebatable_fee_metadata = {
        us_checking_account.unlimited_fee_rebate.FEE_TYPE_METADATA_KEY: "FX_FEE"
    }
    excluded_txn_type_metadata = {"type": parameters.EXCLUDED_TRANSACTION}

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
            template_params=template_params or parameters.checking_account_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or parameters.checking_account_instance_params,
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

    def test_validate_primary_denomination(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=3)
        sub_tests = [
            SubTest(
                description="Hard settlement in unsupported denomination "
                "- accepted with force override",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="SGP",
                        instruction_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(BalanceDimensions(denomination="SGP"), "100")],
                    },
                },
            ),
            SubTest(
                description="Hard settlement in unsupported denomination - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="JPY",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in the given denomination, "
                        "transactions must be one of ['USD']",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Hard settlements in supported denomination - accepted",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1499",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="99",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "1400")],
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

    def test_derived_parameters(self):
        start = default_simulation_start_date
        end = start + relativedelta(minutes=5)

        sub_tests = [
            SubTest(
                description="Get active account tier name derived parameter. Since no flag present,"
                "return last value in account_tier_names, i.e. LOWER_TIER",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start,
                        account_id=accounts.CHECKING_ACCOUNT,
                        name=us_checking_account.PARAM_ACTIVE_ACCOUNT_TIER_NAME,
                        value="LOWER_TIER",
                    )
                ],
            ),
            SubTest(
                description="Get active account tier name derived parameter after flag event",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=30),
                        flag_definition_id="MIDDLE_TIER",
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(minutes=1),
                        expiry_timestamp=end,
                        flag_definition_id="MIDDLE_TIER",
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        name=us_checking_account.PARAM_ACTIVE_ACCOUNT_TIER_NAME,
                        value="MIDDLE_TIER",
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

    @ac_coverage(["CPP-1912-AC05", "CPP-1912-AC07"])
    def test_interest_accrual_positive_rate(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=5, minutes=1)

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # round(1000 * round((0.01/365), 10), 5)  +
                # round(2000 * round((0.02/365), 10), 5)  +
                # round(2000 * round((0.035/365), 10), 5) = 0.32877
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.32877")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.32877")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Updated interest rate when balance increases",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5500",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # round(1000 * round((0.01/365), 10), 5)  +
                    # round(2000 * round((0.02/365), 10), 5)  +
                    # round(2000 * round((0.035/365), 10), 5) = 0.32877
                    # 0.32877 + 0.32877 = 0.65754
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.65754")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.65754")),
                        ],
                    },
                    # round(1000 * round((0.01/365), 10), 5)  +
                    # round(2000 * round((0.02/365), 10), 5)  +
                    # round(2000 * round((0.035/365), 10), 5) +
                    # round(5000 * round((0.05/365), 10), 5)  +
                    # round(500  * round((0.06/365), 10), 5)  = 1.09589
                    # 0.65754 + 1.09589 = 1.75343
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343")),
                        ],
                    },
                },
            ),
            SubTest(
                description="No interest accrued for a 0 USD",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10500",
                        event_datetime=start + relativedelta(days=3, seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343"))
                        ],
                    },
                },
            ),
            SubTest(
                description="No interest accrued for a negative balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(days=4, seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=5, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1")),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343"))
                        ],
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

    @ac_coverage(["CPP-1912-AC06", "CPP-1912-AC07"])
    def test_interest_accrual_negative_rate(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=5, minutes=1)
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: dumps(
                {
                    "0.00": "-0.01",
                    "1000.00": "-0.02",
                    "3000.00": "-0.035",
                    "5000.00": "-0.05",
                    "10000.00": "-0.06",
                }
            ),
        }
        first_accrual_event = (start + relativedelta(days=1)).replace(
            hour=int(
                template_params[
                    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR
                ]
            ),
            minute=int(
                template_params[
                    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE
                ]
            ),
            second=int(
                template_params[
                    us_checking_account.tiered_interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Check daily interest calculation after 1 day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                # round(1000 * round((-0.01/365), 10), 5)  +
                # round(2000 * round((-0.02/365), 10), 5)  +
                # round(2000 * round((-0.035/365), 10), 5) = 0.32877 (RECEIVABLE)
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5000")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-0.32877")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.32877")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_accrual_event],
                        event_id=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Updated interest rate when balance increases",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5500",
                        event_datetime=start + relativedelta(days=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    # round(1000 * round((-0.01/365), 10), 5)  +
                    # round(2000 * round((-0.02/365), 10), 5)  +
                    # round(2000 * round((-0.035/365), 10), 5) = 0.32877
                    # 0.32877 + 0.32877 = 0.65754 (RECEIVABLE)
                    start
                    + relativedelta(days=2, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-0.65754")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-0.65754")),
                        ],
                    },
                    # round(1000 * round((-0.01/365), 10), 5)  +
                    # round(2000 * round((-0.02/365), 10), 5)  +
                    # round(2000 * round((-0.035/365), 10), 5) +
                    # round(5000 * round((-0.05/365), 10), 5)  +
                    # round(500  * round((-0.06/365), 10), 5)  = 1.09589
                    # 0.65754 + 1.09589 = 1.75343 (RECEIVABLE)
                    start
                    + relativedelta(days=3, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10500")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343")),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            first_accrual_event + relativedelta(days=i) for i in range(1, 3)
                        ],
                        event_id=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="No interest accrued for a 0 USD",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10500",
                        event_datetime=start + relativedelta(days=3, seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=4, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_accrual_event + relativedelta(days=3)],
                        event_id=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="No interest accrued for a negative balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(days=4, seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=5, seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("-1.75343")),
                        ],
                        accounts.ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-1.75343"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_accrual_event + relativedelta(days=4)],
                        event_id=us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=5,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1913-AC03", "CPP-1913-AC06", "CPP-1913-AC07", "CPP-1913-AC08"])
    def test_interest_application_monthly(self):
        start = default_simulation_start_date.replace(day=15)
        end = datetime(year=2023, month=2, day=28, minute=10, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_DAY: "29",
        }
        first_expected_schedule_datetime = datetime(2023, 1, 29, tzinfo=ZoneInfo("UTC")).replace(
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )
        second_expected_schedule_datetime = first_expected_schedule_datetime.replace(
            month=2, day=28
        )

        sub_tests = [
            SubTest(
                description="Check accrued interest payable to customer - month 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=9),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    # 14 days of interest accrued 500 * 0.0000273973 = 0.01370 * 14 = 0.19180
                    # checking just before interest application
                    first_expected_schedule_datetime
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.19180")),
                            (dimensions.DEFAULT, Decimal("500")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    first_expected_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("500.19")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.19"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_expected_schedule_datetime],
                        event_id=us_checking_account.interest_application.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check accrued interest payable to customer - month 2",
                expected_balances_at_ts={
                    # 30 days of interest accrued 500.19 * 0.0000273973 = 0.01370 * 30 = 0.41100
                    # checking just before interest application
                    second_expected_schedule_datetime
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.41100")),
                            (dimensions.DEFAULT, Decimal("500.19")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.19"))],
                    },
                    second_expected_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("500.60")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.60"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_expected_schedule_datetime],
                        event_id=us_checking_account.interest_application.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=2,
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

    @ac_coverage(["CPP-1913-AC04"])
    def test_interest_application_quarterly(self):
        start = default_simulation_start_date
        end = datetime(year=2023, month=4, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "quarterly"
            ),
        }
        expected_schedule_datetime = datetime(
            year=2023, month=4, day=1, tzinfo=ZoneInfo("UTC")
        ).replace(
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Check accrued interest payable to customer",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=9),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    # 90 days of interest accrued 1000 * 0.0000273973 = 0.02740 * 90 = 2.46600
                    # checking just before interest application
                    expected_schedule_datetime
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("2.46600")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    expected_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1002.47")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("2.47"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_datetime],
                        event_id=us_checking_account.interest_application.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1913-AC05"])
    def test_interest_application_annually(self):
        start = default_simulation_start_date
        end = datetime(year=2024, month=1, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
        }

        expected_schedule_datetime = datetime(
            year=2024, month=1, day=1, tzinfo=ZoneInfo("UTC")
        ).replace(
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_SECOND
                ]
            ),
        )

        sub_tests = [
            SubTest(
                description="Check accrued interest payable to customer",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=9),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    # 365 days of interest accrued 1000 * 0.0000273973 = 0.02740 * 365 = 10.001
                    # checking just before interest application
                    expected_schedule_datetime
                    - relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("10.00100")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    expected_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1010.00")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("10.00"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_datetime],
                        event_id=us_checking_account.interest_application.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
            )
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1911-AC01", "CPP-1911-AC02", "CPP-1911-AC04", "CPP-1911-AC05"])
    def test_dormancy_scenarios(self):
        start = default_simulation_start_date
        end = datetime(year=2023, month=3, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        accrual_run_times = [start + relativedelta(days=i) for i in range(1, 60)]
        application_run_times = [start + relativedelta(months=i, minutes=1) for i in range(1, 3)]

        sub_tests = [
            SubTest(
                description="Postings accepted when dormancy flag off",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Postings rejected when dormancy flag on",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        expiry_timestamp=start + relativedelta(months=1, minutes=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=self.account_id_base,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Account flagged 'Dormant' does "
                        "not accept external transactions.",
                    )
                ],
            ),
            SubTest(
                description="Check that no interest accrued or applied when account dormant",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Check that interest accrued and applied when dormancy flag expires",
                expected_balances_at_ts={
                    end
                    - relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.76720")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    end: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("1000.77")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.77"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=accrual_run_times,
                        event_id=(us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=59,
                    ),
                    ExpectedSchedule(
                        run_times=application_run_times,
                        event_id=(us_checking_account.interest_application.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=2,
                    ),
                ],
            ),
            # TODO: Add coverage for CPP-1911-AC03 when fees are implemented
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_maximum_daily_withdrawal_by_transaction_type(self):
        start = default_simulation_start_date
        end = start + relativedelta(minutes=5)

        sub_tests = [
            SubTest(
                description="Fund the account and Verify atm withdrawal is rejected due to"
                "exceeding limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM withdrawal"
                        " limit of 1000 USD to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="Verify atm withdrawal is successful due to being under limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination="USD",
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "1500")],
                    },
                },
            ),
            SubTest(
                description="Verify additional atm withdrawal is successful due to meeting limit"
                "and charged fees do not contribute to daily transaction limit checks",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="500",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details={"TRANSACTION_TYPE": "ATM"},
                            ),
                            OutboundHardSettlement(
                                amount="5",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.rebatable_fee_metadata,
                            ),
                            OutboundHardSettlement(
                                amount="10",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.non_rebatable_fee_metadata,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=3),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "990")],
                        accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT: [(dimensions.DEFAULT, "5")],
                    },
                },
            ),
            SubTest(
                description="Verify additional atm withdrawal is rejected due to exceeding limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=4),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM withdrawal"
                        " limit of 1000 USD to be exceeded.",
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

    def test_maximum_daily_withdrawal_by_transaction_type_after_parameter_update(self):
        start = default_simulation_start_date
        end = start + relativedelta(minutes=5)

        sub_tests = [
            SubTest(
                description="Fund the account and withdraw the daily limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
            SubTest(
                description="Verify additional atm withdrawal is rejected due to exceeding limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=3),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM withdrawal"
                        " limit of 1000 USD to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="Update the ATM withdrawal limit",
                events=[
                    create_instance_parameter_change_event(
                        start + relativedelta(seconds=4),
                        accounts.CHECKING_ACCOUNT,
                        daily_withdrawal_limit_by_transaction_type=dumps(
                            {
                                "ATM": "1500",
                                "CASH": "500",
                            }
                        ),
                    )
                ],
            ),
            SubTest(
                description="Verify additional atm is accepted due to new limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "500")],
                    },
                },
            ),
            SubTest(
                description="Verify additional atm is rejected due to exceeding new limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"TRANSACTION_TYPE": "ATM"},
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=6),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transactions would cause the maximum daily ATM withdrawal"
                        " limit of 1500 USD to be exceeded.",
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

    @ac_coverage(["CPP-2031-AC05", "CPP-2031-AC06"])
    def test_inactivity_scenarios(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=1)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=(default_simulation_start_date.month + 1),
            day=int(
                parameters.checking_account_instance_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )
        expected_schedule_month_2 = expected_schedule_month_1 + relativedelta(months=1)
        expected_schedule_month_3 = expected_schedule_month_2 + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 100",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_1,
                            expected_schedule_month_2,
                            expected_schedule_month_3,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=3,
                    ),
                ],
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=start + relativedelta(months=2, minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on",
                expected_balances_at_ts={
                    # Inactivity fee applied: 10 (1 month)
                    # Month 1 interest accrued: 31 * ROUND(100 * (0.01/365), 5) = 0.08494
                    start
                    + relativedelta(months=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.08494")),
                            (dimensions.DEFAULT, Decimal("90")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    # Inactivity fee applied: 20 (2 months)
                    # Month 1 interest applied: 0.08
                    # Month 2 interest accrued: 28 * ROUND(90.08 * (0.01/365), 5) = 0.06916
                    start
                    + relativedelta(months=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.06916")),
                            (dimensions.DEFAULT, Decimal("80.08")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.08"))],
                    },
                    # Inactivity fee applied: 20 (2 months)
                    # Interest applied: 0.15 (2 months)
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("80.15")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.15"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity flag has expired and inactivity fee is not charged",
                expected_balances_at_ts={
                    # Inactivity fee applied: 20 (2 months)
                    # Interest applied: 0.15 (2 months)
                    # Month 3 interest accrued: 31 * ROUND(80.15 * (0.01/365), 5) = 0.06820
                    start
                    + relativedelta(months=3): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.06820")),
                            (dimensions.DEFAULT, Decimal("80.15")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.15"))],
                    },
                    # Inactivity fee applied: 20 (months 1 and 2)
                    # Interest applied: 0.22 (months 1, 2, 3)
                    start
                    + relativedelta(months=3, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("80.22")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.22"))],
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

    @ac_coverage(["CPP-2031-AC04", "CPP-2031-AC09", "CPP-2031-AC10", "CPP-2031-AC11"])
    def test_inactivity_scenarios_with_partial_payment(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=10)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=(default_simulation_start_date.month + 1),
            day=int(
                parameters.checking_account_instance_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )
        expected_schedule_month_2 = expected_schedule_month_1 + relativedelta(months=1)
        expected_schedule_month_3 = expected_schedule_month_2 + relativedelta(months=1)
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE: "0",
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: dumps(
                {"UPPER_TIER": "0", "MIDDLE_TIER": "0", "LOWER_TIER": "0"}
            ),
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "5",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 15",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("15")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=start + relativedelta(months=3, minutes=20),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("15")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on - month 1",
                expected_balances_at_ts={
                    # Inactivity fee applied: 10 (1 month)
                    # Month 1 interest accrued: 31 * ROUND(15 * (0.01/365), 5) = 0.01271
                    start
                    + relativedelta(months=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.01271")),
                            (dimensions.DEFAULT, Decimal("5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    # Interest is applied.
                    start
                    + relativedelta(months=1, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("5.01")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.01"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_1,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on uses overdraft limit "
                "- month 2",
                expected_balances_at_ts={
                    # Inactivity fee applied: 20 (2 months)
                    # Interest applied: 0.15 (2 months)
                    expected_schedule_month_2: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.00392")),
                            (dimensions.DEFAULT, Decimal("-4.99")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20.00"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.01"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_2,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
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
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.00392")),
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("9.99")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20.01"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.01"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_3,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, minutes=8): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.00392")),
                            (dimensions.DEFAULT, Decimal("-5")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("4.99")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("25.01"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.01"))],
                    },
                },
            ),
            SubTest(
                description="Partial Fee cleared when account is funded sufficiently",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(months=3, minutes=9),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, minutes=9): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.00392")),
                            (dimensions.DEFAULT, Decimal("0.01")),
                            (dimensions.OUTSTANDING_INACTIVITY_FEE_TRACKER, Decimal("0")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("30"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.01"))],
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

    @ac_coverage(["CPP-2031-AC08"])
    def test_inactivity_fee_applied_with_insufficient_funds(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1)
        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=(default_simulation_start_date.month + 1),
            day=int(
                parameters.checking_account_instance_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
                dumps(
                    {
                        parameters.UPPER_TIER: "0",
                        parameters.MIDDLE_TIER: "0",
                        parameters.LOWER_TIER: "0",
                    }
                )
            ),
        }

        sub_tests = [
            SubTest(
                description="Insufficiently fund the account and apply inactivity flag to account.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=start + relativedelta(months=2, minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("5")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_1,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Validate inactivity fee still applied with insufficient funds.",
                expected_balances_at_ts={
                    expected_schedule_month_1: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                        ],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
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

    @ac_coverage(["CPP-2031-AC12"])
    def test_inactivity_fee_application_on_non_existent_day(self):
        # When the inactivity fee application day is on the 29, 30, or 31 and does not exist for
        # that month, the fee is applied on the previous day (last day of the month).
        start = default_simulation_start_date
        end = start.replace(month=2, day=28, hour=23, minute=59)

        accrual_run_times = [start + relativedelta(days=i) for i in range(1, 59)]  # 58 days
        application_run_times = [start + relativedelta(months=1, minutes=1)]  # 1 interest app day

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR: "23",
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE: "59",
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND: "0",
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY: "31",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 100",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fee applied on end of Feb",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=3),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=end + relativedelta(seconds=1),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    # 29 days of interest accrued: 29 * ROUND(100 * (0.01/365), 5) = 0.07946
                    start
                    + relativedelta(days=29): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.07946")),
                            (dimensions.DEFAULT, Decimal("100.00")),
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    end: {
                        # 1 month of interest applied.
                        # 27 days interest accrued: 27 * ROUND(100.08 * (0.01/365), 5) = 0.07398
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.07398")),
                            (dimensions.DEFAULT, Decimal("90.08")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.08"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[end],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,  # 1 inactivity application on 2023-02-28 23:59:00
                    ),
                    ExpectedSchedule(
                        run_times=accrual_run_times,
                        event_id=(us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=58,  # From 2023-01-01 to 2023-02-28 = 58 days
                    ),
                    ExpectedSchedule(
                        run_times=application_run_times,
                        event_id=(us_checking_account.interest_application.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,  # 1 interest application on 2023-02-01 00:01:00
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

    @ac_coverage(["CPP-1911-AC03"])
    def test_inactivity_fee_account_dormant_and_fee_not_applied(self):
        # Account becomes inactive and inactivity fees are charged and interest accrued/applied.
        # After account becomes dormant, there should be no transactions / interest / fees.
        start = default_simulation_start_date
        end = start + relativedelta(months=3, days=1)

        expected_schedule_month_1 = default_simulation_start_date.replace(
            month=(default_simulation_start_date.month + 1),
            day=int(
                parameters.checking_account_instance_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_DAY
                ]
            ),
            hour=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_HOUR
                ]
            ),
            minute=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_MINUTE
                ]
            ),
            second=int(
                parameters.checking_account_template_params[
                    us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_APPLICATION_SECOND
                ]
            ),
        )
        expected_schedule_month_2 = expected_schedule_month_1 + relativedelta(months=1)
        expected_schedule_month_3 = expected_schedule_month_2 + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 100",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule_month_1,
                            expected_schedule_month_2,
                            expected_schedule_month_3,
                        ],
                        event_id=us_checking_account.inactivity_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=3,
                    ),
                ],
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=start + relativedelta(months=5, minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Inactivity fees applied when inactivity flag on",
                expected_balances_at_ts={
                    # Inactivity fee applied: 10 (1 month)
                    # Month 1 interest accrued: 31 * ROUND(100 * (0.01/365), 5) = 0.08494
                    start
                    + relativedelta(months=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.08494")),
                            (dimensions.DEFAULT, Decimal("90")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                    },
                    # Inactivity fee applied: 20 (2 months)
                    # Month 1 interest applied: 0.08
                    # Month 2 interest accrued: 28 * ROUND(90.08 * (0.01/365), 5) = 0.06916
                    start
                    + relativedelta(months=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0.06916")),
                            (dimensions.DEFAULT, Decimal("80.08")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.08"))],
                    },
                    # Inactivity fee applied: 20 (2 months)
                    # Interest applied: 0.15 (2 months)
                    start
                    + relativedelta(months=2, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("80.15")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.15"))],
                    },
                },
            ),
            SubTest(
                description="Create and apply dormancy flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(months=2, hours=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(months=2, hours=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                        expiry_timestamp=start + relativedelta(months=5, minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, hours=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("80.15")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.15"))],
                    },
                },
            ),
            SubTest(
                description="Account has dormancy flag applied: no fees, no interest",
                expected_balances_at_ts={
                    # No activity fee applied.
                    # No accrued interest.
                    start
                    + relativedelta(months=3, minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("80.15")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                        accounts.INTEREST_PAID_ACCOUNT: [(dimensions.DEFAULT, Decimal("0.15"))],
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

    @ac_coverage(["CPP-2031-AC13"])
    def test_inactivity_fee_closure_with_outstanding_fees(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=5)

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
                dumps(
                    {
                        parameters.UPPER_TIER: "0",
                        parameters.MIDDLE_TIER: "0",
                        parameters.LOWER_TIER: "0",
                    }
                )
            ),
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE_PARTIAL_FEE_ENABLED: "True",
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Create and apply inactivity flag to account",
                events=[
                    create_flag_definition_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=2),
                        flag_definition_id=parameters.TEST_INACTIVITY_FLAG,
                        expiry_timestamp=start + relativedelta(months=5, minutes=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Account closure rejected while outstanding fees have not been paid",
                events=[
                    update_account_status_pending_closure(
                        start + relativedelta(months=4),
                        accounts.CHECKING_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario=test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    @ac_coverage(
        [
            "CPP-1922-AC01",
            "CPP-1922-AC02",
            "CPP-1922-AC03",
            "CPP-1922-AC04",
            "CPP-1922-AC06",
            "CPP-1922-AC07",
            "CPP-1922-AC08",
            "CPP-1922-AC09",
            "CPP-1922-AC13",
            "CPP-1922-AC17",
        ]
    )
    def test_minimum_balance_limit_fee_varying_balances(self):
        start = default_simulation_start_date

        # Schedule run times
        first_schedule_run = datetime(year=2023, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))
        second_schedule_run = datetime(year=2023, month=3, day=29, minute=1, tzinfo=ZoneInfo("UTC"))
        third_schedule_run = datetime(year=2023, month=4, day=29, minute=1, tzinfo=ZoneInfo("UTC"))

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
        }

        # When application day is 29, 30, or 31 and not exist in current month.
        # application should happen on the last day of the month.
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE_DAY: "29",
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                    },
                },
            ),
            SubTest(
                description="Fee charged with insufficient funds takes balance negative",
                expected_balances_at_ts={
                    first_schedule_run: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-15.00")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account with balance under threshold",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="35",
                        event_datetime=first_schedule_run + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(hours=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("20"))],
                    },
                },
            ),
            SubTest(
                description="Fee charged with sufficient funds",
                expected_balances_at_ts={
                    second_schedule_run: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "40"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account with balance greater than threshold",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="110",
                        event_datetime=second_schedule_run + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    second_schedule_run
                    + relativedelta(hours=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("110"))],
                    },
                },
            ),
            SubTest(
                description="Fee not charged with balance greater than threshold",
                expected_balances_at_ts={
                    third_schedule_run: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "110")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "40"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_run, second_schedule_run, third_schedule_run],
                        event_id=(
                            us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT  # noqa: E501
                        ),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=3,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=third_schedule_run,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC15", "CPP-1922-AC16"])
    def test_minimum_balance_limit_fee_skip_first_application_day(self):
        # When account is opened on 15th of Jan and application day is 1st
        # then the first minimum balance fee application should happen only on 1st March.
        start = default_simulation_start_date.replace(day=15)

        # Schedule run times
        first_schedule_run = datetime(year=2023, month=3, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("20"))],
                    },
                },
            ),
            SubTest(
                description="Schedule doesn't run - it is less than one month from account opening",
                expected_balances_at_ts={
                    datetime(year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "20")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="First schedule run - fee is charged",
                expected_balances_at_ts={
                    first_schedule_run: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, "20"),
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_run],
                        event_id=(
                            us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT  # noqa: E501
                        ),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=first_schedule_run,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC14"])
    def test_minimum_balance_limit_fee_ignores_current_day_in_average(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=1)

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_flag_definition_event(
                        timestamp=start,
                        flag_definition_id="UPPER_TIER",
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(seconds=1),
                        flag_definition_id="UPPER_TIER",
                        expiry_timestamp=end,
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="25.01",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "25.01")],
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=35): {
                        # Check balance after outbound hard settlement
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
                    },
                    start
                    + relativedelta(months=1, minutes=2): {
                        # Check balance after minimum monthly balance fee schedule
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0.01")],
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

    @ac_coverage(["CPP-1922-AC10", "CPP-1922-AC11", "CPP-1922-AC12"])
    def test_minimum_balance_limit_fee_partial_fee_collection(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, hours=1)

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",  # noqa: E501
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "5",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }
        # Schedule run times
        first_schedule_run = datetime(year=2023, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC"))

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                    },
                },
            ),
            SubTest(
                description="Fee charged with insufficient funds is partially applied and uses "
                "overdraft",
                expected_balances_at_ts={
                    first_schedule_run: {
                        accounts.CHECKING_ACCOUNT: [
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_run
                    + relativedelta(minutes=2): {
                        accounts.CHECKING_ACCOUNT: [
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
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1922-AC18"])
    def test_outstanding_minimum_balance_fee_prevents_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, hours=1)

        # Set to annually so monthly interest application doesn't apply
        # and change the account balance for the current test.
        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_PARTIAL_FEE_ENABLED: "True",  # noqa: E501
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient balance for fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
            ),
            SubTest(
                description="Verify outstanding minimum balance fee prevents closure",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end, account_id=accounts.CHECKING_ACCOUNT
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    @ac_coverage(["CPP-1991-AC03", "CPP-1991-AC04", "CPP-1991-AC05", "CPP-1991-AC12"])
    def test_paper_statement_fee_scenarios(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(months=4, days=2)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual:
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE: "20",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_HOUR: "23",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_MINUTE: "59",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_SECOND: "59",
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            # Enable Paper Statement Fee
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_DAY: "31",
        }

        # First execution is scheduled for February 31, 2023, which does not exist,
        # ScheduleFailover.FIRST_VALID_DAY_AFTER moves this schedule to the next valid day.
        expected_schedule_1 = default_simulation_start_date.replace(
            month=3, day=1, hour=23, minute=59, second=59
        )
        expected_schedule_2 = expected_schedule_1.replace(month=3, day=31)
        expected_schedule_3 = expected_schedule_2.replace(month=5, day=1)

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-20"))],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Validate Schedule runs on an existent day.",
                expected_balances_at_ts={
                    expected_schedule_1: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_1],
                        event_id=(us_checking_account.paper_statement_fee.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Validate Paper Statement Fee is applied with insufficient funds.",
                expected_balances_at_ts={
                    expected_schedule_2: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-20")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("40"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_2],
                        event_id=(us_checking_account.paper_statement_fee.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Validate Paper Statement Fee is not applied when account is dormant.",
                events=[
                    create_flag_definition_event(
                        timestamp=expected_schedule_2 + relativedelta(seconds=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=expected_schedule_2 + relativedelta(seconds=1),
                        expiry_timestamp=expected_schedule_3 + relativedelta(seconds=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_3: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-20")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("40")),
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_3],
                        event_id=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=3,
                    )
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

    @ac_coverage(["CPP-1921-AC13"])
    def test_paper_statement_fee_application(self):
        start = datetime(2023, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        end = start + relativedelta(months=1, days=15)

        # paper statement fee must be applied greater than 1 month from account opening
        expected_schedule = datetime(2023, 3, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
        }

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Validate paper statement fee application",
                expected_balances_at_ts={
                    expected_schedule: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("80")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule],
                        event_id=(us_checking_account.paper_statement_fee.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
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

    @ac_coverage(["CPP-1991-AC08", "CPP-1991-AC09", "CPP-1991-AC10"])
    def test_paper_statement_fee_partially_applied(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(months=2, days=1)

        expected_schedule_1 = default_simulation_start_date + relativedelta(months=1)
        expected_schedule_2 = expected_schedule_1 + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            # Enable Paper Statement Partial Fee
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED: (
                "True"
            ),
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "5",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }
        sub_tests = [
            SubTest(
                description="Fund account to have just enough for a partial payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("15")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Apply paper statement fee with partial funds available uses overdraft "
                "- month 1",
                expected_balances_at_ts={
                    expected_schedule_1: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_1],
                        event_id=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Apply paper statement fee with partial funds available uses overdraft "
                "- month 2",
                expected_balances_at_ts={
                    expected_schedule_2: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("-5")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("20"),
                            ),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule_2],
                        event_id=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=2,
                    )
                ],
            ),
            SubTest(
                description="Fund account to check remainder of paper statement fee is collected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="25",
                        event_datetime=expected_schedule_2 + relativedelta(minutes=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_2
                    + relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("40"))
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

    @ac_coverage(["CPP-1991-AC14"])
    def test_outstanding_paper_statement_fee_prevents_account_closure(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(months=1, days=1)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            # Enable Paper Statement Partial Fee
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED: (
                "True"
            ),
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }
        sub_tests = [
            SubTest(
                description="Verify outstanding paper statement fee prevents closure",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end, account_id=accounts.CHECKING_ACCOUNT
                    )
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

        self.run_test_scenario(
            test_scenario=test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    def test_paper_statement_fee_not_applied_when_account_dormant(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(months=1, days=1)

        expected_schedule = default_simulation_start_date + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
        }

        sub_tests = [
            SubTest(
                description="Fund account and validate paper statement fee has been applied.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                    start
                    + relativedelta(months=1, days=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("80")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("-100"))],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[expected_schedule],
                        event_id=(us_checking_account.paper_statement_fee.APPLICATION_EVENT),
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
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

    @ac_coverage(["CPP-1991-AC11"])
    def test_paper_statement_fee_not_applied_when_fee_disabled(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        expected_schedule = default_simulation_start_date + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE: "20",
        }

        sub_tests = [
            SubTest(
                description="Initial deposit of 100",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Validate Paper Statement Fee not applied as it has not been enabled.",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=1, seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.ACCRUED_INTEREST_PAYABLE, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("100")),
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_schedule,
                        ],
                        event_id=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    ),
                ],
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1967-AC01", "CPP-1911-AC02"])
    def test_capitalise_accrued_interest_on_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=10, hours=1)

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.deposit_parameters.PARAM_CAPITALISE_ACCRUED_INTEREST_ON_ACCOUNT_CLOSURE: (  # noqa: E501
                "True"
            ),
        }
        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Verify interest is accrued for 10 days",
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "3.28770"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-3.28770")
                        ],
                    },
                },
            ),
            SubTest(
                description="Account closure before interest application capitalised",
                events=[
                    update_account_status_pending_closure(
                        end,
                        accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5003.29"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
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
        )

        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1967-AC01", "CPP-1911-AC04"])
    def test_forfeit_accrued_interest_on_account_closure(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=10, hours=1)

        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
            ),
            SubTest(
                description="Verify interest is accrued for 10 days",
                expected_balances_at_ts={
                    end
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5000"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "3.28770"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (dimensions.DEFAULT, "-3.28770")
                        ],
                    },
                },
            ),
            SubTest(
                description="Account closure",
                events=[
                    update_account_status_pending_closure(
                        end,
                        accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, "5000.00"),
                            (dimensions.ACCRUED_INTEREST_PAYABLE, "0"),
                        ],
                        accounts.ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(dimensions.DEFAULT, "0")],
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

    @ac_coverage(
        [
            "CPP-1921-AC01",
            "CPP-1921-AC02",
            "CPP-1921-AC03",
            "CPP-1921-AC04",
            "CPP-1921-AC05",
            "CPP-1921-AC06",
            "CPP-1921-AC07",
            "CPP-1921-AC08",
            "CPP-1921-AC09",
            "CPP-1921-AC10",
        ]
    )
    def test_maintenance_monthly_fee_application(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=4)

        # Schedule run times
        first_schedule_datetime = datetime(
            year=2023, month=2, day=28, minute=1, tzinfo=ZoneInfo("UTC")
        )
        second_schedule_datetime = datetime(
            year=2023, month=3, day=29, minute=1, tzinfo=ZoneInfo("UTC")
        )
        third_schedule_datetime = datetime(
            year=2023, month=4, day=29, minute=1, tzinfo=ZoneInfo("UTC")
        )

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: ("29"),
        }

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Check monthly maintenance fee not charged when less than a month",
                expected_balances_at_ts={
                    default_simulation_start_date
                    + relativedelta(months=1): {
                        # When account is opened on 1st of Jan and application day is 29th then
                        # the first minimum balance fee application should happen only on 28th Feb.
                        # Thus we check for no balance change during the first month.
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Check monthly maintenance fee charged when more than a month",
                expected_balances_at_ts={
                    first_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("0"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Apply monthly maintenance with insufficient funds",
                expected_balances_at_ts={
                    second_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Monthly maintenance fees not applied when dormancy flag on",
                events=[
                    # Setting dormancy flag on so the fee is not going to be charged
                    create_flag_definition_event(
                        timestamp=third_schedule_datetime - relativedelta(minutes=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                    ),
                    create_flag_event(
                        timestamp=third_schedule_datetime - relativedelta(minutes=1),
                        flag_definition_id=parameters.DORMANCY_FLAG,
                        expiry_timestamp=third_schedule_datetime + relativedelta(seconds=1),
                        account_id=accounts.CHECKING_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    third_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("-5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("10"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[third_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=3,
                    )
                ],
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

    @ac_coverage(["CPP-1921-AC11", "CPP-1921-AC12", "CPP-1921-AC13"])
    def test_maintenance_monthly_fee_application_allow_partial_fee(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1)

        # Schedule run times
        expected_schedule_1 = datetime(year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))
        expected_schedule_2 = expected_schedule_1 + relativedelta(months=1)

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa: E501
                "True"
            ),
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "5",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund account to have just enough for a partial payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("3"))],
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
                        accounts.CHECKING_ACCOUNT: [
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
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Apply monthly maintenance with partial funds available uses overdraft "
                "- month 2",
                expected_balances_at_ts={
                    expected_schedule_2: {
                        accounts.CHECKING_ACCOUNT: [
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
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_2
                    + relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [
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
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    expected_schedule_2
                    + relativedelta(minutes=2): {
                        accounts.CHECKING_ACCOUNT: [
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
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1921-AC14"])
    def test_maintenance_monthly_fee_closure_with_outstanding_fees(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        # Schedule run times
        schedule_datetime = datetime(year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC"))

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa: E501
                "True"
            ),
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }

        sub_tests = [
            SubTest(
                description="Fund account with insufficient funds",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
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
                        accounts.CHECKING_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )
        self.run_test_scenario(
            test_scenario=test_scenario,
            expected_simulation_error=generic_error("Cannot close account with outstanding fees."),
        )

    @ac_coverage(["CPP-1916-AC03"])
    def test_overdraft_coverage_arranged_not_set_unarranged_not_set_with_opt_in(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        instance_parameters = {
            **parameters.checking_account_instance_params,
            _overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "",
            _overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3500",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -3500, which exceeds the available "
                        "balance of USD 3000.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2500",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "500")],
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
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            InboundHardSettlement(
                                amount="750",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=4),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "250")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(
        ["CPP-1916-AC04", "CPP-1916-AC05", "CPP-1916-AC06", "CPP-1916-AC07", "CPP-1916-AC08"]
    )
    def test_overdraft_coverage_arranged_set_unarranged_not_set_with_opt_in_with_param_change(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=14)
        instance_parameters = {
            **parameters.checking_account_instance_params,
            _overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100",
            _overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="CPP-1916-AC04: Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3150",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -3150, which exceeds the available "
                        "balance of USD 3100.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3050",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                },
            ),
            SubTest(
                description="CPP-1916-AC05: Pay overdraft, Change arranged overdraft: 100 to 50, "
                "reject -100 Debit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=5),
                        account_id=accounts.CHECKING_ACCOUNT,
                        **{_overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "50"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=6),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -100, which exceeds the available "
                        "balance of USD 50.",
                    )
                ],
            ),
            SubTest(
                description="CPP-1916-AC06: Change arranged overdraft: 50 to 0, reject -100 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=7),
                        account_id=accounts.CHECKING_ACCOUNT,
                        **{_overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=8),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=8): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=8),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -100, which exceeds the available "
                        "balance of USD 0.",
                    )
                ],
            ),
            SubTest(
                description="Change arranged overdraft: 0 to 100, Accept -100 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=9),
                        account_id=accounts.CHECKING_ACCOUNT,
                        **{_overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "100"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start + relativedelta(seconds=10),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=10): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-100")],
                    },
                },
            ),
            SubTest(
                description="CPP-1916-AC07: Change arranged overdraft: 100 to 50, Reject -0.01 "
                "Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=11),
                        account_id=accounts.CHECKING_ACCOUNT,
                        **{_overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "50"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="0.01",
                        event_datetime=start + relativedelta(seconds=12),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=12): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-100")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=12),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -0.01, which exceeds the available "
                        "balance of USD -50.",
                    )
                ],
            ),
            SubTest(
                description="CPP-1916-AC08: Change arranged overdraft: 50 to 150, Accept -10 Debit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + relativedelta(seconds=13),
                        account_id=accounts.CHECKING_ACCOUNT,
                        **{_overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "150"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=start + relativedelta(seconds=14),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=14): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-110")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_coverage_arranged_not_set_unarranged_set_with_opt_in(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=4)
        instance_parameters = {
            **parameters.checking_account_instance_params,
            _overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "",
            _overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "50",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound over balance limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3100",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -3100, which exceeds the available "
                        "balance of USD 3050.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound under current balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3050",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-50")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    @ac_coverage(["CPP-1917-AC02", "CPP-1917-AC03"])
    def test_overdraft_coverage_arranged_set_unarranged_set_with_opt_in(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=6)

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Reject outbound greater than available balance + arranged and "
                "unarranged overdraft",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3155",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=2),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -3155, which exceeds the available "
                        "balance of USD 3150.",
                    )
                ],
            ),
            SubTest(
                description="Reject excluded txn greater than available balance + arranged and "
                "unarranged overdraft",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3155",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details=self.excluded_txn_type_metadata,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=3),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -3155, which exceeds the available "
                        "balance of USD 3150.",
                    )
                ],
            ),
            SubTest(
                description="Accept outbound less than available balance + arranged and unarranged "
                "overdraft",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3145",
                        event_datetime=start + relativedelta(seconds=4),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-145")],
                    },
                },
            ),
            SubTest(
                description="Further account funding",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3145",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Excluded txn greater than available balance uses overdraft limit due "
                "to opt-in being set to True",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3001",
                        event_datetime=start + relativedelta(seconds=6),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details=self.excluded_txn_type_metadata,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-1")],
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

    @ac_coverage(["CPP-1917-AC04"])
    def test_overdraft_coverage_without_opt_in(self):
        start = default_simulation_start_date
        end = start + relativedelta(seconds=10)
        instance_parameters = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_OVERDRAFT_OPT_IN: "false",
        }

        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Due to not opting in reject excluded transaction type outbound  "
                "greater than available balance but less than available balance + arranged and "
                "unarranged overdraft",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3001",
                        event_datetime=start + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                        instruction_details=self.excluded_txn_type_metadata,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=1),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="posting_type='excluded_transaction_type' exceeds the "
                        "total available balance of the account. This transaction is an excluded "
                        "transaction type which requires overdraft coverage opt-in to utilise the "
                        "overdraft limit.",
                    )
                ],
            ),
            SubTest(
                description="Non excluded transaction uses the overdraft limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3001",
                        event_datetime=start + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-1")],
                    },
                },
            ),
            SubTest(
                description="Further fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3001",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=3): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Excluded txn first in batch is accepted as the excluded transaction "
                "type amount is less than the available balance",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="2990",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.excluded_txn_type_metadata,
                            ),
                            OutboundHardSettlement(
                                amount="110",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=4),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=4): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-100")],
                    },
                },
            ),
            SubTest(
                description="Further fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3100",
                        event_datetime=start + relativedelta(seconds=5),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=5): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Excluded txn last in batch is rejected as the excluded transaction "
                "type amount would utilise the overdraft limit and opt-in is False",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="2990",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            OutboundHardSettlement(
                                amount="110",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.excluded_txn_type_metadata,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=6),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=6): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + relativedelta(seconds=6),
                        account_id=accounts.CHECKING_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="posting_type='excluded_transaction_type' exceeds the "
                        "total available balance of the account. This transaction is an excluded "
                        "transaction type which requires overdraft coverage opt-in to utilise the "
                        "overdraft limit.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_parameters
        )
        self.run_test_scenario(test_scenario)

    def test_partial_payment_fee_hierarchy(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2)

        maintenance_fee_expected_schedule = datetime(
            year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )
        paper_statement_fee_expected_schedule = start + relativedelta(months=1, days=1)

        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Minimum Balance Fee
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Disable Inactivity Fee
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            # Enable Partial Payments for Paper Statement Fee
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED: (
                "True"
            ),
            # Enable Maintenance Fees
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa
                "True"
            ),
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
        }

        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.maintenance_fees.PARAM_MAINTENANCE_FEE_APPLICATION_DAY: "1",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_DAY: "2",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED: "True",
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }
        # Paper Statement Fee: $20
        # Maintenance Fee: $5
        sub_tests = [
            SubTest(
                description="Fund account to have just enough for a "
                "maintenance fee partial payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Partially apply monthly maintenance fee.",
                expected_balances_at_ts={
                    maintenance_fee_expected_schedule: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[maintenance_fee_expected_schedule],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Partially apply paper statement fee.",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[paper_statement_fee_expected_schedule],
                        event_id=us_checking_account.paper_statement_fee.APPLICATION_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    paper_statement_fee_expected_schedule: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("20"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Fund account to pay outstanding maintenance fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2",
                        event_datetime=paper_statement_fee_expected_schedule
                        + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    paper_statement_fee_expected_schedule
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("20"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    }
                },
            ),
            SubTest(
                description="Fund account to pay outstanding paper statement fee.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20",
                        event_datetime=paper_statement_fee_expected_schedule
                        + relativedelta(seconds=2),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    paper_statement_fee_expected_schedule
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                        accounts.PAPER_STATEMENT_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("20"))
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

    @ac_coverage(["CPP-1996-AC02", "CPP-1996-AC04"])
    def test_atm_fee_rebate(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1)
        sub_tests = [
            SubTest(
                description="Fund Account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "3000")],
                    },
                },
            ),
            SubTest(
                description="Charge Fees on withdrawal",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="100",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            OutboundHardSettlement(
                                amount="5",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.rebatable_fee_metadata,
                            ),
                            OutboundHardSettlement(
                                amount="10",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.non_rebatable_fee_metadata,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=1),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "2890")],
                        accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT: [(dimensions.DEFAULT, "5")],
                    },
                },
            ),
            SubTest(
                description="Ensure rebatable fees are excluded from overdraft checks",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                # 2890 balance + 150 overdraft limit
                                amount="3040",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            OutboundHardSettlement(
                                amount="5",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.rebatable_fee_metadata,
                            ),
                        ],
                        event_datetime=start + relativedelta(seconds=2),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, "-150")],
                        accounts.OUT_OF_NETWORK_ATM_FEE_REBATE_ACCOUNT: [
                            (dimensions.DEFAULT, "10")
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_fee_rebate_and_partial_fee_collection(self):
        start = default_simulation_start_date
        maintenance_fee_expected_schedule = datetime(
            year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )
        end = maintenance_fee_expected_schedule + relativedelta(seconds=1)
        template_params = {
            **parameters.checking_account_template_params,
            # Disable Interest Accrual
            us_checking_account.tiered_interest_accrual.PARAM_TIERED_INTEREST_RATES: (
                dumps({"0.00": "0.00"})
            ),
            # Disable Other Fees
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.inactivity_fee.PARAM_INACTIVITY_FEE: "0",
            us_checking_account.paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE: "0",
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            # Enable Maintenance Fees
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa
                "True"
            ),
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
        }
        instance_params = {
            **parameters.checking_account_instance_params,
            us_checking_account.overdraft_coverage.PARAM_ARRANGED_OVERDRAFT_AMOUNT: "0",
            us_checking_account.overdraft_coverage.PARAM_UNARRANGED_OVERDRAFT_AMOUNT: "0",
        }
        sub_tests = [
            SubTest(
                description="Fund account to have just enough for a "
                "maintenance fee partial payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("0")),
                            (
                                dimensions.OUTSTANDING_MONTHLY_PAPER_STATEMENT_FEE_TRACKER,
                                Decimal("0"),
                            ),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Partially apply monthly maintenance fee.",
                expected_balances_at_ts={
                    maintenance_fee_expected_schedule: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("2")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("3"))
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[maintenance_fee_expected_schedule],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=1,
                    )
                ],
            ),
            SubTest(
                description="Batch containing $101 credit and $100 withdrawal with rebatable fee "
                "of $1",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                amount="100",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                            OutboundHardSettlement(
                                amount="1",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                                instruction_details=self.rebatable_fee_metadata,
                            ),
                            InboundHardSettlement(
                                amount="101",
                                target_account_id=accounts.CHECKING_ACCOUNT,
                                internal_account_id=accounts.DEPOSIT_ACCOUNT,
                                denomination=parameters.TEST_DENOMINATION,
                            ),
                        ],
                        event_datetime=maintenance_fee_expected_schedule + relativedelta(seconds=1),
                    )
                ],
                expected_balances_at_ts={
                    maintenance_fee_expected_schedule
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.OUTSTANDING_MONTHLY_MAINTENANCE_FEE_TRACKER, Decimal("1")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("4"))
                        ],
                    }
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

    @ac_coverage(["CPP-1925-AC01", "CPP-1925-AC02", "CPP-1925-AC05", "CPP-1925-AC06"])
    def test_maintenance_monthly_fee_waived_minimum_balance(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1)

        # Schedule run times
        first_schedule_datetime = datetime(
            year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )
        second_schedule_datetime = datetime(
            year=2023, month=3, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa: E501
                "True"
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund account to meet minimum balance waive fee requirement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Do not apply maintenance fee with minimum balance requirement met",
                expected_balances_at_ts={
                    first_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("100"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Outbound hard settlement to bring balance below minimum requirement",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=first_schedule_datetime + relativedelta(minutes=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_datetime
                    + relativedelta(minutes=1): {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("10"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Apply maintenance fee with minimum balance below requirement",
                expected_balances_at_ts={
                    second_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [(dimensions.DEFAULT, Decimal("5"))],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[second_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=2,
                    )
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

    @ac_coverage(["CPP-1925-AC03", "CPP-1925-AC04", "CPP-1925-AC07", "CPP-1925-AC08"])
    def test_maintenance_monthly_fee_waived_minimum_deposit(self):
        start = default_simulation_start_date
        end = start + relativedelta(months=2, days=1)

        # Schedule run times
        first_schedule_datetime = datetime(
            year=2023, month=2, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )
        second_schedule_datetime = datetime(
            year=2023, month=3, day=1, minute=1, tzinfo=ZoneInfo("UTC")
        )

        template_params = {
            **parameters.checking_account_template_params,
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_BY_TIER: (
                dumps(parameters.MONTHLY_MAINTENANCE_FEE_BY_TIER)
            ),
            us_checking_account.interest_application.PARAM_INTEREST_APPLICATION_FREQUENCY: (
                "annually"
            ),
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_FEE: "0",
            us_checking_account.maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_PARTIAL_FEE_ENABLED: (  # noqa: E501
                "True"
            ),
            # Set the min balance threshold to a high value so that we do not accidentally waive
            # the monthly maintenance fee.
            us_checking_account.minimum_monthly_balance.PARAM_MINIMUM_BALANCE_THRESHOLD_BY_TIER: (
                dumps(
                    {
                        parameters.LOWER_TIER: "1000",
                        parameters.MIDDLE_TIER: "2000",
                        parameters.UPPER_TIER: "3000",
                    }
                )
            ),
        }

        sub_tests = [
            SubTest(
                description="Fund account to meet deposit waive fee requirement",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=start,
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"type": "direct_deposit"},
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("100")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Do not apply maintenance fee with deposit requirement met",
                expected_balances_at_ts={
                    first_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("100")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("0")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Fund account with non direct deposit transaction",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=first_schedule_datetime + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_datetime
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("200")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("0")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account with inbound auth direct deposit transaction",
                events=[
                    create_inbound_authorisation_instruction(
                        amount="100",
                        event_datetime=first_schedule_datetime + relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"type": "direct_deposit"},
                    ),
                ],
                expected_balances_at_ts={
                    first_schedule_datetime
                    + relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("200")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("0")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Fund account to meet deposit waive fee requirement on application day",
                events=[
                    # This inbound hard settlement will be counted towards next months deposits.
                    # This is because it is on the same day as the application day.
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=second_schedule_datetime - relativedelta(seconds=1),
                        target_account_id=accounts.CHECKING_ACCOUNT,
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        denomination=TEST_DENOMINATION,
                        instruction_details={"type": "direct_deposit"},
                    ),
                ],
                expected_balances_at_ts={
                    second_schedule_datetime
                    - relativedelta(seconds=1): {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("300")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("100")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("0"))
                        ],
                    },
                },
            ),
            SubTest(
                description="Apply maintenance fee with no direct deposits in last month",
                expected_balances_at_ts={
                    second_schedule_datetime: {
                        accounts.CHECKING_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("295")),
                            (dimensions.DIRECT_DEPOSIT_TRACKER, Decimal("100")),
                        ],
                        accounts.MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (dimensions.DEFAULT, Decimal("5"))
                        ],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[first_schedule_datetime, second_schedule_datetime],
                        event_id=us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                        account_id=accounts.CHECKING_ACCOUNT,
                        count=2,
                    )
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
