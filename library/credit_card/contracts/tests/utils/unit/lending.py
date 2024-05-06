# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from collections import defaultdict
from library.credit_card.tests.utils.common.common import offset_datetime
from library.credit_card.tests.utils.common.lending import (
    AVAILABLE,
    INTERNAL,
    OUTSTANDING,
    FULL_OUTSTANDING,
    EVENT_PDD,
    EVENT_SCOD,
)
from library.credit_card.contracts.tests.utils.unit.common import (
    BaseTestCase,
    make_internal_transfer_instructions_call,
    start_workflow_call,
    ACCOUNT_ID,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    DEFAULT_DENOM,
    HOOK_EXECUTION_ID,
    POSTING_ID,
)
from datetime import date, datetime, time
from decimal import Decimal
from json import dumps
from unittest.mock import ANY

DEFAULT_DATE = datetime(2019, 1, 1)

ACCRUAL_TIME = time(0, 0, 0)

SCOD_TIME = time(0, 0, 2)

PDD_TIME = time(0, 0, 1)

ANNUAL_FEE_TIME = time(23, 50, 0)


class LendingContractTest(BaseTestCase):
    BaseTestCase.default_denom = "GBP"

    def create_mock(
        self,
        account_creation_date=offset_datetime(2019, 1, 1),
        payment_due_period=20,
        balance_ts=None,
        posting_instructions=None,
        transaction_types=dumps(
            {
                "purchase": {},
                "cash_advance": {"charge_interest_from_transaction_date": "True"},
                "transfer": {},
                "balance_transfer": {},
            }
        ),
        transaction_references=dumps({"balance_transfer": []}),
        transaction_code_to_type_map=dumps(
            {
                "01": "purchase",
                "00": "cash_advance",
                "02": "transfer",
                "03": "balance_transfer",
            }
        ),
        transaction_type_fees=dumps(
            {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "flat_fee": "0",
                    "percentage_fee": "0",
                }
            }
        ),
        transaction_type_limits=dumps({}),
        annual_percentage_rate=dumps({"cash_advance": "3", "purchase": "1", "transfer": "2"}),
        transaction_annual_percentage_rate=dumps({"balance_transfer": {"REF1": "0.3"}}),
        minimum_amount_due=Decimal(100),
        minimum_percentage_due=dumps(
            {
                "balance_transfer": "0.3",
                "cash_advance": "0.2",
                "purchase": "0.01",
                "transfer": "0.2",
                "interest": "1.0",
                "fees": "1.0",
            }
        ),
        base_interest_rates=dumps({"cash_advance": "0.2", "purchase": "0.01", "transfer": "0.2"}),
        transaction_base_interest_rates=dumps({"balance_transfer": {}}),
        overlimit=Decimal(0),
        overlimit_fee=Decimal(0),
        overlimit_opt_in="True",
        denomination=DEFAULT_DENOM,
        last_scod_execution_time=None,
        last_pdd_execution_time=None,
        late_repayment_fee=Decimal(100),
        annual_fee=Decimal(100),
        accrual_blocking_flags='["90_DAYS_DELINQUENT", "CUSTOMER_FLAGGED"]',
        accrue_interest_on_unpaid_interest="False",
        accrue_interest_on_unpaid_fees="False",
        interest_on_fees_internal_accounts_map=dumps(
            {
                "air": "fees_interest_air",
                "income": "fees_interest_income",
                "loan": "fees_interest_loan",
            }
        ),
        account_closure_flags='["ACCOUNT_CLOSURE_REQUESTED"]',
        account_write_off_flags='["OVER_150_DPD"]',
        mad_as_full_statement_flags='["OVER_90_DPD"]',
        mad_equal_to_zero_flags='["REPAYMENT_HOLIDAY"]',
        overdue_amount_blocking_flags='["REPAYMENT_HOLIDAY"]',
        billed_to_unpaid_transfer_blocking_flags='["REPAYMENT_HOLIDAY"]',
        flags_ts=None,
        client_transaction=None,
        credit_limit=Decimal("1000"),
        effective_date=DEFAULT_DATE,
        interest_write_off_internal_account="interest_write_off_internal_account",
        off_balance_sheet_contra_internal_account="off_balance_sheet_contra_internal_account",
        other_liability_internal_account="other_liability_internal_account",
        principal_write_off_internal_account="principal_write_off_internal_account",
        revocable_commitment_internal_account="revocable_commitment_internal_account",
        transaction_type_internal_accounts_map=dumps(
            {
                "purchase": "purchase_internal_account",
                "cash_advance": "cash_advance_internal_account",
                "transfer": "transfer_internal_account",
                "balance_transfer": "balance_transfer_internal_account",
            }
        ),
        transaction_type_fees_internal_accounts_map=dumps(
            {
                "cash_advance": {
                    "loan": "cash_advance_fee_loan_internal_account",
                    "income": "cash_advance_fee_income_internal_account",
                }
            }
        ),
        transaction_type_interest_internal_accounts_map=dumps(
            {
                "purchase": {
                    "air": "purchase_air_internal_account",
                    "income": "purchase_interest_income_internal_account",
                },
                "cash_advance": {
                    "air": "cash_advance_air_internal_account",
                    "income": "cash_advance_interest_income_internal_account",
                },
                "transfer": {
                    "air": "transfer_air_internal_account",
                    "income": "transfer_interest_income_internal_account",
                },
                "balance_transfer": {
                    "air": "balance_transfer_air_internal_account",
                    "income": "balance_transfer_interest_income_internal_account",
                },
            }
        ),
        overlimit_fee_internal_accounts=dumps(
            {
                "income": "overlimit_fee_income_internal_account",
                "loan": "overlimit_fee_loan_internal_account",
            }
        ),
        late_repayment_fee_internal_accounts=dumps(
            {
                "income": "late_repayment_fee_income_internal_account",
                "loan": "late_repayment_fee_loan_internal_account",
            }
        ),
        annual_fee_internal_accounts=dumps(
            {
                "income": "annual_fee_income_internal_account",
                "loan": "annual_fee_loan_internal_account",
            }
        ),
        external_fee_types=dumps(["dispute_fee", "atm_withdrawal_fee"]),
        external_fee_internal_accounts=dumps(
            {
                "dispute_fee": {
                    "income": "dispute_fee_income_internal_account",
                    "loan": "dispute_fee_loan_internal_account",
                },
                "atm_withdrawal_fee": {
                    "income": "atm_withdrawal_fee_income_internal_account",
                    "loan": "atm_withdrawal_fee_loan_internal_account",
                },
            }
        ),
        interest_free_expiry=dumps({}),
        transaction_interest_free_expiry=dumps({}),
        accrue_interest_from_txn_day="True",
        accrual_schedule_hour=str(ACCRUAL_TIME.hour),
        accrual_schedule_minute=str(ACCRUAL_TIME.minute),
        accrual_schedule_second=str(ACCRUAL_TIME.second),
        scod_schedule_hour=str(SCOD_TIME.hour),
        scod_schedule_minute=str(SCOD_TIME.minute),
        scod_schedule_second=str(SCOD_TIME.second),
        pdd_schedule_hour=str(PDD_TIME.hour),
        pdd_schedule_minute=str(PDD_TIME.minute),
        pdd_schedule_second=str(PDD_TIME.second),
        annual_fee_schedule_hour=str(ANNUAL_FEE_TIME.hour),
        annual_fee_schedule_minute=str(ANNUAL_FEE_TIME.minute),
        annual_fee_schedule_second=str(ANNUAL_FEE_TIME.second),
    ):
        # Because we use locals() this should always be the first statement in the method
        params = {key: {"value": value} for key, value in locals().items()}

        # We can't capture optional parameters in the method args so we override these below
        params.update(
            {
                "overlimit": {
                    "value": overlimit,
                    "optional": True,
                    "default_value": Decimal(0),
                },
                "overlimit_opt_in": {
                    "value": overlimit_opt_in,
                    "optional": True,
                    "default_value": "False",
                },
                "accrue_interest_on_unpaid_interest": {
                    "value": accrue_interest_on_unpaid_interest,
                    "optional": True,
                    "default_value": "False",
                },
                "accrue_interest_on_unpaid_fees": {
                    "value": accrue_interest_on_unpaid_fees,
                    "optional": True,
                    "default_value": "False",
                },
            }
        )

        param_timeseries = BaseTestCase.param_map_to_timeseries(params, account_creation_date)

        flags_ts = flags_ts if flags_ts else {}
        mock_vault = BaseTestCase.create_mock(
            self,
            account_creation_date=account_creation_date,
            balance_timeseries=balance_ts,
            flag_timeseries=flags_ts,
            parameter_timeseries=param_timeseries,
            last_execution_times={
                EVENT_SCOD: last_scod_execution_time,
                EVENT_PDD: last_pdd_execution_time,
            },
            client_transactions=defaultdict(lambda: client_transaction),
            postings=posting_instructions,
        )

        return mock_vault

    def mock_with_auth(self, balances, auth_amount, settled_amount, unsettled_amount, **kwargs):
        """
        creates a mock with an existing client_transaction based on an auth
        :param balances: mock balances
        :param auth_amount: original auth amount
        :param settled_amount: amount of the auth that is already settled
        :param unsettled_amount: remaining unsettled amount on the auth
        :param kwargs: keyword args for the standard mock
        :return: Mock
        """

        ct_postings = [self.purchase_auth(auth_amount)]

        client_transaction = self.mock_client_transaction(
            postings=ct_postings,
            authorised=auth_amount,
            released=Decimal(0),
            settled=settled_amount,
            unsettled=unsettled_amount,
        )

        return self.create_mock(
            balance_ts=balances, client_transaction=client_transaction, **kwargs
        )

    def txn_with_ref_auth(
        self,
        amount=Decimal(0),
        denomination=DEFAULT_DENOM,
        transaction_code="",
        transaction_ref="",
    ):
        instruction_details = {
            "transaction_code": transaction_code,
            "transaction_ref": transaction_ref,
        }
        return self.auth(
            amount=amount,
            denomination=denomination,
            instruction_details=instruction_details,
        )

    def txn_with_ref_settle(
        self,
        amount=Decimal(0),
        denomination=DEFAULT_DENOM,
        transaction_code="",
        transaction_ref="",
    ):
        instruction_details = {
            "transaction_code": transaction_code,
            "transaction_ref": transaction_ref,
        }
        return self.settle(
            amount=amount,
            final=True,
            denomination=denomination,
            instruction_details=instruction_details,
        )

    # If additional types are introduced that employ refs this should be made generic and accept a
    # transaction mapping code

    def balance_transfer(
        self,
        amount=Decimal(0),
        client_transaction_id=None,
        denomination=DEFAULT_DENOM,
        posting_id=POSTING_ID,
        value_timestamp=None,
        advice=False,
        ref=None,
    ):
        return self.mock_posting_instruction(
            amount=amount,
            client_transaction_id=client_transaction_id,
            denomination=denomination,
            id=posting_id,
            instruction_details={"transaction_code": "03", "transaction_ref": ref},
            value_timestamp=value_timestamp,
            advice=advice,
        )

    def cash_advance(
        self,
        amount=Decimal(0),
        client_transaction_id=None,
        denomination=DEFAULT_DENOM,
        posting_id=POSTING_ID,
        value_timestamp=None,
        advice=False,
    ):
        return self.mock_posting_instruction(
            amount=amount,
            client_transaction_id=client_transaction_id,
            denomination=denomination,
            id=posting_id,
            instruction_details={"transaction_code": "00"},
            value_timestamp=value_timestamp,
            advice=advice,
        )

    def dispute_fee(
        self,
        amount=Decimal(0),
        client_transaction_id=None,
        denomination=DEFAULT_DENOM,
        posting_id=POSTING_ID,
        value_timestamp=None,
    ):
        return self.mock_posting_instruction(
            amount=amount,
            client_transaction_id=client_transaction_id,
            denomination=denomination,
            id=posting_id,
            instruction_details={"transaction_code": "05", "fee_type": "DISPUTE_FEE"},
            value_timestamp=value_timestamp,
        )

    def purchase(
        self,
        amount=Decimal(0),
        denomination=DEFAULT_DENOM,
        posting_id=POSTING_ID,
        advice=False,
    ):
        return self.mock_posting_instruction(
            amount=amount,
            denomination=denomination,
            instruction_details={},
            id=posting_id,
            advice=advice,
        )

    def purchase_auth(self, amount=Decimal(0), denomination=DEFAULT_DENOM):
        return self.auth(amount=amount, denomination=denomination)

    def repay(self, amount=Decimal(0), denomination=DEFAULT_DENOM, posting_id=POSTING_ID):
        return self.mock_posting_instruction(
            amount=amount, denomination=denomination, credit=True, id=posting_id
        )

    def create_mock_for_param_test(
        self,
        account_creation_date=offset_datetime(2019, 1, 1),
        param_val_update=(),
        param_val_remove=(),
        accrue_interest_on_unpaid_fees="False",
    ):
        """
        Create a mock for testing _check_txn_type_parameter_configuration with
        simplified parameter structure

        :param self:
        :param account_creation_date: Account creation date
        :param parameter_update: Tuple of (parameter name, dict) pairs to modify default parameters
        :param parameter_remove: Tuple of (parameter name, key) pairs to remove 'key' from parameter
        :param accrue_interest_on_unpaid_fees: Whether to accrue interest on unpaid interest
        :return: Mock
        """
        params = {}
        params["transaction_types"] = ["A", "B", "C"]
        params["transaction_references"] = {"C": {}}
        params["transaction_code_to_type_map"] = {"1": "A", "2": "B", "3": "C"}
        params["transaction_type_fees"] = {"A": {"percentage": "0.05"}}
        params["transaction_type_limits"] = {"A": "100", "B": "200", "C": "300"}
        params["annual_percentage_rate"] = {"A": "0.01", "B": "0.02"}
        params["transaction_annual_percentage_rate"] = {"C": {"REF1": "0.05"}}
        params["minimum_percentage_due"] = {
            "A": "0.05",
            "B": "0.05",
            "C": "0.05",
            "fees": "1",
            "interest": "1",
        }
        params["base_interest_rates"] = {"A": "0.05", "B": "0"}
        params["transaction_base_interest_rates"] = {"C": {"REF1": "0.05"}}
        params["transaction_type_internal_accounts_map"] = {
            "A": "1",
            "B": "2",
            "C": "3",
        }
        params["transaction_type_fees_internal_accounts_map"] = {"A": "5"}
        params["transaction_type_interest_internal_accounts_map"] = {
            "A": "6",
            "B": "6",
            "C": "6",
        }
        params["accrue_interest_on_unpaid_fees"] = accrue_interest_on_unpaid_fees
        params["interest_free_expiry"] = {}
        params["transaction_interest_free_expiry"] = {}

        # Make adjustments specific for this test then turn parameters into JSON timeseries
        for param_key, items in param_val_update:
            params[param_key].update(items)

        for param_key, keys in param_val_remove:
            for key in keys:
                del params[param_key][key]

        params = {k: {"value": dumps(v)} for k, v in params.items()}
        params["accrue_interest_on_unpaid_fees"] = {
            "value": accrue_interest_on_unpaid_fees,
            "optional": True,
            "default_value": "False",
        }

        param_timeseries = BaseTestCase.param_map_to_timeseries(params, account_creation_date)

        mock_vault = BaseTestCase.create_mock(
            self,
            account_creation_date=account_creation_date,
            parameter_timeseries=param_timeseries,
        )

        return mock_vault


