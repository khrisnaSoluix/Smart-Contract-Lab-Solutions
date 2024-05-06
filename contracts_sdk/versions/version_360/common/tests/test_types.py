import uuid
from datetime import datetime
from decimal import Decimal
from ..types import (
    Phase,
    Balance,
    BalanceDefaultDict,
    BalanceTimeseries,
    PostingInstruction,
    PostingInstructionBatch,
    ClientTransaction,
    defaultAddress,
    defaultAsset,
    HookDirectives,
    AddAccountNoteDirective,
    AmendScheduleDirective,
    RemoveSchedulesDirective,
    NoteType,
    WorkflowStartDirective,
    PostingInstructionBatchDirective,
    PostingInstructionType,
)
from ....version_350.common.tests.test_types import PublicCommonV350TypesTestCase
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .....utils import symbols


class PublicCommonV360TypesTestCase(PublicCommonV350TypesTestCase):
    TS_360 = datetime(year=2020, month=1, day=1)
    request_id_360 = str(uuid.uuid4())
    account_id_360 = "test_account_id"

    def test_balance_aggregation_add(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        aggregated_balance = balance_1 + balance_2
        self.assertEqual(30, aggregated_balance.credit)
        self.assertEqual(40, aggregated_balance.debit)
        self.assertEqual(-10, aggregated_balance.net)

    def test_balance_aggregation_iadd(self):
        aggregated_balance = Balance()
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        aggregated_balance += balance_1
        aggregated_balance += balance_2
        self.assertEqual(30, aggregated_balance.credit)
        self.assertEqual(40, aggregated_balance.debit)
        self.assertEqual(-10, aggregated_balance.net)

    def test_balance_dict_aggregation_add(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = (address, asset, denomination, Phase.COMMITTED)
        balance_key_out = (address, asset, denomination, Phase.PENDING_OUT)
        balance_key_in = (address, asset, denomination, Phase.PENDING_IN)

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict = balance_default_dict_1 + balance_default_dict_2

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_committed].net,
            aggregated_balance_default_dict[balance_key_committed].net,
        )

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_out].net,
            aggregated_balance_default_dict[balance_key_out].net,
        )

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_in].net,
            aggregated_balance_default_dict[balance_key_in].net,
        )

    def test_balance_dict_aggregation_iadd(self):
        aggregated_balance_default_dict = BalanceDefaultDict(lambda *_: Balance())
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = (address, asset, denomination, Phase.COMMITTED)
        balance_key_out = (address, asset, denomination, Phase.PENDING_OUT)
        balance_key_in = (address, asset, denomination, Phase.PENDING_IN)

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict += balance_default_dict_1
        aggregated_balance_default_dict += balance_default_dict_2

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertDictEqual(
            expected_aggregated_balance_default_dict, aggregated_balance_default_dict
        )

    def test_balance_aggregation_radd(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_3 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        aggregated_balance = sum([balance_1, balance_2, balance_3], Balance())
        self.assertEqual(
            Balance(credit=Decimal(60), debit=Decimal(60), net=Decimal(0)), aggregated_balance
        )

    def test_balance_dict_aggregation_radd(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = (address, asset, denomination, Phase.COMMITTED)
        balance_key_out = (address, asset, denomination, Phase.PENDING_OUT)
        balance_key_in = (address, asset, denomination, Phase.PENDING_IN)

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict = sum(
            [balance_default_dict_1, balance_default_dict_2],
            BalanceDefaultDict(lambda *_: Balance()),
        )

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertDictEqual(
            expected_aggregated_balance_default_dict, aggregated_balance_default_dict
        )

    def test_posting_instruction_batch_rejects_invalid_insertion_timestamp(self):
        with self.assertRaises(StrongTypingError):
            PostingInstructionBatch(
                batch_details={},
                client_batch_id="international-payment",
                insertion_timestamp="bananas",
                value_timestamp=self.TS_360,
                posting_instructions=[],
            )

    def test_balance_credit(self):
        balance = Balance(credit=Decimal(100))
        self.assertEqual(balance.credit, Decimal(100))
        self.assertEqual(balance.net, 0)
        self.assertEqual(balance.debit, 0)

    def test_balance_net(self):
        balance = Balance(net=Decimal(120))
        self.assertEqual(balance.credit, 0)
        self.assertEqual(balance.net, Decimal(120))
        self.assertEqual(balance.debit, 0)

    def test_balance_debit(self):
        balance = Balance(debit=Decimal(19.99))
        self.assertEqual(balance.credit, 0)
        self.assertEqual(balance.net, 0)
        self.assertEqual(balance.debit, Decimal(19.99))

    def test_balance_timeseries(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0), purchase),
                (datetime(2020, 1, 15, 12, 25, 0), refund),
            ]
        )
        self.assertEqual(balances.at(timestamp=datetime(2020, 1, 15, 11, 20, 0)), purchase)

    def test_balance_defaultdict_type_checking_on_init(self):
        key = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        with self.assertRaises(StrongTypingError):
            BalanceDefaultDict(mapping={key: "not_a_balance"})

    def test_balance_default_dict_default_factory_from_proto(self):
        balance_default_dict = BalanceDefaultDict(
            mapping={"wrong type": "not_a_balance"}, _from_proto=True
        )
        self.assertEqual(balance_default_dict["wrong type"], "not_a_balance")
        with self.assertRaises(StrongTypingError):
            balance_default_dict["another wrong type"]

    def test_balance_default_dict_default_factory_raises_when_using_wrong_type(self):
        balance_default_dict = BalanceDefaultDict()
        with self.assertRaises(StrongTypingError):
            balance_default_dict["wrong type"]

    def test_balance_default_dict_default_factory_happy_path(self):
        balance_default_dict = BalanceDefaultDict()
        valid_type_balance_key = (
            defaultAddress.fixed_value,
            defaultAsset.fixed_value,
            "GBP",
            Phase.PENDING_OUT,
        )
        self.assertEqual(balance_default_dict[valid_type_balance_key], Balance())

    def test_balance_defaultdict_bypass_type_checking_on_init(self):
        key = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        purchase = BalanceDefaultDict(mapping={key: "not_a_balance"}, _from_proto=True)
        self.assertEqual(purchase[key], "not_a_balance")

    def test_balance_timeseries_type_checking(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        not_a_balance = "not_a_balance"
        with self.assertRaises(StrongTypingError):
            BalanceTimeseries(
                [
                    (datetime(2020, 1, 15, 11, 19, 0), purchase),
                    (datetime(2020, 1, 15, 12, 25, 0), refund),
                    (datetime(2020, 1, 15, 12, 31, 0), not_a_balance),
                ]
            )

    def test_balance_timeseries_bypass_type_checking(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        not_a_balance = "not_a_balance"
        BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0), purchase),
                (datetime(2020, 1, 15, 12, 25, 0), refund),
                (datetime(2020, 1, 15, 12, 31, 0), not_a_balance),
            ],
            _from_proto=True,
        )

    def test_posting_instruction_types(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_missing_kwargs(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(id="101", account_id="1234512", amount=Decimal(10))

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        post_two = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="in",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id="1231234",
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_hook_directives(self):
        hook_directives = HookDirectives(
            add_account_note_directives=[
                AddAccountNoteDirective(
                    idempotency_key=self.request_id_360,
                    account_id=self.account_id_360,
                    body="some_body",
                    note_type=NoteType.RAW_TEXT,
                    date=self.TS_360,
                    is_visible_to_customer=True,
                )
            ],
            amend_schedule_directives=[
                AmendScheduleDirective(
                    event_type="event_type_1",
                    new_schedule={
                        "day": "1",
                        "hour": "23",
                        "year": "2020",
                    },
                    request_id=self.request_id_360,
                    account_id=self.account_id_360,
                )
            ],
            remove_schedules_directives=[
                RemoveSchedulesDirective(
                    account_id=self.account_id_360,
                    event_types=["event_type_1", "event_type_2"],
                    request_id=self.request_id_360,
                )
            ],
            workflow_start_directives=[
                WorkflowStartDirective(
                    workflow="test_workflow",
                    context={"key": "value"},
                    account_id=self.account_id_360,
                    idempotency_key=self.request_id_360,
                )
            ],
            posting_instruction_batch_directives=[
                PostingInstructionBatchDirective(
                    request_id=self.request_id_360,
                    posting_instruction_batch=PostingInstructionBatch(
                        batch_id="test",
                        batch_details={},
                        client_id="Visa",
                        client_batch_id="international-payment",
                        value_timestamp=self.TS_360,
                        posting_instructions=[
                            PostingInstruction(
                                custom_instruction_grouping_key="some_key",
                                client_transaction_id="the-main-payment-id",
                                pics=["INTERNATIONAL_PAYMENT"],
                                instruction_details={"TYPE": "PURCHASE"},
                                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                                credit=True,
                                amount=Decimal(10),
                                denomination="GBP",
                                account_id=self.account_id_360,
                                account_address=symbols.DEFAULT_ADDRESS,
                                asset=symbols.DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                    ),
                )
            ],
        )
        self.assertEqual(
            self.request_id_360, hook_directives.add_account_note_directives[0].idempotency_key
        )
        self.assertEqual(
            self.request_id_360, hook_directives.amend_schedule_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_360, hook_directives.remove_schedules_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_360, hook_directives.posting_instruction_batch_directives[0].request_id
        )
        self.assertEqual(
            self.request_id_360, hook_directives.workflow_start_directives[0].idempotency_key
        )

    def test_posting_instruction_advice_not_set(self):
        common_kwargs = {
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.CUSTOM_INSTRUCTION, phase=Phase.COMMITTED, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(
            type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

    def test_posting_instruction_advice_set(self):
        common_kwargs = {
            "advice": True,
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                phase=Phase.COMMITTED,
                **common_kwargs
            )

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_360,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
            override_all_restrictions=False,
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_360,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    pics=["INTERNATIONAL_PAYMENT"],
                    instruction_details={"TYPE": "PURCHASE"},
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    credit=True,
                    amount=Decimal(10),
                    denomination="GBP",
                    account_id=self.account_id_360,
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()

    def test_posting_instruction_batch_directive(self):
        posting_instr_batch = PostingInstructionBatch(
            batch_id="test",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_360,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    denomination="GBP",
                    account_id=self.account_id_360,
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    pics=["INTERNATIONAL_PAYMENT"],
                    account_address=symbols.DEFAULT_ADDRESS,
                    asset=symbols.DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                ),
            ],
        )
        posting_instruction_batch_directive = PostingInstructionBatchDirective(
            request_id=self.request_id_360,
            posting_instruction_batch=posting_instr_batch,
        )
        self.assertEqual(self.request_id_360, posting_instruction_batch_directive.request_id)

    def test_posting_instruction_advice_field(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_360,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                advice="test",
            )

    def test_posting_instruction_override_all_restrictions(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_360,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                override_all_restrictions="test",
            )
