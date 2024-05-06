from decimal import Decimal
from functools import lru_cache

from . import enums
from .....utils import symbols
from .....utils import types_utils


class PostingInstruction:

    value_timestamp = NotImplementedError("Missing implementation")
    client_batch_id = NotImplementedError("Missing implementation")
    batch_details = NotImplementedError("Missing implementation")
    client_id = NotImplementedError("Missing implementation")
    batch_id = NotImplementedError("Missing implementation")

    def __init__(self, **kwargs):
        super().__setattr__("_from_proto", kwargs.pop("_from_proto", False))
        if not self._from_proto:
            expected = {
                "id": kwargs.get("id"),
                "type": kwargs.get("type"),
                "client_transaction_id": kwargs.get("client_transaction_id"),
                "instruction_details": kwargs.get("instruction_details"),
                "pics": kwargs.get("pics"),
                "custom_instruction_grouping_key": kwargs.get("custom_instruction_grouping_key"),
            }
            self._spec().assert_constructor_args(self._registry, expected)

            instruction_type = kwargs.get("type")
            instruction_params = [
                "account_id",
                "account_address",
                "amount",
                "asset",
                "credit",
                "denomination",
            ]
            if instruction_type == enums.PostingInstructionType.CUSTOM_INSTRUCTION:
                instruction_params.append("phase")
            elif instruction_type == enums.PostingInstructionType.SETTLEMENT:
                instruction_params.append("final")

            instruction_kwargs = {kw: kwargs.get(kw) for kw in instruction_params}
            self._spec().assert_constructor_args(self._registry, instruction_kwargs)

        _vault = kwargs.pop("_vault", None)
        if _vault:
            super().__setattr__("_vault", _vault)

        attrsetter = self.__setattr__
        for name, value in kwargs.items():
            attrsetter(name, value)

    def __setattr__(self, name, value):
        if not self._from_proto and name not in {"_batch_id", "balances"}:
            self._spec().assert_attribute_value(self._registry, name, value)
        super().__setattr__(name, value)

    def balances(self):
        raise NotImplementedError("Missing implementation")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostingInstruction",
            docstring=(
                "A PostingInstruction is an instruction sent to Vault to move some amount to/from "
                "an Account."
            ),
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=[
                    types_utils.ValueSpec(
                        name="account_address",
                        type="str",
                        docstring=(
                            "The account address whose balance is affected by this "
                            "PostingInstruction. Only populated if "
                            "type == PostingInstructionType.CUSTOM_INSTRUCTION."
                        ),
                    ),
                    types_utils.ValueSpec(
                        name="account_id",
                        type="str",
                        docstring=(
                            "The account id whose balance is affected by this PostingInstruction."
                        ),
                    ),
                    types_utils.ValueSpec(
                        name="amount",
                        type="Optional[Decimal]",
                        docstring="The amount moved by this PostingInstruction.",
                    ),
                    types_utils.ValueSpec(
                        name="asset",
                        type="str",
                        docstring="The asset the PostingInstruction is denominated in.",
                    ),
                    types_utils.ValueSpec(
                        name="credit",
                        type="bool",
                        docstring=(
                            "True if the PostingInstruction is crediting the account_id; "
                            "False otherwise."
                        ),
                    ),
                    types_utils.ValueSpec(
                        name="denomination",
                        type="str",
                        docstring="The denomination of the amount moved by the PostingInstruction.",
                    ),
                    types_utils.ValueSpec(
                        name="final",
                        type="bool",
                        docstring="""
                            Indicates that a settlement PostingInstruction is final.
                            Only present when type == PostingInstructionType.SETTLEMENT.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="phase",
                        type="Phase",
                        docstring="""
                            Indicates the "phase" (pending in, pending out, committed) of the amount
                            that this PostingInstruction is moving.
                            Only present when type == PostingInstructionType.CUSTOM_INSTRUCTION.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="id",
                        type="Optional[str]",
                        docstring="""
                            Uniquely identifies the posting instruction in vault.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="type",
                        type="PostingInstructionType",
                        docstring="The type of the PostingInstruction.",
                    ),
                    types_utils.ValueSpec(
                        name="client_transaction_id",
                        type="str",
                        docstring=(
                            "The id of the ClientTransaction that this PostingInstruction is a "
                            "part of. A PostingInstruction may be viewed as a change of state to a "
                            "ClientTransaction."
                        ),
                    ),
                    types_utils.ValueSpec(
                        name="instruction_details",
                        type="Optional[Dict[str, str]]",
                        docstring="An optional mapping containing instruction-level metadata.",
                    ),
                    types_utils.ValueSpec(
                        name="pics",
                        type="List[str]",
                        docstring="""
                            A list of Posting Identification Codes that may be consumed
                            by downstream services.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="custom_instruction_grouping_key",
                        type="str",
                        docstring=(
                            "Key used for grouping custom instructions together into one "
                            "instruction."
                        ),
                    ),
                ],
            ),
            public_methods=[
                types_utils.MethodSpec(
                    name="balances",
                    docstring="Returns the net balance changes caused by this PostingInstruction.",
                    args=[],
                    return_value=types_utils.ReturnValueSpec(
                        type="BalanceDefaultDict",
                        docstring=(
                            "The key is (account_address, asset, denomination, phase) and the "
                            "value is an object which contains the debit, credit and net balance "
                            "changes. If non-existing key is accessed, value with zero debit, "
                            "credit and net balance changes returned."
                        ),
                    ),
                )
            ],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_address",
                type="str",
                docstring="""
                    The account address whose balance is affected by this PostingInstruction.
                    Only populated if type == PostingInstructionType.CUSTOM_INSTRUCTION.
                """,
            ),
            types_utils.ValueSpec(
                name="account_id",
                type="str",
                docstring="The account id whose balance is affected by this PostingInstruction.",
            ),
            types_utils.ValueSpec(
                name="amount",
                type="Optional[Decimal]",
                docstring="The amount moved by this PostingInstruction.",
            ),
            types_utils.ValueSpec(
                name="asset",
                type="str",
                docstring="The asset the PostingInstruction is denominated in.",
            ),
            types_utils.ValueSpec(
                name="batch_details",
                type="Optional[Dict[str, str]]",
                docstring="An optional mapping containing batch-level metadata.",
            ),
            types_utils.ValueSpec(
                name="client_batch_id",
                type="str",
                docstring="""
                    An id which allows related PostingInstructions (e.g. interest accrual payments)
                    to be associated with each other.
                """,
            ),
            types_utils.ValueSpec(
                name="client_id",
                type="str",
                docstring="""
                    The id of the client that created the PostingInstruction.
                    All PostingInstructions created by contract execution have the
                    client_id set to %r
                """
                % symbols.POSTINGS_V3_KAFKA_CLIENT_ID,
            ),
            types_utils.ValueSpec(
                name="client_transaction_id",
                type="str",
                docstring="""
                    The id of the ClientTransaction that this PostingInstruction is a part of.
                    A PostingInstruction may be viewed as a change of state to a ClientTransaction.
                """,
            ),
            types_utils.ValueSpec(
                name="credit",
                type="bool",
                docstring=(
                    "True if the PostingInstruction is crediting the account_id; False otherwise."
                ),
            ),
            types_utils.ValueSpec(
                name="denomination",
                type="str",
                docstring="The denomination of the amount moved by the PostingInstruction.",
            ),
            types_utils.ValueSpec(
                name="final",
                type="bool",
                docstring="""
                    Indicates that a settlement PostingInstruction is final.
                    Only present when type == PostingInstructionType.SETTLEMENT.
                """,
            ),
            types_utils.ValueSpec(
                name="id",
                type="Optional[str]",
                docstring="""
                    Uniquely identifies the posting instruction in vault.
                """,
            ),
            types_utils.ValueSpec(
                name="instruction_details",
                type="Optional[Dict[str, str]]",
                docstring="An optional mapping containing instruction-level metadata.",
            ),
            types_utils.ValueSpec(
                name="phase",
                type="Phase",
                docstring="""
                    Indicates the "phase" (pending in, pending out, committed) of the amount
                    that this PostingInstruction is moving.
                    Only present when type == PostingInstructionType.CUSTOM_INSTRUCTION.
                """,
            ),
            types_utils.ValueSpec(
                name="pics",
                type="List[str]",
                docstring="""
                    A list of Posting Identification Codes that may be consumed
                    by downstream services.
                """,
            ),
            types_utils.ValueSpec(
                name="type",
                type="PostingInstructionType",
                docstring="The type of the PostingInstruction.",
            ),
            types_utils.ValueSpec(
                name="value_timestamp",
                type="datetime",
                docstring="The logical timestamp at which the PostingInstruction takes effect.",
            ),
            types_utils.ValueSpec(
                name="custom_instruction_grouping_key",
                type="str",
                docstring="Key used for grouping custom instructions Postings "
                "together into one PostingInstruction.",
            ),
            types_utils.ValueSpec(
                name="batch_id", type="Optional[str]", docstring="The id of the batch."
            ),
        ]