# helpers for mock workflow calls


def late_repayment_workflow_call(
    mad=ANY,
    repayments=ANY,
    scod=ANY,
    full_outstanding_balance=ANY,
    statement_balance=ANY,
):
    """
    :param mad: str, minimum amount due for the statement cycle
    :param repayments: str, total repayments for the statement cycle
    :param scod: str, dd/m/yyyy, statement cut-off-date for the statement cycle
    :param full_outstanding_balance: str, full outstanding balance at PDD
    :param statement_balance: str, statement balance
    :return: call object
    """

    return start_workflow_call(
        workflow="LATE_REPAYMENT",
        context={
            "account_id": ACCOUNT_ID,
            "mad_balance": mad,
            "repaid_after_scod": repayments,
            "scod": scod,
            "remaining_full_outstanding_balance": full_outstanding_balance,
            "statement_balance": statement_balance,
        },
    )


def publish_statement_workflow_call(
    mad=ANY,
    start_of_statement=ANY,
    end_of_statement=ANY,
    statement_amount=ANY,
    current_pdd=ANY,
    next_pdd=ANY,
    next_scod=ANY,
    is_final="False",
):
    """
    :param mad: str, minimum amount due for the statement cycle
    :param start_of_statement: str, YYYY-MM-DD representing start of statement date
    :param end_of_statement: str, YYYY-MM-DD representing end of statement date
    :param statement_amount: str, quoted decimal value statement amount
    :param current_pdd: str, YYYY-MM-DD payment due date for the statement that has just ended
    :param next_pdd: str, YYYY-MM-DD, payment due date for the next statement cycle
    :param next_scod: str, YYYY-MM-DD, statement cut-off-date for the next statement cycle
    :param is_final: str, 'True' if final workflow 'False' otherwise
    :return: workflow context
    """

    return start_workflow_call(
        workflow="CREDIT_CARD_PUBLISH_STATEMENT_DATA",
        context={
            "account_id": ACCOUNT_ID,
            "start_of_statement_period": start_of_statement,
            "end_of_statement_period": end_of_statement,
            "current_statement_balance": statement_amount,
            "minimum_amount_due": mad,
            "current_payment_due_date": current_pdd,
            "next_payment_due_date": next_pdd,
            "next_statement_cut_off": next_scod,
            "is_final": is_final,
        },
    )


