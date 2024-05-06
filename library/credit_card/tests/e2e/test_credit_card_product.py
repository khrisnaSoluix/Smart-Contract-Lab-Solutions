# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from json import dumps, loads

# third party
import pytz
from dateutil.relativedelta import relativedelta
from requests import HTTPError

# common
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.core_api_helper as core_api_helper
from inception_sdk.test_framework.endtoend.balances import BalanceDimensions
from inception_sdk.test_framework.endtoend.helper import (
    retry_call,
    COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
)

# credit card test utils
import library.credit_card.tests.utils.common.lending as lending
from library.credit_card.tests.e2e.common import standard_teardown as credit_card_teardown

DEFAULT_DENOM = "GBP"
LOCAL_UTC_OFFSET = 0
INSTANCE_PARAM_OVERRIDES = {}

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

endtoend.testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID = {
    "TSIDE_ASSET": [],
    "TSIDE_LIABILITY": ["1", "PRINCIPAL_WRITE_OFF", "INTEREST_WRITE_OFF"],
}

endtoend.testhandle.CONTRACTS = {
    "credit_card": {
        "path": "library/credit_card/contracts/credit_card.py",
        "template_params": lending.DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS,
    },
}

endtoend.testhandle.WORKFLOWS = {
    "CREDIT_CARD_APPLICATION": ("library/credit_card/workflows/credit_card_application.yaml"),
    "CREDIT_CARD_BALANCE_TRANSFER": (
        "library/credit_card/workflows/credit_card_balance_transfer.yaml"
    ),
    "CREDIT_CARD_EXPIRE_INTEREST_FREE_PERIODS": (
        "library/credit_card/workflows/credit_card_expire_interest_free_periods.yaml"
    ),
}

endtoend.testhandle.FLAG_DEFINITIONS = {
    "ACCOUNT_CLOSURE_REQUESTED": (
        "library/credit_card/flag_definitions/account_closure_requested.resource.yaml"
    ),
    "MANUAL_WRITE_OFF": ("library/credit_card/flag_definitions/manual_write_off.resource.yaml"),
}

endtoend.testhandle.ACCOUNT_SCHEDULE_TAGS = {
    "CREDIT_CARD_ACCRUE_INTEREST_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CREDIT_CARD_STATEMENT_CUT_OFF_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CREDIT_CARD_ANNUAL_FEE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    "CREDIT_CARD_PAYMENT_DUE_AST": COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
}

endtoend.testhandle.internal_account = "1"

utc = pytz.utc
offset_tz = timezone(offset=timedelta(hours=LOCAL_UTC_OFFSET))


def standard_setup(test):

    """
    The standard credit card tests all start with:
    - Creating a customer
    - Opening an account
    :return:
    """
    instance_param_vals = deepcopy(lending.DEFAULT_CREDIT_CARD_INSTANCE_PARAMS)
    instance_param_vals.update(INSTANCE_PARAM_OVERRIDES.get(test._testMethodName, {}))
    test.cust_id = endtoend.core_api_helper.create_customer()
    test.account = endtoend.contracts_helper.create_account(
        customer=test.cust_id,
        contract="credit_card",
        instance_param_vals=instance_param_vals,
        permitted_denominations=[DEFAULT_DENOM],
        status="ACCOUNT_STATUS_OPEN",
    )
    test.account_id = test.account["id"]


def override_instance_param(overrides):
    """
    Set instance param values overrides for a test to be used in common setUp
    """

    def test_decorator(test_item):
        # At the point the decorator is called the test_item has not been properly initialised, so
        # _testMethodName can't be used
        INSTANCE_PARAM_OVERRIDES[test_item.__name__] = overrides
        return test_item

    return test_decorator