class PostingInstructionBatch(types_utils.TypedList("PostingInstruction")):
    def __init__(
        self,
        *,
        batch_details,
        client_batch_id,
        value_timestamp=None,
        batch_id=None,
        client_id=None,
        posting_instructions=(),
        _from_proto=False
    ):
        super().__init__(posting_instructions, _from_proto)
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "batch_details": batch_details,
                    "client_batch_id": client_batch_id,
                    "value_timestamp": value_timestamp,
                    "batch_id": batch_id,
                    "client_id": client_id,
                    "posting_instructions": posting_instructions,
                },
            )

        super().__setattr__("_from_proto", _from_proto)

        self.batch_id = batch_id
        self.batch_details = batch_details
        self.client_batch_id = client_batch_id
        self.value_timestamp = value_timestamp
        self.client_id = client_id or ""

    def __setattr__(self, name, value):
        if not self._from_proto and name != "balances":
            self._spec().assert_attribute_value(self._registry, name, value)
        super().__setattr__(name, value)

    def balances(self):
        raise NotImplementedError("Missing implementation")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostingInstructionBatch",
            docstring="""
                An atomic batch of PostingInstructions that will be (or have been) all accepted
                or all rejected. Returns a List[PostingInstruction].
            """,
            public_attributes=[
                types_utils.ValueSpec(
                    name="batch_details",
                    type="Dict[str, str]",
                    docstring="Dictionary containing batch-level metadata.",
                ),
                types_utils.ValueSpec(
                    name="client_batch_id",
                    type="str",
                    docstring="""
                        An id which allows related PostingInstructions (e.g. interest accrual
                        payments) to be associated with each other.
                    """,
                ),
                types_utils.ValueSpec(
                    name="value_timestamp",
                    type="Optional[datetime]",
                    docstring="The logical timestamp at which the batch takes effect.",
                ),
                types_utils.ValueSpec(
                    name="batch_id",
                    type="Optional[str]",
                    docstring="""
                        Uniquely identifies the PostingInstructionBatch in vault. This field will
                        only be non-None when the PostingInstructionBatch has come from a historic
                        timeseries.
                    """,
                ),
                types_utils.ValueSpec(
                    name="client_id",
                    type="str",
                    docstring="The id of the client that created the PostingInstruction.",
                ),
            ],
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=[
                    types_utils.ValueSpec(
                        name="batch_details",
                        type="Dict[str, str]",
                        docstring="Dictionary containing batch-level metadata.",
                    ),
                    types_utils.ValueSpec(
                        name="client_batch_id",
                        type="str",
                        docstring="""
                            An id which allows related PostingInstructions (e.g. interest accrual
                            payments) to be associated with each other.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="value_timestamp",
                        type="Optional[datetime]",
                        docstring="The logical timestamp at which the batch takes effect.",
                    ),
                    types_utils.ValueSpec(
                        name="batch_id",
                        type="Optional[str]",
                        docstring="""
                            Uniquely identifies the PostingInstructionBatch in vault. This field
                            will only be non-None when the PostingInstructionBatch has come from a
                            historic timeseries.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="client_id",
                        type="Optional[str]",
                        docstring="""
                            The id of the client that created the PostingInstruction.
                            This argument should not be specified by Smart Contracts creating
                            batches except in exceptional circumstances.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="posting_instructions",
                        type="Optional[List[PostingInstruction]]",
                        docstring="""
                            An optional list of PostingInstruction objects to populate
                            the batch with.
                        """,
                    ),
                ],
            ),
            public_methods=[
                types_utils.MethodSpec(
                    name="balances",
                    docstring=(
                        "Returns the net balance changes caused by this PostingInstructionBatch."
                    ),
                    args=[],
                    return_value=types_utils.ReturnValueSpec(
                        type="BalanceDefaultDict",
                        docstring="""
                            The key is (account_address, asset, denomination, phase) and the value
                            is an object which contains the debit, credit and net balance changes.
                            If non-existing key is accessed, value with zero debit, credit and net
                            balance changes returned.
                        """,
                    ),
                )
            ],
        )


class ClientTransaction(types_utils.TypedList("PostingInstruction")):
    @property
    def is_custom(self):
        return self[0].type == enums.PostingInstructionType.CUSTOM_INSTRUCTION

    @property
    def cancelled(self):
        return any(
            posting_instruction.type == enums.PostingInstructionType.RELEASE
            for posting_instruction in self
        )

    @property
    def start_time(self):
        return self[0].value_timestamp

    def effects(self, *, timestamp=None):
        raise NotImplementedError("Missing implementation")

    def balances(self, *, timestamp=None, instruction_id=None):
        raise NotImplementedError("Missing implementation")

    def __str__(self):
        return "ClientTransaction(%s instructions)" % len(self)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ClientTransaction",
            docstring="""
                A sequence of [PostingInstruction](#classes-PostingInstruction) objects with the
                same `client_transaction_id` field.

                This object represents the lifecycle of a single transaction. The lifecycle may be
                as trivial as a single "hard settlement" (immediate movement of funds), or contain
                any combination of authorisation, reauthorisation etc (see
                [PostingInstructionType](#enums-PostingInstructionType)).

                Each [PostingInstruction](#classes-PostingInstruction) in this sequence represents a
                change in state in the transaction's lifecycle.

                Although the object schema allows for
                [PostingInstruction](#classes-PostingInstruction) objects within the same
                [ClientTransaction](#classes-ClientTransaction) to have differing account_id, asset,
                and denomination fields, by convention they should all be the same, in which case
                the [PostingInstruction](#classes-PostingInstruction) only represents a change to
                the net amount and/or [Phase](#enums-Phase) of its parent transaction.
            """,
            public_attributes=[
                types_utils.ValueSpec(
                    name="is_custom",
                    type="bool",
                    docstring="""
                        The value will be True if and only if all PostingInstruction objects are of
                        type PostingInstructionType.CUSTOM_INSTRUCTION.
                    """,
                ),
                types_utils.ValueSpec(
                    name="cancelled",
                    type="bool",
                    docstring="""
                        This value will be True if and only if the ClientTransaction ends with
                        a PostingInstruction of type RELEASE.
                    """,
                ),
                types_utils.ValueSpec(
                    name="start_time",
                    type="datetime",
                    docstring="""
                        This value is a datetime whose value is equal to the value_timestamp of the
                        first PostingInstruction.
                    """,
                ),
            ],
            public_methods=[
                types_utils.MethodSpec(
                    name="effects",
                    docstring="""
                        Returns the net "state" of the ClientTransaction; identically, the net
                        "effects" that the ClientTransaction has had on the Account.
                    """,
                    args=[
                        types_utils.ValueSpec(
                            name="timestamp",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only PostingInstructions that happened before or on the
                                timestamp are included in the result.
                            """,
                        )
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="ClientTransactionEffectsDefaultDict",
                        docstring="""
                            Returns ClientTransactionEffectsDefaultDict - defaultdict where each
                            key is (account_address, asset, denomination) and each value is a
                            ClientTransactionEffects object.
                            If non-existing key is accessed, value with zero effects object will be
                            returned. Returns zero effects object for CustomInstruction as well.
                        """,
                    ),
                ),
                types_utils.MethodSpec(
                    name="balances",
                    docstring="Returns the net balance changes caused by this ClientTransaction.",
                    args=[
                        types_utils.ValueSpec(
                            name="timestamp",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only PostingInstructions that happened before or on the
                                timestamp are included in the result.
                            """,
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="BalanceDefaultDict",
                        docstring="""
                            The key is (account_address, asset, denomination, phase) and the value
                            is an object which contains the debit, credit and net balance changes.
                            If non-existing key is accessed, value with zero debit, credit and net
                            balance changes returned.
                        """,
                    ),
                ),
            ],
        )


class ClientTransactionEffects:
    def __init__(
        self,
        *,
        authorised=Decimal(0),
        released=Decimal(0),
        settled=Decimal(0),
        unsettled=Decimal(0),
        _from_proto=False
    ):
        super().__setattr__("_from_proto", _from_proto)
        kwargs = {
            "authorised": authorised,
            "released": released,
            "settled": settled,
            "unsettled": unsettled,
        }
        attrsetter = self.__setattr__
        for name, value in kwargs.items():
            attrsetter(name, value)

    def __setattr__(self, name, value):
        if not self._from_proto:
            self._spec().assert_attribute_value(self._registry, name, value)
        super().__setattr__(name, value)

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self.authorised == other.authorised
            and self.released == other.released
            and self.settled == other.settled
            and self.unsettled == other.unsettled
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ClientTransactionEffects",
            docstring="""
                The "effects" that a ClientTransaction has had on the balances of an Account,
                or the "current state" of the ClientTransaction.
                Note: This method is not implemented for CustomInstruction type -
                for ClientTransaction with CustomInstructions - `Decimal(0)`
                will be returned for each effects attribute.
            """,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="authorised",
                type="Decimal",
                docstring="The total amount that has been authorised. "
                "Note: value is updated on Adjustment instructions, "
                "however, is not updated on Settlement or Release instructions.",
            ),
            types_utils.ValueSpec(
                name="released",
                type="Decimal",
                docstring="The total amount that has been released. "
                "Note: this is also updated on final Settlement instructions,"
                "if not full amount that was authorised is being settled.",
            ),
            types_utils.ValueSpec(
                name="settled", type="Decimal", docstring="The total amount that has been settled."
            ),
            types_utils.ValueSpec(
                name="unsettled",
                type="Decimal",
                docstring="The total amount that has been authorised (including adjustments)"
                " but is yet to be released or settled.",
            ),
        ]


_effects_item_type = "Dict[Tuple[str, str, str], ClientTransactionEffects]"


class ClientTransactionEffectsDefaultDict(types_utils.TypedDefaultDict(_effects_item_type)):
    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="ClientTransactionEffectsDefaultDict",
            docstring="""
                The key is (address, asset, denomination) tuple and the value is a
                ClientTransactionEffects object.
                Returns defaultdict object,
                type - `Dict[Tuple[str, str, str], ClientTransactionEffects]`.
                If non-existing key is accessed, value with zero effects object will be
                returned. Returns zero effects object for CustomInstruction as well.
            """,
        )