def all_charged_dispute_fee_calls(fees=None, include_info_balances=True):

    calls = []
    total_amount = 0

    for fee in fees:
        fee_amount = fee["fee_amount"]
        fee_type = fee.get("fee_type", None)
        posting_id = fee.get("fee_posting_id", POSTING_ID)
        if fee_amount is ANY or total_amount is ANY:
            total_amount = ANY
        else:
            total_amount += Decimal(fee_amount)
            calls.extend(
                [
                    fee_rebalancing_call(
                        amount=fee_amount, fee_type=fee_type, posting_id=posting_id
                    ),
                    charge_dispute_fee_loan_to_customer_call(
                        amount=fee_amount, posting_id=posting_id
                    ),
                    charge_dispute_fee_off_bs_call(amount=fee_amount, posting_id=posting_id),
                ]
            )

    purpose = ""
    if include_info_balances:
        calls.extend(
            [
                adjust_available_balance_call(amount=total_amount, increase=False, purpose=purpose),
                make_internal_transfer_instructions_call(
                    from_account_address=OUTSTANDING,
                    to_account_address=INTERNAL,
                    amount=total_amount,
                ),
                make_internal_transfer_instructions_call(
                    from_account_address=FULL_OUTSTANDING,
                    to_account_address=INTERNAL,
                    amount=total_amount,
                ),
            ]
        )

    return calls


