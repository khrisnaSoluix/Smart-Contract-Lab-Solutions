# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

# library
from library.bnpl.constants import accounts, dimensions, files, test_parameters
from library.bnpl.contracts.template import bnpl

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_product_version_update_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    ExpectedRejection,
    SimulationTestCase,
)

bnpl_instance_params = test_parameters.bnpl_instance_params
bnpl_template_params = test_parameters.bnpl_template_params
default_denomination = test_parameters.default_denomination


class BNPLTest(SimulationTestCase):
    account_id_base = accounts.BNPL
    contract_filepaths = [files.BNPL_CONTRACT]
    internal_accounts = test_parameters.default_internal_accounts
    total_repayment_count = int(
        bnpl_instance_params[bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT]
    )
    repayment_period = int(bnpl_template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])
    grace_period = int(bnpl_template_params[bnpl.delinquency.PARAM_GRACE_PERIOD])

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
            contract_content=self.smart_contract_path_to_content[files.BNPL_CONTRACT],
            template_params=template_params or bnpl_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or bnpl_instance_params,
                    account_id_base=self.account_id_base,
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

    def test_account_opening_disbursement(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(minutes=1)

        instance_params = bnpl_instance_params.copy()
        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, "120")],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_bnpl_close_account_successful(self):
        start = test_parameters.default_simulation_start_date
        repayment_1_date = start + relativedelta(minutes=10)
        end = start + relativedelta(minutes=20)

        instance_params = {
            **bnpl_instance_params,
            bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: "1",
        }

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("120")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("120")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [
                            (
                                dimensions.DEFAULT,
                                str(instance_params[bnpl.disbursement.PARAM_PRINCIPAL]),
                            )
                        ],
                    }
                },
            ),
            SubTest(
                description="Pay the whole loan",
                events=[
                    # Principal
                    create_inbound_hard_settlement_instruction(
                        amount="120",
                        event_datetime=repayment_1_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    ),
                ],
                expected_balances_at_ts={
                    repayment_1_date
                    + relativedelta(minutes=1): {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("120")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=repayment_1_date,
                        notification_type=bnpl.LOAN_PAID_OFF_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=self.account_id_base,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        self.account_id_base: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            # EMI must zero out.
                            (dimensions.EMI, Decimal("0")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
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
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    # TODO Make an E2E test case for this [INC-8364].
    def test_bnpl_close_account_failed(self):
        start = test_parameters.default_simulation_start_date
        close_datetime = start + relativedelta(minutes=10)
        end = start + relativedelta(minutes=20)

        instance_params = {
            **bnpl_instance_params,
            bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT: "1",
        }

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    start: {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.EMI, Decimal("120")),
                            (dimensions.INTEREST_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("120")),
                            (dimensions.INTEREST_OVERDUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                        accounts.DEPOSIT: [
                            (
                                dimensions.DEFAULT,
                                str(instance_params[bnpl.disbursement.PARAM_PRINCIPAL]),
                            )
                        ],
                    }
                },
            ),
            SubTest(
                description="Close the account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=close_datetime,
                        account_id=self.account_id_base,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        with self.assertRaises(Exception) as context:
            self.run_test_scenario(test_scenario)
        # Needs to be changed to assertEqual since right now its returning the http code also
        # Return value right now:
        # {'grpc_code': 3, 'http_code': 400, 'message': 'The loan cannot be closed until all
        # outstanding debt is repaid', 'http_status': 'Bad Request', 'details': []}
        self.assertIn(
            "The loan cannot be closed until all outstanding debt is repaid",
            str(context.exception),
        )

    def test_due_amount_monthly_schedules_with_repayments_final_due_amount_is_remaining_principal(
        self,
    ):
        start_datetime = test_parameters.default_simulation_start_date
        repayment_frequency = bnpl.config_repayment_frequency.MONTHLY
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
            bnpl.disbursement.PARAM_PRINCIPAL: "315.73",
        }

        template_params = {**bnpl_template_params}

        due_amount_notification_hour = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR]
        )
        due_amount_notification_minute = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE]
        )
        due_amount_notification_second = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND]
        )

        notification_period = int(
            template_params[bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD]
        )
        repayment_period = int(template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])
        end_datetime = start_datetime + relativedelta(
            months=3, days=5
        )  # to account for repayment period
        repayment_1_datetime = start_datetime + relativedelta(days=1, minutes=1)
        due_amount_calc_1_datetime = start_datetime + relativedelta(
            months=1, hour=0, minute=1, second=0
        )
        due_amount_notification_1_datetime = due_amount_calc_1_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_1_datetime = due_amount_calc_1_datetime + relativedelta(days=repayment_period)
        repayment_2_datetime = due_amount_calc_1_datetime + relativedelta(days=1)

        due_amount_calc_2_datetime = due_amount_calc_1_datetime + relativedelta(months=1)
        due_amount_notification_2_datetime = due_amount_calc_2_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_2_datetime = due_amount_calc_2_datetime + relativedelta(days=repayment_period)
        repayment_3_datetime = due_amount_calc_2_datetime + relativedelta(days=1)

        due_amount_calc_3_datetime = due_amount_calc_2_datetime + relativedelta(months=1)
        due_amount_notification_3_datetime = due_amount_calc_3_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_3_datetime = due_amount_calc_3_datetime + relativedelta(days=repayment_period)
        repayment_4_datetime = due_amount_calc_3_datetime + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="EMI should be charged in advanced on account opening",
                expected_balances_at_ts={
                    start_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("236.8")),
                            (dimensions.PRINCIPAL_DUE, Decimal("78.93")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Principal due cleared out after 1st repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="78.93",
                        event_datetime=repayment_1_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("236.8")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                        accounts.DEPOSIT: [(dimensions.DEFAULT, Decimal("315.73"))],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 1 month",
                expected_balances_at_ts={
                    due_amount_calc_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("157.87")),
                            (dimensions.PRINCIPAL_DUE, Decimal("78.93")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_1_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("78.93"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_1_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after after 2nd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="78.93",
                        event_datetime=repayment_2_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("157.87")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("2")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 2 months",
                expected_balances_at_ts={
                    due_amount_calc_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("78.94")),
                            (dimensions.PRINCIPAL_DUE, Decimal("78.93")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_2_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("78.93"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_2_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 3rd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="78.93",
                        event_datetime=repayment_3_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("78.94")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("3")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation for final month must take all the remaining"
                " principal even if emi is less than principal",
                expected_balances_at_ts={
                    due_amount_calc_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("78.94")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("4")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_3_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("78.94"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_3_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 4th repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="78.94",
                        event_datetime=repayment_4_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("4")),
                        ],
                    },
                },
            ),
            SubTest(
                description="schedules should occur with a monthly cadence",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            due_amount_calc_1_datetime,
                            due_amount_calc_2_datetime,
                            due_amount_calc_3_datetime,
                        ],
                        event_id=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=accounts.BNPL,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_due_amount_weekly_schedules_with_repayments(self):
        start_datetime = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        repayment_frequency = bnpl.config_repayment_frequency.WEEKLY
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }
        template_params = {**bnpl_template_params}
        due_amount_notification_hour = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR]
        )
        due_amount_notification_minute = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE]
        )
        due_amount_notification_second = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND]
        )

        notification_period = int(
            template_params[bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD]
        )
        repayment_period = int(template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])

        repayment_1_datetime = start_datetime + relativedelta(days=1, minute=1)
        due_amount_calc_2_datetime = start_datetime + relativedelta(weeks=1, minute=1)
        due_amount_notification_2_date = due_amount_calc_2_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_2_datetime = due_amount_calc_2_datetime + relativedelta(
            days=repayment_period,
        )
        repayment_2_datetime = start_datetime + relativedelta(weeks=1, days=1)
        due_amount_calc_3_datetime = start_datetime + relativedelta(weeks=2, minute=1)
        due_amount_notification_3_datetime = due_amount_calc_3_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_3_datetime = due_amount_calc_3_datetime + relativedelta(
            days=repayment_period,
        )
        repayment_3_datetime = start_datetime + relativedelta(weeks=2, days=1)
        due_amount_calc_4_datetime = start_datetime + relativedelta(weeks=3, minute=1)
        due_amount_notification_4_datetime = due_amount_calc_4_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_4_datetime = due_amount_calc_4_datetime + relativedelta(
            days=repayment_period,
        )
        end_datetime = due_amount_calc_4_datetime

        sub_tests = [
            SubTest(
                description="EMI should be charged in advanced on account opening",
                expected_balances_at_ts={
                    start_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Principal due cleared out after 1st repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_1_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 1 week",
                expected_balances_at_ts={
                    due_amount_calc_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_2_date,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_2_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 2nd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_2_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 2 weeks",
                expected_balances_at_ts={
                    due_amount_calc_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_3_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_3_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 3rd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_3_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 3 weeks",
                expected_balances_at_ts={
                    due_amount_calc_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_4_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_4_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_due_amount_fortnightly_schedules_with_repayments(self):
        start_datetime = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        repayment_frequency = bnpl.config_repayment_frequency.FORTNIGHTLY
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }
        template_params = {**bnpl_template_params}
        due_amount_notification_hour = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR]
        )
        due_amount_notification_minute = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE]
        )
        due_amount_notification_second = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND]
        )

        notification_period = int(
            template_params[bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD]
        )

        repayment_period = int(template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])
        repayment_1_datetime = start_datetime + relativedelta(days=1, minute=1)
        due_amount_calc_2_datetime = start_datetime + relativedelta(weeks=2, minute=1)
        due_amount_notification_2_datetime = due_amount_calc_2_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_2_datetime = due_amount_calc_2_datetime + relativedelta(
            days=repayment_period,
        )
        repayment_2_datetime = start_datetime + relativedelta(weeks=2, days=1)
        due_amount_calc_3_datetime = start_datetime + relativedelta(weeks=4, minute=1)
        due_amount_notification_3_datetime = due_amount_calc_3_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_3_datetime = due_amount_calc_3_datetime + relativedelta(
            days=repayment_period,
        )
        repayment_3_datetime = start_datetime + relativedelta(weeks=4, days=1)
        due_amount_calc_4_datetime = start_datetime + relativedelta(weeks=6, minute=1)
        due_amount_notification_4_datetime = due_amount_calc_4_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_4_datetime = due_amount_calc_4_datetime + relativedelta(
            days=repayment_period,
        )
        end_datetime = due_amount_calc_4_datetime

        repayment_frequency = bnpl.config_repayment_frequency.FORTNIGHTLY
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }

        sub_tests = [
            SubTest(
                description="EMI should be charged in advanced on account opening",
                expected_balances_at_ts={
                    start_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Principal due cleared out after 1st repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_1_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 2 weeks",
                expected_balances_at_ts={
                    due_amount_calc_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_2_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_2_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 2nd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_2_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 4 weeks",
                expected_balances_at_ts={
                    due_amount_calc_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_3_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_3_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Principal due cleared out after 3rd repayment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_3_datetime,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 6 weeks",
                expected_balances_at_ts={
                    due_amount_calc_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_4_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_4_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_full_lifecycle_without_monthly_repayments(self):
        start_datetime = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        repayment_frequency = bnpl.config_repayment_frequency.MONTHLY
        frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[repayment_frequency]
        due_amount_calc_1_datetime = start_datetime + relativedelta(minutes=1)
        overdue_1_datetime = start_datetime + relativedelta(days=self.repayment_period, minute=1)
        late_repay_1_datetime = overdue_1_datetime + relativedelta(days=self.grace_period, minute=1)
        delinquency_notification_datetime = late_repay_1_datetime + (
            frequency_delta
            * (self.total_repayment_count - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET)
        )
        end_datetime = delinquency_notification_datetime

        sub_tests = self.full_lifecycle_without_repayments_sub_tests(
            start_datetime=start_datetime,
            due_amount_calc_1_datetime=due_amount_calc_1_datetime,
            overdue_1_datetime=overdue_1_datetime,
            late_repay_1_datetime=late_repay_1_datetime,
            delinquency_notification_datetime=delinquency_notification_datetime,
            repayment_frequency_delta=frequency_delta,
        )

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_full_lifecycle_without_weekly_repayments(self):
        start_datetime = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        repayment_frequency = bnpl.config_repayment_frequency.WEEKLY
        frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[repayment_frequency]
        due_amount_calc_1_datetime = start_datetime + relativedelta(minutes=1)
        overdue_1_datetime = start_datetime + relativedelta(days=self.repayment_period, minute=1)
        late_repay_1_datetime = overdue_1_datetime + relativedelta(days=self.grace_period, minute=1)
        delinquency_notification_datetime = late_repay_1_datetime + (
            frequency_delta
            * (self.total_repayment_count - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET)
        )
        end_datetime = delinquency_notification_datetime
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }

        sub_tests = self.full_lifecycle_without_repayments_sub_tests(
            start_datetime=start_datetime,
            due_amount_calc_1_datetime=due_amount_calc_1_datetime,
            overdue_1_datetime=overdue_1_datetime,
            late_repay_1_datetime=late_repay_1_datetime,
            delinquency_notification_datetime=delinquency_notification_datetime,
            repayment_frequency_delta=frequency_delta,
        )

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )

        self.run_test_scenario(test_scenario)

    def test_full_lifecycle_without_fortnightly_repayments(self):
        start_datetime = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        repayment_frequency = bnpl.config_repayment_frequency.FORTNIGHTLY
        frequency_delta = bnpl.config_repayment_frequency.FREQUENCY_MAP[repayment_frequency]
        due_amount_calc_1_datetime = start_datetime + relativedelta(minutes=1)
        overdue_1_datetime = start_datetime + relativedelta(days=self.repayment_period, minute=1)
        late_repay_1_datetime = overdue_1_datetime + relativedelta(days=self.grace_period, minute=1)
        delinquency_notification_datetime = late_repay_1_datetime + (
            frequency_delta
            * (self.total_repayment_count - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET)
        )
        end_datetime = delinquency_notification_datetime

        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }

        sub_tests = self.full_lifecycle_without_repayments_sub_tests(
            start_datetime=start_datetime,
            due_amount_calc_1_datetime=due_amount_calc_1_datetime,
            overdue_1_datetime=overdue_1_datetime,
            late_repay_1_datetime=late_repay_1_datetime,
            delinquency_notification_datetime=delinquency_notification_datetime,
            repayment_frequency_delta=frequency_delta,
        )

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
            debug=True,
        )

        self.run_test_scenario(test_scenario)

    def full_lifecycle_without_repayments_sub_tests(
        self,
        start_datetime: datetime,
        due_amount_calc_1_datetime: datetime,
        overdue_1_datetime: datetime,
        late_repay_1_datetime: datetime,
        delinquency_notification_datetime: datetime,
        repayment_frequency_delta: relativedelta,
    ):
        due_amount_notification_hour = int(
            bnpl_template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR]
        )
        due_amount_notification_minute = int(
            bnpl_template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE]
        )
        due_amount_notification_second = int(
            bnpl_template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND]
        )

        notification_period = int(
            bnpl_template_params[bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD]
        )
        # Second repayment cycle
        due_amount_calc_2_datetime = due_amount_calc_1_datetime + repayment_frequency_delta
        due_amount_notification_2_datetime = due_amount_calc_2_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_2_datetime = overdue_1_datetime + repayment_frequency_delta
        late_repay_2_datetime = late_repay_1_datetime + repayment_frequency_delta
        # Third repayment cycle
        due_amount_calc_3_datetime = due_amount_calc_1_datetime + (repayment_frequency_delta * 2)
        due_amount_notification_3_datetime = due_amount_calc_3_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_3_datetime = overdue_1_datetime + (repayment_frequency_delta * 2)
        late_repay_3_datetime = late_repay_1_datetime + (repayment_frequency_delta * 2)
        # Fourth repayment cycle
        due_amount_calc_4_datetime = due_amount_calc_1_datetime + (repayment_frequency_delta * 3)
        due_amount_notification_4_datetime = due_amount_calc_4_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_4_datetime = overdue_1_datetime + (repayment_frequency_delta * 3)
        late_repay_4_datetime = late_repay_1_datetime + (repayment_frequency_delta * 3)
        delinquency_notification_datetime = delinquency_notification_datetime

        return [
            SubTest(
                description="EMI should be charged in advanced on account opening",
                expected_balances_at_ts={
                    start_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check overdue amount for 1st due repayment",
                expected_balances_at_ts={
                    overdue_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_1_datetime,
                        notification_type=bnpl.OVERDUE_REPAYMENT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "overdue_interest": "0",
                            "overdue_principal": "30",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_1_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check late repayment fee is charged for 1st due repayment",
                expected_balances_at_ts={
                    late_repay_1_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 2 weeks",
                expected_balances_at_ts={
                    due_amount_calc_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_2_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_2_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amount for 2nd due repayment",
                expected_balances_at_ts={
                    overdue_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("60")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_2_datetime,
                        notification_type=bnpl.OVERDUE_REPAYMENT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "overdue_interest": "0",
                            "overdue_principal": "30",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_2_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check late repayment fee is charged for 2nd due repayment",
                expected_balances_at_ts={
                    late_repay_2_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("60")),
                            (dimensions.PENALTIES, Decimal("50")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 4 weeks",
                expected_balances_at_ts={
                    due_amount_calc_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("60")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_3_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_3_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amount for 3rd due repayment",
                expected_balances_at_ts={
                    overdue_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("90")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_3_datetime,
                        notification_type=bnpl.OVERDUE_REPAYMENT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "overdue_interest": "0",
                            "overdue_principal": "30",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_3_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check late repayment fee is charged for 3rd due repayment",
                expected_balances_at_ts={
                    late_repay_3_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("90")),
                            (dimensions.PENALTIES, Decimal("75")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Due amount calculation after 6 weeks",
                expected_balances_at_ts={
                    due_amount_calc_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("90")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=due_amount_notification_4_datetime,
                        notification_type=bnpl.DUE_AMOUNT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "due_principal": str("30"),
                            "due_interest": str("0"),
                            "overdue_date": str(overdue_4_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    ),
                ],
            ),
            SubTest(
                description="Check overdue amount for 4th due repayment",
                expected_balances_at_ts={
                    overdue_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("120")),
                            (dimensions.PENALTIES, Decimal("75")),
                        ],
                    },
                },
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=overdue_4_datetime,
                        notification_type=bnpl.OVERDUE_REPAYMENT_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                            "overdue_interest": "0",
                            "overdue_principal": "30",
                            "late_repayment_fee": "25",
                            "overdue_date": str(overdue_4_datetime.date()),
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Check late repayment fee is charged for 4th due repayment",
                expected_balances_at_ts={
                    late_repay_4_datetime: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("120")),
                            (dimensions.PENALTIES, Decimal("100")),
                        ],
                    },
                },
            ),
            SubTest(
                description="Check delinquency notification",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=delinquency_notification_datetime,
                        notification_type=bnpl.DELINQUENCY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

    def test_derived_parameters(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        due_amount_1_overdue_date = start + relativedelta(days=4)
        due_amount_calc_2_date = start + relativedelta(months=1, minute=1)
        due_amount_calc_3_date = start + relativedelta(months=2, minute=1)
        due_amount_calc_4_date = start + relativedelta(months=3, minute=1)
        repayment_date = start + relativedelta(months=3, hour=1)
        end = repayment_date

        sub_tests = [
            SubTest(
                description="Check derived parameters after opening",
                expected_balances_at_ts={
                    after_opening: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="3 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=after_opening,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="First due amount becomes overdue",
                expected_balances_at_ts={
                    due_amount_1_overdue_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-02-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="3 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_1_overdue_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Check derived parameters on second due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_2_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-03-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="2 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="145.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_2_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Check derived parameters on third due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_3_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("30")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("60")),
                            (dimensions.PENALTIES, Decimal("50")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="1 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="170.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_3_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Check derived parameters on fourth due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_4_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("90")),
                            (dimensions.PENALTIES, Decimal("75")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="0 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="195.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="120.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=due_amount_calc_4_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="0.00",
                    ),
                ],
            ),
            SubTest(
                description="Repay all outstanding debt",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="195",
                        event_datetime=repayment_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.emi.PARAM_EQUATED_INSTALMENT_AMOUNT,
                        value="30",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_LOAN_END_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_NEXT_REPAYMENT_DATE,
                        value="2020-04-01",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.config_repayment_frequency.PARAM_REMAINING_TERM,
                        value="0 month(s)",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_OUTSTANDING_DEBT,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_TOTAL_REMAINING_PRINCIPAL,
                        value="0.00",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=repayment_date,
                        account_id=accounts.BNPL,
                        name=bnpl.derived_params.PARAM_PRINCIPAL_PAID_TO_DATE,
                        value="120.00",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_repayment_rejected_on_overpayment_of_due(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        repayment_1_date = start + relativedelta(days=3)
        due_amount_calc_2_date = start + relativedelta(months=1, minute=1)
        repayment_2_date = start + relativedelta(months=1, days=3)
        end = repayment_2_date

        sub_tests = [
            SubTest(
                description="Check balances after opening",
                expected_balances_at_ts={
                    after_opening: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment rejected on overpayment of due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="40",
                        event_datetime=repayment_1_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        repayment_1_date,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than what is due.",
                    )
                ],
            ),
            SubTest(
                description="Check balances on second repayment due date",
                expected_balances_at_ts={
                    due_amount_calc_2_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment rejected on overpayment of due "
                "(including penalties and overdue)",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="90",
                        event_datetime=repayment_2_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        repayment_2_date,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than what is due.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_repayment_rejected_on_overpayment_of_total_debt(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        repayment_1_date = start + relativedelta(days=3)
        due_amount_calc_2_date = start + relativedelta(months=1, minute=1)
        repayment_2_date = start + relativedelta(months=1, days=3)
        end = repayment_2_date

        sub_tests = [
            SubTest(
                description="Check balances after opening",
                expected_balances_at_ts={
                    after_opening: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment rejected on overpayment of total debt",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="130",
                        event_datetime=repayment_1_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        repayment_1_date,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than what is owed.",
                    )
                ],
            ),
            SubTest(
                description="Check balances on second repayment due date",
                expected_balances_at_ts={
                    due_amount_calc_2_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment rejected on overpayment of total debt",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="150",
                        event_datetime=repayment_2_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_2_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("60")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("25")),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        repayment_2_date,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot pay more than what is owed.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_debit_rejected(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        end = after_opening

        sub_tests = [
            SubTest(
                description="Reject debit posting from BNPL account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        event_datetime=after_opening,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        after_opening,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Debiting from this account is not allowed.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_repayment_repays_debt_in_order(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        repayment_1_date = start + relativedelta(days=3)
        due_amount_calc_4_date = start + relativedelta(months=3, minute=1)
        repayment_4_pay_overdue_date = start + relativedelta(months=3, minute=7)
        repayment_4_pay_penalties_date = start + relativedelta(months=3, minute=12)
        repayment_4_pay_due_date = start + relativedelta(months=3, minute=40)
        end = repayment_4_pay_due_date

        sub_tests = [
            SubTest(
                description="Check balances after opening",
                expected_balances_at_ts={
                    after_opening: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment pays out principal due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_1_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_1_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DEFAULT, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Check balances after third due amount calculation",
                expected_balances_at_ts={
                    due_amount_calc_4_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("60")),
                            (dimensions.PENALTIES, Decimal("50")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment pays out overdue",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="60",
                        event_datetime=repayment_4_pay_overdue_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_4_pay_overdue_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("50")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment pays penalties",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=repayment_4_pay_penalties_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_4_pay_penalties_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
            SubTest(
                description="Repayment pays out principal due",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=repayment_4_pay_due_date,
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        denomination=default_denomination,
                    )
                ],
                expected_balances_at_ts={
                    repayment_4_pay_due_date: {
                        accounts.BNPL: [
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("0")),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_delinquency_notification_sent(self):
        """
        Test if the due, overdue or principal is not 0 there should be a notification sent.
        """
        start = test_parameters.default_simulation_start_date
        total_repayment_count = int(
            bnpl_instance_params[bnpl.lending_params.PARAM_TOTAL_REPAYMENT_COUNT]
        )
        repayment_period = int(bnpl_template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])
        grace_period = int(bnpl_template_params[bnpl.delinquency.PARAM_GRACE_PERIOD])
        delinquency_notification_end_days = repayment_period + grace_period
        end = start + relativedelta(
            months=total_repayment_count, days=delinquency_notification_end_days
        )
        delinquency_notification_date = start + relativedelta(
            months=total_repayment_count - bnpl.emi_in_advance.EMI_IN_ADVANCE_OFFSET,
            days=delinquency_notification_end_days,
            hour=int(bnpl_template_params[bnpl.delinquency.PARAM_CHECK_DELINQUENCY_HOUR]),
            minute=int(bnpl_template_params[bnpl.delinquency.PARAM_CHECK_DELINQUENCY_MINUTE]),
            second=int(bnpl_template_params[bnpl.delinquency.PARAM_CHECK_DELINQUENCY_SECOND]),
        )
        instance_params = {
            **bnpl_instance_params,
        }

        sub_tests = [
            SubTest(
                description="Schedule should occur only once in the entire BNPL product lifecycle.",
                expected_balances_at_ts={
                    delinquency_notification_date: {
                        accounts.BNPL: [
                            (dimensions.PRINCIPAL_OVERDUE, Decimal("120")),
                            (dimensions.PRINCIPAL_DUE, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("0")),
                            (dimensions.PENALTIES, Decimal("100")),
                        ],
                    }
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            delinquency_notification_date,
                        ],
                        event_id=bnpl.delinquency.CHECK_DELINQUENCY_EVENT,
                        account_id=accounts.BNPL,
                    ),
                ],
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=delinquency_notification_date,
                        notification_type=bnpl.DELINQUENCY_NOTIFICATION,
                        notification_details={
                            "account_id": accounts.BNPL,
                        },
                        resource_id=accounts.BNPL,
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_posting_accepted_for_force_override(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=30)

        sub_tests = [
            SubTest(
                description="Test force override accepts postings, even with wrong denomination.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        instruction_details={"force_override": "true"},
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.BNPL: [
                            (dimensions.USD_DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-31")),
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                    start
                    + relativedelta(seconds=3): {
                        accounts.BNPL: [
                            (dimensions.USD_DEFAULT, Decimal("-30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-31")),
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_no_repayment_postings_generated_for_force_override(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=30)

        sub_tests = [
            SubTest(
                description="Test that when force override is accepted "
                "no extra postings are generated.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="30",
                        event_datetime=start + relativedelta(seconds=3),
                        target_account_id=accounts.BNPL,
                        internal_account_id="1",
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start: {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("0")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-31")),
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                    end: {
                        accounts.BNPL: [
                            (dimensions.DEFAULT, Decimal("-30")),
                            (dimensions.PRINCIPAL, Decimal("90")),
                            (dimensions.PRINCIPAL_DUE, Decimal("30")),
                            (dimensions.INTERNAL_CONTRA, Decimal("-31")),
                            (dimensions.EMI, Decimal("30")),
                            (dimensions.PENALTIES, Decimal("0")),
                            (dimensions.DUE_CALCULATION_EVENT_COUNTER, Decimal("1")),
                        ],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(start=start, end=end, sub_tests=sub_tests)
        self.run_test_scenario(test_scenario)

    def test_restricted_parameter_change(self):
        start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        after_opening = start + relativedelta(hours=1)
        end = after_opening

        sub_tests = [
            SubTest(
                description="Reject restricted parameter change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=after_opening, account_id=accounts.BNPL, principal="10"
                    )
                ],
                expected_parameter_change_rejections=[
                    ExpectedRejection(
                        after_opening,
                        account_id=accounts.BNPL,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="T&Cs of this loan cannot be changed once opened.",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=bnpl_instance_params,
            internal_accounts=test_parameters.default_internal_accounts,
            debug=True,
        )
        self.run_test_scenario(test_scenario)

    def test_schedules_are_preserved_after_conversion(self):
        """
        Test ~ a month's worth of schedules running as expected after two account conversions:
        - the first on account opening day
        - the second at mid month

        Test setup borrowed from test_due_amount_monthly_schedules
        """
        start_datetime = test_parameters.default_simulation_start_date
        repayment_frequency = bnpl.config_repayment_frequency.MONTHLY
        instance_params = {
            **bnpl_instance_params,
            bnpl.config_repayment_frequency.PARAM_REPAYMENT_FREQUENCY: repayment_frequency,
        }

        template_params = {**bnpl_template_params}

        due_amount_notification_hour = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_HOUR]
        )
        due_amount_notification_minute = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_MINUTE]
        )
        due_amount_notification_second = int(
            template_params[bnpl.due_amount_notification.PARAM_DUE_NOTIFICATION_SECOND]
        )

        notification_period = int(
            template_params[bnpl.due_amount_notification.PARAM_NOTIFICATION_PERIOD]
        )
        repayment_period = int(template_params[bnpl.overdue.PARAM_REPAYMENT_PERIOD])
        grace_period = int(template_params[bnpl.delinquency.PARAM_GRACE_PERIOD])
        end_datetime = start_datetime + relativedelta(
            months=1, days=repayment_period + grace_period + 1
        )  # to account for repayment period and grace period

        # Define expected schedule timings
        overdue_1_datetime = start_datetime + relativedelta(
            days=repayment_period, minutes=1, seconds=0
        )
        check_late_repayment_1_datetime = overdue_1_datetime + relativedelta(days=grace_period)
        due_amount_calc_datetime = datetime(
            year=2020, month=2, day=5, hour=0, minute=1, second=0, tzinfo=ZoneInfo("UTC")
        )
        due_amount_notification_datetime = due_amount_calc_datetime - relativedelta(
            days=notification_period,
            hour=due_amount_notification_hour,
            minute=due_amount_notification_minute,
            second=due_amount_notification_second,
        )
        overdue_2_datetime = due_amount_calc_datetime + relativedelta(days=repayment_period)
        check_late_repayment_2_datetime = overdue_2_datetime + relativedelta(days=grace_period)

        # Define the conversion timings
        conversion_1 = start_datetime + relativedelta(hour=1)
        convert_to_version_id_1 = "5"
        convert_to_contract_config_1 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.BNPL_CONTRACT],
            smart_contract_version_id=convert_to_version_id_1,
            template_params=template_params,
            account_configs=[],
        )
        conversion_2 = conversion_1 + relativedelta(days=15)
        convert_to_version_id_2 = "6"
        convert_to_contract_config_2 = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.BNPL_CONTRACT],
            smart_contract_version_id=convert_to_version_id_2,
            template_params=template_params,
            account_configs=[],
        )

        sub_tests = [
            SubTest(
                description="Trigger Conversions and Check Schedules at EoM",
                events=[
                    create_account_product_version_update_instruction(
                        timestamp=conversion_1,
                        account_id=accounts.BNPL,
                        product_version_id=convert_to_version_id_1,
                    ),
                    create_account_product_version_update_instruction(
                        timestamp=conversion_2,
                        account_id=accounts.BNPL,
                        product_version_id=convert_to_version_id_2,
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        # First overdue event is always repayment_period days after account opening
                        run_times=[
                            overdue_1_datetime,
                            overdue_2_datetime,
                        ],
                        event_id=bnpl.overdue.CHECK_OVERDUE_EVENT,
                        account_id=accounts.BNPL,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            check_late_repayment_1_datetime,
                            check_late_repayment_2_datetime,
                        ],
                        event_id=bnpl.late_repayment.CHECK_LATE_REPAYMENT_EVENT,
                        account_id=accounts.BNPL,
                        count=2,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            due_amount_notification_datetime,
                        ],
                        event_id=bnpl.due_amount_notification.NOTIFY_DUE_AMOUNT_EVENT,
                        account_id=accounts.BNPL,
                        count=1,
                    ),
                    ExpectedSchedule(
                        run_times=[
                            due_amount_calc_datetime,
                        ],
                        event_id=bnpl.due_amount_calculation.DUE_AMOUNT_CALCULATION_EVENT,
                        account_id=accounts.BNPL,
                        count=1,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(
            test_scenario,
            smart_contracts=[convert_to_contract_config_1, convert_to_contract_config_2],
        )
