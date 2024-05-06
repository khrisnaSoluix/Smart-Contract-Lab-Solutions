# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta

# library
from library.line_of_credit.constants import accounts, dimensions, files, test_parameters

# inception sdk
from inception_sdk.test_framework.common.constants import ASSET
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedDerivedParameter,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase


class DrawdownLoanTestBase(SimulationTestCase):
    account_id_base = accounts.DRAWDOWN_LOAN_ACCOUNT
    contract_filepaths = [files.DRAWDOWN_LOAN_CONTRACT]
    internal_accounts = accounts.default_internal_accounts
    default_instance_params = test_parameters.drawdown_loan_instance_params
    default_template_params = test_parameters.drawdown_loan_template_params

    # create internal LOC account for disbursement purposes
    internal_accounts["LINE_OF_CREDIT_ACCOUNT_0"] = ASSET

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
            contract_content=self.smart_contract_path_to_content[files.DRAWDOWN_LOAN_CONTRACT],
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
            internal_accounts=internal_accounts or self.internal_accounts,
            debug=debug,
        )


class InitialDisbursementTest(DrawdownLoanTestBase):
    def test_initial_disbursement(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(hours=2)

        sub_tests = [
            SubTest(
                description="Check deposit account has principal",
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        accounts.DRAWDOWN_LOAN_ACCOUNT: [
                            (dimensions.PRINCIPAL, "1000"),
                            (dimensions.EMI, "90.21"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                        "LINE_OF_CREDIT_ACCOUNT_0": [
                            (dimensions.TOTAL_PRINCIPAL, "1000"),
                            (dimensions.TOTAL_EMI, "90.21"),
                        ],
                    },
                },
                expected_derived_parameters=[
                    # since there are no extra early repayment fees, the early repayment amount is
                    # the same as the maximum overpayment including the associated overpayment fee.
                    # early_repayment_amount = total outstanding amount + max overpayment fee,
                    # where the max overpayment fee is:
                    # (remaining principal * overpayment fee rate) / (1 - overpayment fee rate)
                    # so: 1000 + 1000 * 0.05 / (1-0.05) = 1052.63
                    ExpectedDerivedParameter(
                        timestamp=start + relativedelta(hours=2),
                        account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        name="per_loan_early_repayment_amount",
                        value="1052.63",
                    ),
                ],
            )
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=self.default_instance_params,
            template_params=self.default_template_params,
            internal_accounts=self.internal_accounts,
        )
        self.run_test_scenario(test_scenario)


class PrePostingTest(DrawdownLoanTestBase):
    def test_pre_posting_hook_accepts_and_rejects_postings(self):
        start = test_parameters.default_simulation_start_date
        end = start + relativedelta(seconds=2)
        sub_tests = [
            SubTest(
                description="Check balances when account opens",
                expected_balances_at_ts={
                    start: {
                        accounts.DRAWDOWN_LOAN_ACCOUNT: [(dimensions.DEFAULT, "0")],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "1000")],
                    },
                },
            ),
            SubTest(
                description="Check posting directly to drawdown loan is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        amount="250",
                        event_datetime=start + relativedelta(seconds=1),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(seconds=1),
                        account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        rejection_type="Custom",
                        rejection_reason="All postings should be made to the Line of Credit "
                        "account",
                    )
                ],
            ),
            SubTest(
                description="Accepts the posting if a force override is added",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=accounts.DRAWDOWN_LOAN_ACCOUNT,
                        amount="250",
                        event_datetime=start + relativedelta(seconds=2),
                        internal_account_id=accounts.DEPOSIT_ACCOUNT,
                        instruction_details={"force_override": "true"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(seconds=2): {
                        accounts.DRAWDOWN_LOAN_ACCOUNT: [
                            (dimensions.DEFAULT, "-250"),
                        ],
                        accounts.DEPOSIT_ACCOUNT: [(dimensions.DEFAULT, "750")],
                    },
                },
            ),
        ]
        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=self.default_instance_params,
            template_params=self.default_template_params,
            internal_accounts=self.internal_accounts,
        )
        self.run_test_scenario(test_scenario)