def all_charged_fee_calls(fees=None, include_info_balances=True, initial_info_balances=None):

    calls = []
    total_amount = 0

    for fee in fees:
        fee_amount = Decimal(fee["fee_amount"])
        fee_type = fee.get("fee_type", None)
        event_type = fee.get("event_type", None)
        txn_type = fee.get("txn_type", None)
        posting_id = fee.get("fee_posting_id", "")
        if fee_amount is ANY or total_amount is ANY:
            total_amount = ANY
        else:
            total_amount += Decimal(fee_amount)
        if txn_type:
            calls.extend(
                [
                    fee_rebalancing_call(
                        amount=fee_amount, txn_type=txn_type, posting_id=posting_id
                    ),
                    fee_rebalancing_call(
                        amount=fee_amount,
                        from_address=DEFAULT_ADDRESS,
                        txn_type=txn_type,
                        posting_id=posting_id,
                    ),
                    txn_fee_loan_to_income_call(
                        amount=fee_amount, txn_type=txn_type, posting_id=posting_id
                    ),
                    charge_txn_type_fee_off_bs_call(
                        amount=fee_amount, txn_type=txn_type, posting_id=posting_id
                    ),
                ]
            )
        else:
            calls.extend(
                [
                    fee_rebalancing_call(
                        amount=fee_amount, fee_type=fee_type, posting_id=posting_id
                    ),
                    fee_rebalancing_call(
                        amount=fee_amount,
                        from_address=DEFAULT_ADDRESS,
                        fee_type=fee_type,
                        posting_id=posting_id,
                    ),
                    fee_loan_to_income_call(amount=fee_amount, fee_type=fee_type),
                    charge_fee_off_bs_call(amount=fee_amount, fee_type=fee_type),
                ]
            )

    purpose = event_type if event_type else fee_type
    if include_info_balances:
        available = Decimal(initial_info_balances[AVAILABLE])
        outstanding = Decimal(initial_info_balances[OUTSTANDING])
        full_outstanding = Decimal(initial_info_balances[FULL_OUTSTANDING])
        calls.extend(
            [
                override_info_balance_call(
                    info_balance=AVAILABLE,
                    delta_amount=fee_amount,
                    amount=available - fee_amount,
                    increase=False,
                    trigger=purpose,
                ),
                override_info_balance_call(
                    info_balance=OUTSTANDING,
                    delta_amount=fee_amount,
                    amount=outstanding + fee_amount,
                    increase=True,
                    trigger=purpose,
                ),
                override_info_balance_call(
                    info_balance=FULL_OUTSTANDING,
                    delta_amount=fee_amount,
                    amount=full_outstanding + fee_amount,
                    increase=True,
                    trigger=purpose,
                ),
            ]
        )

    return calls


def accrue_interest_call(
    amount=ANY,
    daily_rate=Decimal(0),
    balance=Decimal(0),
    denomination=DEFAULT_DENOM,
    txn_type="PURCHASE",
    ref=None,
    accrual_type=None,
):
    stem = f"{txn_type}_{ref}" if ref else txn_type
    stem_with_accrual_type = f"{stem}_{accrual_type}" if accrual_type else stem

    if accrual_type:
        from_account_address = f"{stem}_INTEREST_{accrual_type}_UNCHARGED"
    else:
        from_account_address = f"{stem}_INTEREST_UNCHARGED"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=from_account_address,
        to_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=f"ACCRUE_INTEREST-{HOOK_EXECUTION_ID}-{stem_with_accrual_type}",
        instruction_details={
            "description": f"Daily interest accrued at {daily_rate:.7f}% on"
            f" balance of {balance:.2f}, for"
            f" transaction type {stem_with_accrual_type}"
        }
        if daily_rate is not ANY and balance is not ANY
        else ANY,
    )


def charge_interest_air_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    interest_value_date=date(1970, 1, 1),
    txn_type="PURCHASE",
):
    is_fee = txn_type.endswith("_FEE")

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id="fees_interest_air"
        if is_fee
        else f"{txn_type.lower()}_air_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        to_account_id="fees_interest_income"
        if is_fee
        else f"{txn_type.lower()}_interest_income_internal_account",
        client_transaction_id=f"AIR_TO_INCOME_GL-{HOOK_EXECUTION_ID}-INTEREST_CHARGED_{txn_type}",
        instruction_details={
            "accounting_event": "LOAN_CHARGED_INTEREST",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
            "interest_value_date": str(interest_value_date),
        },
        override_all_restrictions=True,
    )


