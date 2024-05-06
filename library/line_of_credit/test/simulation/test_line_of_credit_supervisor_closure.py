# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps

# library
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.test_parameters as test_parameters
from library.line_of_credit.supervisors.template import line_of_credit_supervisor
from library.line_of_credit.test.simulation.test_line_of_credit_supervisor_common import (
    LineOfCreditSupervisorCommonTest,
    get_mimic_loan_creation_subtest,
)

# inception sdk
import inception_sdk.test_framework.contracts.simulation.errors as simulation_errors
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    update_account_status_pending_closure,
)

ACCRUAL_EVENT = line_of_credit_supervisor.interest_accrual_supervisor.ACCRUAL_EVENT


class LineOfCreditClosureTest(LineOfCreditSupervisorCommonTest):
    def test_close_partially_paid_loan(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(hours=1)

        sub_tests = [
            # Cannot use get_mimic_loan_creation_subtest() here because the test scenario cannot
            # contain expectations when a simulation error is expected.
            SubTest(
                description="Mimic loan creation",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="1000",
                        event_datetime=start,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        amount="1000",
                        event_datetime=start,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Attempt to close both drawdown loans",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0",
                    ),
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1",
                    ),
                ],
            ),
        ]
        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=self._get_default_supervisor_config(drawdown_loan_instances=2),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(
            test_scenario,
            expected_simulation_error=simulation_errors.generic_error(
                message="The loan cannot be closed until all outstanding debt is repaid"
            ),
        )

    def test_close_fully_paid_loan(self):
        start = test_parameters.default_simulation_start_date
        first_due_amount_event = datetime(
            year=2020, month=2, day=5, hour=0, minute=0, second=2, tzinfo=timezone.utc
        )
        payment_event = first_due_amount_event + relativedelta(seconds=1)
        close_date = payment_event + relativedelta(hours=1)
        end = close_date + relativedelta(hours=1)

        sub_tests = [
            get_mimic_loan_creation_subtest(start=start, amount="1000", drawdown_loan_instances=2),
            SubTest(
                description="Check due amounts",
                expected_balances_at_ts={
                    first_due_amount_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-91.21")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.PRINCIPAL_DUE, Decimal("77.55")),
                            (dimensions.INTEREST_DUE, Decimal("14.29")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-91.21")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.TOTAL_PRINCIPAL_DUE, Decimal("155.1")),
                            (dimensions.TOTAL_INTEREST_DUE, Decimal("28.58")),
                            (dimensions.TOTAL_ORIGINAL_PRINCIPAL, Decimal("2000")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Pay off all outstanding amounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        # due amounts = (77.55 + 14.29) * 2 = 183.68
                        # non due principal = 2000 - 155.1 = 1844.9
                        # overpayment fee = 1844.9 * 0.05 / (1-0.05) = 97.10
                        # total payment required = 183.68 + 1844.9 + 97.10 = 2125.68
                        amount="2125.68",
                        event_datetime=payment_event,
                        target_account_id=f"{accounts.LOC_ACCOUNT}_0",
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_balances_at_ts={
                    payment_event: {
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_0": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("922.45")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-921.82")),
                        ],
                        f"{accounts.DRAWDOWN_LOAN_ACCOUNT}_1": [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.OVERPAYMENT, Decimal("922.45")),
                            (dimensions.EMI, Decimal("90.21")),
                            (dimensions.EMI_PRINCIPAL_EXCESS, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.ACCRUED_EXPECTED_INTEREST, Decimal("0")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-921.82")),
                        ],
                        f"{accounts.LOC_ACCOUNT}_0": [
                            # 2000 - 2125.68 (repayment) + 97.10 (overpayment fee) = -28.58
                            (dimensions.DEFAULT, Decimal("-28.58")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_EMI, Decimal("180.42")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("0")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.TOTAL_ORIGINAL_PRINCIPAL, Decimal("2000")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=payment_event,
                        account_id=f"{accounts.LOC_ACCOUNT}_0",
                        name="total_original_principal",
                        value="2000.00",
                    ),
                ],
            ),
            SubTest(
                description="Close both drawdown loans",
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
                            (dimensions.DEFAULT, Decimal("2000")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.TOTAL_EMI, Decimal("0")),
                            (dimensions.TOTAL_PRINCIPAL, Decimal("0")),
                            (dimensions.TOTAL_ACCRUED_INTEREST_RECEIVABLE, Decimal("0")),
                            (dimensions.TOTAL_ORIGINAL_PRINCIPAL, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=payment_event,  # the notification is sent upon payment
                        notification_type=line_of_credit_supervisor.LOANS_PAID_OFF_NOTIFICATION,
                        notification_details={
                            "account_ids": dumps(
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
                        timestamp=close_date + relativedelta(seconds=1),
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
            supervisor_config=self._get_default_supervisor_config(drawdown_loan_instances=2),
            internal_accounts=accounts.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)
