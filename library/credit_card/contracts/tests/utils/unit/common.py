# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
from collections import defaultdict, namedtuple
from inception_sdk.test_framework.contracts.unit.common import BalanceDimensions
from library.credit_card.tests.utils.common.common import (
    offset_datetime,
)
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    Balance,
    ClientTransaction,
    ClientTransactionEffects,
    Parameter,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionType,
    Tside,
    BalanceDefaultDict,
)
from typing import List, Dict, Optional, Tuple
from unittest.mock import Mock, ANY, call
from unittest import TestCase


ACCOUNT_ID = "current_account"
CLIENT_TRANSACTION_ID = "trigger"
DEFAULT_DATE = datetime(2019, 1, 1)
HOOK_EXECUTION_ID = "hook_execution_id"
POSTING_ID = "posting_id"
POSTING_CLIENT_ID = "client_id"
DEFAULT_DENOM = "GBP"
LOCAL_UTC_OFFSET = 0
GENERIC_POSTING = PostingInstruction(
    account_address=DEFAULT_ADDRESS,
    amount=Decimal(1000),
    denomination=DEFAULT_DENOM,
    credit=False,
    phase=Phase.COMMITTED,
    override_all_restrictions=False,
    instruction_details={},
)


class BaseTestCase(TestCase):

    contract_file: str = ""
    tside: Tside = Tside.ASSET
    default_denom: str = ""

    def setUp(self):
        contract = self.contract_file
        with open(contract, "r", encoding="utf-8") as content_file:
            self.smart_contract = content_file.read()

    @staticmethod
    def param_map_to_timeseries(param_map, default_dt):
        param_timeseries = {}
        for param_name, param_details in param_map.items():
            if type(param_details["value"]) == list:
                param_timeseries.update(
                    {
                        param_name: param_details["value"]
                        if not param_details.get("optional", False)
                        else [
                            (
                                timeseries_entry[0],
                                OptionalValue(
                                    value=timeseries_entry[1],
                                    is_set=timeseries_entry[1] != param_details["default_value"],
                                ),
                            )
                            for timeseries_entry in param_details["value"]
                        ]
                    }
                )

            else:
                param_timeseries.update(
                    {
                        param_name: [
                            (default_dt, param_details["value"])
                            if not param_details.get("optional", False)
                            else (
                                default_dt,
                                OptionalValue(
                                    value=param_details["value"],
                                    is_set=param_details["value"] != param_details["default_value"],
                                ),
                            )
                        ]
                    }
                )

        return param_timeseries

    def create_mock(
        self,
        account_creation_date: datetime = offset_datetime(2019, 1, 1),
        balance_timeseries: List[
            Tuple[datetime, Dict[Tuple[str, str, str, Phase], Balance]]
        ] = None,
        client_transactions=None,
        flag_timeseries: Dict[str, List[Tuple[datetime, bool]]] = None,
        hook_execution_id: str = HOOK_EXECUTION_ID,
        parameter_timeseries: Dict[str, List[Tuple[datetime, Parameter]]] = None,
        last_execution_times: Dict[str, datetime] = None,
        postings=None,
        posting_batches=None,  # TODO: implement get_posting_batches mock
    ):
        """

        :param account_creation_date:
        :param balance_timeseries:
        :param client_transactions:
        :param flag_timeseries:
        :param hook_execution_id:
        :param parameter_timeseries:
        :param last_execution_times:
        :param postings:
        :param posting_batches:
        :return:
        """

        def mock_get_account_creation_date():
            return account_creation_date

        def mock_get_balance_timeseries():
            return TimeSeries(balance_timeseries)

        def mock_get_client_transactions(include_proposed):
            return client_transactions

        def mock_get_flag_timeseries(flag):
            return TimeSeries(flag_timeseries.get(flag, []), return_on_empty=False)

        def mock_get_last_execution_name(event_type):
            return last_execution_times[event_type]

        def mock_get_parameter_timeseries(name):
            return TimeSeries(parameter_timeseries[name])

        def mock_get_postings(include_proposed=False):
            return postings or []

        def mock_make_internal_transfer_instructions(
            amount,
            denomination,
            from_account_id,
            from_account_address,
            to_account_id,
            to_account_address,
            asset,
            client_transaction_id,
            instruction_details,
            override_all_restrictions,
        ):

            from_posting = self.mock_posting_instruction(
                amount=amount,
                denomination=denomination,
                instruction_details=instruction_details,
                asset=asset,
                client_transaction_id=client_transaction_id,
                account_id=from_account_id,
                account_address=from_account_address,
                credit=False,
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                override_all_restrictions=override_all_restrictions,
            )
            to_posting = self.mock_posting_instruction(
                amount=amount,
                denomination=denomination,
                instruction_details=instruction_details,
                asset=asset,
                client_transaction_id=client_transaction_id,
                account_id=to_account_id,
                account_address=to_account_address,
                credit=True,
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                override_all_restrictions=override_all_restrictions,
            )
            return [from_posting, to_posting]

        mock_vault = Mock()
        mock_vault.account_id = "current_account"
        mock_vault.get_account_creation_date.side_effect = mock_get_account_creation_date
        mock_vault.get_balance_timeseries.side_effect = mock_get_balance_timeseries
        mock_vault.get_client_transactions.side_effect = mock_get_client_transactions
        mock_vault.get_flag_timeseries.side_effect = mock_get_flag_timeseries
        mock_vault.get_hook_execution_id.return_value = HOOK_EXECUTION_ID
        mock_vault.get_last_execution_time.side_effect = mock_get_last_execution_name
        mock_vault.make_internal_transfer_instructions.side_effect = (
            mock_make_internal_transfer_instructions
        )
        mock_vault.get_parameter_timeseries.side_effect = mock_get_parameter_timeseries
        mock_vault.get_postings.side_effect = mock_get_postings

        return mock_vault

    def check_mock_vault_method_calls(
        self,
        mock_vault_method,
        expected_calls=None,
        unexpected_calls=None,
        exact_order=False,
        exact_match=False,
    ):
        """
        Asserts that expected calls were made and no unexpected calls were
        param mock_vault_method: Mock, method from vault mock after test has run
        param expected_calls: list(call), list of expected calls
        param unexpected_calls: list(call), list of unexpected calls
        param exact_order: Boolean, True if exact order of call matters
        param exact_match: Boolean, True if exact order and number of calls matters
        return: Boolean, True if expected calls were made
        """

        actual_calls = mock_vault_method.mock_calls
        expected_calls = expected_calls or []
        unexpected_calls = unexpected_calls or []

        if exact_match:
            self.assertEqual(
                len(expected_calls),
                len(actual_calls),
                "The number of actual calls and expected calls do not match",
            )

        if exact_match:
            for index, expected_call in enumerate(expected_calls):
                # call at a given index must be identical on expected and actual
                self.assertEqual(
                    expected_call,
                    actual_calls[index],
                    f"Expected at {index}: {expected_call} \n but found {actual_calls[index]}",
                )
        elif exact_order:
            # we allow for other calls to be in between the ones we expect, as long as the ones
            # we expect are found in the right order
            expected_call_index = 0
            for index, actual_call in enumerate(actual_calls):
                if actual_call == expected_calls[expected_call_index]:
                    expected_call_index += 1

                remaining_expected_calls = len(expected_calls) - expected_call_index
                remaining_actual_calls = len(actual_calls) - index - 1
                if remaining_expected_calls == 0:
                    break

                self.assertGreaterEqual(
                    remaining_actual_calls,
                    remaining_expected_calls,
                    f"{remaining_actual_calls} actual calls left to match"
                    f" {remaining_expected_calls} expected calls.\n The first "
                    f"{expected_call_index + 1} calls were matched in order",
                )
        else:
            for index, expected_call in enumerate(expected_calls):
                # TODO: we need to pop the matched actual_call off in case we expect
                #  two identical calls to be made
                self.assertEqual(
                    True,
                    expected_call in actual_calls,
                    f"Expected call not found in actual calls: {expected_call}\n"
                    f"Actual calls: {actual_calls}",
                )

        for unexpected_call in unexpected_calls:
            self.assertEqual(
                unexpected_call in actual_calls,
                False,
                f"Unexpected call found in actual calls: {unexpected_call}\n"
                f"Actual calls:{actual_calls}",
            )

    def check_calls_for_vault_methods(
        # mock_vault is used inside an eval statement
        self,
        mock_vault,
        expected_calls=None,
        unexpected_calls=None,
        exact_order=False,
        exact_match=False,
    ):
        """
        Asserts that expected calls were made and no unexpected calls were
        param mock_vault: Mock, mock vault
        param expected_calls: list(VaultCall), list of expected calls
        param unexpected_calls: list(VaultCall), list of unexpected calls
        param exact_order: Boolean, True if exact order of call matters. Note this is not enforced
        across different vault methods
        param exact_match: Boolean, True if exact order and number of calls matters. Note this is
        not enforced across different vault methods
        return: Boolean, True if expected calls were made
        """

        calls_by_method = defaultdict(lambda: defaultdict(lambda: []))

        # Group calls by method
        for vault_call in expected_calls or []:
            calls_by_method[vault_call.vault_method]["expected_calls"].append(vault_call.call)

        for vault_call in unexpected_calls or []:
            calls_by_method[vault_call.vault_method]["unexpected_calls"].append(vault_call.call)

        for method in calls_by_method:
            self.check_mock_vault_method_calls(
                mock_vault_method=eval(f"mock_vault.{method.value}"),
                expected_calls=calls_by_method[method]["expected_calls"],
                unexpected_calls=calls_by_method[method]["unexpected_calls"],
                exact_match=exact_match,
                exact_order=exact_order,
            )

    @staticmethod
    def assert_no_side_effects(mock_vault):
        """
        Asserts that no postings, workflows or schedules were created/amended/deleted
        param mock_vault: Mock, vault mock after test has run
        return:
        """
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()
        mock_vault.start_workflow.assert_not_called()
        mock_vault.amend_schedule.assert_not_called()

    def mock_posting_instruction(
        self,
        account_address=DEFAULT_ADDRESS,
        account_id=ACCOUNT_ID,
        asset=DEFAULT_ASSET,
        amount: Optional[Decimal] = Decimal(0),
        client_id=POSTING_CLIENT_ID,
        client_transaction_id=CLIENT_TRANSACTION_ID,
        credit=False,
        denomination="",
        final=False,
        id=POSTING_ID,
        instruction_details: Dict[str, str] = None,
        mocks_as_any: bool = False,
        override_all_restrictions=False,
        phase=Phase.COMMITTED,
        type: PostingInstructionType = PostingInstructionType.HARD_SETTLEMENT,
        unsettled_amount: Decimal = Decimal(0),
        value_timestamp=None,
        advice=False,
        original_credit: Optional[bool] = None,
    ):
        """
        Creates a mock posting instruction to be fed into unit tests. All parameters as per
        PostingInstruction type, except for those documented below
        :param account_address:
        :param account_id:
        :param asset:
        :param amount:
        :param client_id:
        :param client_transaction_id:
        :param credit:
        :param denomination:
        :param final:
        :param id:
        :param instruction_details:
        :param mocks_as_any: if set to True, all PostingInstruction methods return 'ANY'. Use
        if you need to compare mocks and actual contract outputs
        :param override_all_restrictions:
        :param phase:
        :param type:
        :param value_timestamp:
        :param unsettled_amount: use to mock instruction balances for secondary instructions where
         amount may be None. In Vault this would be calculated using the client transaction, but
         for unit tests we just want to specify the amount
        :param advice:
        :param original_credit: set to True for auth_adjust to inbound auth, False for auth_adjust
         to outbound_auth
        :return:
        """
        denomination = denomination or self.default_denom
        amount = Decimal(amount) if amount else None
        unsettled_amount = Decimal(unsettled_amount)
        instruction_details = instruction_details or {}
        instruction = PostingInstruction(
            account_address=account_address,
            account_id=account_id,
            asset=asset,
            amount=amount,
            client_transaction_id=client_transaction_id,
            denomination=denomination,
            credit=credit,
            phase=phase,
            override_all_restrictions=override_all_restrictions,
            instruction_details=instruction_details,
            type=type,
            id=id,
            advice=advice,
        )
        instruction.client_id = client_id
        instruction.final = final
        instruction.value_timestamp = value_timestamp

        if type == PostingInstructionType.CUSTOM_INSTRUCTION:
            instruction.custom_instruction_grouping_key = client_transaction_id

        # This is used to return ANY instead of mocks so that comparisons between what is generated
        # in the tests and the expected returns match
        if mocks_as_any:
            instruction.batch_details = ANY
            instruction.client_batch_id = ANY
            instruction.value_timestamp = ANY
            instruction.batch_id = ANY
            instruction.balances = ANY

            return instruction

        balances = {}
        if instruction.type == PostingInstructionType.CUSTOM_INSTRUCTION:
            dimensions = BalanceDimensions(account_address, asset, denomination, phase)
            value = balance(
                debit=0 if credit else amount,
                credit=amount if credit else 0,
                tside=self.tside,
            )
            balances = {dimensions: value}

        elif instruction.type == PostingInstructionType.AUTHORISATION:
            dimensions = BalanceDimensions(
                DEFAULT_ADDRESS,
                asset,
                denomination,
                phase.PENDING_IN if credit else phase.PENDING_OUT,
            )
            value = balance(
                debit=0 if credit else amount,
                credit=amount if credit else 0,
                tside=self.tside,
            )
            balances = {dimensions: value}

        elif instruction.type in [
            PostingInstructionType.HARD_SETTLEMENT,
            PostingInstructionType.TRANSFER,
        ]:
            dimensions = BalanceDimensions(DEFAULT_ADDRESS, asset, denomination, phase.COMMITTED)
            value = balance(
                debit=0 if credit else amount,
                credit=amount if credit else 0,
                tside=self.tside,
            )
            balances = {dimensions: value}

        # TODO: handle absolute auth adjust amounts
        elif instruction.type == PostingInstructionType.AUTHORISATION_ADJUSTMENT:
            # original_credit should be true for inbound auth and false for outbound auth
            if original_credit:
                if credit:  # increasing an inbound auth
                    value = balance(debit=Decimal(0), credit=amount, tside=self.tside)
                else:  # decreasing an inbound auth
                    value = balance(debit=abs(amount), credit=Decimal(0), tside=self.tside)
            else:
                if credit:  # decreasing an outbound auth
                    value = balance(debit=Decimal(0), credit=abs(amount), tside=self.tside)
                else:  # increasing an outbound auth
                    value = balance(debit=amount, credit=Decimal(0), tside=self.tside)

            dimensions = BalanceDimensions(
                DEFAULT_ADDRESS,
                asset,
                denomination,
                phase.PENDING_IN if original_credit else phase.PENDING_OUT,
            )
            balances = {dimensions: value}

        elif instruction.type == PostingInstructionType.SETTLEMENT:
            # credit should be true for inbound auth and false for outbound auth
            settlement_amount = amount or unsettled_amount
            if final:
                auth_amount = unsettled_amount
            else:
                auth_amount = min(settlement_amount, unsettled_amount)

            # this zeroes the pending balance
            value_pending = balance(
                debit=auth_amount if credit else 0,
                credit=0 if credit else auth_amount,
                tside=self.tside,
            )
            # this debits/credits the
            value_committed = balance(
                debit=0 if credit else settlement_amount,
                credit=settlement_amount if credit else 0,
                tside=self.tside,
            )

            dimensions_pending = BalanceDimensions(
                DEFAULT_ADDRESS,
                asset,
                denomination,
                phase.PENDING_IN if credit else phase.PENDING_OUT,
            )

            dimensions_committed = BalanceDimensions(
                DEFAULT_ADDRESS, asset, denomination, phase.COMMITTED
            )

            balances = {
                dimensions_pending: value_pending,
                dimensions_committed: value_committed,
            }

        elif instruction.type == PostingInstructionType.RELEASE:
            # credit should be true for inbound auth and false for outbound auth
            # this zeroes the pending balance
            value_pending = balance(
                debit=unsettled_amount if credit else 0,
                credit=0 if credit else unsettled_amount,
                tside=self.tside,
            )

            dimensions_pending = BalanceDimensions(
                DEFAULT_ADDRESS,
                asset,
                denomination,
                phase.PENDING_IN if credit else phase.PENDING_OUT,
            )

            balances = {
                dimensions_pending: value_pending,
            }

        instruction.balances = Mock(
            return_value=BalanceDefaultDict(
                lambda: Balance(Decimal(0), Decimal(0), Decimal(0)), balances
            )
        )

        return instruction

    # TODO: add inbound/outbound auth methods to avoid errors with credit
    def auth(
        self,
        amount=Decimal(0),
        credit=False,
        denomination="",
        id=POSTING_ID,
        instruction_details={},
    ):

        return self.mock_posting_instruction(
            amount=amount,
            credit=credit,
            denomination=denomination or self.default_denom,
            id=id,
            instruction_details=instruction_details,
            type=PostingInstructionType.AUTHORISATION,
        )

    def inbound_auth_adjust(self, amount=Decimal(0), denomination=""):

        credit = amount > 0

        return self.mock_posting_instruction(
            amount=abs(amount),
            credit=credit,
            denomination=denomination or self.default_denom,
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT,
            original_credit=True,  # inbound auth is always credit True
        )

    def outbound_auth_adjust(self, amount=Decimal(0), denomination=""):

        credit = not (amount > 0)

        return self.mock_posting_instruction(
            amount=abs(amount),
            credit=credit,
            denomination=denomination or self.default_denom,
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT,
            original_credit=False,  # outbound auth is always credit False
        )

    # TODO: add inbound/outbound settle methods to avoid errors with credit
    def settle(
        self,
        amount,
        final,
        denomination="",
        id=POSTING_ID,
        credit=False,
        instruction_details={},
        unsettled_amount=Decimal(0),
    ):

        return self.mock_posting_instruction(
            amount=amount,
            credit=credit,
            denomination=denomination or self.default_denom,
            id=id,
            instruction_details=instruction_details,
            final=final,
            type=PostingInstructionType.SETTLEMENT,
            unsettled_amount=unsettled_amount,
        )

    # TODO: add inbound/outbound release methods to avoid errors with credit
    def release(self, denomination="", unsettled_amount=Decimal(0), credit=False):

        return self.mock_posting_instruction(
            credit=credit,
            denomination=denomination or self.default_denom,
            unsettled_amount=unsettled_amount,
            type=PostingInstructionType.RELEASE,
        )

    # TODO: add inbound/outbound hard settlement methods to avoid errors with credit
    def hard_settlement(self, amount, denomination="", credit=False, advice=False):
        return self.mock_posting_instruction(
            amount=amount,
            credit=credit,
            advice=advice,
            denomination=denomination or self.default_denom,
            type=PostingInstructionType.HARD_SETTLEMENT,
        )

    # TODO: add inbound/outbound transfer methods to avoid errors with credit
    def transfer(self, amount, denomination="", credit=False):
        return self.mock_posting_instruction(
            amount=amount,
            credit=credit,
            denomination=denomination or self.default_denom,
            type=PostingInstructionType.TRANSFER,
        )

    def custom_instruction(
        self,
        amount,
        account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        client_transaction_id=None,
        credit=False,
        denomination="",
        value_timestamp=datetime(1970, 1, 1),
        phase=Phase.COMMITTED,
    ):

        return self.mock_posting_instruction(
            amount=amount,
            account_address=account_address,
            asset=asset,
            client_transaction_id=client_transaction_id,
            credit=credit,
            denomination=denomination or self.default_denom,
            phase=phase,
            type=PostingInstructionType.CUSTOM_INSTRUCTION,
            value_timestamp=value_timestamp,
        )

    def mock_posting_instruction_batch(self, posting_instructions=None, batch_details=None):

        posting_instructions = posting_instructions or []

        pib = PostingInstructionBatch(
            posting_instructions=posting_instructions or [],
            batch_details=batch_details or {},
        )

        # PIB balances are just merged posting instruction balances
        balances = BalanceDefaultDict(lambda: Balance(0, 0, 0))
        for posting_instruction in posting_instructions:
            for dimensions, value in posting_instruction.balances().items():
                balances[dimensions] = balance(
                    debit=balances[dimensions].debit + value.debit,
                    credit=balances[dimensions].credit + value.credit,
                    tside=self.tside,
                )

        pib.balances = Mock(return_value=balances)

        return pib

    @staticmethod
    def mock_client_transaction(
        postings=None,
        authorised=Decimal(0),
        released=Decimal(0),
        settled=Decimal(0),
        unsettled=Decimal(0),
    ):

        # TODO: this should be expanded to allow address, asset, denom to be specified
        effect = ClientTransactionEffects()
        effect.authorised = authorised
        effect.released = released
        effect.settled = settled
        effect.unsettled = unsettled
        client_transaction = ClientTransaction(postings or [])
        client_transaction.effects.return_value = defaultdict(lambda: effect)

        return client_transaction