def adjust_available_balance_call(amount, increase, purpose=""):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=INTERNAL if increase else AVAILABLE,
        to_account_address=AVAILABLE if increase else INTERNAL,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={},
        client_transaction_id=ANY
        if purpose is ANY
        else f"ADJUST_AVAILABLE_BALANCE-{HOOK_EXECUTION_ID}-{purpose}",
    )


def cleanup_address_call(amount, from_account_address, to_account_address, event):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        from_account_address=from_account_address,
        to_account_address=to_account_address,
        override_all_restrictions=True,
        client_transaction_id=f"REBALANCE_{from_account_address}_TO_{to_account_address}-"
        f"{HOOK_EXECUTION_ID}-CLEANUP_{event}",
    )


def txn_fee_loan_to_income_call(
    amount=Decimal(0), denomination=DEFAULT_DENOM, posting_id=POSTING_ID, txn_type=""
):

    fee_type = f"{txn_type.upper()}_FEE"

    loan_account = f"{fee_type.lower()}_loan_internal_account"
    income_account = f"{fee_type.lower()}_income_internal_account"
    cti = f"LOAN_TO_INCOME_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_{fee_type}_{posting_id}"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        to_account_address=DEFAULT_ADDRESS,
        from_account_id=loan_account,
        to_account_id=income_account,
        client_transaction_id=cti,
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def fee_loan_to_income_call(amount=Decimal(0), denomination=DEFAULT_DENOM, fee_type=""):

    loan_account = f"{fee_type.lower()}_loan_internal_account"
    income_account = f"{fee_type.lower()}_income_internal_account"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        to_account_address=DEFAULT_ADDRESS,
        from_account_id=loan_account,
        to_account_id=income_account,
        client_transaction_id=f"LOAN_TO_INCOME_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_{fee_type}",
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def charge_interest_call(
    amount=ANY,
    txn_type="PURCHASE",
    rebalanced_address="",
    ref=None,
    charge_interest_free_period=False,
    accrual_type=None,
    accrual_type_in_trigger=None,
):
    stem = f"{txn_type}_{ref}" if ref else txn_type
    if not rebalanced_address:
        rebalanced_address = f"{stem}_INTEREST_CHARGED"

    if charge_interest_free_period:
        trigger_base = "INTEREST_FREE_PERIOD_INTEREST"
    elif accrual_type_in_trigger:
        trigger_base = f"{accrual_type_in_trigger.upper()}_INTEREST"
    else:
        trigger_base = "INTEREST"

    return interest_rebalancing_call(
        amount=amount,
        txn_type=stem,
        rebalancing_pot=rebalanced_address,
        trigger_base=trigger_base,
    )


def increase_credit_limit_revocable_commitment_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    from_account_id="off_balance_sheet_contra_internal_account",
    to_account_id="revocable_commitment_internal_account",
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=from_account_id,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=to_account_id,
        client_transaction_id=f"INCREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-CREDIT_LIMIT_INCREASED",
        instruction_details={
            "accounting_event": "LOAN_LIMIT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def decrease_credit_limit_revocable_commitment_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    from_account_id="revocable_commitment_internal_account",
    to_account_id="off_balance_sheet_contra_internal_account",
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=from_account_id,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=to_account_id,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-CREDIT_LIMIT_DECREASED",
        instruction_details={
            "accounting_event": "LOAN_LIMIT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


# TODO: can we remerge dispute/txn fee helpers into generic fee rebalancing?
def dispute_fee_rebalancing_call(amount, from_address=None, posting_id=POSTING_ID):

    fee_type = "DISPUTE_FEE"
    from_address = from_address or f"{fee_type}S_CHARGED"

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_address,
        to_account_address=INTERNAL,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={"fee_type": fee_type},
        client_transaction_id=f"REBALANCE_{from_address}-{HOOK_EXECUTION_ID}-FEES_CHARGED_"
        f"{fee_type}_{posting_id}",
    )


def fee_rebalancing_call(amount, txn_type=None, fee_type=None, from_address=None, posting_id=None):

    if txn_type:
        fee_type = f"{txn_type.upper()}_FEE"

    from_address = from_address or f"{fee_type}S_CHARGED"
    label = from_address
    to_address = INTERNAL

    if amount is not ANY:
        amount = Decimal(amount)
        if amount < 0:
            amount = -amount
            to_address = from_address
            from_address = INTERNAL

    if posting_id:
        posting_id_text = f"_{posting_id}"
    else:
        posting_id_text = f"_{POSTING_ID}" if txn_type else ""

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_address,
        to_account_address=to_address,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={"fee_type": fee_type},
        client_transaction_id=f"REBALANCE_{label}-{HOOK_EXECUTION_ID}-FEES_CHARGED_"
        f"{fee_type}{posting_id_text}",
    )


def interest_rebalancing_call(amount, txn_type, rebalancing_pot, trigger_base="INTEREST"):

    from_account_address = rebalancing_pot
    to_account_address = INTERNAL

    if amount is not ANY:
        amount = Decimal(amount)
        if amount < 0:
            amount = -amount
            from_account_address = INTERNAL
            to_account_address = rebalancing_pot

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_account_address,
        to_account_address=to_account_address,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={},
        client_transaction_id=f"REBALANCE_{rebalancing_pot}-{HOOK_EXECUTION_ID}-"
        f"{trigger_base}_CHARGED_{txn_type}"
        if (txn_type is not ANY and rebalancing_pot is not ANY)
        else ANY,
    )


def internal_account_txn_type_fee_call(
    amount, txn_type, denomination=DEFAULT_DENOM, posting_id=POSTING_ID
):

    return txn_fee_loan_to_income_call(
        amount=amount,
        denomination=denomination,
        posting_id=posting_id,
        txn_type=txn_type,
    )


