from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Optional, List, Dict, Union
from zoneinfo import ZoneInfo

from . import enums
from .....utils import exceptions, symbols, types_utils
from ....version_400.common.types import (
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Phase,
    PostingInstructionType,
    Tside,
)
from .....utils.exceptions import (
    InvalidSmartContractError,
    InvalidPostingInstructionException,
    StrongTypingError,
)
from .....utils.posting_logic import (
    derive_balance_diff_from_committed_postings,
    SingleAccountClientTransaction,
)
from .....utils.timezone_utils import validate_timezone_is_utc


class Posting:
    def __init__(
        self,
        *,
        credit: bool,
        amount: Decimal,
        denomination: str,
        account_id: str,
        account_address: str,
        asset: str,
        phase: Phase,
        _from_proto: bool = False,
    ):
        self.denomination = denomination
        self.account_id = account_id
        self.account_address = account_address
        self.asset = asset
        self.credit = credit
        self.amount = amount
        self.phase = phase
        if not _from_proto:
            self._validate_attributes()

    def __eq__(self, other) -> bool:
        if type(self) is type(other):
            return self.__dict__ == other.__dict__
        return False

    def _validate_attributes(self):
        # As this is now used when instructing CustomInstruction directive ensure that all
        # validation previously existing in vault method exist.
        str_args = {
            "denomination": self.denomination,
            "account_id": self.account_id,
            "account_address": self.account_address,
            "asset": self.asset,
        }
        missing = [k for k, v in str_args.items() if not v]
        if missing:
            raise InvalidSmartContractError(f"Postings missing required argument(s): {missing}")
        if self.amount <= 0:
            raise InvalidSmartContractError(f"Amount must be greater than 0, {self.amount}")
        try:
            self.phase = Phase(self.phase)
        except ValueError:
            raise StrongTypingError("'phase' must be set to a Phase value")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Posting",
            docstring="""
                Posting ledger entry that represents a financial movement
                that resulted from each different posting instruction type intent.
            """,  # noqa E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new Posting",
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
                name="credit",
                type="bool",
                docstring="""
                    Represent the direction of the financial movement.
                """,
            ),
            types_utils.ValueSpec(
                name="amount",
                type="Decimal",
                docstring="""
                    Represent the value of the financial movement.
                """,
            ),
            types_utils.ValueSpec(
                name="denomination",
                type="str",
                docstring="""
                    The denomination of the Posting.
                """,
            ),
            types_utils.ValueSpec(
                name="account_id",
                type="str",
                docstring="""
                    An account_id that is targeted by the financial movement.
                """,
            ),
            types_utils.ValueSpec(
                name="account_address",
                type="str",
                docstring="""
                    An address of the account that is targeted by the financial movement.
                """,
            ),
            types_utils.ValueSpec(
                name="asset",
                type="str",
                docstring="""
                    Represent the asset type of the financial movement.
                """,
            ),
            types_utils.ValueSpec(
                name="phase",
                type="Phase",
                docstring="""
                    Represent the phase of the financial movement.
                """,
            ),
        ]


class TransactionCode:
    def __init__(
        self, *, domain: str, family: str, subfamily: str, _from_proto: Optional[bool] = False
    ):
        self.domain = domain
        self.family = family
        self.subfamily = subfamily
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        types_utils.validate_type(
            self.domain, str, check_empty=True, prefix="TransactionCode.domain"
        )
        types_utils.validate_type(
            self.family, str, check_empty=True, prefix="TransactionCode.family"
        )
        types_utils.validate_type(
            self.subfamily, str, check_empty=True, prefix="TransactionCode.subfamily"
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="TransactionCode",
            docstring="""
                ISO20022 Bank Transaction Code with information about payment domain, family and subfamily.
                For further information, see the [Postings API reference](/reference/postings_api/#key_components-what_is_a_posting_instruction).
            """,  # noqa E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new TransactionCode",
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
                name="domain",
                type="str",
                docstring="""
                    Business area of the transaction.
                """,
            ),
            types_utils.ValueSpec(
                name="family",
                type="str",
                docstring="""
                    A family within the domain.
                """,
            ),
            types_utils.ValueSpec(
                name="subfamily",
                type="str",
                docstring="""
                    Sub-product family within a specific family.
                """,
            ),
        ]


