# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import unittest
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters
import library.line_of_credit.contracts.template.drawdown_loan as drawdown_loan
import library.line_of_credit.contracts.template.line_of_credit as line_of_credit
from library.line_of_credit.supervisors.template import line_of_credit_supervisor
from library.line_of_credit.test.simulation.test_line_of_credit_supervisor_common import (
    DEFAULT_PLAN_ID,
)

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    ExpectedWorkflow,
    SimulationTestScenario,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

LINE_OF_CREDIT = "line_of_credit"
DRAWDOWN_LOAN = "drawdown_loan"

REPAYMENT_DUE_NOTIFICATION = line_of_credit_supervisor.REPAYMENT_DUE_NOTIFICATION
REPAYMENT_OVERDUE_NOTIFICATION = (
    f"{line_of_credit_supervisor.LOC_ACCOUNT_TYPE}"
    f"{line_of_credit_supervisor.overdue.OVERDUE_REPAYMENT_NOTIFICATION_SUFFIX}"
)
DELINQUENT_NOTIFICATION = line_of_credit_supervisor.DELINQUENT_NOTIFICATION

default_simulation_start_date = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
DEFAULT_DENOMINATION = "GBP"

# default parameters values copied and adapted from line_of_credit/constants/test_parameters.py
default_loan_instance_params = {
    **test_parameters.drawdown_loan_instance_params,
    drawdown_loan.disbursement.PARAM_PRINCIPAL: "1000",
    drawdown_loan.disbursement.PARAM_DEPOSIT_ACCOUNT: accounts.DEPOSIT_ACCOUNT,
    drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.149",
    drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "12",
    drawdown_loan.PARAM_LOC_ACCOUNT_ID: f"{accounts.LOC_ACCOUNT}_0",
}

default_loan_template_params = {
    **test_parameters.drawdown_loan_template_params,
    drawdown_loan.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    drawdown_loan.interest_accrual.PARAM_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: (
        accounts.ACCRUED_INTEREST_RECEIVABLE
    ),
    drawdown_loan.interest_application.PARAM_INTEREST_RECEIVED_ACCOUNT: (
        accounts.INTERNAL_INTEREST_RECEIVED_ACCOUNT
    ),
    drawdown_loan.interest_accrual.PARAM_DAYS_IN_YEAR: "365",
    # Penalty Interest Parameters
    drawdown_loan.PARAM_PENALTY_INTEREST_RATE: "0",
    drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE: "False",
    drawdown_loan.PARAM_PENALTY_INTEREST_INCOME_ACCOUNT: (
        accounts.INTERNAL_PENALTY_INTEREST_INCOME_ACCOUNT
    ),
    line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.01",
}

default_loc_instance_params = {
    **test_parameters.loc_instance_params,
    line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "10000",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "5",
}

default_loc_template_params = {
    **test_parameters.loc_template_params,
    line_of_credit.common_parameters.PARAM_DENOMINATION: DEFAULT_DENOMINATION,
    line_of_credit.credit_limit.PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL: "outstanding",
    line_of_credit.maximum_loan_principal.PARAM_MAXIMUM_LOAN_PRINCIPAL: "10000",
    line_of_credit.minimum_loan_principal.PARAM_MINIMUM_LOAN_PRINCIPAL: "1000",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_HOUR: "0",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_MINUTE: "0",
    line_of_credit.interest_accrual.PARAM_INTEREST_ACCRUAL_SECOND: "1",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_HOUR: "0",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_MINUTE: "0",
    line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_SECOND: "2",
    line_of_credit.maximum_outstanding_loans.PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS: "6",
    # Overdue Parameters
    line_of_credit.overdue.PARAM_REPAYMENT_PERIOD: "5",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_HOUR: "0",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_MINUTE: "0",
    line_of_credit.overdue.PARAM_CHECK_OVERDUE_SECOND: "3",
    line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
    line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT
    ),
    # Delinquency Parameters
    line_of_credit.delinquency.PARAM_GRACE_PERIOD: "5",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_HOUR: "0",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_MINUTE: "0",
    line_of_credit.delinquency.PARAM_CHECK_DELINQUENCY_SECOND: "2",
    # Overpayment Parameters
    line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE: "reduce_term",
    line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_RATE: "0.01",
    line_of_credit.overpayment.PARAM_OVERPAYMENT_FEE_INCOME_ACCOUNT: (
        accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT
    ),
}


class LOCSupervisorTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [
            contract_files.LOC_SUPERVISOR,
            contract_files.LOC_CONTRACT,
            contract_files.DRAWDOWN_LOAN_CONTRACT,
        ]

        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            LINE_OF_CREDIT: "1000",
            DRAWDOWN_LOAN: "1001",
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
                    account_id_base=f"{accounts.LOC_ACCOUNT}_",
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
                    account_id_base=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_",
                    number_of_accounts=loan_instances,
                )
            ],
            contract_content=self.smart_contract_path_to_content[
                contract_files.DRAWDOWN_LOAN_CONTRACT
            ],
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                        ],
                        f"{accounts.DEPOSIT_ACCOUNT}": [
                            (dimensions.DEFAULT, "1000"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_ORIGINAL_PRINCIPAL, Decimal("1000")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
                        value="1000.00",
                    ),
                ],
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

    def test_postings_made_to_drawdown_acc_are_always_rejected(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=6, tzinfo=timezone.utc)

        # reducing so that we do not hit the credit_limit
        loc_template_params = {
            **default_loc_template_params,
            "maximum_loan_principal": "3000",
            "minimum_loan_principal": "500",
        }

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "7000",
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "3",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("6000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Posting made against Drawdown account is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="Custom",
                        rejection_reason="All postings should be made to the Line of Credit "
                        "account",
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
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
                loan_instance_params=loan_instance_params,
            ),
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
        loc_template_params = {
            **default_loc_template_params,
            "maximum_loan_principal": "3000",
            "minimum_loan_principal": "500",
        }

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "7000",
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "3",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 2000 exceeds"
                        " available credit limit of 1000.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Drawdown below remaining credit limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 501 exceeds"
                        " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Pay some due principal to reduce outstanding principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2012.38",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=4): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated. The remaining limit is
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 3000 exceeds"
                        " available credit limit of 2494.54",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Smaller drawdown accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=7),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=7): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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

    def test_1_C_loc_limits_based_on_original_principal(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2020, month=2, day=6, tzinfo=timezone.utc)

        loc_template_params = {
            **default_loc_template_params,
            "maximum_loan_principal": "3000",
            "minimum_loan_principal": "500",
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT_APPLICABLE_PRINCIPAL: "original",
        }

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.credit_limit.PARAM_CREDIT_LIMIT: "7000",
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: "3",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(minutes=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(minutes=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 2000 exceeds"
                        " available credit limit of 1000.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Drawdown below remaining credit limit accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        # note this reflects the change in limit despite the 500GBP loan
                        # not yet being associated
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 501 exceeds"
                        " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Pay some due principal to reduce outstanding principal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2012.38",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=4),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=4): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("4487.62")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Original principal limit respected still",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="501",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        # 7000 - 6500 (original principals) + 2*997.27 (principal repayments)
                        # Based on outstanding principal, credit limit = 2494.54
                        # Based on original principal, credit limit = 500
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 501 exceeds"
                        " available credit limit of 500.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Smaller drawdown accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=7),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=7): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("4987.62")),
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

    def test_max_loan_number_respected_by_supervisor_at_limit(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 3, tzinfo=timezone.utc)

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[
            line_of_credit.maximum_outstanding_loans.PARAM_MAXIMUM_NUMBER_OF_OUTSTANDING_LOANS
        ] = "5"

        sub_tests = [
            SubTest(
                description="Drawdown when number of loans not yet exceeded",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL, Decimal("4000")),
                            (dimensions.DEFAULT, Decimal("1000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Additional Credit Limit can be ringfenced until loan is associated",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL, Decimal("4000")),
                            (dimensions.DEFAULT, Decimal("6000")),
                        ],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=3),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Incoming posting of 5000 exceeds"
                        " available credit limit of 4000.00",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=4,
                loc_template_params=loc_template_params,
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"
        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            # Accrue from 2020-1-1 to 2020-2-5 at 3.1% on $3000 (i.e. 35 days)
                            # 4 accruals not in EMI from 2020-1-1 to 2020-1-4
                            # 4* round(3000 * 0.031/365, 5) = 1.01916
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("1.01916")),
                            # 31 accruals included in EMI from 2020-1-5 to 2020-1-5
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("7.89849")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        delinquency_check_1 = datetime(2020, 2, 15, 0, 0, 2, tzinfo=timezone.utc)
        end = overdue_check_date_1 + relativedelta(days=5)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[line_of_credit.overdue.PARAM_REPAYMENT_PERIOD] = str(repayment_period)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params[drawdown_loan.PARAM_PENALTY_INTEREST_RATE] = "0.043"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fee and notification and delinquent checks made",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "492.64",
                            "overdue_interest": "17.84",
                            line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_1,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amounts moved before accruing penalties",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        delinquency_check_1 = datetime(2020, 2, 15, 0, 0, 2, tzinfo=timezone.utc)
        end = overdue_check_date_1 + relativedelta(days=5)

        loc_instance_params = default_loc_instance_params.copy()
        loc_template_params = default_loc_template_params.copy()

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"
        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params[drawdown_loan.PARAM_PENALTY_INTEREST_RATE] = "0.043"
        loan_template_params[drawdown_loan.PARAM_INCLUDE_BASE_RATE_IN_PENALTY_RATE] = "True"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="overdue fee and notification and delinquent checks made",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "492.64",
                            "overdue_interest": "17.84",
                            line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_1,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amounts moved before accruing penalties",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[line_of_credit.overdue.PARAM_REPAYMENT_PERIOD] = "5"
        loc_template_params[line_of_credit.delinquency.PARAM_GRACE_PERIOD] = "5"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Repayment notification sent on first due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_1,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "510.48",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on first overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_1: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "25"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_1,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "492.64",
                            "overdue_interest": "17.84",
                            line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
                            "overdue_date": str(overdue_check_date_1.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_date_1,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Repayment notification sent on second due amount schedule",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_check_date_2,
                        notification_type=REPAYMENT_DUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "repayment_amount": "508.44",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Fee is charged and notification sent on second overdue schedule",
                expected_balances_at_ts={
                    overdue_check_date_2: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "50"),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, "50"),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_check_date_2,
                        notification_type=REPAYMENT_OVERDUE_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                            "overdue_principal": "494.88",
                            "overdue_interest": "13.56",
                            line_of_credit.late_repayment.PARAM_LATE_REPAYMENT_FEE: "25",
                            "overdue_date": str(overdue_check_date_2.date()),
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=delinquency_check_date_2,
                        notification_type=DELINQUENT_NOTIFICATION,
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for second period",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Repay all overdue/due amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="534.46",
                        denomination="GBP",
                        event_datetime=due_amount_calc_2 + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_2
                    + relativedelta(hours=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PRINCIPAL_DUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="300",
                        denomination="GBP",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="210.48",
                        denomination="GBP",
                        event_datetime=due_amount_calc_1 + relativedelta(hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=2): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[line_of_credit.overdue.PARAM_REPAYMENT_PERIOD] = "5"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        loan_template_params = default_loan_template_params.copy()
        loan_template_params[drawdown_loan.PARAM_PENALTY_INTEREST_RATE] = "0.043"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Overdue amounts updated and fee is charged",
                expected_balances_at_ts={
                    overdue_check_date: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT}": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "25"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            # overdue balance 255.24
                            # 5 * round(255.24 * 0.031 / 365 , 5) = 0.15
                            (dimensions.PENALTIES, Decimal("0.15")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        # 255.24 overdue + 0.15 penalties per Loan + 25 penalties on LOC
                        amount="535.78",
                        denomination="GBP",
                        event_datetime=overdue_check_date + relativedelta(days=5, hours=1),
                        instruction_details={"event": "INCOMING_REPAYMENT"},
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    overdue_check_date
                    + relativedelta(days=5, hours=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_OVERDUE, "0"),
                            (dimensions.INTEREST_OVERDUE, "0"),
                            (dimensions.PENALTIES, "0"),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Due/Overdue Amounts for first period",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": expected_loan_0_balances,
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="246.32",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": expected_loan_0_balances,
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="10000",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(hours=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The repayment amount 10000 GBP exceeds the total maximum "
                        "repayment amount of 3036.73 GBP.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    )
                ],
            ),
            SubTest(
                description="Repay interest due on loan 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="8.92",
                        denomination="GBP",
                        instruction_details={
                            "event": "TARGETED_REPAYMENT",
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        },
                        event_datetime=due_amount_calc_1 + relativedelta(hours=3),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=3): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": expected_loan_0_balances,
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)
        loc_instance_params[line_of_credit.credit_limit.PARAM_CREDIT_LIMIT] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[
            line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE
        ] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "1005.17"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "1005.17"),
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT}": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_3 + relativedelta(hours=1),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_3
                    + relativedelta(hours=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                            (dimensions.INTERNAL_CONTRA, Decimal("1754.77")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                            (dimensions.INTERNAL_CONTRA, Decimal("2008.32")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                    ),
                    update_account_status_pending_closure(
                        timestamp=due_amount_calc_3 + relativedelta(hours=2),
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                    ),
                ],
                expected_balances_at_ts={
                    due_amount_calc_3
                    + relativedelta(hours=2): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "1005.17"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "1005.17"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check Accrued Interest is correct before due amount calc",
                expected_balances_at_ts={
                    due_amount_calc_1
                    - relativedelta(microseconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.OVERPAYMENT, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT}": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[
            line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE
        ] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Due Amounts for first period + 1 accrual",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        # repayment amount - overpayment fee = total due + total not-yet-due
                        # since the overpayment fee = (repayment amount - total due) * overpayment fee, # noqa: E501
                        # repayment amount - ((repayment amount - 2012.38) * 0.01) = 2012.38 + 4005.46 .34018 # noqa: E501
                        # if x is the repayment amount, x - 0.01x + 2012.38 * 0.01 = 6018.18018
                        # so x = 5998.05638 / .99 = 6058.64280
                        # Rounded total is 6058.64
                        amount="6058.65",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=5),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=due_amount_calc_1 + relativedelta(days=1, hours=5),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="The repayment amount 6058.65 GBP exceeds the "
                        "total maximum repayment amount of 6058.64 GBP.",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        # repayment amount - overpayment fee = total due + total not-yet-due
                        # since the overpayment fee = (repayment amount - total due) * overpayment fee, # noqa: E501
                        # repayment amount - ((repayment amount - 2012.38) * 0.01) = 2012.38 + 4005.46 .34018 # noqa: E501
                        # if x is the repayment amount, x - 0.01x + 2012.38 * 0.01 = 6018.18018
                        # so x = 5998.05638 / .99 = 6058.64280
                        # Rounded total is 6058.64
                        amount="6058.64",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=6),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1, hours=6): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, Decimal("40.46")),
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[
            line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE
        ] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Check Due Amounts for first period + 1 accrual",
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(days=1, hours=6),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(days=1, hours=6): {
                        # 39.56 deducted for overpayment fee
                        f"{accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, Decimal("39.56")),
                        ],
                        # due interest/principal paid off across both loans = 2012.38
                        # then principal + accrued interest on loan 1 = 2002.9
                        # which leaves 5968.08-39.56-2012.38-2002.9 = 1913.24 for loan 2
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("2002.73")),
                            # Not updated until Due Amount Calculation
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0.17009")),
                        ],
                        # Remaining 1913.24 for principal/interest interest
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        balances_for_duration_of_holiday = {
            f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
            f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                    check_overdue_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=check_delinquency_1,
                        notification_type="LOC_DELINQUENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                    ExpectedContractNotification(
                        timestamp=check_delinquency_3,
                        notification_type="LOC_DELINQUENT",
                        notification_details={
                            "account_id": f"{accounts.LOC_ACCOUNT}_0",
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        count=2,  # should be 2 -> before and after flag
                    ),
                ],
            ),
            SubTest(
                description="overdue notification",
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="LINE_OF_CREDIT_OVERDUE_REPAYMENT_NOTIFICATION",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)
        loc_instance_params[line_of_credit.credit_limit.PARAM_CREDIT_LIMIT] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "6000"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=1),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
                        # aggregate balance doesn't account for unassociated loans
                        # as this is updated via the activation hook of the loan
                        value="6000.00",
                    ),
                ],
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # 29 * round(2002.73 * 0.031 / 365 ,5) = 4.93
                            (dimensions.INTEREST_DUE, Decimal("4.93")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1000.24")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_2 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_2
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("1002.49")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Note that dues < EMI for the final period
                            # 31 * round(1002.49 * 0.031 / 365 ,5) = 2.64
                            (dimensions.INTEREST_DUE, Decimal("2.64")),
                            (dimensions.PRINCIPAL_DUE, Decimal("1002.49")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=final_repay,
                    )
                ],
                expected_balances_at_ts={
                    final_repay: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        timestamp=final_repay,  # the notification is sent upon payment
                        notification_type=line_of_credit_supervisor.LOANS_PAID_OFF_NOTIFICATION,
                        notification_details={
                            "account_ids": json.dumps(
                                [
                                    f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                                    f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                                ]
                            )
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Trigger Close Code for both loans",
                events=[
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                    ),
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                    ),
                ],
                expected_balances_at_ts={
                    close_date: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_monthly_repayment",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
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
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)
        loc_instance_params[line_of_credit.credit_limit.PARAM_CREDIT_LIMIT] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"
        loan_instance_params[drawdown_loan.lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT] = "3"
        loan_template_params = default_loan_template_params.copy()
        loan_template_params[drawdown_loan.PARAM_PENALTY_INTEREST_RATE] = "0.05"

        loc_template_params = default_loc_template_params.copy()
        loc_template_params[
            line_of_credit.overpayment.PARAM_OVERPAYMENT_IMPACT_PREFERENCE
        ] = "reduce_emi"

        sub_tests = [
            SubTest(
                description="Make postings to use credit limit - loans already opened due to sim"
                "setup",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="3000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "6000"),
                        ]
                    },
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
                        # aggregate balance doesn't account for unassociated loans
                        # as this is updated via the activation hook of the loan
                        value="6000.00",
                    ),
                ],
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            # Due amounts exceed EMI becase of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("997.27")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2002.73")),
                            (dimensions.EMI, Decimal("1005.17")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                        ],
                        f"{accounts.OVERPAYMENT_FEE_INCOME_ACCOUNT}": [
                            (dimensions.DEFAULT, Decimal("5.05")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Final Due Amounts + Penalties - no further change to EMI",
                expected_balances_at_ts={
                    extra_accrual: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=final_repay,
                    )
                ],
                expected_balances_at_ts={
                    final_repay: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                            # Little business meaning, but useful to investigate issues
                            (dimensions.INTERNAL_CONTRA, Decimal("1757.42732")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                            (dimensions.INTERNAL_CONTRA, Decimal("2012.1")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        notification_type="LOC_LOANS_PAID_OFF",
                        notification_details={
                            "account_ids": json.dumps(
                                [
                                    f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                                    f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                                ]
                            )
                        },
                        resource_id=f"{accounts.LOC_ACCOUNT}_0",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=final_repay,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                    ),
                    update_account_status_pending_closure(
                        timestamp=close_date,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                    ),
                ],
                expected_balances_at_ts={
                    close_date: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_monthly_repayment",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
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

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check overdue amounts updated for drawdowns and aggregated on LOC",
                expected_balances_at_ts={
                    check_overdue_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check due amounts updated for drawdowns and aggregated on LOC",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.EMI, Decimal("254.22")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_due",
                        value="510.48",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
        loc_instance_params[line_of_credit.credit_limit.PARAM_CREDIT_LIMIT] = "10000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.TOTAL_PRINCIPAL, Decimal("6000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts for first period with extra interest",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=due_amount_calc_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    due_amount_calc_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("92.64")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="5600.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("92.64")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="5600.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=check_overdue_1 + relativedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    check_overdue_1
                    + relativedelta(hours=5): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("1.56")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_outstanding_principal",
                        value="5507.36",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=check_overdue_1 + relativedelta(hours=5),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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
        # given we are accruing 1 day over 3 loans, we expect: 0.40822 * 3 = 1.22466
        # there is 0 in NON_EMI_ACCRUED_INTEREST_RECEIVABLE since there is exactly 1 cal month
        # from the start of the loan until the first due event
        start = datetime(year=2020, month=1, day=5, tzinfo=timezone.utc)
        end = start + relativedelta(days=1, hours=2)

        sub_tests = [
            SubTest(
                description="check interest accrual receivable",
                expected_balances_at_ts={
                    end: {
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.TOTAL_NON_EMI_ACCRUED_INTEREST_RECEIVABLE, "0"),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, "1.22466"),
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
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    # creations are all offset by a millisecond, would be nice to handle this in
                    # the framework
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "270.63"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check due amounts updated for drawdowns",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "2767.33"),
                            (dimensions.INTEREST_DUE, Decimal("42.86")),
                            (dimensions.PRINCIPAL_DUE, Decimal("232.67")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                # early_repayment_amount = total outstanding amount + max overpayment fee,
                # where the max overpayment fee is:
                # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                # total_outstanding_debt:
                #   2767.33 remaining principal
                #   + 232.67 principal due
                #   + 42.86 interest due
                #   = 3042.86
                # per_loan_early_repayment_amount: 3042.86 + 2767.33 * 0.01 / (1-0.01) = 3070.81
                description="Check per_loan_early_repayment_amount derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="3070.81",
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
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "3000"
        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.031"

        sub_tests = [
            SubTest(
                description="Check Principal is disbursed",
                expected_balances_at_ts={
                    start
                    + relativedelta(microseconds=1000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                    start
                    + relativedelta(microseconds=2000): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, "0"),
                            (dimensions.PRINCIPAL, "3000"),
                            (dimensions.EMI, "254.22"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Check total_early_repayment_amount after due calc",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                        ],
                    },
                },
                # early_repayment_amount = total outstanding amount + max overpayment fee,
                # where the max overpayment fee is:
                # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                # total_outstanding_debt:
                #   2753.68 remaining principal
                #   + 246.32 principal due
                #   + 8.92 interest due
                #   = 3008.92
                # per_loan_early_repayment_amount: 3008.92 + 2753.68 * 0.01 / (1-0.01) = 3036.73
                # total_early_repayment_amount: 3036.73 * 2 loans
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="3036.73",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="3036.73",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_1,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="6073.47",
                    ),
                ],
            ),
            SubTest(
                description="Check total_early_repayment_amount after extra accrual",
                expected_balances_at_ts={
                    extra_accrual: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "2753.68"),
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0.23387")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="3036.96",  # previous value plus accrued interest
                    ),
                    ExpectedDerivedParameter(
                        timestamp=extra_accrual,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="3036.96",  # previous value plus accrued interest
                    ),
                    ExpectedDerivedParameter(
                        timestamp=extra_accrual,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="6073.94",
                    ),
                ],
            ),
            SubTest(
                description="Check total_early_repayment_amount after targeted early repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3036.96",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=early_repayment_1,
                        instruction_details={
                            "target_account_id": f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0"
                        },
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                        name="per_loan_early_repayment_amount",
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_1,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                        name="per_loan_early_repayment_amount",
                        value="3036.96",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=early_repayment_1,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_early_repayment_amount",
                        value="3036.96",
                    ),
                ],
            ),
            SubTest(
                description="Check total_early_repayment_amount - final early repayment",
                events=[
                    # don't need to target this repayment as there is only one loan left
                    create_inbound_hard_settlement_instruction(
                        amount="3036.96",
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        event_datetime=early_repayment_2,
                    )
                ],
                expected_balances_at_ts={
                    early_repayment_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL, "0"),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
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
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
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

    def test_6_g_loc_change_due_amount_calc_day_later_in_month(self):
        # The due amount days are as follows:
        #    1st         2nd  Param  3rd
        #                     change
        # 2020/2/5 -> 2020/3/5 -> 2020/4/9
        old_due_amount_calc_day = 5
        new_due_amount_calc = 9
        repayment_period = 5

        # timestamps in chronological order
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=old_due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        overdue_calc_1 = due_amount_calc_1 + relativedelta(days=repayment_period, second=3)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        overdue_calc_2 = due_amount_calc_2 + relativedelta(days=repayment_period, second=3)
        param_change = due_amount_calc_2 + relativedelta(days=5)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1, day=new_due_amount_calc)
        overdue_calc_3 = due_amount_calc_3 + relativedelta(days=repayment_period, second=3)
        end = overdue_calc_3

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                old_due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="first due amount calculation for 2020/1/1 -> 2020/2/5",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI because of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            # EMI = 246.32 + 8.92 - 1.02 = 254.22
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                description="overdue check for 2020/2/5 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                    },
                },
            ),
            SubTest(
                description="second due amount calculation for 2020/2/5 -> 2020/3/5",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue check for 2020/3/5 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Change parameter and check nothing has moved to due",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=param_change,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=str(new_due_amount_calc),
                    ),
                ],
                expected_balances_at_ts={
                    # we check at the datetime of when the next scheduled event should have taken
                    # place before the parameter change
                    due_amount_calc_2
                    + relativedelta(months=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("6.59866")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("6.59866")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts have now accumulated after param change",
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2259.47")),
                            (dimensions.EMI, Decimal("254.22")),
                            # extra interest due because of extra accrual days after
                            # parameter change:
                            # Interest due 7.45 = 35 * round (2506.24 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("7.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.77")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2259.47")),
                            (dimensions.EMI, Decimal("254.22")),
                            # extra interest due because of extra accrual days after
                            # parameter change:
                            # Interest due 7.45 = 35 * round (2506.24 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("7.45")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.77")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue check after param change for 2020/4/9 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2259.47")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("23.15")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("740.53")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2259.47")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("23.15")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("740.53")),
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

    def test_6_g_loc_change_due_amount_calc_day_earlier_in_month(self):
        # The due amount days are as follows:
        #    1st         2nd  Param  3rd
        #                     change
        # 2020/2/5 -> 2020/3/5 -> 2020/4/4
        old_due_amount_calc_day = 5
        new_due_amount_calc = 4
        repayment_period = 5

        # timestamps in chronological order
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(
            year=2020, month=2, day=old_due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        overdue_calc_1 = due_amount_calc_1 + relativedelta(days=repayment_period, second=3)
        due_amount_calc_2 = due_amount_calc_1 + relativedelta(months=1)
        overdue_calc_2 = due_amount_calc_2 + relativedelta(days=repayment_period, second=3)
        param_change = due_amount_calc_2 + relativedelta(days=5)
        due_amount_calc_3 = due_amount_calc_2 + relativedelta(months=1, day=new_due_amount_calc)
        overdue_calc_3 = due_amount_calc_3 + relativedelta(days=repayment_period, second=3)
        end = overdue_calc_3

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                old_due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="first due amount calculation for 2020/1/1 -> 2020/2/5",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Due amounts exceed EMI because of 4 extra accruals
                            # 4 * round(3000 * 0.031 / 365 ,5) = 1.02
                            # EMI = 246.32 + 8.92 - 1.02 = 254.22
                            (dimensions.INTEREST_DUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
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
                description="overdue check for 2020/2/5 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                    },
                },
            ),
            SubTest(
                description="second due amount calculation for 2020/2/5 -> 2020/3/5",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due is 6.78 = 29 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue check for 2020/3/5 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.7")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check Due Amounts have now accumulated after param change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=param_change,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day=str(new_due_amount_calc),
                    ),
                ],
                expected_balances_at_ts={
                    due_amount_calc_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2258.41")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due 6.39 = 30 * round (2506.24 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.39")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.83")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2258.41")),
                            (dimensions.EMI, Decimal("254.22")),
                            # Interest due 6.39 = 30 * round (2506.24 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("6.39")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.83")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue check after param change for 2020/4/4 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_3: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2258.41")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("22.09")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("741.59")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2258.41")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("22.09")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("741.59")),
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

    def test_6_change_due_amount_day_scenarios(self):
        """
        There are 6 scenarios relating to a due_amount_calc_day change
        after the first due date
        3 where the due_amount_calc_day change request occurs after the months due_amount_calc_day
        and 3 where the due_amount_calc_day change request occurs before the current months
        due_amount_calc_day

        scenarios:
            after due_amount_calc_day has passed:
                1. old_due_amount_calc_day < change_day < new_due_amount_calc_day
                    (e.g. on 15th change from 12th to 20th)
                2. old due_amount_calc_day < new_due_amount_calc_day < change_day
                    e.g. on 23rd change from 20th to 21st)
                3. new_due_amount_calc_day < old_due_amount_calc_day < change_day
                    (e.g. on 23rd change from 21st to 12th)

            before due_amount_calc_day:
                1. change_day < old_due_amount_calc_day < new_due_amount_calc_day
                    (e.g. on 9th change from 12th to 15th)
                2. change_day < new_due_amount_calc_day < old due_amount_calc_day
                    (e.g. on 9th change from 15th to 13th)
                3. new_due_amount_calc_day < change_day < old_due_amount_calc_day
                    (e.g. on 9th change from 13th to 5th)
        """
        start = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "12",
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="Change due day after current months due_amount_calc_day event",
                events=[
                    # After due day - scenario 1
                    # start on 2020/01/11, 1st sched on 2020/01/12
                    # on 2020/02/15 change from 12th to 20th
                    # expect next schedule 2020/03/20
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 2, 15, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="20",
                    ),
                    # After due day - scenario 2
                    # on 2020/03/23 change from 20th to 21st
                    # expect next schedule 2020/04/21
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 3, 23, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="21",
                    ),
                    # After due day - scenario 3
                    # on 2020/04/23 change from 21st to 12th
                    # expect next schedule 2020/05/12
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 4, 23, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="12",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=12,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=20,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=21,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=12,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=12,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=20,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=21,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=12,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        plan_id=DEFAULT_PLAN_ID,
                    ),
                ],
            ),
            SubTest(
                description="Change due day before current months due_amount_calc_day event",
                events=[
                    # Before due day - scenario 1
                    # on 2020/06/09 change from 12th to 15th
                    # expect next schedule 2020/06/15
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 6, 9, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="15",
                    ),
                    #  Before due day - scenario 2
                    # on 2020/07/09 change from 15th to 13th
                    # expect next schedule 2020/07/13
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 7, 9, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="13",
                    ),
                    # Before due day - scenario 3
                    # on 2020/08/09 change from 13th to 5th
                    # expect next schedule 2020/08/13
                    # and the subsequent on 2020/09/05
                    create_instance_parameter_change_event(
                        timestamp=datetime(2020, 8, 9, 10, tzinfo=timezone.utc),
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        due_amount_calculation_day="5",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=15,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=7,
                                day=13,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=13,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        plan_id=DEFAULT_PLAN_ID,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=6,
                                day=15,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=8,
                                day=13,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=9,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=10,
                                day=5,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=start + relativedelta(months=9),
            supervisor_config=self._get_default_supervisor_config(
                loan_instances=2,
                loc_instance_params=loc_instance_params,
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_6_eom_edge_case_schedules(self):
        # in this test the following end of month edge cases will be examined:
        # due_amount_calc_day = 31, expected schedules are:
        # EOM: 2020-2-29
        # EOM: 2020-3-31
        # EOM: 2020-4-30
        # EOM: 2020-5-31
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 6, 1, tzinfo=timezone.utc)

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: "31",
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "5000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="expected end of month schedules for DUE_AMOUNT_CALCULATION",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=29,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=3,
                                day=31,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=4,
                                day=30,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                            datetime(
                                year=2020,
                                month=5,
                                day=31,
                                hour=0,
                                minute=0,
                                second=2,
                                tzinfo=timezone.utc,
                            ),
                        ],
                        event_id="DUE_AMOUNT_CALCULATION",
                        plan_id=DEFAULT_PLAN_ID,
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

    def test_6_loc_due_amount_calc_day_on_29th_non_leap_year(self):
        # this test checks that we reschedule the DUE_AMOUNT_CALCULATION event
        # for months without the 29th, i.e. non leap years
        # 2021 is not a leap year, so this date is used to check 28/02/2021
        due_amount_calc_day = 29
        repayment_period = 5

        # timestamps in chronological order
        start = datetime(year=2021, month=1, day=25, tzinfo=timezone.utc)
        due_amount_calc_1 = datetime(year=2021, month=2, day=28, second=2, tzinfo=timezone.utc)
        overdue_calc_1 = due_amount_calc_1 + relativedelta(days=repayment_period, second=3)
        due_amount_calc_2 = datetime(
            year=2021, month=3, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        overdue_calc_2 = due_amount_calc_2 + relativedelta(days=repayment_period, second=3)
        end = overdue_calc_2 + relativedelta(minutes=1)

        loc_instance_params = {
            **default_loc_instance_params,
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY: str(
                due_amount_calc_day
            ),
        }

        loan_instance_params = {
            **default_loan_instance_params,
            drawdown_loan.disbursement.PARAM_PRINCIPAL: "3000",
            drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE: "0.031",
        }

        sub_tests = [
            SubTest(
                description="first due amount calculation 2021/02/28",
                expected_balances_at_ts={
                    due_amount_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # 01/25 -> 02/28 = 34 days
                            # Interest due is 8.66 = 34 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            # 01/25 -> 02/28 = 34 days
                            # Interest due is 8.66 = 34 * round (2753.68 * 0.031 / 365, 5)
                            (dimensions.INTEREST_DUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_DUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.NON_EMI_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="overdue check for 2021/02/28 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_1: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2753.68")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                        ],
                    },
                },
            ),
            SubTest(
                description="second due amount calculation 2020/03/29",
                expected_balances_at_ts={
                    due_amount_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("6.78")),
                            (dimensions.PRINCIPAL_DUE, Decimal("247.44")),
                            (dimensions.INTEREST_OVERDUE, Decimal("8.66")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("246.32")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="second overdue check for 2020/03/29 + repayment_period",
                expected_balances_at_ts={
                    overdue_calc_2: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.44")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("2506.24")),
                            (dimensions.EMI, Decimal("254.22")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            # Previous due amounts not paid so moved to overdue
                            (dimensions.INTEREST_OVERDUE, Decimal("15.44")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("493.76")),
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

    def test_6_e_clearing_remaining_principal_in_final_due_amount(self):
        due_amount_calc_day = 5
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        final_due_amount_calc = datetime(
            year=2021, month=1, day=due_amount_calc_day, second=2, tzinfo=timezone.utc
        )
        end = datetime(year=2021, month=1, day=6, tzinfo=timezone.utc)

        loc_instance_params = default_loc_instance_params.copy()
        loc_instance_params[
            line_of_credit.due_amount_calculation.PARAM_DUE_AMOUNT_CALCULATION_DAY
        ] = str(due_amount_calc_day)
        loc_instance_params[line_of_credit.credit_limit.PARAM_CREDIT_LIMIT] = "1000000"

        loan_instance_params = default_loan_instance_params.copy()
        loan_instance_params[drawdown_loan.disbursement.PARAM_PRINCIPAL] = "200000"

        loan_instance_params[drawdown_loan.fixed_rate.PARAM_FIXED_INTEREST_RATE] = "0.02"

        sub_tests = [
            SubTest(
                description="Check entire remaining principal is due",
                expected_balances_at_ts={
                    final_due_amount_calc
                    - relativedelta(microseconds=1): {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("16820.61")),
                            (dimensions.EMI, Decimal("16847.77")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("2189.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("183179.39")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("28.57208")),
                        ],
                    },
                    final_due_amount_calc: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("16847.77")),
                            (dimensions.INTEREST_DUE, Decimal("28.57")),
                            # Expected to get the full principal amount
                            # instead of EMI-interest_to_accrue
                            (dimensions.PRINCIPAL_DUE, Decimal("16820.61")),
                            (dimensions.INTEREST_OVERDUE, Decimal("2189.92")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("183179.39")),
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
                loan_instance_params=loan_instance_params,
            ),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)
