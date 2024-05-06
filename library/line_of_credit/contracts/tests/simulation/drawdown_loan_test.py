# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.contracts.simulation.helper import (
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
)

import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.dimensions as dimensions
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.test_parameters as test_parameters

LOAN_ACCOUNT = "DRAWDOWN_LOAN"
DRAWDOWN_LOAN = "drawdown_loan"

default_instance_params = test_parameters.loan_instance_params
default_template_params = test_parameters.loan_template_params


class DrawdownLoanTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [contract_files.LOAN_CONTRACT]

        cls.DEFAULT_SUPERVISEE_VERSION_IDS = {
            "line_of_credit": "1000",
            "drawdown_loan": "2000",
        }
        super().setUpClass()

    account_id_base = accounts.DRAWDOWN_LOAN_ACCOUNT
    default_instance_params = default_instance_params
    default_template_params = default_template_params

    def _get_contract_config(
        self,
        account_id_base: str = "",
        contract_version_id=None,
        instance_params=None,
        template_params=None,
    ):
        contract_config = ContractConfig(
            template_params=template_params or self.default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or self.default_instance_params,
                    account_id_base=account_id_base,
                )
            ],
            contract_content=self.smart_contract_path_to_content[contract_files.LOAN_CONTRACT],
            clu_resource_id=DRAWDOWN_LOAN,
            smart_contract_version_id=self.DEFAULT_SUPERVISEE_VERSION_IDS[DRAWDOWN_LOAN],
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
        debug=False,
    ):
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self._get_contract_config(
                account_id_base=accounts.DRAWDOWN_LOAN_ACCOUNT,
                template_params=template_params,
                instance_params=instance_params,
            ),
            internal_accounts=internal_accounts,
            debug=debug,
        )

    def get_internal_accounts(self):
        internal_accounts = accounts.default_internal_accounts
        # need to create internal LOC account
        internal_accounts["LINE_OF_CREDIT_ACCOUNT 0"] = accounts.ASSET
        return internal_accounts

    def test_postings_rejected_unless_force_override(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Regular posting rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start,
                        target_account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start,
                        rejection_type="Custom",
                        rejection_reason="Reject all regular postings when unsupervised",
                        account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                    )
                ],
            ),
            SubTest(
                description="Force override posting accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=start + relativedelta(hours=1),
                        target_account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        internal_account_id=accounts.DEFAULT_INTERNAL_ACCOUNT,
                        denomination="GBP",
                        batch_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1): {
                        accounts.DRAWDOWN_LOAN_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=default_template_params,
            instance_params=default_instance_params,
            internal_accounts=self.get_internal_accounts(),
        )
        self.run_test_scenario(test_scenario)

    def test_2_A_loan_disbursement(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, 23, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Check deposit account has principal",
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.DRAWDOWN_LOAN_ACCOUNT: [(dimensions.PRINCIPAL, "1000")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            )
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=default_instance_params,
            template_params=default_template_params,
            internal_accounts=self.get_internal_accounts(),
        )
        self.run_test_scenario(test_scenario)