def internal_to_address_call(
    amount=ANY,
    address=ANY,
    credit=False,
    asset=ANY,
    denomination=ANY,
    override_all_restrictions=ANY,
    client_transaction_id=ANY,
    instruction_details=ANY,
):
    """
    This method should be used when we want to check that posting occurs between INTERNAL and
    the specified address
    """
    if credit:
        to_account_address = address
        from_account_address = INTERNAL
    else:
        to_account_address = INTERNAL
        from_account_address = address

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_id="current_account",
        from_account_address=from_account_address,
        to_account_id="current_account",
        to_account_address=to_account_address,
        asset=asset,
        denomination=denomination,
        instruction_details=instruction_details,
        override_all_restrictions=override_all_restrictions,
        client_transaction_id=client_transaction_id,
    )


def overlimit_bank_charge_rebalancing_call(amount):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address="FEES_CHARGED",
        to_account_address=INTERNAL,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={
            "description": "Rebalance bank charges (interest or fees).",
            "fee_type": "overlimit_fee",
        },
        client_transaction_id=f"OVERLIMIT_FEE-{HOOK_EXECUTION_ID}_rebalance_FEES_CHARGED",
    )


def override_info_balance_call(
    delta_amount=ANY,
    amount=ANY,
    info_balance=ANY,
    increase=True,
    trigger="STATEMENT_CUT_OFF",
):
    if amount is not ANY:
        amount = Decimal(amount)

    return make_internal_transfer_instructions_call(
        amount=delta_amount,
        from_account_address=info_balance if increase else INTERNAL,
        to_account_address=INTERNAL if increase else info_balance,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={"description": f"Set {info_balance} to {amount:.2f}"}
        if amount is not ANY
        else ANY,
        client_transaction_id=f"OVERRIDE_{info_balance}-{HOOK_EXECUTION_ID}-" f"{trigger}"
        if trigger is not ANY
        else ANY,
    )


def interest_write_off_call(amount):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=DEFAULT_ADDRESS,
        to_account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id="interest_write_off_internal_account",
        to_account_id=ACCOUNT_ID,
        instruction_details={
            "accounting_event": "LOAN_CHARGE_OFF",
            "account_id": ACCOUNT_ID,
        },
        client_transaction_id=f"CHARGE_OFF_INTEREST-{HOOK_EXECUTION_ID}-ACCOUNT_CHARGED_OFF",
    )


def principal_write_off_call(amount):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=DEFAULT_ADDRESS,
        to_account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id="principal_write_off_internal_account",
        to_account_id=ACCOUNT_ID,
        instruction_details={
            "accounting_event": "LOAN_CHARGE_OFF",
            "account_id": ACCOUNT_ID,
        },
        client_transaction_id=f"CHARGE_OFF_PRINCIPAL-{HOOK_EXECUTION_ID}-ACCOUNT_CHARGED_OFF",
    )


def rebalance_statement_bucket_call(amount, transaction_type):

    from_account_address = f"{transaction_type}_BILLED"
    to_account_address = f"{transaction_type}_CHARGED"

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_account_address,
        to_account_address=to_account_address,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={
            "description": f"Move balance from {from_account_address} to {to_account_address}"
        },
        client_transaction_id=f"REBALANCE_{from_account_address}_TO_{to_account_address}-"
        f"{HOOK_EXECUTION_ID}-STATEMENT_CUT_OFF",
    )


def reverse_uncharged_interest_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    txn_type="PURCHASE",
    trigger="OUTSTANDING_REPAID",
    txn_ref=None,
    accrual_type=None,
):

    if amount is not ANY:
        amount = Decimal(amount)
    stem = f"{txn_type}_{txn_ref}" if txn_ref else txn_type
    stem_with_accrual_type = f"{stem}_{accrual_type}" if accrual_type else stem
    if accrual_type:
        to_account_address = f"{stem}_INTEREST_{accrual_type}_UNCHARGED"
    else:
        to_account_address = f"{stem}_INTEREST_UNCHARGED"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        to_account_address=to_account_address,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=(
            f"REVERSE_UNCHARGED_INTEREST-{HOOK_EXECUTION_ID}-{stem_with_accrual_type}"
        ),
        instruction_details={
            "description": f"Uncharged interest reversed for {stem_with_accrual_type} - {trigger}"
        },
    )


def zero_out_mad_balance_call(amount=ANY, denomination=DEFAULT_DENOM):

    if amount is not ANY:
        amount = Decimal(amount)

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        to_account_address="MAD_BALANCE",
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        client_transaction_id="ZERO_OUT_MAD_BALANCE-hook_execution_id-MAD_BALANCE",
        instruction_details={"description": "MAD balance zeroed out"},
    )


def repayment_rebalancing_call(
    amount, from_address="INTERNAL", to_address="", posting_id=POSTING_ID, repay_count=0
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_address,
        to_account_address=to_address,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={},
        client_transaction_id=f"REPAY_{to_address}-{HOOK_EXECUTION_ID}-REPAYMENT_RECEIVED_"
        f"{posting_id}_{repay_count}",
    )