class PostingInstructionBase:
    # These 2 below class attributes are needed for type checking and they are overidden
    # with private types in private language version path
    _balance_class = Balance
    _balance_coordinate_class = BalanceCoordinate
    _balance_default_dict_class = BalanceDefaultDict
    # The below attributes are set on a class instance are either
    # output fields or other indirect attributes
    _insertion_datetime: Optional[datetime] = None
    _value_datetime: Optional[datetime] = None
    _client_batch_id: Optional[str] = None
    _batch_id: Optional[str] = None
    _committed_postings: Optional[List[Posting]] = None
    _instruction_id: Optional[str] = None
    _unique_client_transaction_id: Optional[str] = None
    _client_transaction_id: Optional[str] = None
    _own_account_id: Optional[str] = None
    _tside: Optional[Tside] = None
    # Appended to each class doc-string
    _class_docs_note = """
        To enable posting instruction methods that return indirect or output attributes
        to work in unit tests, you must set private posting instruction attributes when
        mocking vault data. Do this by calling `_set_output_attributes()` method on the
        posting instruction class instance; see example in the
        [Contracts SDK](/reference/contracts/development_and_testing/#contracts_sdk) section.
    """
    # Public attribute that returns the posting instruction type - set on each sub-class
    type: Optional[PostingInstructionType] = None

    def __init__(
        self,
        *,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        self.instruction_details = instruction_details or {}
        self.transaction_code = transaction_code
        self.override_all_restrictions = override_all_restrictions
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        types_utils.validate_type(
            self.transaction_code,
            TransactionCode,
            hint="TransactionCode",
            is_optional=True,
            prefix=f"{self.type.value}.transaction_code",
        )

        # Avoids iterable errors in the native_to_proto.
        types_utils.validate_type(
            self.instruction_details,
            dict,
            hint="Dict[str, str]",
            is_optional=True,
            prefix=f"{self.type.value}.instruction_details",
        )

    def __repr__(self):
        args = []
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                args.append(f"{key}={str(value)}")
        return f'{self.__class__.__name__}({", ".join(args)})'

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def _set_output_attributes(
        self,
        insertion_datetime: Optional[datetime] = None,
        value_datetime: Optional[datetime] = None,
        client_batch_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        committed_postings: Optional[List[Posting]] = None,
        instruction_id: Optional[str] = None,
        unique_client_transaction_id: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
        own_account_id: Optional[str] = None,
        tside: Optional[Tside] = None,
    ):
        """
        This method could be used in Contracts unit tests when mocking posting instruction
        data to set output attributes that are needed for `.balances()`, `.value_datetime()`
        and similar methods to work.
        Note that this method never needs to be called in the Contract code itself - just in
        unit tests when mocking posting instruction data.
        In the Contracts simulation and real Vault Contracts execution, all posting instruction
        objects that the Contract receives from Vault (via hook arguments or vault historical data
        methods) already have the output attributes set.
        """
        if insertion_datetime is not None:
            validate_timezone_is_utc(
                insertion_datetime,
                "insertion_datetime",
                self.type.value if self.type else "posting instruction",
            )
            self._insertion_datetime = insertion_datetime
        if value_datetime is not None:
            validate_timezone_is_utc(
                value_datetime,
                "value_datetime",
                self.type.value if self.type else "posting instruction",
            )
            self._value_datetime = value_datetime
        if client_batch_id is not None:
            self._client_batch_id = client_batch_id
        if batch_id is not None:
            self._batch_id = batch_id
        # Make sure the committed_postings are not reset to empty list for the
        # Smart Contract-instructed Custom Instructions that are sent to Supervisor Contracts
        if committed_postings is not None and not self._committed_postings:
            self._committed_postings = committed_postings
        if instruction_id is not None:
            self._instruction_id = instruction_id
        if unique_client_transaction_id is not None:
            self._unique_client_transaction_id = unique_client_transaction_id
        if client_transaction_id is not None:
            self._client_transaction_id = client_transaction_id
        if own_account_id is not None:
            self._own_account_id = own_account_id
        if tside is not None:
            self._tside = tside

    @property
    def id(self) -> Optional[str]:
        # Could be None for the proposed PIs
        return self._instruction_id

    @property
    def batch_id(self) -> Optional[str]:
        return self._batch_id

    @property
    def client_batch_id(self) -> Optional[str]:
        return self._client_batch_id

    @property
    def unique_client_transaction_id(self) -> Optional[str]:
        return self._unique_client_transaction_id

    @property
    def insertion_datetime(self) -> Optional[datetime]:
        # Could be None for the proposed PIs
        return self._insertion_datetime

    @property
    def value_datetime(self) -> Optional[datetime]:
        return self._value_datetime

    def balances(
        self,
        account_id: Optional[str] = None,
        tside: Optional[Tside] = None,
    ) -> BalanceDefaultDict:

        account_id = account_id or self._own_account_id
        tside = tside or self._tside
        if not account_id:
            raise InvalidSmartContractError(
                "An account_id must be specified for the balances calculation."
            )
        if self._committed_postings is None:
            instruction_type = self.type.value if self.type else "posting instruction"
            raise InvalidSmartContractError(
                f"The {instruction_type} posting instruction type does not support the balances "
                f"method for the non-historical data as committed_postings are not available."
            )
        if not tside:
            raise InvalidSmartContractError(
                "A tside must be specified for the balances calculation."
            )

        committed_postings_in_account_id = []
        for committed_postings in self._committed_postings:
            if committed_postings.account_id == account_id:
                committed_postings_in_account_id.append(committed_postings)

        balance_diffs = derive_balance_diff_from_committed_postings(
            committed_postings_in_account_id  # type: ignore
        )

        def _transform_balance_to_versioned_balance(balance_value):
            result = self._balance_class()
            result._adjust(  # noqa: SLF001
                credit=balance_value.credit,
                debit=balance_value.debit,
                tside=tside,
            )
            return result

        def _transform_balance_key(balance_key):
            return self._balance_coordinate_class(
                account_address=balance_key.account_address,
                asset=balance_key.asset,
                denomination=balance_key.denomination,
                phase=balance_key.phase,
            )

        balances = self._balance_default_dict_class(
            # defaults to 0 net, credit and debit
            lambda *_: self._balance_class(),  # type: ignore
            {
                _transform_balance_key(balance_key): _transform_balance_to_versioned_balance(
                    balance_value
                )
                for balance_key, balance_value in balance_diffs.items()
            },
        )

        return balances

    @classmethod
    def _public_methods(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.MethodSpec(
                name="balances",
                docstring="""
                        Returns the net balance changes caused by this posting instruction.
                    """,
                args=[
                    types_utils.ValueSpec(
                        name="account_id",
                        type="Optional[str]",
                        docstring=(
                            "The ID of an account for which the balance changes should be returned"
                            ". Does not need to be provided for historical posting instructions "
                            "returned via vault methods or the new posting instructions that hook "
                            "receives via arguments in `pre_posting_hook` and `post_posting_hook`. "
                            "In these cases, it defaults to the `account_id` of the Smart Contract "
                            "or the ID of the supervisee account in Supervisor Contract. "
                            "Only required to be passed for the balances method on the new posting "
                            "instruction objects instantiated by the Smart Contract (directives), "
                            "as these might contain instructions for multiple accounts. This "
                            "also applies for the balances of the posting instruction directives "
                            "accessible in a Supervisor Contract via `get_hook_result` vault "
                            "method."
                        ),
                    ),
                    types_utils.ValueSpec(
                        name="tside",
                        type="Optional[Tside]",
                        docstring=(
                            "The Tside of an account which is used in calculation of balances net"
                            ". Does not need to be provided for historical posting instructions "
                            "returned via vault methods or the new posting instructions that hook "
                            "receives via arguments in `pre_posting_hook` and `post_posting_hook`. "
                            "In these cases, it defaults to the `tside` of the Smart Contract "
                            "or the tside of the supervisee account in Supervisor Contract. "
                            "Only required to be passed for the balances method on the new posting "
                            "instruction objects instantiated by the Smart Contract (directives), "
                            "as these might contain instructions for multiple accounts. "
                            "Note that the tside is not required to be provided for balances of "
                            "the posting instruction directives accessible in a Supervisor "
                            "Contract via `get_hook_result` vault method and defaults to the tside "
                            "of the supervisee account."
                        ),
                    ),
                ],
                return_value=types_utils.ReturnValueSpec(
                    type="BalanceDefaultDict",
                    docstring="""
                        The default balance dictionary where the key is the
                        [BalanceCoordinate](#classes-BalanceCoordinate) and the value is
                        a [Balance](#classes-Balance) object which contains the debit,
                        credit and net balance changes. If a non-existing key is accessed,
                        an object with zero debit, credit and net balance changes is returned.
                    """,
                ),
            ),
        ]

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="instruction_details",
                type="Optional[Dict[str, str]]",
                docstring="An optional mapping containing instruction-level metadata.",
            ),
            types_utils.ValueSpec(
                name="transaction_code",
                type="Optional[TransactionCode]",
                docstring="""
                    ISO20022 Bank Transaction Code field; a set of properties to identify the
                    underlying transaction.
                """,
            ),
            types_utils.ValueSpec(
                name="override_all_restrictions",
                type="bool",
                docstring="""
                    Specifies whether to ignore all restrictions.
                """,
            ),
        ]

    @classmethod
    def _output_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="type",
                type="PostingInstructionType",
                docstring="The posting instruction type, such as CustomInstruction or Transfer.",
            ),
            types_utils.ValueSpec(
                name="id",
                type="Optional[str]",
                docstring="""
                    Uniquely identifies the posting instruction in vault.
                """,
            ),
            types_utils.ValueSpec(
                name="client_batch_id",
                type="str",
                docstring="""
                    An id which allows related posting instructions
                    (for example, interest accrual payments)
                    to be associated with each other.
                """,
            ),
            types_utils.ValueSpec(
                name="unique_client_transaction_id",
                type="str",
                docstring="""
                    The globally unique id of the ClientTransaction that this posting
                    instruction is a part of. This value is not deterministic and therefore is
                    not guaranteed to be consistent between different contract executions for
                    the same ClientTransaction.
                    A posting instruction may be viewed as a change of state to a ClientTransaction.
                    Note: This value will be used as a key in the map returned in the
                    [get_client_transactions](/reference/contracts/apis_4XX/smart_contracts_api_reference4XX/vault/#methods-get_client_transactions)
                    Vault method.
                """,
            ),
            types_utils.ValueSpec(
                name="insertion_datetime",
                type="Optional[datetime]",
                docstring="""
                    The datetime indicating when the posting instruction was inserted
                    into the posting ledger.
                """,
            ),
            types_utils.ValueSpec(
                name="value_datetime",
                type="Optional[datetime]",
                docstring="""
                    The logical datetime at which the posting instruction takes effect.
                """,
            ),
            types_utils.ValueSpec(
                name="batch_id",
                type="Optional[str]",
                docstring="""
                    The id of the batch of posting instructions which get atomically
                    inserted into the ledger.
                """,
            ),
        ]

    @classmethod
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        public_attributes = cls._constructor_args(language_code=language_code)
        public_attributes.extend(cls._output_attributes(language_code=language_code))
        return public_attributes