def balance(
    net: Optional[Decimal] = None,
    debit: Optional[Decimal] = None,
    credit: Optional[Decimal] = None,
    tside: Tside = Tside.ASSET,
):
    """
    Given a net, or a dr/cr pair, return an equivalent Balance object
    :param net:
    :param debit:
    :param credit:
    :param tside:
    """
    if net is None:
        if tside == Tside.LIABILITY:
            net = Decimal(credit) - Decimal(debit)
        else:
            net = Decimal(debit) - Decimal(credit)
    else:
        net = Decimal(net)
        if tside == Tside.LIABILITY:
            if net >= 0 and tside == Tside.LIABILITY:
                credit = net
                debit = Decimal(0)
            else:
                credit = Decimal(0)
                debit = abs(net)
        else:
            if net >= 0:
                debit = net
                credit = Decimal(0)
            else:
                debit = Decimal(0)
                credit = abs(net)

    return Balance(credit=credit, debit=debit, net=net)


# TODO: we're assuming asset here, but should be able to feed this in
def init_balances(
    dt=DEFAULT_DATE - timedelta(days=1), balance_defs=None, contract_tside=Tside.ASSET
):
    """
    Creates a simple balance timeseries with a single date
    :param dt: the date for which the balances are initialised
    :param balance_defs: List(dict) the balances to define for this date. Each def is a dict with
    'address', 'denomination' 'phase' and 'asset' attributes for dimensions and 'net, 'dr', 'cr' and
    'crdr' for the balance. Dimensions default to their default value as per Postings/Contracts API.
    Rest is as per the `balance` helper
    :param contract_tside: The Tside to work with
    :return: List[datetime, defaultdict[Tuple(str, str, str, Phase), Balance]
    """
    balance_defs = balance_defs or []
    balance_dict = BalanceDefaultDict(
        lambda: Balance(Decimal(0), Decimal(0), Decimal(0)),
        {
            BalanceDimensions(
                address=balance_def.get("address", DEFAULT_ADDRESS).upper(),
                denomination=balance_def.get("denomination", DEFAULT_DENOM),
                phase=balance_def.get("phase", Phase.COMMITTED),
                asset=balance_def.get("asset", DEFAULT_ASSET),
            ): balance(
                net=balance_def.get("net"),
                debit=balance_def.get("dr"),
                credit=balance_def.get("cr"),
                tside=balance_def.get("tside", contract_tside),
            )
            for balance_def in balance_defs
        },
    )
    return TimeSeries([(dt, balance_dict)])


