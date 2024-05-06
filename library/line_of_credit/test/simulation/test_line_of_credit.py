# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# library
from library.line_of_credit.constants import accounts, dimensions, files, test_parameters

# inception sdk
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase


class LineOfCreditLoanTest(SimulationTestCase):
    account_id_base = accounts.LOC_ACCOUNT
    contract_filepaths = [files.LOC_CONTRACT]
    internal_accounts = accounts.default_internal_accounts
    default_instance_params = test_parameters.loc_instance_params
    default_template_params = test_parameters.loc_template_params

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=True,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.LOC_CONTRACT],
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
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

    def test_new_drawdowns_only_accepted_if_each_loan_within_loan_limit(self):
        # Ensure that each new drawdown adheres to the minimum and maximum loan limit

        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 23, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="Drawdown at minimum loan amount limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start,
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start: {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "50")]}
                },
            ),
            SubTest(
                description="Drawdown at maximum loan amount limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "1050")]}
                },
            ),
            SubTest(
                description="Drawdown over maximum loan amount limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot create loan larger than maximum loan amount "
                        "limit of: 1000.",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Drawdown under minimum loan amount limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="49",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot create loan smaller than minimum loan amount "
                        "limit of: 50.",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Ensure max and min loan limit are not considered for repayments",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="49",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(hours=5),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=5): {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "0")]}
                },
            ),
            SubTest(
                description="Drawdown over maximum loan amount limit accepted with force override",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1001",
                        event_datetime=start + relativedelta(hours=6),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=6): {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "1001")]}
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=self.default_template_params,
            instance_params=self.default_instance_params,
            internal_accounts=self.internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_repayments_rejected_during_repayment_holiday(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(hours=2)

        sub_tests = [
            SubTest(
                description="Create flag definition",
                events=[create_flag_definition_event(start, test_parameters.REPAYMENT_HOLIDAY)],
            ),
            SubTest(
                description="Apply flag",
                events=[
                    create_flag_event(
                        timestamp=start + relativedelta(hours=1),
                        flag_definition_id=test_parameters.REPAYMENT_HOLIDAY,
                        account_id=accounts.LOC_ACCOUNT,
                        effective_timestamp=start + relativedelta(hours=1),
                        expiry_timestamp=end,
                    )
                ],
            ),
            SubTest(
                description="Ensure repayments are rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Repayments blocked for this account",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=self.default_template_params,
            instance_params=self.default_instance_params,
            internal_accounts=self.internal_accounts,
        )
        self.run_test_scenario(test_scenario)
