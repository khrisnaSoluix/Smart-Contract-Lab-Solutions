# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_event,
    create_flag_definition_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    SimulationTestScenario,
    SubTest,
    ContractConfig,
    AccountConfig,
    ExpectedRejection,
    ExpectedDerivedParameter,
)

import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters


LOC_ACCOUNT = "LINE_OF_CREDIT"
LINE_OF_CREDIT = "line_of_credit"

default_instance_params = test_parameters.loc_instance_params
default_template_params = test_parameters.loc_template_params


class LineOfCreditTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [contract_files.LOC_CONTRACT]

        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            "line_of_credit": "1000",
            "drawdown_loan": "2000",
        }
        super().setUpClass()

    account_id_base = accounts.LOC_ACCOUNT
    default_instance_params = default_instance_params
    default_template_params = default_template_params

    def _get_simulation_test_scenario(
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
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=self.account_id_base,
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.LOC_CONTRACT],
            clu_resource_id=LINE_OF_CREDIT,
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS[LINE_OF_CREDIT],
        )

        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=self.internal_accounts or internal_accounts,
            debug=debug,
        )

    def test_force_override_forces_postings_to_be_accepted(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 1, tzinfo=timezone.utc)
        instance_params = default_instance_params.copy()
        instance_params["credit_limit"] = "10000"

        sub_tests = [
            SubTest(
                description="Posting above max loan limit rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100000",
                        event_datetime=start,
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Cannot create loan larger than maximum loan amount "
                        "limit of: 10000.",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Same posting accepted with force override",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100000",
                        event_datetime=start,
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "100000")],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=default_template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
            debug=True,
        )
        self.run_test_scenario(test_scenario)

    def test_3_A_B_new_drawdowns_only_accepted_if_each_loan_within_loan_limit(self):
        # Ensure that each new drawdown adheres to the minimum and maximum loan limit

        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 23, tzinfo=timezone.utc)

        # reducing so that we do not hit the credit_limit
        template_params_decreased_max_loan_limit = default_template_params.copy()
        template_params_decreased_max_loan_limit["maximum_loan_amount"] = "2000"
        instance_params = default_instance_params.copy()
        instance_params["credit_limit"] = "10000"

        sub_tests = [
            SubTest(
                description="Drawdown at minimum loan amount limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start: {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "1000")]}
                },
            ),
            SubTest(
                description="Drawdown at maximum loan amount limit - accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {accounts.LOC_ACCOUNT: [(dimensions.DEFAULT, "3000")]}
                },
            ),
            SubTest(
                description="Drawdown over maximum loan amount limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2001",
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
                        "limit of: 2000.",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Drawdown under minimum loan amount limit - rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="999",
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
                        "limit of: 1000.",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Ensure max and min loan limit are not considered for repayments",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="999",
                        event_datetime=start + relativedelta(hours=3),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="2001",
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
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params_decreased_max_loan_limit,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_11_f_repayments_rejected_during_repayment_holiday(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Create Flag definition",
                events=[create_flag_definition_event(start, "REPAYMENT_HOLIDAY")],
            ),
            SubTest(
                description="Apply Flag",
                events=[
                    create_flag_event(
                        timestamp=start + relativedelta(hours=1),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id=accounts.LOC_ACCOUNT,
                        expiry_timestamp=end,
                    )
                ],
            ),
            SubTest(
                description="Ensure repayments are rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50",
                        event_datetime=start + relativedelta(hours=2),
                        target_account_id=accounts.LOC_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=2),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Repayments blocked for this account",
                        account_id=accounts.LOC_ACCOUNT,
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)

    def test_derived_parameters(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 2, 28, tzinfo=timezone.utc)

        check_next_repayment_date_param_1 = datetime(2020, 1, 2, tzinfo=timezone.utc)
        check_next_repayment_date_param_2 = datetime(2020, 2, 7, 1, tzinfo=timezone.utc)

        instance_params = default_instance_params.copy()
        instance_params["due_amount_calculation_day"] = "3"

        template_params = default_template_params.copy()
        template_params["repayment_period"] = "4"

        events = []
        sub_tests = [
            SubTest(
                description="check derived parameters",
                events=events,
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=check_next_repayment_date_param_1,
                        account_id=accounts.LOC_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-02-07 00:00:02",
                    ),
                    ExpectedDerivedParameter(
                        timestamp=check_next_repayment_date_param_2,
                        account_id=accounts.LOC_ACCOUNT,
                        name="next_repayment_date",
                        value="2020-03-07 00:00:02",
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
            internal_accounts=accounts.default_internal_accounts,
        )
        self.run_test_scenario(test_scenario)