def make_internal_transfer_instructions_call(
    amount=ANY,
    from_account_id=ANY,
    from_account_address=ANY,
    to_account_id=ANY,
    to_account_address=ANY,
    asset=ANY,
    denomination=ANY,
    override_all_restrictions=ANY,
    client_transaction_id=ANY,
    instruction_details=ANY,
):

    return VaultCall(
        vault_method=VaultMethods.MAKE_INTERNAL_TRANSFER_INSTRUCTIONS,
        amount=Decimal(amount) if amount is not ANY else ANY,
        from_account_id=from_account_id,
        from_account_address=from_account_address,
        to_account_id=to_account_id,
        to_account_address=to_account_address,
        asset=asset,
        denomination=denomination,
        override_all_restrictions=override_all_restrictions,
        client_transaction_id=client_transaction_id,
        instruction_details=instruction_details,
    )


def amend_schedule_call(event_type=ANY, new_schedule=ANY):

    return VaultCall(
        vault_method=VaultMethods.AMEND_SCHEDULE,
        event_type=event_type,
        new_schedule=new_schedule,
    )


def update_event_type_call(event_type=ANY, schedule=ANY):

    return VaultCall(
        vault_method=VaultMethods.UPDATE_EVENT_TYPE,
        event_type=event_type,
        schedule=schedule,
    )


