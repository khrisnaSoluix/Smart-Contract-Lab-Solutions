# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import unittest
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# common
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedRejection,
    SupervisorConfig,
    SimulationTestScenario,
    SubTest,
    ExpectedWorkflow,
    ExpectedDerivedParameter,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_account_plan_assoc_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)

# Line of Credit constants
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.test_parameters as test_parameters

LINE_OF_CREDIT = "line_of_credit"
DRAWDOWN_LOAN = "drawdown_loan"
DEFAULT_PLAN_ID = "1"

DRAWDOWN_ACC_PREFIX = f"{accounts.DRAWDOWN_LOAN_ACCOUNT} "
DRAWDOWN_0 = f"{DRAWDOWN_ACC_PREFIX}0"
DRAWDOWN_1 = f"{DRAWDOWN_ACC_PREFIX}1"

default_loan_instance_params = test_parameters.loan_instance_params
default_loan_template_params = test_parameters.loan_template_params
default_loc_instance_params = test_parameters.loc_instance_params
default_loc_template_params = test_parameters.loc_template_params


class LOCSupervisorTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [
            contract_files.LOAN_CONTRACT,
            contract_files.LOC_CONTRACT,
            contract_files.LOC_SUPERVISOR,
        ]

        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            LINE_OF_CREDIT: "1000",
            DRAWDOWN_LOAN: "2000",
        }

        super().setUpClass()

    def _get_default_supervisor_config(
        self,
        loc_instance_params=default_loc_instance_params,
        loc_template_params=default_loc_template_params,
        loan_instance_params=default_loan_instance_params,
        loan_template_params=default_loan_template_params,
        loan_instances=1,
    ):
        loc_supervisee = ContractConfig(
            template_params=loc_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=loc_instance_params,
                    account_id_base=f"{accounts.LOC_ACCOUNT} ",
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.LOC_CONTRACT],
            clu_resource_id=LINE_OF_CREDIT,
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS[LINE_OF_CREDIT],
        )
        loan_supervisee = ContractConfig(
            template_params=loan_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=loan_instance_params,
                    account_id_base=DRAWDOWN_ACC_PREFIX,
                    number_of_accounts=loan_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.LOAN_CONTRACT],
            clu_resource_id=DRAWDOWN_LOAN,
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS[DRAWDOWN_LOAN],
        )

        supervisor_config = SupervisorConfig(
            supervisor_contract=self.smart_contract_path_to_content[contract_files.LOC_SUPERVISOR],
            supervisee_contracts=[
                loc_supervisee,
                loan_supervisee,
            ],
            supervisor_contract_version_id="supervisor version 1",
            plan_id=DEFAULT_PLAN_ID,
        )

        return supervisor_config

    def test_loan_disbursement(self):
        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=1, hour=12, minute=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Initial loan disbursement",
                expected_balances_at_ts={
                    end: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "1000"),
                        ],
                        f"{accounts.DEPOSIT_ACCOUNT}": [
                            (dimensions.DEFAULT, "1000"),
                        ],
                    }
                },
            )
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(loan_instances=1),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_1_A_B_loc_limits_based_on_outstanding_principal(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=2, day=6, tzinfo=timezone.utc)

        # reducing so that we do not hit the credit_limit
        loc_template_params = default_loc_template_params.copy()
        loc_template_params["maximum_loan_amount"] = "3000"
        loc_template_params["minimum_loan_amount"] = "500"
        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["credit_limit"] = "7000"
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["total_term"] = "3"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, Decimal("6000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Drawdown over remaining credit limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Attempted drawdown 2000 GBP exceeds the remaining "
                        "limit of 1000.00 GBP, based on outstanding principal",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="Drawdown below remaining credit limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, Decimal("6500")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Drawdown above remaining credit limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="501",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated
                        rejection_reason="Attempted drawdown 501 GBP exceeds the remaining "
                        "limit of 500.00 GBP, based on outstanding principal",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="Pay some due principal to reduce outstanding principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2012.38",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=4),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=4): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, Decimal("4487.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Large drawdown above updated limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated. The remaining limit is
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        rejection_reason="Attempted drawdown 3000 GBP exceeds the remaining "
                        "limit of 2494.54 GBP, based on outstanding principal",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="Smaller drawdown accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=7),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=7): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, Decimal("5487.62")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_3_A_B_loan_limits_respected_by_supervisor(self):
        # The 3. scenarios are tested more thoroughly on the loc contract - here we are just
        # checking that the Rejections raised by the loc propagate correctly

        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 2, tzinfo=timezone.utc)

        # reducing so that we do not hit the credit_limit
        loc_template_params = default_loc_template_params.copy()
        loc_template_params["maximum_loan_amount"] = "2000"
        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["credit_limit"] = "10000"

        sub_tests = [
            SubTest(
                description="Drawdown over maximum loan amount limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2001",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated. The remaining limit is
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        rejection_reason="Cannot create loan larger than maximum loan amount "
                        "limit of: 2000.",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_4_A_B_C_daily_accrual(self):
        start = datetime(year=2020, month=1, day=10, hour=23, minute=59, tzinfo=timezone.utc)
        before_accrual_time = start + relativedelta(day=11, hour=22, minute=29)
        after_accrual_time = start + relativedelta(day=11, hour=22, minute=31)

        loc_template_params = default_loc_template_params.copy()
        new_accrual_time = {
            "interest_accrual_hour": "22",
            "interest_accrual_minute": "30",
            "interest_accrual_second": "0",
        }
        loc_template_params.update(new_accrual_time)

        sub_tests = [
            SubTest(
                description="check interest accrual receivable",
                expected_balances_at_ts={
                    before_accrual_time: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.INTERNAL_CONTRA, "0"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                    after_accrual_time: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, Decimal("1000"))],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=after_accrual_time,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                loan_instances=1,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_6_a_b_c_d_due_amount_calculation_with_extra_interest(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        end = datetime(year=2020, month=3, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for second period with no extra interest",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_6_d_due_amount_calculation_excludes_loans_less_than_month_old(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        # 2 weeks before due amount calc
        new_loan_opening = datetime(year=2020, month=1, day=22, second=2, tzinfo=timezone.utc)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        end = datetime(year=2020, month=3, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_0_instance_params = default_loan_instance_params.copy()
        loan_0_instance_params["principal"] = "3000"
        loan_0_instance_params["loan_start_date"] = "2020-01-01"
        loan_0_instance_params["fixed_interest_rate"] = "0.031"

        loan_1_instance_params = loan_0_instance_params.copy()
        loan_1_instance_params["loan_start_date"] = str(new_loan_opening.date())

        sub_tests = [
            SubTest(
                description="Open a loan within a month of due amount calculation date",
                events=[
                    create_account_instruction(
                        timestamp=new_loan_opening,
                        account_id=DRAWDOWN_1,
                        product_id=self.DEFAULT_SUPERVISEE_VERSION_IDS["drawdown_loan"],
                        instance_param_vals=loan_1_instance_params,
                    ),
                    create_account_plan_assoc_instruction(
                        timestamp=new_loan_opening,
                        assoc_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT} 1 assoc",
                        account_id=DRAWDOWN_1,
                        plan_id=DEFAULT_PLAN_ID,
                    ),
                ],
            ),
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    # this is considerably later than the check above, but also before the next one
                    new_loan_opening: {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-22 to 2020-2-5 at 3.1% on $3000 (i.e. 14 days)
                            # so 14 * round(3000 * 0.031 / 365, 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("3.56706")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("3000")),
                            # All due amounts are 0 as loan is < 1 month old and not considered
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("3.56706")),
                        ],
                    },
                },
            ),
            # This subtest validates that there's no extra interest in the second period
            # for the first loan, and extra interest for the second loan
            SubTest(
                description="Check Due Amounts for second period",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.17")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 14 extra accruals
                            # 14 * round(3000 * 0.031 / 365 ,5) = 3.57
                            (dimensions.INTEREST_DUE, Decimal("10.96")),
                            # Note the slight discrepancy for this loan due to start date diff
                            (dimensions.PRINCIPAL_DUE, Decimal("246.83")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=1,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_0_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_a_b_c_d_overdue_fees_and_notifications(self):
        due_amount_calc_day = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=timezone.utc)
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(2020, 2, 10, 0, 0, 3, tzinfo=timezone.utc)
        overdue_check_date_2 = datetime(2020, 3, 10, 0, 0, 3, tzinfo=timezone.utc)
        end = datetime(year=2020, month=3, day=15, hour=12, minute=1, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = "5"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_a_c_d_overdue_schedules_correct_day_1_day_repayment_period(self):
        due_amount_calc_day = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=timezone.utc)
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(2020, 2, 6, 0, 0, 3, tzinfo=timezone.utc)
        overdue_check_date_2 = datetime(2020, 3, 6, 0, 0, 3, tzinfo=timezone.utc)
        end = datetime(year=2020, month=4, day=1, hour=12, minute=1, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = "1"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_a_c_d_overdue_schedules_correct_day_27_day_repayment_period(self):
        due_amount_calc_day = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=timezone.utc)
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(2020, 3, 3, 0, 0, 3, tzinfo=timezone.utc)
        overdue_check_date_2 = datetime(2020, 4, 1, 0, 0, 3, tzinfo=timezone.utc)
        end = datetime(year=2020, month=4, day=1, hour=12, minute=1, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = "27"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_e_penalty_interest(self):
        due_amount_calc_day = 5
        repayment_period = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(
            year=2020,
            month=2,
            day=due_amount_calc_day + repayment_period,
            second=3,
            tzinfo=timezone.utc,
        )
        end = overdue_check_date_1 + relativedelta(days=5)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = str(repayment_period)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params["penalty_interest_rate"] = "0.043"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fee and notification and delinquent checks made",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amounts moved before accruing penalties",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check penalties accrued",
                expected_balances_at_ts={
                    end: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # overdue balance 255.24
                            # 5 * round(255.24 * 0.043 / 365 , 2) = 0.15
                            (dimensions.PENALTIES, Decimal("0.15")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.PENALTIES, Decimal("0.15")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
                loan_template_params=loan_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_e_penalty_interest_include_base_rate(self):
        due_amount_calc_day = 5
        repayment_period = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(
            year=2020,
            month=2,
            day=due_amount_calc_day + repayment_period,
            second=3,
            tzinfo=timezone.utc,
        )
        end = overdue_check_date_1 + relativedelta(days=5)

        loc_instance_params = default_loc_instance_params.copy()
        loc_template_params = default_loc_template_params.copy()

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params["penalty_interest_rate"] = "0.043"
        loan_template_params["penalty_includes_base_rate"] = "True"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fee and notification and delinquent checks made",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amounts moved before accruing penalties",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check penalties accrued",
                expected_balances_at_ts={
                    end: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # overdue balance 255.24
                            # 5 * round(255.24 * (0.031+0.043) / 365, 2) = 0.25
                            (dimensions.PENALTIES, Decimal("0.25")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.PENALTIES, Decimal("0.25")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
                loan_template_params=loan_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_7_f_delinquency_schedules_correct_day_5_day_grace_period(self):
        due_amount_calc_day = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        due_check_date_1 = datetime(2020, 2, 5, 0, 0, 2, tzinfo=timezone.utc)
        due_check_date_2 = datetime(2020, 3, 5, 0, 0, 2, tzinfo=timezone.utc)
        overdue_check_date_1 = datetime(2020, 2, 10, 0, 0, 3, tzinfo=timezone.utc)
        overdue_check_date_2 = datetime(2020, 3, 10, 0, 0, 3, tzinfo=timezone.utc)
        delinquency_check_date_1 = datetime(2020, 3, 15, 0, 0, 2, tzinfo=timezone.utc)
        delinquency_check_date_2 = datetime(2020, 3, 15, 0, 0, 2, tzinfo=timezone.utc)
        end = datetime(year=2020, month=4, day=1, hour=12, minute=1, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = "5"
        loc_template_params["grace_period"] = "5"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "510.48",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type="LINE_OF_CREDIT_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT} 0",
                            "repayment_amount": "508.44",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        run_times=[delinquency_check_date_1, delinquency_check_date_2],
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_8_repayment_processing_single_loan(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        end = datetime(year=2020, month=3, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for second period",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay all overdue/due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="534.46",
                        denomination="GBP",
                        event_datetime=due_amount_calc_2 + relativedelta(hours=1),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_2
                    + relativedelta(hours=1): {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=1,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_8_repayment_processing_multiple_loans_and_partial_repayments(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=2, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay partially",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="300",
                        denomination="GBP",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=1),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("192.64")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay remainder",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="210.48",
                        denomination="GBP",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=2),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=2): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_8_penalty_interest_and_fees_repayment(self):
        due_amount_calc_day = 5

        start = datetime(year=2020, month=1, day=1, hour=12, minute=0, tzinfo=timezone.utc)
        overdue_check_date = datetime(2020, 2, 10, 0, 0, 3, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=16, hour=12, minute=1, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["repayment_period"] = "5"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params["penalty_interest_rate"] = "0.043"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Overdue amounts updated and fee is charged",
                expected_balances_at_ts={
                    overdue_check_date: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        DRAWDOWN_0: [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        DRAWDOWN_1: [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check penalty interest accrued on overdue",
                expected_balances_at_ts={
                    overdue_check_date
                    + relativedelta(days=5): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        DRAWDOWN_0: [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # overdue balance 255.24
                            # 5 * round(255.24 * 0.031 / 365 , 5) = 0.15
                            (dimensions.PENALTIES, Decimal("0.15")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.PENALTIES, Decimal("0.15")),
                        ],
                    },
                },
            ),
            SubTest(
                description="send repayment posting that will repay all addresses",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        # 255.24 overdue + 0.15 penalties per Loan + 25 penalties on LOC
                        amount="535.78",
                        denomination="GBP",
                        event_datetime=overdue_check_date + relativedelta(days=5, hours=1),
                        instruction_details={"event": "INCOMING_REPAYMENT"},
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    overdue_check_date
                    + relativedelta(days=5, hours=1): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "0"),
                        ],
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
                loan_template_params=loan_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_8_repayment_processing_multiple_loans_targeted_repayment(self):
        # loan_0's balances shouldnt change throughout
        expected_loan_0_balances = [
            (dimensions.DEFAULT, Decimal("0")),
            (dimensions.PRINCIPAL, Decimal("2753.68")),
            (dimensions.EMI, Decimal("254.22")),
            (dimensions.INTEREST_DUE, Decimal("8.92")),
            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
        ]
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=2, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: expected_loan_0_balances,
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Send partial targeted repayment to loan_1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="246.32",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": DRAWDOWN_1,
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=1),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=1): {
                        DRAWDOWN_0: expected_loan_0_balances,
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Invalid overpayment behaves the same for targeted repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="10000",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": DRAWDOWN_0,
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=2),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Repayment amount 10000.00 exceeds total outstanding "
                        "+ overpayment fees 3036.46",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="Repay interest due on loan 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        amount="8.92",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": DRAWDOWN_1,
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=3),
                        internal_account_id=accounts.DUMMY_CONTRA,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=3): {
                        DRAWDOWN_0: expected_loan_0_balances,
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_9_a_c_d_overpayment_reduces_emi_results_in_fee_and_is_reflected_in_accruals(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        end = due_amount_calc_3 + relativedelta(hours=6)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"
        loc_instance_params["credit_limit"] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["overpayment_impact_preference"] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make postings to use credit limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, "6000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                            # no overpayments to expected interest == actual interest
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.91765")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.91765")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            # All accrued interest is reset on due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Overpayment made on a single loan",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2, so overpay by 500 to reduce EMI.
                        # A fee of 1% is charged, so required overpayment is
                        # round(500/(1-0.99),2) = 505.05
                        amount="2517.43",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1502.73")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # All accrued interest is reset on due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME}": [
                            (dimensions.DEFAULT, Decimal("5.05")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Accrual after Overpayment",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1502.73")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # accruing on 1502.73 instead of 2002.73
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.12763")),
                            # still accruing on 2002.73
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        # Unchanged as no overpayment affects this account
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Still accruing on 2002.73
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts reflect updated EMI",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("752.15")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            # EMI is updated to reflect overpayment
                            (dimensions.EMI, Decimal("754.28")),
                            # Interest accrued at 0.12763 per day vs 0.17009 expected (ignoring
                            # overpayments), so interest due is 3.7 vs 4.93 expected and the
                            # excess is 1.23
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("1.23")),
                            (dimensions.INTEREST_DUE, Decimal("3.7")),
                            (dimensions.PRINCIPAL_DUE, Decimal("750.58")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1000.24")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Final Due Amounts - no further change to EMI",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            (dimensions.EMI, Decimal("754.28")),
                            # Interest accrued at 0.06388 per day vs 0.10645 expected (ignoring
                            # overpayments), so interest due is 1.98 vs 3.30 expected and the
                            # extra excess is 1.32
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("2.55")),
                            # Note: due amounts are < EMI
                            (dimensions.INTEREST_DUE, Decimal("1.98")),
                            (dimensions.PRINCIPAL_DUE, Decimal("752.15")),
                            (dimensions.INTEREST_OVERDUE, Decimal("3.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("750.58")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Note: due amounts are < EMI
                            (dimensions.INTEREST_DUE, Decimal("2.64")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1002.49")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("1000.24")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay final due/overdue amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # see above for sum of due/overdue amounts across both loans. Regular
                        # repayment only so no additional fees
                        amount="3543.71",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_3 + relativedelta(hours=1),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_3
                    + relativedelta(hours=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            (dimensions.EMI, Decimal("754.28")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("2.55")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("1757.77")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("2011.32")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # Default includes both original principals and repayments, so the
                            # remainder after all repayments will be the interest profit:
                            # 14.6 interest on loan 1, 16.49 on loan 2
                            # The fees are not present here because:
                            # - overpayment fee is directly deducted from DEFAULT
                            # - late repayment fee is rebalanced from DEFAULT on repayment
                            (dimensions.DEFAULT, "-31.09"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Trigger Close Code for both loans",
                events=[
                    update_account_status_pending_closure(
                        timestamp=due_amount_calc_3 + relativedelta(hours=2),
                        account_id=DRAWDOWN_0,
                    ),
                    update_account_status_pending_closure(
                        timestamp=due_amount_calc_3 + relativedelta(hours=2),
                        account_id=DRAWDOWN_1,
                    ),
                ],
                expected_balances_at_ts={
                    due_amount_calc_3
                    + relativedelta(hours=2): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # the original principals are 'returned'. The hard settlements made
                            # to make the drawdown will need to zero this out
                            (dimensions.DEFAULT, "6000"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_9_b_c_d_overpayment_reduces_term_results_in_fee_and_is_reflected_in_accruals(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        end = due_amount_calc_2

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.91765")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("8.91765")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            # All accrued interest is reset on due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Overpayment made on a single loan",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2, so overpay by 1005 to reduce term by 1 month
                        # A fee of 1% is charged, so required overpayment is
                        # round(1005/(1-0.99),2) = 1015.15
                        amount="3027.53",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("997.73")),
                            (dimensions.OVERPAYMENT, Decimal("1005")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # All accrued interest is reset on due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME}": [
                            (dimensions.DEFAULT, Decimal("10.15")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Accrual after Overpayment",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # Overpayment amount is moved from principal to overpayment balance
                            (dimensions.PRINCIPAL, Decimal("997.73")),
                            (dimensions.OVERPAYMENT, Decimal("1005")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # accruing on 997.73 instead of 2002.73
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.08474")),
                            # still accruing on 2002.73
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        # Unchanged as no overpayment affects this account
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Still accruing on 2002.73
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts reflect excess principal",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            # No more principal left - the loan has ended
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("1005")),
                            # EMI is unchanged as overpayment is not set to reduce emi
                            (dimensions.EMI, Decimal("1005.17")),
                            # Interest accrued at 0.08474 per day vs 0.17009 expected (ignoring
                            # overpayments), so interest due is 2.46 vs 4.93 expected and the
                            # excess is 2.47
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("2.47")),
                            (dimensions.INTEREST_DUE, Decimal("2.46")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.73")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1000.24")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_10_a_b_early_repayment_only_accepted_if_equalling_total_outstanding(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = due_amount_calc_1 + relativedelta(days=2)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["overpayment_impact_preference"] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Due Amounts for first period + 1 accrual",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            # Single accrual round(2002.73 * 0.031 / 365, 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Early Repayment attempted with excessive amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2 = 2012.38
                        # Not-yet-due principal is 2 * 2002.73 = 4005.46
                        # Not-yet-due interest is 2 * 0.17009 = .34018
                        # Overpayment fees round(0.01 * 4005.46, 2) = 40.05
                        # Rounded total is 6058.23
                        amount="6058.24",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=5),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(days=1, hours=5),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Repayment amount 6058.24 exceeds total outstanding "
                        "+ overpayment fees 6058.23",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                    )
                ],
            ),
            SubTest(
                description="Early Repayment attempted with exact amount",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2 = 2012.38
                        # Not-yet-due principal is 2 * 2002.73 = 4005.46
                        # Not-yet-due interest is 2 * 0.17009 = .34018
                        # Overpayment fees round(0.01 * 4005.46, 2) = 40.05
                        amount="6058.23",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=6),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1, hours=6): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Remainders are handled in close code
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME}": [
                            (dimensions.DEFAULT, Decimal("40.05")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_10_a_b_early_repayment_on_one_loan_and_partial_on_another(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = due_amount_calc_1 + relativedelta(days=2)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["overpayment_impact_preference"] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Due Amounts for first period + 1 accrual",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            # Single accrual round(2002.73 * 0.031 / 365, 5)
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Early Repayment attempted with exact amount for one loan only",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2 = 2012.38
                        # Not-yet-due principal is 2 * 2002.73 = 4005.46
                        # Not-yet-due interest is 2 * 0.17009 = .34018
                        # Remove 50 to not fully repay the non due interest/principal on loan 2
                        # Overpayment fees round(0.01 * 3955.46, 2) = 39.56
                        amount="5968.08",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=6),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1, hours=6): {
                        # 39.56 deducted for overpayment fee
                        f"{accounts.OVERPAYMENT_FEE_INCOME}": [
                            (dimensions.DEFAULT, Decimal("39.56")),
                        ],
                        # due interest/principal paid off across both loans = 2012.38
                        # then principal + accrued interest on loan 1 = 2002.9
                        # which leaves 5968.08-39.56-2012.38-2002.9 = 1913.24 for loan 2
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Remainders are handled in close code
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        # Remaining 1913.24 for principal/interest interest
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("89.49")),
                            (dimensions.OVERPAYMENT, Decimal("1913.24")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.17009")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                    },
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_11_a_blocking_daily_accrual(self):
        start = datetime(year=2020, month=1, day=11, hour=1, tzinfo=timezone.utc)
        after_first_accrual = start + relativedelta(days=1, hours=2)
        after_second_accrual = start + relativedelta(days=2, hours=2)
        after_third_accrual = start + relativedelta(days=3, hours=2)

        loc_template_params = default_loc_template_params.copy()

        sub_tests = [
            SubTest(
                description="Create Flag definition",
                events=[create_flag_definition_event(start, "REPAYMENT_HOLIDAY")],
            ),
            SubTest(
                description="check interest is accrued without the flag applied",
                expected_balances_at_ts={
                    after_first_accrual: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Apply Flag",
                events=[
                    create_flag_event(
                        timestamp=after_first_accrual,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        expiry_timestamp=after_second_accrual,
                    )
                ],
            ),
            SubTest(
                description="Check interest is no longer accrued",
                expected_balances_at_ts={
                    after_second_accrual: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.40822")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Interest accrued again after flag expires",
                expected_balances_at_ts={
                    after_third_accrual: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.81644")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=after_third_accrual,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                loan_instances=1,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_11_b_c_e_h_blocking_during_repayment_holiday(self):
        due_amount_calc_day = 5
        # repayment and grace periods match defaults
        repayment_period = 5
        grace_period = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        # due amount dates
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)

        # check overdue dates
        check_overdue_1 = due_amount_calc_1 + relativedelta(days=repayment_period, second=3)
        check_overdue_2 = due_amount_calc_2 + relativedelta(days=repayment_period, second=3)
        check_overdue_3 = due_amount_calc_3 + relativedelta(days=repayment_period, second=3)

        # check delinquency dates
        check_delinquency_1 = check_overdue_1 + relativedelta(days=grace_period, second=2)
        check_delinquency_2 = check_overdue_2 + relativedelta(days=grace_period, second=2)
        check_delinquency_3 = check_overdue_3 + relativedelta(days=grace_period, second=2)

        end = check_delinquency_3

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        balances_for_duration_of_holiday = {
            DRAWDOWN_0: [
                (dimensions.DEFAULT, Decimal("0")),
                (dimensions.PRINCIPAL, Decimal("2753.68")),
                (dimensions.EMI, Decimal("254.22")),
                # Existing due amounts have been moved to overdue, but no new due
                # amounts are added
                (dimensions.INTEREST_DUE, Decimal("0")),
                (dimensions.PRINCIPAL_DUE, Decimal("0")),
                (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                # accrual is at 00:00:01 and check delinquency at 00:00:02
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
            ],
            DRAWDOWN_1: [
                (dimensions.DEFAULT, Decimal("0")),
                (dimensions.PRINCIPAL, Decimal("2753.68")),
                (dimensions.EMI, Decimal("254.22")),
                (dimensions.INTEREST_DUE, Decimal("0")),
                (dimensions.PRINCIPAL_DUE, Decimal("0")),
                (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.3387")),
            ],
        }

        sub_tests = [
            SubTest(
                description="Create Flag definition",
                events=[create_flag_definition_event(start, "REPAYMENT_HOLIDAY")],
            ),
            SubTest(
                description="Check amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                    check_overdue_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 5 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.16935")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.16935")),
                        ],
                    },
                    check_delinquency_1: balances_for_duration_of_holiday,
                },
            ),
            SubTest(
                description="Apply Flag",
                events=[
                    create_flag_event(
                        timestamp=check_delinquency_1 + relativedelta(minutes=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        expiry_timestamp=check_delinquency_2 + relativedelta(minutes=1),
                    )
                ],
            ),
            SubTest(
                description="Check amounts for second period have not changed due to"
                "repayment holiday",
                expected_balances_at_ts={
                    due_amount_calc_2: balances_for_duration_of_holiday,
                    check_overdue_2: balances_for_duration_of_holiday,
                    check_delinquency_2: balances_for_duration_of_holiday,
                },
            ),
            SubTest(
                description="Check amounts change in third period after repayment holiday "
                "ends and loans are re-amortised",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            # EMI is reamortised with previous P = 2753.68
                            # N = 10 and R is 0.031/12
                            (dimensions.EMI, Decimal("279.30")),
                            # Repayment holiday is effective 2020/02/15 - 2020/03/15 (31 days)
                            # so accrue 2020/02/05 - 2020/02/15 and 2020/03/15 - 2020/04/05
                            # 7.25 = 31 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("7.25")),
                            (dimensions.PRINCIPAL_DUE, Decimal("272.05")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("7.25")),
                            (dimensions.PRINCIPAL_DUE, Decimal("272.05")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                    check_overdue_3: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 5 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.05385")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("1.05385")),
                        ],
                    },
                    check_delinquency_3: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            # Existing due amounts have been moved to overdue, but no new due
                            # amounts are added
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            # accrual is at 00:00:01 and check overdue at 00:00:03
                            # so 10 days of accruals since due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.1077")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2481.63")),
                            (dimensions.EMI, Decimal("279.30")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("16.17")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("518.37")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("2.1077")),
                        ],
                    },
                },
            ),
            SubTest(
                description="delinquency checks made in first and third period",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_MARK_DELINQUENT",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        count=2,
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    @unittest.skip("Can't check lack of contract notifications yet")
    def test_11_d_blocking_notifications(self):
        start = datetime(year=2020, month=1, day=1, hour=1, tzinfo=timezone.utc)
        after_first_repayment_day = start + relativedelta(months=1, days=7)
        after_second_repayment_day = after_first_repayment_day + relativedelta(months=1)
        end = after_second_repayment_day + relativedelta(months=1, days=5)

        loc_template_params = default_loc_template_params.copy()

        sub_tests = [
            SubTest(
                description="Create Flag definition",
                events=[create_flag_definition_event(start, "REPAYMENT_HOLIDAY")],
            ),
            SubTest(
                description="Apply Flag",
                events=[
                    create_flag_event(
                        timestamp=after_first_repayment_day,
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        expiry_timestamp=after_second_repayment_day,
                    )
                ],
            ),
            # count workflows
            SubTest(
                description="due notification",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_REPAYMENT_NOTIFICATION",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        count=2,  # should be 2 -> before and after flag
                    ),
                ],
            ),
            SubTest(
                description="overdue notification",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_OVERDUE_REPAYMENT_NOTIFICATION",
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        count=1,  # should be 1 -> after flag
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loc_template_params=loc_template_params,
                loan_instances=1,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_12_closing_loan_no_overdue_no_overpayments_no_penalties(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        final_repay = due_amount_calc_3 + relativedelta(hours=1)
        close_date = final_repay + relativedelta(hours=1)
        end = close_date + relativedelta(hours=1)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"
        loc_instance_params["credit_limit"] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, "6000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Pay dues for first due amount schedule",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2012.38",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for second period",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # 29 * round(2002.73 * 0.031 / 365 ,5) = 4.93
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1000.24")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1000.24")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Pay dues for second due amount schedule",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1005.17 * 2
                        amount="2010.34",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_2 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_2
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for final period",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Note that dues < EMI for the final period
                            # 31 * round(1002.49 * 0.031 / 365 ,5) = 2.64
                            (dimensions.INTEREST_DUE, Decimal("2.64")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1002.49")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("2.64")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1002.49")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay final due/overdue amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1005.13 * 2
                        amount="2010.26",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=final_repay,
                    )
                ],
                expected_balances_at_ts={
                    final_repay: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # Default includes both original principals and repayments, so the
                            # remainder after all repayments will be the interest profit:
                            # 16.49 per loan
                            (dimensions.DEFAULT, "-32.98"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repay,
                        notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
                        notification_details={
                            "account_ids": json.dumps(
                                [
                                    DRAWDOWN_0,
                                    DRAWDOWN_1,
                                ]
                            )
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Trigger Close Code for both loans",
                events=[
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=DRAWDOWN_0,
                    ),
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=DRAWDOWN_1,
                    ),
                ],
                expected_balances_at_ts={
                    close_date: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # the original principals are 'returned'. The hard settlements made
                            # to make the drawdown will need to zero this out
                            (dimensions.DEFAULT, "6000"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        # Have to use a timestamp after close_code is run or the sim evaluates
                        # using the earlier balances
                        timestamp=end,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_monthly_repayment",
                        value="0.00",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_12_closing_loan_with_overdue_overpayments_penalties(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1)
        extra_accrual = due_amount_calc_3 + relativedelta(days=1)
        final_repay = extra_accrual + relativedelta(hours=1)
        close_date = final_repay + relativedelta(hours=1)
        end = close_date + relativedelta(hours=1)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["due_amount_calculation_day"] = str(due_amount_calc_day)
        loc_instance_params["loc_start_date"] = "2020-01-01"
        loc_instance_params["credit_limit"] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"
        loan_instance_params["total_term"] = "3"
        loan_template_params = default_loan_template_params.copy()
        loan_template_params["penalty_interest_rate"] = "0.05"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params["overpayment_impact_preference"] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, "6000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Overpayment made on a single loan",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # Total due is 1006.19 * 2, so overpay by 500 to reduce EMI.
                        # A fee of 1% is charged, so required overpayment is
                        # round(500/(1-0.99),2) = 505.05
                        amount="2517.43",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1502.73")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # All accrued interest is reset on due amount calculation
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME}": [
                            (dimensions.DEFAULT, Decimal("5.05")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Final Due Amounts + Penalties - no further change to EMI",
                expected_balances_at_ts={
                    extra_accrual: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            (dimensions.EMI, Decimal("754.28")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("2.55")),
                            # Note: due amounts are < EMI
                            (dimensions.INTEREST_DUE, Decimal("1.98")),
                            (dimensions.PRINCIPAL_DUE, Decimal("752.15")),
                            (dimensions.INTEREST_OVERDUE, Decimal("3.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("750.58")),
                            # accrued at round(0.05 * (3.7 + 750.58) / 365, 2) from EOD
                            #  2020/03/10 to EOD 2020/04/05 so 27 accruals in total
                            (dimensions.PENALTIES, Decimal("2.70")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            # Single accrual on excess principal+ overpayment at
                            # round(0.031*502.55/365, 5)
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.04268")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Note: due amounts are < EMI
                            (dimensions.INTEREST_DUE, Decimal("2.64")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1002.49")),
                            (dimensions.INTEREST_OVERDUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("1000.24")),
                            # accrued at round(0.05 * (4.93 + 1000.24) / 365, 2) from EOD
                            #  2020/03/10 to EOD 2020/04/05 so 27 accruals in total
                            (dimensions.PENALTIES, Decimal("3.78")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay final due/overdue amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # see above for sum of due/overdue amounts across both loans. Regular
                        # repayment only so no additional fees
                        # 3487.62 + 25 + 6.48
                        amount="3550.19",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=final_repay,
                    )
                ],
                expected_balances_at_ts={
                    final_repay: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("500")),
                            (dimensions.EMI, Decimal("754.28")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("2.55")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.04268")),
                            # Little business meaning, but useful to investigate issues
                            (dimensions.INTERNAL_CONTRA, Decimal("1760.42732")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("2015.1")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # Default includes both original principals and repayments, so the
                            # remainder after all repayments will be the interest profit:
                            # 17.3 interest on loan 1, 20.27 on loan 2
                            # The fees are not present here because:
                            # - overpayment fee is directly deducted from DEFAULT
                            # - late repayment fee is rebalanced from DEFAULT on repayment
                            (dimensions.DEFAULT, "-37.57"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=final_repay,
                        notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
                        notification_details={
                            "account_ids": json.dumps(
                                [
                                    DRAWDOWN_0,
                                    DRAWDOWN_1,
                                ]
                            )
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT} 0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_repay,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_monthly_repayment",
                        value="1759.45",
                    ),
                ],
            ),
            SubTest(
                description="Trigger Close Code for both loans",
                events=[
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=DRAWDOWN_0,
                    ),
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=DRAWDOWN_1,
                    ),
                ],
                expected_balances_at_ts={
                    close_date: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            # the original principals are 'returned'. The hard settlements made
                            # to make the drawdown will need to zero this out
                            (dimensions.DEFAULT, "6000"),
                            (dimensions.PENALTIES, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        # Have to use a timestamp after close_code is run or the sim evaluates
                        # using the earlier balances
                        timestamp=end,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_monthly_repayment",
                        value="0.00",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
                loc_template_params=loc_template_params,
                loan_template_params=loan_template_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_d_total_arrears_aggregation(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        check_overdue_1 = datetime(year=2020, month=2, day=10, second=3, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check overdue amounts updated for drawdowns and aggregated on LOC",
                expected_balances_at_ts={
                    check_overdue_1: {
                        DRAWDOWN_0: [
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("17.84")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("492.64")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check total_arrears derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_arrears",
                        value="510.48",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=check_overdue_1,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_e_h_total_outstanding_due_and_total_monthly_repayment_aggregation(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(year=2020, month=2, day=5, second=2, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["loc_start_date"] = "2020-01-01"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check due amounts updated for drawdowns and aggregated on LOC",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("17.84")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("492.64")),
                            (dimensions.TOTAL_EMI, Decimal("508.44")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check total_outstanding_due derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_outstanding_due",
                        value="510.48",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_monthly_repayment",
                        value="508.44",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=due_amount_calc_1,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_f_g_total_outstanding_principal_and_available_credit_aggregation(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(year=2020, month=2, day=5, second=3, tzinfo=timezone.utc)
        check_overdue_1 = datetime(year=2020, month=2, day=10, second=3, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params["loc_start_date"] = "2020-01-01"
        loc_instance_params["credit_limit"] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["loan_start_date"] = "2020-01-01"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_PRINCIPAL, Decimal("6000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("17.84")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("492.64")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("5507.36")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Partial repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("92.64")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("17.84")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("92.64")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("5507.36")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check total_outstanding_principal and available_credit derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_outstanding_principal",
                        value="5600.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_available_credit",
                        # 10000.00 - 5600.00 (total_outstanding_principal)
                        value="4400.00",
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amounts updated for drawdowns and aggregated on LOC",
                expected_balances_at_ts={
                    check_overdue_1: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("92.64")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("17.84")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("92.64")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("5507.36")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check derived params are unchanged by due to overdue move",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_outstanding_principal",
                        value="5600.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_available_credit",
                        # 10000.00 - 5600.00 (total_outstanding_principal)
                        value="4400.00",
                    ),
                ],
            ),
            SubTest(
                description="Partially repay overdue balances",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=check_overdue_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    check_overdue_1
                    + relativedelta(hours=5): {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("1.56")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_INTEREST_OVERDUE, Decimal("10.48")),
                            (dimensions.TOTAL_PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("5507.36")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check derived params updated after repaying overdue",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_outstanding_principal",
                        value="5507.36",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_available_credit",
                        # 10000.00 - 5507.36 (total_outstanding_principal)
                        value="4492.64",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=check_overdue_1 + relativedelta(hours=12),
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_interest_aggregation(self):
        # given we are accruing 1 day over 3 loans, we expect: round(0.40822,2) * 3 = 1.23)
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        end = start + relativedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="check interest accrual receivable",
                expected_balances_at_ts={
                    end: {
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "1.23"),
                        ],
                    }
                },
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(loan_instances=3),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_a_per_loan_early_repayment(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(year=2020, month=2, day=5, second=2, tzinfo=timezone.utc)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check due amounts updated for drawdowns",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "2767.33"),
                            (dimensions.INTEREST_DUE, Decimal("42.86")),
                            (dimensions.PRINCIPAL_DUE, Decimal("232.67")),
                        ],
                    },
                },
            ),
            SubTest(
                # expected value calculation:
                # (2767.33 + 42.86 + 232.67) + (2767.33 * 0.01) = 3042.86 + 27.67
                # total = 3070.53
                description="Check per_loan_early_repayment_amount derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=DRAWDOWN_0,
                        name="per_loan_early_repayment_amount",
                        value="3070.53",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=due_amount_calc_1,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=1,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_14_b_total_early_repayment_derived_param(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(year=2020, month=2, day=5, second=2, tzinfo=timezone.utc)
        extra_accrual = due_amount_calc_1 + relativedelta(days=1)
        early_repayment_1 = extra_accrual + relativedelta(hours=1)
        early_repayment_2 = early_repayment_1 + relativedelta(hours=1)
        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params["principal"] = "3000"
        loan_instance_params["fixed_interest_rate"] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        DRAWDOWN_0: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        DRAWDOWN_1: [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check total_early_repayment_amount after due calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                        ],
                    },
                },
                # expected value calculation:
                # total outstanding (due and non due) + overpayment fee
                # = 2 * (2753.68 + 8.92 + 246.32) + round(2 * 2753.68 * 0.01, 2))
                # = 2 * 6017.84 + 55.07 = 6072.91
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_early_repayment_amount",
                        value="6072.91",
                    ),
                ],
            ),
            SubTest(
                # expected value = previous amount + 2 * round(2753.68 * 0.031 / 365, 2)
                # = 6072.91 + 2 * 0.23 = 6073.37
                # note that interest is rounded on a per-loan basis before aggregation, or the
                # interest would have increased by round(2 * 2753.68 * 0.031 / 365, 2) = 0.47
                description="Check total_early_repayment_amount after extra accrual",
                expected_balances_at_ts={
                    extra_accrual: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.23387")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.23387")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=extra_accrual,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_early_repayment_amount",
                        value="6073.37",
                    ),
                ],
            ),
            SubTest(
                description="Check total_early_repayment_amount after targeted early repayment",
                # expected value calculation:
                # total outstanding (due and non due) + overpayment fee for loan 0 only
                # = 2753.68 + 8.92 + 246.32 + round(2753.68 * 0.01, 2))
                # = 3036.46
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3036.46",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=early_repayment_1,
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": DRAWDOWN_0,
                        },
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_1: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # residual interest is expected and cleared up as part of close_code
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00387")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.23387")),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_1,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_early_repayment_amount",
                        # the residual interest on drawdown loan 0 is not reflected here or this
                        # amount would be 3036.7
                        value="3036.69",
                    ),
                ],
            ),
            SubTest(
                description="Check total_early_repayment_amount - final early repayment",
                events=[
                    # don't need to target this repayment as there is only one loan left
                    create_inbound_hard_settlement_instruction(
                        amount="3036.69",
                        target_account_id=f"{accounts.LOC_ACCOUNT} 0",
                        event_datetime=early_repayment_2,
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_2: {
                        DRAWDOWN_0: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00387")),
                        ],
                        DRAWDOWN_1: [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.00387")),
                        ],
                        f"{accounts.LOC_ACCOUNT} 0": [
                            (dimensions.TOTAL_PRINCIPAL, "0"),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "0"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_2,
                        account_id=f"{accounts.LOC_ACCOUNT} 0",
                        name="total_early_repayment_amount",
                        value="0.00",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=early_repayment_2 + relativedelta(hours=1),
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)