def repay_principal_revocable_commitment_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    off_balance_sheet_contra_internal_account="off_balance_sheet_contra_internal_account",
    posting_id=POSTING_ID,
    repay_count=0,
    revocable_commitment_internal_account="revocable_commitment_internal_account",
    txn_type="purchase",
):
    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=off_balance_sheet_contra_internal_account,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=revocable_commitment_internal_account,
        client_transaction_id=f"INCREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-PRINCIPAL_REPAID_"
        f"{txn_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def repay_billed_interest_customer_to_loan_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    repay_count=0,
    txn_type="purchase",
    posting_id=POSTING_ID,
):
    is_fee = txn_type.endswith("_fee")
    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id="fees_interest_loan" if is_fee else f"{txn_type}_internal_account",
        client_transaction_id=f"CUSTOMER_TO_LOAN_GL-{HOOK_EXECUTION_ID}-BILLED_INTEREST_REPAID_"
        f"{txn_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def repay_billed_interest_off_bs_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    repay_count=0,
    txn_type="purchase",
    posting_id=POSTING_ID,
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id="off_balance_sheet_contra_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        to_account_id="revocable_commitment_internal_account",
        client_transaction_id=f"INCREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-BILLED_INTEREST_REPAID_"
        f"{txn_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def repay_charged_dispute_fee_customer_to_loan_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    repay_count=0,
):

    loan_account = "dispute_fee_loan_internal_account"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=loan_account,
        client_transaction_id=f"CUSTOMER_TO_LOAN_GL-{HOOK_EXECUTION_ID}-"
        f"FEES_REPAID_DISPUTE_FEE_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def repay_charged_fee_customer_to_loan_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    repay_count=0,
    fee_type="",
    posting_id=POSTING_ID,
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=f"{fee_type.lower()}_loan_internal_account",
        client_transaction_id=f"CUSTOMER_TO_LOAN_GL-{HOOK_EXECUTION_ID}"
        f"-FEES_REPAID_{fee_type}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def repay_charged_fee_off_bs_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    repay_count=0,
    fee_type="",
    posting_id=POSTING_ID,
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id="off_balance_sheet_contra_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        to_account_id="revocable_commitment_internal_account",
        client_transaction_id=f"INCREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}"
        f"-FEES_REPAID_{fee_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def repay_charged_interest_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    repay_count=0,
    txn_type="purchase",
    posting_id=POSTING_ID,
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=f"{txn_type}_air_internal_account",
        client_transaction_id=f"CUSTOMER_TO_AIR-{HOOK_EXECUTION_ID}-CHARGED_INTEREST_REPAID_"
        f"{txn_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def repay_principal_loan_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    repay_count=0,
    txn_type="purchase",
    txn_type_account_id=None,
):

    txn_type_account_id = txn_type_account_id or f"{txn_type}_internal_account"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=txn_type_account_id,
        client_transaction_id=f"LOAN_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-PRINCIPAL_REPAID_"
        f"{txn_type.upper()}_{posting_id}_{repay_count}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def other_liability_gl_call(
    amount, client_transaction_id, instruction_details, denomination=DEFAULT_DENOM
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id="other_liability_internal_account",
        to_account_address=INTERNAL,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
        override_all_restrictions=True,
    )


def repay_other_liability_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id="other_liability_internal_account",
        client_transaction_id=f"CUSTOMER_TO_OTHER_LIABILITY_GL-{HOOK_EXECUTION_ID}-"
        f"REPAYMENT_RECEIVED_{posting_id}",
        instruction_details={
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def spend_other_liability_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    event="LOAN_DISBURSEMENT",
    trigger=None,
    posting_id=POSTING_ID,
    txn_type="",
):

    instruction_details = {
        "accounting_event": event,
        "account_id": ACCOUNT_ID,
        "inst_type": txn_type.lower(),
    }
    cti_prefix = f"OTHER_LIABILITY_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-{trigger}"

    client_transaction_id = f"{cti_prefix}_{txn_type.upper()}_{posting_id}"

    return other_liability_gl_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
    )


def generic_fee_other_liability_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    fee_type="",
):

    instruction_details = {
        "accounting_event": "LOAN_FEES",
        "account_id": ACCOUNT_ID,
    }
    cti = f"OTHER_LIABILITY_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_{fee_type}"

    return other_liability_gl_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=cti,
        instruction_details=instruction_details,
    )


def txn_specific_fee_other_liability_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    fee_type="",
    posting_id=POSTING_ID,
    txn_type="",
):

    instruction_details = {
        "accounting_event": "LOAN_FEES",
        "account_id": ACCOUNT_ID,
    }
    if txn_type != "":
        instruction_details.update({"inst_type": txn_type.lower()})
    cti = f"OTHER_LIABILITY_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_{fee_type}_{posting_id}"

    return other_liability_gl_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=cti,
        instruction_details=instruction_details,
    )


def interest_other_liability_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    txn_type="",
):

    instruction_details = {
        "accounting_event": "LOAN_CHARGED_INTEREST",
        "account_id": ACCOUNT_ID,
        "inst_type": txn_type.lower(),
    }
    trigger = f"INTEREST_CHARGED_{txn_type.upper()}"
    client_transaction_id = f"OTHER_LIABILITY_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-{trigger}"

    return other_liability_gl_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
    )