def remove_schedule_call(event_type=ANY):

    return VaultCall(vault_method=VaultMethods.REMOVE_SCHEDULE, event_type=event_type)


def start_workflow_call(workflow=ANY, context=ANY):

    return VaultCall(vault_method=VaultMethods.START_WORKFLOW, workflow=workflow, context=context)


def instruct_posting_batch_call(
    posting_instructions=ANY,
    batch_details=ANY,
    client_batch_id=ANY,
    effective_date=ANY,
    request_id=ANY,
):

    kwargs = dict()

    kwargs["posting_instructions"] = posting_instructions
    kwargs["effective_date"] = effective_date

    if batch_details is not ANY:
        kwargs["batch_details"] = batch_details
    if client_batch_id is not ANY:
        kwargs["client_batch_id"] = client_batch_id
    if request_id is not ANY:
        kwargs["request_id"] = request_id

    return VaultCall(vault_method=VaultMethods.INSTRUCT_POSTING_BATCH, **kwargs)


def compare_balances(balance_1: Balance, balance_2: Balance):
    """

    :param balance_1:
    :param balance_2:
    :return: True if all attributes of the two balances are equal
    """
    return (
        balance_1.credit == balance_2.credit
        and balance_1.debit == balance_2.debit
        and balance_1.net == balance_2.net
    )