class Authorisation(PostingInstructionBase):
    def __init__(
        self,
        *,
        client_transaction_id: str,
        amount: Decimal,
        denomination: str,
        target_account_id: str,
        internal_account_id: str,
        advice: Optional[bool] = False,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.client_transaction_id = client_transaction_id
        self.amount = amount
        self.denomination = denomination
        self.target_account_id = target_account_id
        self.internal_account_id = internal_account_id
        self.advice = advice
        # The init of the base Authorisation class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="client_transaction_id",
                    type="str",
                    docstring="""
                    The id of the ClientTransaction that this posting instruction is a
                    part of. A posting instruction may be viewed as a change of state to a
                    ClientTransaction.
                """,
                ),
                types_utils.ValueSpec(
                    name="amount",
                    type="Decimal",
                    docstring="The amount moved by this posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="The denomination of the amount moved by the posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="target_account_id",
                    type="str",
                    docstring="""
                        The account id whose balance is affected by this posting instruction.
                    """,
                ),
                types_utils.ValueSpec(
                    name="internal_account_id",
                    type="str",
                    docstring="An internal Vault account ID",
                ),
                types_utils.ValueSpec(
                    name="advice",
                    type="Optional[bool]",
                    docstring="""
                    This indicates that the Smart Contract should skip
                    balance checks for this posting instruction. For the advice flag to be
                    set in the posting instruction object, it must be supported in the
                    specific type posting instruction object in the Core API. This
                    defaults to false if supported by the PostingInstructionType but not
                    supplied.
                """,
                ),
            ]
        )
        return constructor_args