def spend_principal_revocable_commitment_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    off_balance_sheet_contra_internal_account="off_balance_sheet_contra_internal_account",
    posting_id=POSTING_ID,
    revocable_commitment_internal_account="revocable_commitment_internal_account",
    txn_type="purchase",
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=revocable_commitment_internal_account,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=off_balance_sheet_contra_internal_account,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}"
        f"-PRINCIPAL_SPENT_{txn_type.upper()}_{posting_id}",
        instruction_details={
            "accounting_event": "LOAN_DISBURSEMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def statement_to_unpaid_call(amount, txn_type, ref=None):

    stem = f"{txn_type}_{ref}" if ref else txn_type
    from_address = f"{stem}_UNPAID"
    to_address = f"{stem}_BILLED"

    return make_internal_transfer_instructions_call(
        amount=amount,
        from_account_address=from_address,
        to_account_address=to_address,
        asset=DEFAULT_ASSET,
        denomination=DEFAULT_DENOM,
        override_all_restrictions=True,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        instruction_details={"description": f"Move balance from {from_address} to {to_address}"},
        client_transaction_id=f"REBALANCE_{from_address}_TO_{to_address}-{HOOK_EXECUTION_ID}"
        f"-PAYMENT_DUE",
    )


def set_revolver_call():

    return make_internal_transfer_instructions_call(
        amount="1",
        denomination=DEFAULT_DENOM,
        from_account_address=INTERNAL,
        to_account_address="REVOLVER",
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=f"SET_REVOLVER-{HOOK_EXECUTION_ID}-STATEMENT_BALANCE_NOT_PAID",
    )


def spend_principal_customer_to_loan_gl_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    txn_type="purchase",
    txn_type_account_id="purchase_internal_account",
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=txn_type_account_id,
        to_account_address=INTERNAL,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=f"CUSTOMER_TO_LOAN_GL-{HOOK_EXECUTION_ID}-PRINCIPAL_SPENT_"
        f"{txn_type.upper()}_{posting_id}",
        instruction_details={
            "accounting_event": "LOAN_DISBURSEMENT",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
        override_all_restrictions=True,
    )


def unset_revolver_call():

    return make_internal_transfer_instructions_call(
        amount="1",
        denomination=DEFAULT_DENOM,
        from_account_address="REVOLVER",
        to_account_address=INTERNAL,
        from_account_id=ACCOUNT_ID,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=f"UNSET_REVOLVER-{HOOK_EXECUTION_ID}-FULL_OUTSTANDING_REPAID",
    )


# helpers for mock posting instructions


def cash_advance(
    self,
    amount=Decimal(0),
    client_transaction_id=None,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    value_timestamp=None,
    advice=False,
):

    return self.mock_posting_instruction(
        amount=amount,
        client_transaction_id=client_transaction_id,
        denomination=denomination,
        id=posting_id,
        instruction_details={"transaction_code": "00"},
        value_timestamp=value_timestamp,
        advice=advice,
    )


def dispute_fee(
    self,
    amount=Decimal(0),
    client_transaction_id=None,
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    value_timestamp=None,
):

    return self.mock_posting_instruction(
        amount=amount,
        client_transaction_id=client_transaction_id,
        denomination=denomination,
        id=posting_id,
        instruction_details={"transaction_code": "05", "fee_type": "DISPUTE_FEE"},
        value_timestamp=value_timestamp,
    )


def purchase(
    self,
    amount=Decimal(0),
    denomination=DEFAULT_DENOM,
    posting_id=POSTING_ID,
    advice=False,
):

    return self.mock_posting_instruction(
        amount=amount,
        denomination=denomination,
        instruction_details={},
        id=posting_id,
        advice=advice,
    )


def purchase_auth(self, amount=Decimal(0), denomination=DEFAULT_DENOM):

    return self.auth(amount=amount, denomination=denomination)


def repay(self, amount=Decimal(0), denomination=DEFAULT_DENOM, posting_id=POSTING_ID):

    return self.mock_posting_instruction(
        amount=amount, denomination=denomination, credit=True, id=posting_id
    )


def transfer(self, amount=Decimal(0), denomination=DEFAULT_DENOM):

    return self.mock_posting_instruction(
        amount=amount,
        denomination=denomination,
        instruction_details={"transaction_code": "02"},
    )


def bill_interest_air_call(amount, denomination=DEFAULT_DENOM, txn_type="purchase", txn_ref=None):
    stem = f"{txn_type}_{txn_ref}" if txn_ref else txn_type
    is_fee = txn_type.endswith("_fee")
    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=f"LOAN_TO_AIR_GL-{HOOK_EXECUTION_ID}-INTEREST_BILLED"
        f"_{stem.upper()}",
        from_account_id="fees_interest_loan" if is_fee else f"{txn_type}_internal_account",
        from_account_address=DEFAULT_ADDRESS,
        to_account_id="fees_interest_air" if is_fee else f"{txn_type}_air_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "accounting_event": "LOAN_CHARGED_INTEREST",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type,
        },
    )


def bill_interest_off_bs_call(amount, denomination=DEFAULT_DENOM, txn_type="purchase"):
    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-INTEREST_BILLED_"
        f"{txn_type.upper()}",
        from_account_id="revocable_commitment_internal_account",
        from_account_address=DEFAULT_ADDRESS,
        to_account_id="off_balance_sheet_contra_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "accounting_event": "LOAN_CHARGED_INTEREST",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type,
        },
    )


def charge_fee_off_bs_call(amount, denomination=DEFAULT_DENOM, fee_type=""):
    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_"
        f"{fee_type.upper()}",
        from_account_id="revocable_commitment_internal_account",
        from_account_address=DEFAULT_ADDRESS,
        to_account_id="off_balance_sheet_contra_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
        },
    )


def charge_txn_type_fee_off_bs_call(
    amount, denomination=DEFAULT_DENOM, posting_id=POSTING_ID, txn_type=""
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_"
        f"{txn_type.upper()}_FEE_{posting_id}",
        from_account_id="revocable_commitment_internal_account",
        from_account_address=DEFAULT_ADDRESS,
        to_account_id="off_balance_sheet_contra_internal_account",
        to_account_address=DEFAULT_ADDRESS,
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
            "inst_type": txn_type.lower(),
        },
    )


def charge_dispute_fee_loan_to_customer_call(
    amount=ANY, denomination=DEFAULT_DENOM, posting_id=POSTING_ID
):

    loan_account = "dispute_fee_loan_internal_account"

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=loan_account,
        to_account_address=INTERNAL,
        to_account_id=ACCOUNT_ID,
        client_transaction_id=f"LOAN_TO_CUSTOMER_GL-{HOOK_EXECUTION_ID}-"
        f"FEES_CHARGED_DISPUTE_FEE_{posting_id}",
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


def charge_dispute_fee_off_bs_call(
    amount=ANY,
    denomination=DEFAULT_DENOM,
    off_balance_sheet_contra_internal_account="off_balance_sheet_contra_internal_account",
    posting_id=POSTING_ID,
    revocable_commitment_internal_account="revocable_commitment_internal_account",
):

    return make_internal_transfer_instructions_call(
        amount=amount,
        denomination=denomination,
        from_account_address=DEFAULT_ADDRESS,
        from_account_id=revocable_commitment_internal_account,
        to_account_address=DEFAULT_ADDRESS,
        to_account_id=off_balance_sheet_contra_internal_account,
        client_transaction_id=f"DECREASE_COMMITMENT_GL-{HOOK_EXECUTION_ID}-FEES_CHARGED_DISPUTE_FEE"
        f"_{posting_id}",
        instruction_details={
            "accounting_event": "LOAN_FEES",
            "account_id": ACCOUNT_ID,
        },
        override_all_restrictions=True,
    )


# flake8: noqa: B008