# TODO: make this an explicit list of dt->object
class TimeSeries(list):
    def __init__(self, items, return_on_empty=None):
        super().__init__(items)
        self.return_on_empty = return_on_empty

    def at(self, timestamp, inclusive=True):
        for entry in reversed(self):
            if entry[0] <= timestamp:
                if inclusive or entry[0] < timestamp:
                    return entry[1]

        if self.return_on_empty is not None:
            return self.return_on_empty

        # TODO: fix this. Will need to rework all the tests that rely on this faulty behaviour
        # TODO(andrejs): uncommenting self[-1][1] makes tests work when offset is set to 0
        # raise ValueError('No value in timeseries')
        return self[-1][1]

    def before(self, timestamp):
        return self.at(timestamp, inclusive=False)

    def latest(self):
        if not self:
            if self.return_on_empty is not None:
                return self.return_on_empty
        return self[-1][1]

    def all(self):
        return [item for item in self]


class OptionalValue:
    def __init__(self, value, is_set=True):
        self.value = value
        self.is_set = Mock(return_value=is_set)


class VaultMethods(Enum):

    AMEND_SCHEDULE = "amend_schedule"
    INSTRUCT_POSTING_BATCH = "instruct_posting_batch"
    REMOVE_SCHEDULE = "remove_schedule"
    MAKE_INTERNAL_TRANSFER_INSTRUCTIONS = "make_internal_transfer_instructions"
    START_WORKFLOW = "start_workflow"
    UPDATE_EVENT_TYPE = "update_event_type"


class VaultCall(object):

    vault_method = ""
    call = None

    def __init__(self, vault_method: VaultMethods, *args, **kwargs):
        self.vault_method = vault_method
        self.call = call(*args, **kwargs)


# flake8: noqa: B008