class OutboundAuthorisation(Authorisation):
    type = PostingInstructionType.OUTBOUND_AUTHORISATION

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        public_methods = super()._public_methods(language_code)
        class_docstring = (
            """
            An OutboundAuthorisation is a chainable posting instruction that creates an
            outgoing funds hold (ring-fence the funds) on the target account.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="OutboundAuthorisation",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new OutboundAuthorisation",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )


class InboundAuthorisation(Authorisation):
    type = PostingInstructionType.INBOUND_AUTHORISATION

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        public_methods = super()._public_methods(language_code)
        class_docstring = (
            """
            An InboundAuthorisation is a chainable posting instruction that authorises
            incoming funds into the target account.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="InboundAuthorisation",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new InboundAuthorisation",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )


class CustomInstruction(PostingInstructionBase):
    type = PostingInstructionType.CUSTOM_INSTRUCTION

    def __init__(
        self,
        *,
        postings: List[Posting],
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.postings = postings
        # This allows in-flight balances to work for new new CustomInstruction directives
        # that are not yet committed.
        self._set_output_attributes(committed_postings=postings)
        # The init of the base CustomInstruction class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    def _validate_attributes(self):
        super()._validate_attributes()
        type_hint = "Posting"
        iterator = types_utils.get_iterator(
            self.postings, type_hint, name="postings", check_empty=True
        )
        for posting in iterator:
            types_utils.validate_type(posting, Posting, hint=f"List[{type_hint}]")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        public_methods = super()._public_methods(language_code)
        class_docstring = (
            """
            CustomInstruction is a non-chainable posting instruction that specifies a
            list of credits and debits to be written to the ledger.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="CustomInstruction",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new CustomInstruction",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )

    def _validate_postings_and_zero_net_sum(self):
        if len(self.postings) > 64:
            raise InvalidSmartContractError(
                f"Too many postings submitted in the {self.type.value}. "
                f"Number submitted: {len(self.postings)}. Limit: 64.",
            )

        balance_dict = {}
        for p in self.postings:
            balance_key = tuple([p.asset, p.denomination, p.phase])
            if balance_key not in balance_dict.keys():
                balance_dict[balance_key] = {"credit": 0, "debit": 0}
            if p.credit:
                balance_dict[balance_key]["credit"] += p.amount
            else:
                balance_dict[balance_key]["debit"] += p.amount

        for balance_key, balance_value in balance_dict.items():
            if balance_value["credit"] != balance_value["debit"]:
                net_sum = abs(balance_value["credit"] - balance_value["debit"])
                raise InvalidSmartContractError(
                    f"Net of balance coordinate {balance_key} in the "
                    f"CustomInstruction: {net_sum}, Expected: 0.",
                )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="postings",
                    type="List[Posting]",
                    docstring="""
                        A list of Postings (credits and debits).
                    """,
                ),
            ]
        )
        return constructor_args


class AdjustmentAmount:
    def __init__(
        self,
        amount: Optional[Decimal] = None,
        replacement_amount: Optional[Decimal] = None,
        _from_proto: bool = False,
    ):
        self.amount = amount
        self.replacement_amount = replacement_amount
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if (self.amount is None and self.replacement_amount is None) or (
            self.amount and self.replacement_amount
        ):
            raise InvalidSmartContractError(
                "Either amount or replacement amount argument must be set, not both."
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="AdjustmentAmount",
            docstring="""
                Used in the AuthorisationAdjustment posting instructions to adjust an
                authorised amount of a ClientTransaction.
            """,  # noqa E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new AdjustmentAmount",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="amount",
                type="Optional[Decimal]",
                docstring="""
                    Signed delta amount.
                """,
            ),
            types_utils.ValueSpec(
                name="replacement_amount",
                type="Optional[Decimal]",
                docstring="""
                    A new amount to replace an existing authorised amount.
                """,
            ),
        ]


class AuthorisationAdjustment(PostingInstructionBase):
    _authorised_amount: Optional[Decimal] = None
    _delta_amount: Optional[Decimal] = None
    _denomination: Optional[str] = None
    _target_account_id: Optional[str] = None
    _internal_account_id: Optional[str] = None
    type = PostingInstructionType.AUTHORISATION_ADJUSTMENT

    def __init__(
        self,
        *,
        client_transaction_id: str,
        adjustment_amount: AdjustmentAmount,
        advice: Optional[bool] = False,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.client_transaction_id = client_transaction_id
        self.adjustment_amount = adjustment_amount
        self.advice = advice
        # The init of the base AuthorisationAdjustment class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    def _validate_attributes(self):
        super()._validate_attributes()
        if self.adjustment_amount is None:
            raise exceptions.StrongTypingError(
                f"{self.type.value} 'adjustment_amount' must be populated",
            )

        types_utils.validate_type(
            self.adjustment_amount,
            AdjustmentAmount,
            hint="AdjustmentAmount",
            prefix="AuthorisationAdjustment.adjustment_amount",
        )

    def _set_output_attributes(
        self,
        insertion_datetime: Optional[datetime] = None,
        value_datetime: Optional[datetime] = None,
        client_batch_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        committed_postings: Optional[List[Posting]] = None,
        instruction_id: Optional[str] = None,
        unique_client_transaction_id: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
        own_account_id: Optional[str] = None,
        tside: Optional[Tside] = None,
        # Additional class attributes
        authorised_amount: Optional[Decimal] = None,
        delta_amount: Optional[Decimal] = None,
        denomination: Optional[str] = None,
        target_account_id: Optional[str] = None,
        internal_account_id: Optional[str] = None,
    ):
        """
        This method could be used in Contracts unit tests when mocking posting instruction
        data to set output attributes that are needed for `.balances()`, `.value_datetime`
        and similar methods to work.
        Note that this method never needs to be called in the Contract code itself - just in
        unit tests when mocking posting instruction data.
        In the Contracts simulation and real Vault Contracts execution, all posting instruction
        objects that the Contract receives from Vault (via hook arguments or vault historical data
        methods) already have the output attributes set.
        """
        super()._set_output_attributes(
            insertion_datetime=insertion_datetime,
            value_datetime=value_datetime,
            client_batch_id=client_batch_id,
            batch_id=batch_id,
            committed_postings=committed_postings,
            instruction_id=instruction_id,
            unique_client_transaction_id=unique_client_transaction_id,
            client_transaction_id=client_transaction_id,
            own_account_id=own_account_id,
            tside=tside,
        )
        if authorised_amount is not None:
            self._authorised_amount = authorised_amount
        if delta_amount is not None:
            self._delta_amount = delta_amount
        if denomination is not None:
            self._denomination = denomination
        if target_account_id is not None:
            self._target_account_id = target_account_id
        if internal_account_id is not None:
            self._internal_account_id = internal_account_id

    @property
    def authorised_amount(self) -> Optional[Decimal]:
        return self._authorised_amount

    @property
    def delta_amount(self) -> Optional[Decimal]:
        return self._delta_amount

    @property
    def denomination(self) -> Optional[str]:
        return self._denomination

    @property
    def target_account_id(self) -> Optional[str]:
        return self._target_account_id

    @property
    def internal_account_id(self) -> Optional[str]:
        return self._internal_account_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            AuthorisationAdjustment is a chainable posting instruction that can be
            used to change the amount that is ring-fenced by a ClientTransaction.
            The ClientTransaction being adjusted is identified by the
            client_transaction_id attribute.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="AuthorisationAdjustment",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new AuthorisationAdjustment",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=cls._public_methods(language_code=language_code),
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="client_transaction_id",
                    type="str",
                    docstring="""
                    The id of the ClientTransaction that this posting instruction is a
                    part of. A posting instruction may be viewed as a change of state to a
                    ClientTransaction.
                """,
                ),
                types_utils.ValueSpec(
                    name="adjustment_amount",
                    type="AdjustmentAmount",
                    docstring="""
                    The amount of the AuthorisationAdjustment, which can be specified as a delta
                    (the difference between previous amount and the new amount) or as a new
                    total authorised amount.
                """,
                ),
                types_utils.ValueSpec(
                    name="advice",
                    type="Optional[bool]",
                    docstring="""
                    This indicates that the Smart Contract should skip
                    balance checks for this posting instruction. For the advice flag to be
                    set in the posting instruction object, it must be supported in the
                    specific type posting instruction object in the Core API. This
                    defaults to false if supported by the PostingInstructionType but not
                    supplied.
                """,
                ),
            ]
        )
        return constructor_args

    @classmethod
    def _output_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        output_attributes = super()._output_attributes(language_code=language_code)
        output_attributes.extend(
            [
                types_utils.ValueSpec(
                    name="authorised_amount",
                    type="Decimal",
                    docstring="""
                        The total amount authorised for this ClientTransaction after
                        this instruction has been accepted. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="delta_amount",
                    type="Decimal",
                    docstring="""
                        The change that this accepted instruction has made to the amount authorised
                        for this ClientTransaction. Note that this is an output only information,
                        which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="""
                        The instruction denomination. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="target_account_id",
                    type="str",
                    docstring="""
                        The instruction target_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="internal_account_id",
                    type="str",
                    docstring="""
                        The instruction internal_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
            ]
        )
        return output_attributes


class Settlement(PostingInstructionBase):
    _denomination: Optional[str] = None
    _target_account_id: Optional[str] = None
    _internal_account_id: Optional[str] = None
    type = PostingInstructionType.SETTLEMENT

    def __init__(
        self,
        *,
        client_transaction_id: str,
        amount: Optional[Decimal] = None,
        final: Optional[bool] = False,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.client_transaction_id = client_transaction_id
        self.amount = amount
        self.final = final
        # The init of the base Settlement class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    def _set_output_attributes(
        self,
        insertion_datetime: Optional[datetime] = None,
        value_datetime: Optional[datetime] = None,
        client_batch_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        committed_postings: Optional[List[Posting]] = None,
        instruction_id: Optional[str] = None,
        unique_client_transaction_id: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
        own_account_id: Optional[str] = None,
        tside: Optional[Tside] = None,
        # Additional class attributes
        denomination: Optional[str] = None,
        target_account_id: Optional[str] = None,
        internal_account_id: Optional[str] = None,
    ):
        """
        This method could be used in Contracts unit tests when mocking posting instruction
        data to set output attributes that are needed for `.balances()`, `.value_datetime`
        and similar methods to work.
        Note that this method never needs to be called in the Contract code itself - just in
        unit tests when mocking posting instruction data.
        In the Contracts simulation and real Vault Contracts execution, all posting instruction
        objects that the Contract receives from Vault (via hook arguments or vault historical data
        methods) already have the output attributes set.
        """
        super()._set_output_attributes(
            insertion_datetime=insertion_datetime,
            value_datetime=value_datetime,
            client_batch_id=client_batch_id,
            batch_id=batch_id,
            committed_postings=committed_postings,
            instruction_id=instruction_id,
            unique_client_transaction_id=unique_client_transaction_id,
            client_transaction_id=client_transaction_id,
            own_account_id=own_account_id,
            tside=tside,
        )
        if denomination is not None:
            self._denomination = denomination
        if target_account_id is not None:
            self._target_account_id = target_account_id
        if internal_account_id is not None:
            self._internal_account_id = internal_account_id

    @property
    def denomination(self) -> Optional[str]:
        return self._denomination

    @property
    def target_account_id(self) -> Optional[str]:
        return self._target_account_id

    @property
    def internal_account_id(self) -> Optional[str]:
        return self._internal_account_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            Settlement is a chainable posting instruction that clears funds that
            have been previously authorised in a ClientTransaction.
            The ClientTransaction being cleared is identified by the
            client_transaction_id attribute.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="Settlement",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new Settlement",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=cls._public_methods(language_code=language_code),
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="client_transaction_id",
                    type="str",
                    docstring="""
                    The id of the ClientTransaction that this posting instruction is a
                    part of. A posting instruction may be viewed as a change of state to a
                    ClientTransaction.
                """,
                ),
                types_utils.ValueSpec(
                    name="amount",
                    type="Optional[Decimal]",
                    docstring="""
                    The amount to be cleared for a ClientTransaction. Defaults to the total
                    amount authorised for the ClientTransaction.
                """,
                ),
                types_utils.ValueSpec(
                    name="final",
                    type="Optional[bool]",
                    docstring="""
                    If set to true, any remaining amount authorised for the ClientTransaction
                    will be released. No posting instructions may mutate the ClientTransaction
                    once a final Settlement has been accepted.
                """,
                ),
            ]
        )
        return constructor_args

    @classmethod
    def _output_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        output_attributes = super()._output_attributes(language_code=language_code)
        output_attributes.extend(
            [
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="""
                        The instruction denomination. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="target_account_id",
                    type="str",
                    docstring="""
                        The instruction target_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="internal_account_id",
                    type="str",
                    docstring="""
                        The instruction internal_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
            ]
        )
        return output_attributes


class Release(PostingInstructionBase):
    _amount: Optional[Decimal] = None
    _denomination: Optional[str] = None
    _target_account_id: Optional[str] = None
    _internal_account_id: Optional[str] = None
    type = PostingInstructionType.RELEASE

    def __init__(
        self,
        *,
        client_transaction_id: str,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.client_transaction_id = client_transaction_id
        # The init of the base Release class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    def _set_output_attributes(
        self,
        insertion_datetime: Optional[datetime] = None,
        value_datetime: Optional[datetime] = None,
        client_batch_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        committed_postings: Optional[List[Posting]] = None,
        instruction_id: Optional[str] = None,
        unique_client_transaction_id: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
        own_account_id: Optional[str] = None,
        tside: Optional[Tside] = None,
        # Additional class attributes
        amount: Optional[Decimal] = None,
        denomination: Optional[str] = None,
        target_account_id: Optional[str] = None,
        internal_account_id: Optional[str] = None,
    ):
        """
        This method could be used in Contracts unit tests when mocking posting instruction
        data to set output attributes that are needed for `.balances()`, `.value_datetime`
        and similar methods to work.
        Note that this method never needs to be called in the Contract code itself - just in
        unit tests when mocking posting instruction data.
        In the Contracts simulation and real Vault Contracts execution, all posting instruction
        objects that the Contract receives from Vault (via hook arguments or vault historical data
        methods) already have the output attributes set.
        """
        super()._set_output_attributes(
            insertion_datetime=insertion_datetime,
            value_datetime=value_datetime,
            client_batch_id=client_batch_id,
            batch_id=batch_id,
            committed_postings=committed_postings,
            instruction_id=instruction_id,
            unique_client_transaction_id=unique_client_transaction_id,
            client_transaction_id=client_transaction_id,
            own_account_id=own_account_id,
            tside=tside,
        )
        if amount is not None:
            self._amount = amount
        if denomination is not None:
            self._denomination = denomination
        if target_account_id is not None:
            self._target_account_id = target_account_id
        if internal_account_id is not None:
            self._internal_account_id = internal_account_id

    @property
    def amount(self) -> Optional[Decimal]:
        return self._amount

    @property
    def denomination(self) -> Optional[str]:
        return self._denomination

    @property
    def target_account_id(self) -> Optional[str]:
        return self._target_account_id

    @property
    def internal_account_id(self) -> Optional[str]:
        return self._internal_account_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            Release is a chainable posting instruction that removes an authorisation hold
            from a ClientTransaction.
            The ClientTransaction being released is identified by the
            client_transaction_id attribute.
        """
            + cls._class_docs_note
        )
        return types_utils.ClassSpec(
            name="Release",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new Release",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=cls._public_methods(language_code=language_code),
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="client_transaction_id",
                    type="str",
                    docstring="""
                    The id of the ClientTransaction that this posting instruction is a
                    part of. A posting instruction may be viewed as a change of state to a
                    ClientTransaction.
                """,
                ),
            ]
        )
        return constructor_args

    @classmethod
    def _output_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        output_attributes = super()._output_attributes(language_code=language_code)
        output_attributes.extend(
            [
                types_utils.ValueSpec(
                    name="amount",
                    type="Decimal",
                    docstring="""
                        The amount released. Note that this is an output only information, which is
                        calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="""
                        The instruction denomination. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="target_account_id",
                    type="str",
                    docstring="""
                        The instruction target_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
                types_utils.ValueSpec(
                    name="internal_account_id",
                    type="str",
                    docstring="""
                        The instruction internal_account_id. Note that this is an output only
                        information, which is calculated by the ledger.
                    """,
                ),
            ]
        )
        return output_attributes


class HardSettlement(PostingInstructionBase):
    def __init__(
        self,
        *,
        amount: Decimal,
        denomination: str,
        target_account_id: str,
        internal_account_id: str,
        advice: Optional[bool] = False,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.amount = amount
        self.denomination = denomination
        self.target_account_id = target_account_id
        self.internal_account_id = internal_account_id
        self.advice = advice
        # The init of the base HardSettlement class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="amount",
                    type="Decimal",
                    docstring="The amount moved by this posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="The denomination of the amount moved by the posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="target_account_id",
                    type="str",
                    docstring="""
                        The account id whose balance is affected by this posting instruction.
                    """,
                ),
                types_utils.ValueSpec(
                    name="internal_account_id",
                    type="str",
                    docstring="An internal Vault account ID",
                ),
                types_utils.ValueSpec(
                    name="advice",
                    type="Optional[bool]",
                    docstring="""
                    This indicates that the Smart Contract should skip
                    balance checks for this posting instruction. For the advice flag to be
                    set in the posting instruction object, it must be supported in the
                    specific type posting instruction object in the Core API. This
                    defaults to false if supported by the PostingInstructionType but not
                    supplied.
                """,
                ),
            ]
        )
        return constructor_args


class OutboundHardSettlement(HardSettlement):
    type = PostingInstructionType.OUTBOUND_HARD_SETTLEMENT

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            An OutboundHardSettlement is a non-chainable posting instruction that authorises
            and settles outgoing funds from a target account.
        """
            + cls._class_docs_note
        )
        public_methods = super()._public_methods(language_code)
        return types_utils.ClassSpec(
            name="OutboundHardSettlement",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new OutboundHardSettlement",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )


class InboundHardSettlement(HardSettlement):
    type = PostingInstructionType.INBOUND_HARD_SETTLEMENT

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            An InboundHardSettlement is a non-chainable posting instruction that authorises
            and settles incoming funds into a target account.
        """
            + cls._class_docs_note
        )
        public_methods = super()._public_methods(language_code)
        return types_utils.ClassSpec(
            name="InboundHardSettlement",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new InboundHardSettlement",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )


class Transfer(PostingInstructionBase):
    type = PostingInstructionType.TRANSFER

    def __init__(
        self,
        *,
        amount: Decimal,
        denomination: str,
        debtor_target_account_id: str,
        creditor_target_account_id: str,
        instruction_details: Optional[Dict[str, str]] = None,
        transaction_code: Optional[TransactionCode] = None,
        override_all_restrictions: Optional[bool] = False,
        _from_proto: bool = False,
    ):
        # Subclass only attributes settable on the particular PostingInstructionType only
        self.amount = amount
        self.denomination = denomination
        self.debtor_target_account_id = debtor_target_account_id
        self.creditor_target_account_id = creditor_target_account_id
        # The init of the base Transfer class
        super().__init__(
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=_from_proto,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        class_docstring = (
            """
            A Transfer is a non-chainable posting instruction that moves funds from a
            debtor to a creditor target account.
        """
            + cls._class_docs_note
        )
        public_methods = super()._public_methods(language_code)
        return types_utils.ClassSpec(
            name="Transfer",
            docstring=class_docstring,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new Transfer",
                args=cls._constructor_args(language_code=language_code),  # noqa: SLF001
            ),
            public_methods=public_methods,
        )

    @classmethod
    def _constructor_args(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        constructor_args = super()._constructor_args(language_code=language_code)
        constructor_args.extend(
            [
                types_utils.ValueSpec(
                    name="amount",
                    type="Decimal",
                    docstring="The amount moved by this posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="The denomination of the amount moved by the posting instruction.",
                ),
                types_utils.ValueSpec(
                    name="debtor_target_account_id",
                    type="str",
                    docstring="The account being debited.",
                ),
                types_utils.ValueSpec(
                    name="creditor_target_account_id",
                    type="str",
                    docstring="The account being credited.",
                ),
            ]
        )
        return constructor_args


_AllPITypes = (
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
)
_PITypes_str = f"List[Union[{', '.join([pi.type.value for pi in _AllPITypes])}]]"  # noqa: SLF001
PITypes = List[
    Union[
        AuthorisationAdjustment,
        CustomInstruction,
        InboundAuthorisation,
        InboundHardSettlement,
        OutboundAuthorisation,
        OutboundHardSettlement,
        Release,
        Settlement,
        Transfer,
    ]
]


class ClientTransactionEffects:
    def __init__(
        self,
        *,
        authorised: Optional[Decimal] = Decimal(0),
        settled: Optional[Decimal] = Decimal(0),
        unsettled: Optional[Decimal] = Decimal(0),
    ):
        self.authorised = authorised
        self.settled = settled
        self.unsettled = unsettled

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self.authorised == other.authorised
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
                The "effects" that a ClientTransaction has had on the balances of
                an Account, or the "current state" of the ClientTransaction.
                Note: This method is not implemented for ClientTransaction
                with CustomInstruction type - None will be returned
                for such ClientTransaction effects instead.
            """,
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            public_methods=[],
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ClientTransactionEffects",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="authorised",
                type="Optional[Decimal]",
                docstring="The total amount that has been authorised. "
                "Note: value is updated on Adjustment instructions, "
                "however, is not updated on Settlement or Release instructions.",
            ),
            types_utils.ValueSpec(
                name="settled",
                type="Optional[Decimal]",
                docstring="The total amount that has been settled.",
            ),
            types_utils.ValueSpec(
                name="unsettled",
                type="Optional[Decimal]",
                docstring="The total amount that has been authorised (including adjustments)"
                " but is yet to be released or settled.",
            ),
        ]


class ClientTransaction:
    _balance_class = Balance
    _balance_coordinate_class = BalanceCoordinate
    _balance_defaultdict_class = BalanceDefaultDict
    _client_transaction_effects_class = ClientTransactionEffects

    def __init__(
        self,
        *,
        client_transaction_id: str,
        account_id: str,
        posting_instructions: PITypes,
        tside: Tside = None,
        _from_proto: bool = False,
    ):
        self._client_transaction = SingleAccountClientTransaction(
            client_transaction_id=client_transaction_id, account_id=account_id
        )
        self._effects_cache: Dict[Optional[datetime], Optional[ClientTransactionEffects]] = {}
        self._balances_cache: Dict[Optional[datetime], BalanceDefaultDict] = {}
        self.posting_instructions = posting_instructions
        self.client_transaction_id = client_transaction_id
        self.account_id = account_id
        self.tside = tside

        if not _from_proto:
            self._validate_attributes()
        for pi in posting_instructions:
            value_datetime = pi.value_datetime
            if value_datetime and pi._committed_postings:  # noqa: SLF001
                final = pi.final if isinstance(pi, Settlement) else False
                if final is not None:
                    committed_postings = pi._committed_postings  # noqa: SLF001
                    self._client_transaction.add_committed_postings(
                        value_datetime,
                        committed_postings,  # type: ignore[arg-type]
                        pi.type.value,
                        final,
                    )

    def _validate_attributes(self):
        types_utils.validate_type(
            self.posting_instructions,
            list,
            hint=_PITypes_str,
            prefix="ClientTransaction.posting_instructions",
        )

        type_hint = _PITypes_str
        iterator = types_utils.get_iterator(
            self.posting_instructions,
            hint=type_hint,
            name="ClientTransaction.posting_instructions",
            check_empty=True,
        )
        expected_type = _AllPITypes
        for index, item in enumerate(iterator):
            types_utils.validate_type(
                item,
                expected_type,
                hint=type_hint,
                prefix="ClientTransaction.posting_instructions",
            )

            if not item.value_datetime:
                raise InvalidPostingInstructionException(
                    f"'ClientTransaction.posting_instructions[{index}]' has its value_datetime "
                    f"attribute set to {item.value_datetime}. Expected value_datetime to be set."
                )
            if isinstance(item, Settlement) and item.final is None:
                raise InvalidPostingInstructionException(
                    f"'ClientTransaction.posting_instructions[{index}]' Settlement instruction "
                    f"has its final attribute set to {item.final}. Expected True or False."
                )

            postings_iterator = types_utils.get_iterator(
                item._committed_postings,  # noqa: SLF001
                hint="List[Posting]",
                name=f"ClientTransaction.posting_instructions[{index}]._committed_postings",
                check_empty=True,
            )
            for posting_index, posting_item in enumerate(postings_iterator):
                types_utils.validate_type(
                    posting_item,
                    Posting,
                    hint="Posting",
                    prefix=f"ClientTransaction.posting_instructions[{index}]."
                    f"_committed_postings[{posting_index}]",
                )

    def __eq__(self, other):
        """Checks equality of the public attributes. If another attribute is added to the class it
        must be added to the `attributes`
        """
        if type(other) is type(self):
            attributes = {
                "client_transaction_id",
                "account_id",
                "posting_instructions",
                "tside",
            }
            return all(getattr(self, attr) == getattr(other, attr) for attr in attributes)
        return False

    def released(self, *, effective_datetime: datetime = None):
        effective_datetime = effective_datetime or datetime.max.replace(tzinfo=ZoneInfo("UTC"))
        validate_timezone_is_utc(
            effective_datetime,
            "effective_datetime",
            "ClientTransaction.released()",
        )
        return any(
            isinstance(posting_instruction, Release) and value_datetime < effective_datetime
            for posting_instruction in self.posting_instructions
            if (value_datetime := posting_instruction.value_datetime) and value_datetime is not None
        )

    def completed(self, *, effective_datetime: datetime = None):
        effective_datetime = effective_datetime or datetime.max.replace(tzinfo=ZoneInfo("UTC"))
        validate_timezone_is_utc(
            effective_datetime,
            "effective_datetime",
            "ClientTransaction.completed()",
        )
        return any(
            isinstance(posting_instruction, Settlement)
            and posting_instruction.final is True
            and value_datetime < effective_datetime
            for posting_instruction in self.posting_instructions
            if (value_datetime := posting_instruction.value_datetime) and value_datetime is not None
        )

    @property
    def denomination(self) -> Optional[str]:
        posting_instruction = self.posting_instructions[0]
        if (
            isinstance(posting_instruction, InboundAuthorisation)
            or isinstance(posting_instruction, OutboundAuthorisation)
            or isinstance(posting_instruction, InboundHardSettlement)
            or isinstance(posting_instruction, OutboundHardSettlement)
            or isinstance(posting_instruction, Transfer)
        ):
            return posting_instruction.denomination
        else:
            return None

    @property
    def is_custom(self) -> bool:
        return self.posting_instructions[0].type == enums.PostingInstructionType.CUSTOM_INSTRUCTION

    @property
    def start_datetime(self) -> Optional[datetime]:
        return self.posting_instructions[0].value_datetime

    def balances(
        self,
        *,
        effective_datetime: Optional[datetime] = None,
        tside: Optional[Tside] = None,
    ) -> BalanceDefaultDict:
        if effective_datetime:
            validate_timezone_is_utc(
                effective_datetime,
                "effective_datetime",
                "ClientTransaction.balances()",
            )
        if effective_datetime in self._balances_cache:
            return self._balances_cache[effective_datetime]

        self._balances_cache[effective_datetime] = result = self._balances(
            effective_datetime=effective_datetime, tside=tside
        )
        return result

    def _balances(
        self,
        *,
        effective_datetime: Optional[datetime] = None,
        tside: Optional[Tside] = None,
    ) -> BalanceDefaultDict:
        tside = tside or self.tside
        if not tside:
            raise InvalidSmartContractError(
                "A tside must be specified for the balances calculation."
            )

        def _transform_balance_to_versioned_balance(balance_value):
            result = self._balance_class()
            result._adjust(  # noqa: SLF001
                credit=balance_value.credit,
                debit=balance_value.debit,
                tside=tside,
            )
            return result

        def _transform_balance_key(balance_key):
            return self._balance_coordinate_class(
                account_address=balance_key.account_address,
                asset=balance_key.asset,
                denomination=balance_key.denomination,
                phase=balance_key.phase,
            )

        # Get balances for client transaction object from postings logic module
        balances = self._client_transaction.balances(at_datetime=effective_datetime)

        return self._balance_defaultdict_class(
            # defaults to 0 net, credit and debit
            lambda *_: self._balance_class(),  # type: ignore
            {
                _transform_balance_key(balance_key): _transform_balance_to_versioned_balance(
                    balance_value
                )
                for balance_key, balance_value in balances.items()
            },
        )

    def effects(self, *, effective_datetime: datetime = None) -> Optional[ClientTransactionEffects]:
        if effective_datetime:
            validate_timezone_is_utc(
                effective_datetime,
                "effective_datetime",
                "ClientTransaction.effects()",
            )
        if effective_datetime in self._effects_cache:
            return self._effects_cache[effective_datetime]
        self._effects_cache[effective_datetime] = result = self._effects(effective_datetime)
        return result

    def _effects(self, effective_datetime: datetime = None) -> Optional[ClientTransactionEffects]:
        if self.is_custom:
            return None

        # Here we explicitly not care about the tside when calculating effects from balances
        balances = self.balances(effective_datetime=effective_datetime, tside=Tside.LIABILITY)
        if balances == BalanceDefaultDict():
            return self._client_transaction_effects_class()
        all_keys = set(
            (key.account_address, key.asset, key.denomination) for key in balances.keys()
        )
        if len(all_keys) != 1:
            raise InvalidPostingInstructionException(
                "ClientTransaction only supports posting instructions with "
                "the same account_address, denomination and asset attributes."
            )
        balance_key = all_keys.pop()
        # All PI types except CustomInstructions has one committed posting for the initial
        # ClientTransaction posting instruction.
        committed_postings = self.posting_instructions[0]._committed_postings
        if not committed_postings:
            raise InvalidSmartContractError(
                "ClientTransaction only supports posting instructions with"
                "non empty committed postings."
            )

        if committed_postings[0].credit:
            return self._make_inbound_effects(
                balances, *balance_key, effective_datetime=effective_datetime
            )
        else:
            return self._make_outbound_effects(
                balances, *balance_key, effective_datetime=effective_datetime
            )

    def _make_inbound_effects(
        self, balances, address, asset, denomination, effective_datetime=None
    ):
        # This is either authorised, released or settled transaction
        return self._client_transaction_effects_class(
            authorised=balances[
                self._balance_coordinate_class(
                    account_address=address,
                    asset=asset,
                    denomination=denomination,
                    phase=Phase.PENDING_IN,
                )
            ].credit,
            settled=balances[
                self._balance_coordinate_class(
                    account_address=address,
                    asset=asset,
                    denomination=denomination,
                    phase=Phase.COMMITTED,
                )
            ].credit,
            unsettled=(
                Decimal(0)
                if self.released(effective_datetime=effective_datetime)
                else abs(
                    balances[
                        self._balance_coordinate_class(
                            account_address=address,
                            asset=asset,
                            denomination=denomination,
                            phase=Phase.PENDING_IN,
                        )
                    ].net
                )
            ),
        )

    def _make_outbound_effects(
        self, balances, address, asset, denomination, effective_datetime=None
    ):
        # This is either authorised or released or settled transaction
        return self._client_transaction_effects_class(
            authorised=-balances[
                self._balance_coordinate_class(
                    account_address=address,
                    asset=asset,
                    denomination=denomination,
                    phase=Phase.PENDING_OUT,
                )
            ].debit,
            settled=-balances[
                self._balance_coordinate_class(
                    account_address=address,
                    asset=asset,
                    denomination=denomination,
                    phase=Phase.COMMITTED,
                )
            ].debit,
            unsettled=(
                Decimal(0)
                if self.released(effective_datetime=effective_datetime)
                else -abs(
                    balances[
                        self._balance_coordinate_class(
                            account_address=address,
                            asset=asset,
                            denomination=denomination,
                            phase=Phase.PENDING_OUT,
                        )
                    ].net
                )
            ),
        )

    def __str__(self):
        return f"ClientTransaction({len(self.posting_instructions)} posting instruction(s))"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ClientTransaction",
            docstring="""
                A sequence of posting instruction objects with the same `client_transaction_id`
                field.

                This object represents the lifecycle of a single transaction. The lifecycle may be
                as trivial as a single "hard settlement" (immediate movement of funds), or contain
                any combination of authorisation, reauthorisation, and so on (see
                [PostingInstructionType](#enums-PostingInstructionType)).

                Each posting instruction in this sequence represents a change in state in the
                transaction's lifecycle.

                Although the object schema allows for posting instruction objects within the same
                [ClientTransaction](#classes-ClientTransaction) to have differing account_id, asset,
                and denomination fields, by convention they should all be the same, in which case
                the posting instruction only represents a change to the net amount and/or
                [Phase](#enums-Phase) of its parent transaction.
            """,
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=[
                    types_utils.ValueSpec(
                        name="client_transaction_id",
                        type="str",
                        docstring="""
                        The unique ID of this ClientTransaction.
                    """,
                    ),
                    types_utils.ValueSpec(
                        name="account_id",
                        type="str",
                        docstring="""
                        The ID of the account which is the target account for this
                        ClientTransaction.
                        Note that for the ClientTransaction that consist of CustomInstructions
                        that have different target accounts, each ClientTransaction represents
                        the single account client transaction - therefore consists only of
                        CustomInstruction postings for a single account ID.
                    """,
                    ),
                    types_utils.ValueSpec(
                        name="posting_instructions",
                        type=_PITypes_str,
                        docstring="""
                        List of the posting instructions sorted ascending by the value_datetime,
                        sharing the same client_transaction_id that represents a ClientTransaction.
                    """,
                    ),
                ],
            ),
            public_attributes=[
                types_utils.ValueSpec(
                    name="client_transaction_id",
                    type="str",
                    docstring="""
                        The unique ID of this ClientTransaction.
                    """,
                ),
                types_utils.ValueSpec(
                    name="account_id",
                    type="str",
                    docstring="""
                        The ID of the account which is the target account for this
                        ClientTransaction.
                        Note that for the ClientTransaction that consist of CustomInstructions
                        that have different target accounts, each ClientTransaction represents
                        the single account client transaction - therefore consists only of
                        CustomInstruction postings for a single account ID.
                    """,
                ),
                types_utils.ValueSpec(
                    name="denomination",
                    type="str",
                    docstring="""
                        The denomination of the ClientTransaction which is the determined by the
                        denomination of the first posting instruction within the ClientTransaction.
                    """,
                ),
                types_utils.ValueSpec(
                    name="is_custom",
                    type="bool",
                    docstring="""
                        The value will be True if and only if all posting instruction objects are of
                        type PostingInstructionType.CUSTOM_INSTRUCTION.
                    """,
                ),
                types_utils.ValueSpec(
                    name="start_datetime",
                    type="datetime",
                    docstring="""
                        This value is the value_datetime of the first posting instruction within the
                        ClientTransaction. Must be a timezone-aware UTC datetime using the
                        ZoneInfo class.
                    """,
                ),
                types_utils.ValueSpec(
                    name="posting_instructions",
                    type=_PITypes_str,
                    docstring="""
                        List of the posting instructions sorted ascending by the value_datetime,
                        sharing the same client_transaction_id that represents a ClientTransaction.
                    """,
                ),
            ],
            public_methods=[
                types_utils.MethodSpec(
                    name="released",
                    docstring="""
                        This value will be True if and only if the ClientTransaction has ended with
                        a posting instruction of type RELEASE at given effective_datetime.
                    """,
                    args=[
                        types_utils.ValueSpec(
                            name="effective_datetime",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only posting instructions that happened before or on the
                                datetime are included in the result. Must be a timezone-aware
                                UTC datetime. Must be a timezone-aware UTC datetime using the
                                ZoneInfo class.
                            """,
                        )
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="bool",
                        docstring="""
                        This value will be True if and only if the ClientTransaction has ended with
                        a posting instruction of type RELEASE at given effective_datetime.
                        """,
                    ),
                ),
                types_utils.MethodSpec(
                    name="completed",
                    docstring="""
                        This value will be True if and only if the ClientTransaction has ended with
                        a posting instruction of type SETTLEMENT and flag final.
                    """,
                    args=[
                        types_utils.ValueSpec(
                            name="effective_datetime",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only posting instructions that happened before or on the
                                datetime are included in the result. Must be a timezone-aware
                                UTC datetime.
                            """,
                        )
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="bool",
                        docstring="""
                        This value will be True if and only if the ClientTransaction has ended with
                        a posting instruction of type SETTLEMENT and flag final.
                        """,
                    ),
                ),
                types_utils.MethodSpec(
                    name="effects",
                    docstring="""
                        Returns the net state of the ClientTransaction; identically, the net
                        effects that the ClientTransaction has had on the Account.
                        Note: This method is not implemented for ClientTransactions with
                        CustomInstructions.
                    """,
                    args=[
                        types_utils.ValueSpec(
                            name="effective_datetime",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only posting instructions that happened before or on the
                                datetime are included in the result. Must be a timezone-aware UTC
                                datetime.
                            """,
                        )
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="Optional[ClientTransactionEffects]",
                        docstring="""
                            Returns ClientTransactionEffects - The effects of a ClientTransaction
                            on the balances of an Account, or the current state of the
                            ClientTransaction. Returns None for ClientTransactions with
                            CustomInstructions.
                        """,
                    ),
                ),
                types_utils.MethodSpec(
                    name="balances",
                    docstring="Returns the net balance changes caused by this ClientTransaction.",
                    args=[
                        types_utils.ValueSpec(
                            name="effective_datetime",
                            type="Optional[datetime]",
                            docstring="""
                                If set, only posting instructions that happened before or on the
                                datetime are included in the result. Must be a timezone-aware UTC
                                datetime.
                            """,
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="BalanceDefaultDict",
                        docstring="""
                            The default balance dictionary where the key is the
                            [BalanceCoordinate](#classes-BalanceCoordinate) and the value is
                            a [Balance](#classes-Balance) object which contains the debit,
                            credit and net balance changes. If non-existing key is accessed,
                            an object with zero debit, credit and net balance changes is returned.
                        """,
                    ),
                ),
            ],
        )