class CreditCardAccountTest(endtoend.End2Endtest):

    cust_id: str
    account: dict
    account_id: str

    def setUp(self):
        standard_setup(self)

    def tearDown(self):
        credit_card_teardown(self, "ACCOUNT_CLOSURE_REQUESTED")

    def test_cannot_double_spend_available_balance_by_backdating(self):
        # Current-dated posting within limit
        first_posting_ts = datetime.now(tz=timezone.utc)
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            batch_details={"description": "current-dated posting within limit"},
            account_id=self.account_id,
            amount="1500",
            value_datetime=first_posting_ts,
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Backdated posting is within limit as of its value_datetime, but use of live balances
        # should see it get rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            batch_details={"description": "back-dated posting within limit"},
            account_id=self.account_id,
            amount="1500",
            value_datetime=first_posting_ts - timedelta(microseconds=1),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])
        self.assertEqual(
            "CONTRACT_VIOLATION_INSUFFICIENT_FUNDS",
            pib["posting_instructions"][0]["contract_violations"][0]["type"],
        )

        # Current-dated posting within overlimit
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            batch_details={"description": "current-dated posting within overlimit"},
            account_id=self.account_id,
            amount="501",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "2001",
                )
            ],
        )

    def test_cannot_double_spend_deposit_balance_by_backdating(self):

        # Create Deposit Balance
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            batch_details={"description": "current-dated spend"},
            account_id=self.account_id,
            amount="1500",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="DEPOSIT", denomination=DEFAULT_DENOM),
                    "1500",
                )
            ],
        )

        # Partial Deposit Spend
        second_posting_value_datetime = datetime.now(tz=timezone.utc)
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            batch_details={"description": "back-dated spend"},
            account_id=self.account_id,
            amount="750",
            value_datetime=second_posting_value_datetime,
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="DEPOSIT", denomination=DEFAULT_DENOM),
                    "750",
                )
            ],
        )

        # Backdated spend
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="1000",
            value_datetime=second_posting_value_datetime - timedelta(microseconds=1),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (BalanceDimensions(address="DEPOSIT", denomination=DEFAULT_DENOM), "0"),
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "250",
                ),
            ],
        )

    def test_account_rejects_outbound_transfer_gt_available_balance(self):

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="15000",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

    @override_instance_param(
        {
            "transaction_type_limits": dumps({}),
            "transaction_type_fees": dumps({}),
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0", "REF2": "4"}}
            ),
        }
    )
    def test_repayments_follow_hierarchy(self):
        # Making a purchase
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "200",
                ),
            ],
        )

        # cash advance
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="300",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "aaa"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "500",
                ),
            ],
        )

        # Balance Transfer REF2
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="400",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF2"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "400",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "900",
                ),
            ],
        )

        # Balance Transfer REF1
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="500",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF1"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "400",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "500",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "1400",
                ),
            ],
        )

        # Partial Repayment
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "200",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "500",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "1200",
                ),
            ],
        )

        # Partial Repayment
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="300",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "200",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "500",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "900",
                ),
            ],
        )

        # Partial Repayment
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="300",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "100",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "500",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "600",
                ),
            ],
        )

        # Partial Repayment
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="300",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "0",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF2_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "300",
                ),
            ],
        )

    def test_deposit_balance_created_for_over_payment(self):
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="DEPOSIT", denomination=DEFAULT_DENOM),
                    "200",
                )
            ],
        )

    def test_overlimit_allows_overspend_but_prevents_additional_txns(self):
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="2001",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "2001",
                )
            ],
        )

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="1",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

    @override_instance_param(
        {"transaction_type_limits": dumps({"purchase": {"flat": "200", "percentage": "0.5"}})}
    )
    def test_cannot_exceed_txn_type_limit_cumulatively_or_in_single_txn(self):
        # Single purchase above flat limit is rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="210",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Single purchase below flat limit is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="110",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "110",
                )
            ],
        )

        # Purchase cumulatively above flat limit is rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="100",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Purchase cumulatively below flat limit is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="90",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "200",
                )
            ],
        )

    @override_instance_param(
        {
            "credit_limit": "1000",
            "transaction_type_limits": dumps(
                {
                    "purchase": {"flat": "200", "percentage": "0.5"},
                    "cash_advance": {"flat": "700", "percentage": "0.5"},
                }
            ),
        }
    )
    def test_lowest_defined_txn_type_credit_limit_is_used(self):
        # Single purchase above flat limit is rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="210",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Single purchase below flat limit is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="190",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Single cash advance above percentage limit is rejected
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="550",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "aaa"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        # Single cash advance below percentage limit is accepted
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="450",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "aaa"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "190",
                ),
                (
                    BalanceDimensions(address="CASH_ADVANCE_CHARGED", denomination=DEFAULT_DENOM),
                    "450",
                ),
                (
                    BalanceDimensions(
                        address="CASH_ADVANCE_FEES_CHARGED", denomination=DEFAULT_DENOM
                    ),
                    "22.5",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "662.5",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "662.5",
                ),
            ],
        )

    def test_external_fees_rebalanced_correctly(self):
        # Charging dispute fee externally
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="100",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"fee_type": "DISPUTE_FEE"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="DISPUTE_FEES_CHARGED", denomination=DEFAULT_DENOM),
                    "100",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "100",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "100",
                ),
            ],
        )

        # Charging ATM withdrawal fee externally
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="200",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"fee_type": "ATM_WITHDRAWAL_FEE"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="ATM_WITHDRAWAL_FEES_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "200",
                ),
                (
                    BalanceDimensions(address="DISPUTE_FEES_CHARGED", denomination=DEFAULT_DENOM),
                    "100",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "300",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "300",
                ),
            ],
        )

        # Charging unrecognised fee defaults to purchase
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="50",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"fee_type": "UNKNOWN_FEE_TYPE"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "50",
                ),
                (
                    BalanceDimensions(
                        address="ATM_WITHDRAWAL_FEES_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "200",
                ),
                (
                    BalanceDimensions(address="DISPUTE_FEES_CHARGED", denomination=DEFAULT_DENOM),
                    "100",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "350",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "350",
                ),
            ],
        )

    @override_instance_param({"credit_limit": "9999999"})
    def test_account_with_large_credit_limit_and_large_txn(self):
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="999999",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="AVAILABLE_BALANCE", denomination=DEFAULT_DENOM),
                    "9000000",
                ),
                (
                    BalanceDimensions(address="PURCHASE_CHARGED", denomination=DEFAULT_DENOM),
                    "999999",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "999999",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "999999",
                ),
            ],
        )

    @override_instance_param(
        {
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.01", "REF2": "0.02"}}
            ),
        }
    )
    def test_account_rejects_reuse_of_txn_ref(self):

        # Sending first amount with REF1
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="20",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF1"},
        )

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "20",
                )
            ],
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Sending second amount with REF1
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="10",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF1"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

    @override_instance_param(
        {"transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]})}
    )
    def test_account_rejects_missing_txn_ref(self):

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="20",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

    def test_account_rejects_undefined_txn_ref(self):

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="20",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF9"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

    @override_instance_param(
        {
            "transaction_references": dumps({"balance_transfer": ["REF1", "REF2"]}),
            "transaction_annual_percentage_rate": dumps(
                {"balance_transfer": {"REF1": "0.01", "REF2": "0.02"}}
            ),
            "transaction_type_limits": dumps(
                {
                    "cash_advance": {"flat": "200"},
                    "transfer": {"flat": "1000"},
                    "balance_transfer": {"flat": "100"},
                }
            ),
        }
    )
    def test_available_txn_limits_with_refs(self):
        """
        BT < limit accepted
        BT cumulatively > limit rejected
        BT cumulatively <= limit accepted
        """
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="20",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF1"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "20",
                )
            ],
        )

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="81",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF2"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_REJECTED", pib["status"])

        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="80",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF2"},
        )

        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "100",
                )
            ],
        )

    @override_instance_param(
        {
            "credit_limit": "3500",
            "transaction_type_limits": dumps(
                {"balance_transfer": {"allowed_days_after_opening": "14"}}
            ),
            "transaction_annual_percentage_rate": dumps({"balance_transfer": {}}),
            "transaction_base_interest_rates": dumps({"balance_transfer": {}}),
            "transaction_references": dumps({"balance_transfer": []}),
            "transaction_type_fees": dumps(
                {
                    "balance_transfer": {
                        "over_deposit_only": "True",
                        "percentage_fee": "0.02",
                        "flat_fee": "10",
                        "combine": "True",
                        "fee_cap": "100",
                    }
                }
            ),
        }
    )
    def test_balance_transfer_workflow(self):
        # Making a balance transfer using balance_transfer workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_BALANCE_TRANSFER",
            context={"user_id": self.cust_id, "account_id": self.account_id},
        )

        # Workflow will now move through the following states:
        # - retrieve_account_parameter_details
        # - validate_account_details

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_transfer_value",
            event_name="transfer_value_chosen",
            context={"transfer_value": "2800"},
        )

        # Workflow will now move through the following state:
        # - query_balances
        # - validate_transfer_value
        # Try an invalid interest free end date
        # Fetch the full details of the Workflow state to make sure we have transitioned later
        interest_free_period_end = datetime.utcnow() - timedelta(days=1)
        state_id = endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_free_period",
            event_name="interest_free_end_time_chosen",
            context={
                "interest_free_end_date": interest_free_period_end.strftime("%Y-%m-%d"),
                "interest_free_end_time": interest_free_period_end.strftime("%H:%M:%S"),
            },
        )

        # Expect to be put back into the same state after a brief time in
        # validate_interest_free_end_date - make sure Workflow has really
        # transitioned by passing state_id of the first capture_interest_free_period

        # Put a date in the future
        now = datetime.utcnow()
        interest_free_period_end = now + timedelta(days=90)
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_free_period",
            event_name="interest_free_end_time_chosen",
            context={
                "interest_free_end_date": interest_free_period_end.strftime("%Y-%m-%d"),
                "interest_free_end_time": interest_free_period_end.strftime("%H:%M:%S"),
            },
            current_state_id=state_id,
        )

        # Workflow will now move through the following state:
        # - validate_interest_free_end_date
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_transfer_details",
            event_name="details_confirmed",
        )

        # Workflow will now move through the following state:
        # - determine_account_parameters
        # - update_account_parameters
        # - make_balance_transfer

        endtoend.workflows_helper.wait_for_state(wf_id, "successful_balance_transfer")

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                # Balance transfer fee is 2800 * 0.02 + 10 = 66
                (
                    BalanceDimensions(address="AVAILABLE_BALANCE", denomination=DEFAULT_DENOM),
                    "634",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_FEES_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "66",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "2866",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "2866",
                ),
            ],
        )

        # Check the parameter has been updated correctly for the expiry
        # Get the transaction reference ID from the Workflow
        wf_state = endtoend.workflows_helper.get_current_workflow_state(wf_id)
        txn_ref = wf_state["global_state"]["new_txn_ref"]
        expected_expiry = interest_free_period_end.strftime("%Y-%m-%d %H:%M:%S")
        params = endtoend.contracts_helper.get_account(self.account_id)["instance_param_vals"]
        interest_free_expiry = params.get("interest_free_expiry")
        transaction_interest_free_expiry = params.get("transaction_interest_free_expiry")
        self.assertEqual(interest_free_expiry, dumps({}))
        self.assertEqual(
            loads(transaction_interest_free_expiry),
            {"balance_transfer": {txn_ref: expected_expiry}},
        )

        # First balance transfer test successful

        # Try another balance transfer
        # This time it should be rejected due to the transfer value validation
        # Making a balance transfer using balance_transfer workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_BALANCE_TRANSFER",
            context={"user_id": self.cust_id, "account_id": self.account_id},
        )

        # Workflow will now move through the following states:
        # - retrieve_account_parameter_details
        # - validate_account_details

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_transfer_value")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_transfer_value",
            event_name="transfer_value_chosen",
            context={"transfer_value": "620"},
        )

        # The workflow should work out that a fee of 620 * 0.02 + 10 = 22 will be required
        # Since the sum of value & fee exceeds available balance, the workflow will quit now
        endtoend.workflows_helper.wait_for_state(wf_id, "rejected_balance_transfer")

    @override_instance_param(
        {
            "interest_free_expiry": dumps(
                {
                    "cash_advance": "2020-12-31 12:00:00",
                    "transfer": "2018-02-01 12:00:00",
                    "purchase": "2018-01-01 12:00:00",
                }
            ),
            "transaction_interest_free_expiry": dumps(
                {
                    "balance_transfer": {
                        "REF1": "2020-12-31 12:00:00",
                        "REF2": "2020-01-01 12:00:00",
                    }
                }
            ),
        }
    )
    def test_expire_interest_free_periods_workflow(self):
        # Calling expire_interest_free_periods workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_EXPIRE_INTEREST_FREE_PERIODS",
            context={"account_id": self.account_id},
        )

        # Workflow will now move through the following states:
        # - retrieve_account_parameter_details
        # - validate_account_details
        # - update_interest_free_periods
        # - upload_updated_interest_free_periods

        endtoend.workflows_helper.wait_for_state(wf_id, "interest_free_expiry_updated_successfully")

        instance_param_update = endtoend.helper.retry_call(
            func=endtoend.core_api_helper.get_account_updates_by_type,
            f_kwargs={
                "account_id": self.account_id,
                "update_types": ["instance_param_vals_update"],
            },
            expected_result=True,
            result_wrapper=lambda x: len(x) > 0,
            failure_message=f"No account updates for account {self.account_id} could be found.",
        )[-1]

        def result_wrapper_function(result):
            instance_param_vals = result["instance_param_vals_update"]["instance_param_vals"]
            return (
                loads(instance_param_vals["interest_free_expiry"]),
                loads(instance_param_vals["transaction_interest_free_expiry"]),
            )

        retry_call(
            func=core_api_helper.get_account_update,
            f_args=[instance_param_update["id"]],
            expected_result=(
                {"purchase": "", "transfer": "", "cash_advance": ""},
                {"balance_transfer": {"REF1": "", "REF2": ""}},
            ),
            result_wrapper=result_wrapper_function,
        )


class CreditCardAccountClosureTest(endtoend.End2Endtest):

    cust_id: str
    account: dict
    account_id: str

    def setUp(self):
        standard_setup(self)

    def tearDown(self):
        log.info(f"Test Finished: {self._testMethodName}\nTearing Down")
        # Credit card closure tests will manually trigger account closure as part of the test
        # so we don't use standard_teardown()

    def test_close_code_zeroes_out_remaining_balances(self):

        # Spending some money
        posting_id = endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="1500",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "1500",
                )
            ],
        )

        # Mocking an interest accrual
        posting_id = endtoend.postings_helper.create_custom_instruction(
            batch_details={"description": "current-dated posting within limit"},
            postings=[
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="PURCHASE_INTEREST_PRE_SCOD_UNCHARGED",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=False,
                ),
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="INTERNAL",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=True,
                ),
            ],
            value_datetime=datetime.now(tz=timezone.utc),
            instruction_details={"originating_account_id": self.account_id},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])
        # For the interest of testing zeroing out accrual addresses on closure in one test case
        # simulate state where both PRE/POST_SCOD_UNCHARGED addresses and INTEREST_UNCHARGED address
        # have accrued some interest
        posting_id = endtoend.postings_helper.create_custom_instruction(
            batch_details={"description": "current-dated posting within limit"},
            postings=[
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="PURCHASE_INTEREST_POST_SCOD_UNCHARGED",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=False,
                ),
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="INTERNAL",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=True,
                ),
            ],
            value_datetime=datetime.now(tz=timezone.utc),
            instruction_details={"originating_account_id": self.account_id},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        posting_id = endtoend.postings_helper.create_custom_instruction(
            batch_details={"description": "current-dated posting within limit"},
            postings=[
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="PURCHASE_INTEREST_UNCHARGED",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=False,
                ),
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="INTERNAL",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=True,
                ),
            ],
            value_datetime=datetime.now(tz=timezone.utc),
            instruction_details={"originating_account_id": self.account_id},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Mocking an interest free period interest accrual
        posting_id = endtoend.postings_helper.create_custom_instruction(
            batch_details={"description": "current-dated posting within limit"},
            postings=[
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="PURCHASE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=False,
                ),
                endtoend.postings_helper.create_posting(
                    account_id=self.account_id,
                    amount="1.0",
                    asset="COMMERCIAL_BANK_MONEY",
                    account_address="INTERNAL",
                    denomination=DEFAULT_DENOM,
                    phase="POSTING_PHASE_COMMITTED",
                    credit=True,
                ),
            ],
            value_datetime=datetime.now(tz=timezone.utc),
            instruction_details={"originating_account_id": self.account_id},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        # Repaying to populate TOTAL_REPAYMENTS_LAST_STATEMENT
        posting_id = endtoend.postings_helper.inbound_hard_settlement(
            account_id=self.account_id,
            amount="1500",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )
        pib = endtoend.postings_helper.get_posting_batch(posting_id)
        self.assertEqual("POSTING_INSTRUCTION_BATCH_STATUS_ACCEPTED", pib["status"])

        core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping["ACCOUNT_CLOSURE_REQUESTED"],
            self.account_id,
        )

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[(BalanceDimensions(address="FULL_OUTSTANDING_BALANCE"), "0")],
            description="After full repayment full outstanding balance should be zeroed out",
        )

        endtoend.core_api_helper.update_account(
            self.account_id,
            core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=self.account_id, account_update_type="closure_update"
        )
        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (BalanceDimensions(address="FULL_OUTSTANDING_BALANCE"), "0"),
                (BalanceDimensions(address="AVAILABLE_BALANCE"), "0"),
            ],
            description="After close_code full and available balance should be zeroed out",
        )

    def test_write_off_happy_path(self):
        # Spending some money
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="1500",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "xxx"},
        )

        endtoend.balances_helper.wait_for_all_account_balances(
            {
                self.account_id: [
                    (BalanceDimensions(address="FULL_OUTSTANDING_BALANCE"), "1500"),
                    (BalanceDimensions(address="PURCHASE_CHARGED"), "1500"),
                    (BalanceDimensions(address="OUTSTANDING_BALANCE"), "1500"),
                ],
            },
            description="Ensure post-posting has finished before closing the account",
        )

        core_api_helper.create_flag(
            endtoend.testhandle.flag_definition_id_mapping["MANUAL_WRITE_OFF"],
            account_id=self.account_id,
        )

        endtoend.core_api_helper.update_account(
            self.account_id,
            core_api_helper.AccountStatus.ACCOUNT_STATUS_PENDING_CLOSURE,
        )
        endtoend.accounts_helper.wait_for_account_update(
            account_id=self.account_id,
            account_update_type="closure_update",
            target_status="ACCOUNT_UPDATE_STATUS_COMPLETED",
        )

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (BalanceDimensions(address="FULL_OUTSTANDING_BALANCE"), "0"),
                (BalanceDimensions(address="AVAILABLE_BALANCE"), "0"),
            ],
            description="After close_code full and available balance should be zeroed out",
        )


class CreditCardAccountOpeningTest(endtoend.End2Endtest):
    def tearDown(self):
        credit_card_teardown(self, "ACCOUNT_CLOSURE_REQUESTED")

    # These tests do not all use standard setup as we're testing account opening scenarios
    # that may deviate from the standard setup process

    def test_account_opened_with_all_expected_balance_addresses(self):
        standard_setup(self)

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="AVAILABLE_BALANCE", denomination=DEFAULT_DENOM),
                    "2000",
                ),
                (BalanceDimensions(address="INTERNAL", denomination=DEFAULT_DENOM), "-2000"),
                (BalanceDimensions(address="DEPOSIT_BALANCE", denomination=DEFAULT_DENOM), "0"),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "0",
                ),
                (BalanceDimensions(address="MAD_BALANCE", denomination=DEFAULT_DENOM), "0"),
                (BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM), "0"),
                (BalanceDimensions(address="REVOLVER", denomination=DEFAULT_DENOM), "0"),
                (BalanceDimensions(address="STATEMENT_BALANCE", denomination=DEFAULT_DENOM), "0"),
                (
                    BalanceDimensions(
                        address="TOTAL_REPAYMENTS_LAST_STATEMENT", denomination=DEFAULT_DENOM
                    ),
                    "0",
                ),
            ],
        )

    def test_account_opening_with_minimum_pdp(self):
        instance_param_vals = deepcopy(lending.DEFAULT_CREDIT_CARD_INSTANCE_PARAMS)
        pdp = "20"
        instance_param_vals.update({"payment_due_period": pdp})
        cust_id = endtoend.core_api_helper.create_customer()
        with self.assertRaises(HTTPError) as e:
            endtoend.contracts_helper.create_account(
                customer=cust_id,
                contract="credit_card",
                instance_param_vals=instance_param_vals,
                permitted_denominations=[DEFAULT_DENOM],
                status="ACCOUNT_STATUS_OPEN",
            )
        self.assertEqual(
            eval(e.exception.response.text)["message"],
            f"Value {pdp} for Parameter 'payment_due_period' " f"falls outside of allowed range",
        )

        pdp = "21"
        instance_param_vals.update({"payment_due_period": pdp})
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="credit_card",
            instance_param_vals=instance_param_vals,
            permitted_denominations=[DEFAULT_DENOM],
            status="ACCOUNT_STATUS_OPEN",
        )
        # Enables re-use of standard teardown despite bypassing standard setup
        self.account = account
        self.account_id = account["id"]

    def test_account_opening_with_maximum_pdp(self):
        instance_param_vals = deepcopy(lending.DEFAULT_CREDIT_CARD_INSTANCE_PARAMS)
        pdp = "28"
        instance_param_vals.update({"payment_due_period": pdp})
        cust_id = endtoend.core_api_helper.create_customer()
        with self.assertRaises(HTTPError) as e:
            endtoend.contracts_helper.create_account(
                customer=cust_id,
                contract="credit_card",
                instance_param_vals=instance_param_vals,
                permitted_denominations=[DEFAULT_DENOM],
                status="ACCOUNT_STATUS_OPEN",
            )
        self.assertEqual(
            eval(e.exception.response.text)["message"],
            f"Value {pdp} for Parameter 'payment_due_period' " f"falls outside of allowed range",
        )

        pdp = "27"
        instance_param_vals.update({"payment_due_period": pdp})
        account = endtoend.contracts_helper.create_account(
            customer=cust_id,
            contract="credit_card",
            instance_param_vals=instance_param_vals,
            permitted_denominations=[DEFAULT_DENOM],
            status="ACCOUNT_STATUS_OPEN",
        )
        # Enables re-use of standard teardown despite bypassing standard setup
        self.account = account
        self.account_id = account["id"]

    def test_apply_for_credit_card_no_overlimit(self):
        """
        Apply for a Credit Card with overlimit opted out
        """

        cust_id = endtoend.core_api_helper.create_customer()

        # Applying for a credit card using apply_for_credit_card workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["credit_card"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_credit_limit",
            event_name="chosen_credit_limit",
            context={"credit_limit": "9500"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_overlimit_opt_in",
            event_name="overlimit_opt_in_captured",
            context={"overlimit_opt_in": "False"},
        )

        # Workflow will now move through the following states:
        # - query_contract_versions
        # - extract_contract_parameter_details
        # - create_account
        # - open_account
        start_time = datetime.now(tz=timezone.utc)
        offset_days = 0

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        self.account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]

        endtoend.accounts_helper.wait_for_account_update(self.account_id, "activation_update")

        self.account = endtoend.contracts_helper.get_account(self.account_id)
        account_schedules = endtoend.schedule_helper.get_account_schedules(self.account_id)

        # Interest is accrued daily
        accrue_interest_expected_next_run_time = start_time + relativedelta(
            days=1, hour=0, minute=0, second=0
        )

        # Annual fee is charged at 23:50 yearly, starting on the same night the account is created.
        if start_time.hour == 23 and start_time.minute >= 50:
            offset_days = 1

        annual_fee_expected_next_run_time = start_time + relativedelta(
            days=offset_days, hour=23, minute=50, second=0
        )

        self.assertEqual(
            accrue_interest_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ACCRUE_INTEREST"]["next_run_timestamp"],
        )

        self.assertEqual(
            annual_fee_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["ANNUAL_FEE"]["next_run_timestamp"],
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", self.account["status"])

        self.assertEqual("100", self.account["instance_param_vals"]["late_repayment_fee"])

        self.assertEqual("9500", self.account["instance_param_vals"]["credit_limit"])

        self.assertEqual("False", self.account["instance_param_vals"]["overlimit_opt_in"])

        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                (
                    BalanceDimensions(address="AVAILABLE_BALANCE", denomination=DEFAULT_DENOM),
                    "9500",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "0",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "0",
                ),
            ],
        )

    def test_apply_for_credit_card_with_overlimit_and_balance_transfer(self):
        """
        Apply for a Credit Card with overlimit opted in, followed by some balance transfers
        """

        cust_id = endtoend.core_api_helper.create_customer()

        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_APPLICATION",
            context={
                "user_id": cust_id,
                "product_id": endtoend.testhandle.contract_pid_to_uploaded_pid["credit_card"],
            },
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_credit_limit",
            event_name="chosen_credit_limit",
            context={"credit_limit": "10500"},
        )

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_overlimit_opt_in",
            event_name="overlimit_opt_in_captured",
            context={"overlimit_opt_in": "True"},
        )

        # Workflow will now move through the following states:
        # - query_contract_versions
        # - extract_contract_parameter_details
        # - create_account
        # - open_account

        endtoend.workflows_helper.wait_for_state(wf_id, "account_opened_successfully")

        self.account_id = endtoend.workflows_helper.get_global_context(wf_id)["account_id"]
        endtoend.accounts_helper.wait_for_account_update(self.account_id, "activation_update")

        self.account = endtoend.contracts_helper.get_account(self.account_id)
        account_schedules = endtoend.schedule_helper.get_account_schedules(self.account_id)

        # First payment due date is 1 month + 21 days after account creation
        payment_due_expected_next_run_time = datetime.now(tz=timezone.utc) + relativedelta(
            months=1, days=21, hour=0, minute=0, second=1
        )

        self.assertEqual(
            payment_due_expected_next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            account_schedules["PAYMENT_DUE"]["next_run_timestamp"],
        )

        self.assertEqual("ACCOUNT_STATUS_OPEN", self.account["status"])

        self.assertEqual("100", self.account["instance_param_vals"]["overlimit_fee"])

        self.assertEqual("10500", self.account["instance_param_vals"]["credit_limit"])

        self.assertEqual("True", self.account["instance_param_vals"]["overlimit_opt_in"])

        # Making a balance transfer using e2e postings - REF1
        endtoend.postings_helper.outbound_hard_settlement(
            account_id=self.account_id,
            amount="400",
            value_datetime=datetime.now(tz=timezone.utc),
            denomination=DEFAULT_DENOM,
            instruction_details={"transaction_code": "bb", "transaction_ref": "REF1"},
        )

        # Making a balance transfer using balance_transfer workflow
        wf_id = endtoend.workflows_helper.start_workflow(
            "CREDIT_CARD_BALANCE_TRANSFER",
            context={"user_id": cust_id, "account_id": self.account_id},
        )

        # Workflow will now move through the following states:
        # - retrieve_account_parameter_details
        # - validate_account_details

        endtoend.workflows_helper.wait_for_state(wf_id, "capture_transfer_value")

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_transfer_value",
            event_name="transfer_value_chosen",
            context={"transfer_value": "3000"},
        )

        # Workflow will now move through the following state:
        # - query_balances
        # - validate_transfer_value

        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="capture_interest_free_period",
            event_name="no_interest_free_period",
        )
        endtoend.workflows_helper.send_event(
            wf_id,
            event_state="confirm_transfer_details",
            event_name="details_confirmed",
        )

        # - determine_account_parameters
        # - update_account_parameters
        # - make_balance_transfer

        endtoend.workflows_helper.wait_for_state(wf_id, "successful_balance_transfer")

        # Default balance transfer fee parameters are:
        # flat_fee = 25
        # percentage_fee = 0.025
        # combined = True
        # fee_cap = 100
        endtoend.balances_helper.wait_for_account_balances(
            self.account_id,
            expected_balances=[
                # Balance transfer fee for REF1 is 35
                # Balance transfer fee for our workflow is 100. The two fees add up to 135.
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_REF1_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "400",
                ),
                (
                    BalanceDimensions(
                        address="BALANCE_TRANSFER_FEES_CHARGED",
                        denomination=DEFAULT_DENOM,
                    ),
                    "135",
                ),
                (
                    BalanceDimensions(address="AVAILABLE_BALANCE", denomination=DEFAULT_DENOM),
                    "6965",
                ),
                (
                    BalanceDimensions(address="OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM),
                    "3535",
                ),
                (
                    BalanceDimensions(
                        address="FULL_OUTSTANDING_BALANCE", denomination=DEFAULT_DENOM
                    ),
                    "3535",
                ),
            ],
        )


if __name__ == "__main__":
    endtoend.runtests()
