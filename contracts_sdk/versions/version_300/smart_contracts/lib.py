from abc import abstractmethod
from functools import lru_cache

from . import types as smart_contract_types
from ..common import lib as common_lib
from ....utils import symbols, types_utils


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(types_utils.StrictInterface):
    @abstractmethod
    def get_last_execution_time(self, *, event_type):
        pass

    @abstractmethod
    def get_postings(self, *, include_proposed=True):
        pass

    @abstractmethod
    def get_client_transactions(self, *, include_proposed=True):
        pass

    @abstractmethod
    def get_posting_batches(self, include_proposed=True):
        pass

    @abstractmethod
    def add_account_note(
        self, *, body, note_type, is_visible_to_customer, date, idempotency_key=None
    ):
        pass

    @abstractmethod
    def amend_schedule(self, *, event_type, new_schedule):
        pass

    @abstractmethod
    def get_account_creation_date(self):
        pass

    @abstractmethod
    def get_balance_timeseries(self):
        pass

    @abstractmethod
    def get_hook_execution_id(self):
        pass

    @abstractmethod
    def get_parameter_timeseries(self, *, name):
        pass

    @abstractmethod
    def get_flag_timeseries(self, *, flag):
        pass

    @abstractmethod
    def remove_schedule(self, *, event_type):
        pass

    @abstractmethod
    def start_workflow(self, *, workflow, context, idempotency_key=None):
        pass

    @abstractmethod
    def make_internal_transfer_instructions(
        self,
        *,
        amount,
        denomination,
        client_transaction_id,
        from_account_id,
        from_account_address=None,
        to_account_id,
        to_account_address=None,
        pics=None,
        instruction_details=None,
        asset=symbols.DEFAULT_ASSET,
        custom_instruction_grouping_key=None
    ):
        pass

    @abstractmethod
    def instruct_posting_batch(
        self,
        *,
        posting_instructions,
        batch_details=None,
        client_batch_id=None,
        effective_date=None,
        request_id=None
    ):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        spec = types_utils.ClassSpec(
            name="VaultFunctions",
            docstring="""
                The Vault object is present during the execution of every hook and is accessible
                via the `vault` variable.

                Apart from hook-specific arguments and return values, it is the sole method of
                fetching information from Vault or communicating "hook directives" back to Vault.

                All information fetched from the `vault` object must have been statically declared
                at the top of a hook using the `@requires` decorator, and is fetched in a batch
                before the hook starts executing.

                All hook directives are batched until the hook finishes executing, and then
                implemented in Vault at the same time.
            """,
            public_methods=[
                types_utils.MethodSpec(
                    name="get_last_execution_time",
                    docstring="""
                    Gets the most recent time that the `scheduled_code` hook was called for
                    the given `event_type`.
                """,
                    args=[
                        types_utils.ValueSpec(
                            name="event_type",
                            type="str",
                            docstring="The `scheduled_code` hook's `event_type` string.",
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        docstring="The last execution time.", type="datetime"
                    ),
                    examples=[
                        types_utils.Example(
                            title="A simple example",
                            code="vault.get_last_execution_time(event_type='SERVICE_CHARGE')",
                        )
                    ],
                )
            ],
        )
        public_attributes = [
            types_utils.ValueSpec(
                name="account_id",
                type="str",
                docstring="The id of the Account currently being executed.",
            ),
        ]
        for attr in public_attributes:
            spec.public_attributes[attr.name] = attr
        public_methods = [
            types_utils.MethodSpec(
                name="get_postings",
                docstring="""
                     Returns a list of ``[./PostingInstruction]`` objects.
                     The default ordering is by time; further ordering/filtering
                     can be done using the ``sorted`` builtin and other builtin mechanisms.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="include_proposed",
                        type="bool",
                        docstring="""
                            If True, and the current hook is pre/post_posting, the returned list
                            will include the proposed batch of PostingInstructions.
                        """,
                    )
                ],
                return_value=types_utils.ReturnValueSpec(
                    type="List[PostingInstruction]",
                    docstring="The sorted list of PostingInstructions.",
                ),
                examples=[
                    types_utils.Example(
                        title="Counting spend from the default address over the past 24 months",
                        code="""
                            @requires(postings='2 years')
                            def pre_posting_code(postings, effective_date):
                                posting_count = sum(
                                    1 for posting in vault.get_postings(include_proposed=True)
                                    if not posting.credit and
                                    posting.account_address == DEFAULT_ADDRESS
                                )
                        """,
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="get_client_transactions",
                docstring="""
                    Gets a map of (client_id, client_transaction_id) to a ClientTransaction.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="include_proposed",
                        type="bool",
                        docstring="""
                            If True, and the current hook is pre/post_posting,
                            the returned ClientTransactions
                            will include the proposed batch of PostingInstructions.
                        """,
                    )
                ],
                return_value=types_utils.ReturnValueSpec(
                    type="Dict[Tuple[str, str], ClientTransaction]",
                    docstring="The ClientTransaction dict, "
                    "keyed by (client_id, client_transaction_id).",
                ),
                examples=[
                    types_utils.Example(
                        title="Count the number of non-released "
                        "ClientTransactions over a 24 hour period",
                        code="""
                            @requires(parameters=True, balances='latest', postings="1 days")
                            def pre_posting_code(postings, effective_date):
                                number_txns_in_24_hours = sum(
                                    1 for client_txn in vault.get_client_transactions(
                                        include_proposed=True
                                    ).values()
                                    if not client_txn.cancelled
                                )
                                if number_txns_in_24_hours >= 2:
                                    raise Rejected(
                                        'Limit of allowed client transaction number'
                                        'per 24 hours for the account reached',
                                        reason_code=RejectedReason.AGAINST_TNC
                                    )
                        """,
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="get_posting_batches",
                docstring="""
                    Gets a list of "posting batches" ordered by batch timestamp.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="include_proposed",
                        type="bool",
                        docstring="""
                            If True, and the current hook is pre/post_posting, the returned
                            ``[../types/PostingInstruction]`` objects will include the proposed
                            batch of PostingInstructions.
                        """,
                    )
                ],
                return_value=types_utils.ReturnValueSpec(
                    type="List[PostingInstructionBatch]", docstring="The list of batches."
                ),
            ),
            types_utils.MethodSpec(
                name="add_account_note",
                docstring="""
                    Add a note to the account. Can be used to explain charge
                    waivers or signify events.
                    The note will appear in the ops dash, and if *is_visible_to_customer*
                    it can be shown to the account holders.

                    *NoteType.RAW_TEXT* means the body is taken as the
                    text for the account notes.
                    *NoteType.REASON_CODE* means the body is a reason code,
                    that can be used by API users how they see fit.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="body",
                        type="str",
                        docstring="""
                            Can be the text of the note, or a code depending on the note type.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="note_type",
                        type="NoteType",
                        docstring="The type of the note. Used to interpret the note body.",
                    ),
                    types_utils.ValueSpec(
                        name="is_visible_to_customer",
                        type="bool",
                        docstring="""
                            If true the note will be shown to the customer,
                            otherwise it will only be visible to operations users.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="date",
                        type="datetime",
                        docstring="The effective date of the account note.",
                    ),
                    types_utils.ValueSpec(
                        name="idempotency_key",
                        type="str",
                        docstring="""
                            [Deprecated] This attribute is not used from
                            Vault version 2.0.
                            If idempotency_key is specified the account
                            note will only be added if an account note
                            with this idempotency_key is not already on the account.
                            If idempotency_key is not supplied the
                            account note will always be added.
                        """,
                    ),
                ],
                examples=[
                    types_utils.Example(
                        title="How to add a simple account note",
                        code="""
                            vault.add_account_note(
                                body='This is some sample message',
                                note_type=NoteType.RAW_TEXT,
                                is_visible_to_customer=True,
                                date=datetime(2019, 1, 1)
                            )
                        """,
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="amend_schedule",
                docstring="""
                    Replace the schedule for *event_type* to *new_schedule*.
                    Requires full definition of *new_schedule* as this function
                    disables old schedule and creates *new_schedule* in vault.
                    See ``[../hooks/execution_schedules]`` for information on schedules.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="event_type",
                        type="str",
                        docstring="The event_type to change the schedule for.",
                    ),
                    types_utils.ValueSpec(
                        name="new_schedule", type="Dict[str, str]", docstring="The new schedule."
                    ),
                ],
                examples=[
                    types_utils.Example(
                        title="A simple schedule amendment to 23:00 on the 28th of each month",
                        code="vault.amend_schedule('EVENT_NAME', {'day':'28', 'hour': '23'})",
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="get_account_creation_date",
                docstring="Returns the date that the currently executing Account was created.",
                args=[],
                return_value=types_utils.ReturnValueSpec(
                    docstring="The Account creation date.", type="datetime"
                ),
            ),
            types_utils.MethodSpec(
                name="get_balance_timeseries",
                docstring="""
                    Gets the BalanceTimeseries covering
                    all balances over the time period specified
                    by the `@requires` hook decorator.
                """,
                args=[],
                return_value=types_utils.ReturnValueSpec(
                    docstring="The timeseries of balances.", type="BalanceTimeseries"
                ),
            ),
            types_utils.MethodSpec(
                name="get_hook_execution_id",
                docstring="""
                    Returns a string used in generating unique-enough ids
                    for attaching to side-effect
                    objects. The string returned is a combination of
                    account_id, hook, and effective_date.
                """,
                args=[],
                return_value=types_utils.ReturnValueSpec(
                    docstring="The unique-enough id.", type="str"
                ),
            ),
            types_utils.MethodSpec(
                name="get_parameter_timeseries",
                docstring="""
                    Get the ParameterTimeseries containing all timeseries across all contract
                    parameters defined and/or used by this Smart Contract.

                    If `parameters=True` is not specified in the `@requires` decorator, any call
                    to this function will fail.

                    Values for derived parameters are not returned from this function.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="name",
                        type="str",
                        docstring="The name of the ``[../types/ContractParameter]``.",
                    ),
                ],
                return_value=types_utils.ReturnValueSpec(
                    docstring="The timeseries of parameters.", type="ParameterTimeseries"
                ),
            ),
            types_utils.MethodSpec(
                name="get_flag_timeseries",
                docstring="""
                    Get the FlagTimeseries for a given flag definition.

                    If `flags=True` is not specified in the `@requires` decorator, any call
                    to this function will return an empty FlagTimeseries.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="flag",
                        type="str",
                        docstring="The `flag_definition_id` to get the timeseries for.",
                    ),
                ],
                return_value=types_utils.ReturnValueSpec(
                    docstring="The timeseries of flags.", type="FlagTimeseries"
                ),
            ),
            types_utils.MethodSpec(
                name="remove_schedule",
                docstring="""
                    Instructs Vault to stop scheduling execution
                    of the `scheduled_code` hook for the given `event_type`.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="event_type",
                        type="str",
                        docstring="The name of the scheduled event to cancel.",
                    )
                ],
                examples=[
                    types_utils.Example(
                        title="Removal of the EVENT_NAME schedule",
                        code="vault.remove_schedule(event_type='EVENT_NAME')",
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="start_workflow",
                docstring="""
                    Instructs Vault to create and start an instance of a Workflow Definition.
                    The active (default) version of the specified
                    Workflow Definition ID will be instantiated.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="workflow",
                        type="str",
                        docstring="The unique ID of the Workflow Definition to start.",
                    ),
                    types_utils.ValueSpec(
                        name="context",
                        type="Dict[str, str]",
                        docstring="""The context (key-value pairs of data)
                        to be passed to the Workflow Instance.""",
                    ),
                    types_utils.ValueSpec(
                        name="idempotency_key",
                        type="Optional[str]",
                        docstring="""
                            [Deprecated] This attribute is not used from
                            Vault version 2.0.
                            If idempotency_key is specified the workflow
                            will only be added if a start_workflow
                            call has not previously been made for this
                            account with this idempotency_key.
                            If idempotency_key is not supplied the
                            workflow will always be started.
                        """,
                    ),
                ],
                examples=[
                    types_utils.Example(
                        title="Workflow instantiation",
                        code="""
                            vault.start_workflow(
                                workflow='WORKFLOW_DEFINITION_ID',
                                context={
                                    'context_key_1': 'some_value_1',
                                    'context_key_2': 'some_value_2',
                                }
                            )
                        """,
                    )
                ],
            ),
            types_utils.MethodSpec(
                name="make_internal_transfer_instructions",
                docstring="""
                    Returns a list of PostingInstruction objects that implements a transfer
                    of funds between two Vault accounts using CustomInstruction.
                """,
                args=[
                    types_utils.ValueSpec(
                        name="amount", type="Decimal", docstring="The amount to be transferred."
                    ),
                    types_utils.ValueSpec(
                        name="denomination",
                        type="str",
                        docstring="The denomination to be transferred.",
                    ),
                    types_utils.ValueSpec(
                        name="client_transaction_id",
                        type="str",
                        docstring="""
                            The unique id of the ``[./ClientTransaction]``
                            that the generated PostingInstructions
                            should be part of. This may be an existing
                            ClientTransactions's id, or a new
                            unique one generated via a uuid.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="from_account_id",
                        type="str",
                        docstring="The Account id to be debited.",
                    ),
                    types_utils.ValueSpec(
                        name="from_account_address",
                        type="Optional[str]",
                        docstring="""
                            The Account address to be debited. This may only
                            be specified if the from_account_id
                            is the currently executing Account, or an internal Account.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="to_account_id", type="str", docstring="The Account id to be credited."
                    ),
                    types_utils.ValueSpec(
                        name="to_account_address",
                        type="Optional[str]",
                        docstring="""
                            The Account address to be credited. This may only
                            be specified if the from_account_id
                            is the currently executing Account, or an internal Account.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="pics",
                        type="Optional[List[str]]",
                        docstring="An optional list of pics to be attached to"
                        " the created PostingInstruction.",
                    ),
                    types_utils.ValueSpec(
                        name="instruction_details",
                        type="Optional[Dict[str, str]]",
                        docstring="An optional key/value mapping to be attached to"
                        " the created PostingInstruction.",
                    ),
                    types_utils.ValueSpec(
                        name="asset",
                        type="Optional[str]",
                        docstring="""The asset of the denomination to be transferred.
                        If not specified, defaults to ``[./DEFAULT_ASSET]``.""",
                    ),
                    types_utils.ValueSpec(
                        name="custom_instruction_grouping_key",
                        type="Optional[str]",
                        docstring="""
                            An optional key used for grouping `PostingInstruction`s into
                            `CustomInstruction`s when instructing a posting batch. If not provided,
                            it defaults to a unique autogenerated key. All `CustomInstruction`s
                            with the same grouping key must share the same `client_transaction_id`
                            before they are instructed in the same batch.
                        """,
                    ),
                ],
                return_value=types_utils.ReturnValueSpec(
                    docstring="""
                        The list of PostingInstructions that will end up going into Vault.
                        These are not exactly PostingInstruction objects, but internal objects.
                        They should not be inspected or modified.
                    """,
                    type="List[PostingInstruction]",
                ),
            ),
            types_utils.MethodSpec(
                name="instruct_posting_batch",
                docstring="Instructs Vault to create a new batch of PostingInstructions.",
                args=[
                    types_utils.ValueSpec(
                        name="posting_instructions",
                        type="List[PostingInstruction]",
                        docstring="""
                            The PostingInstructions that will go into the created batch. All
                            PostingInstructions with the same `custom_instruction_grouping_key`
                            need to share the same `client_transaction_id`, otherwise
                            `InvalidSmartContractError` is raised.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="batch_details",
                        type="Optional[Dict[str, str]]",
                        docstring="""
                            An optional key/value mapping to be
                            attached to the created batch.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="client_batch_id",
                        type="Optional[str]",
                        docstring="""
                            The client_batch_id (an arbitrary key) to be
                            attached to the created batch.
                            If not specified, defaults to the result
                            of `vault.get_hook_execution_id()`.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="effective_date",
                        type="Optional[datetime]",
                        docstring="""
                            The value_timestamp that is attached to the batch.
                            If not specified, defaults to current UTC time.
                        """,
                    ),
                    types_utils.ValueSpec(
                        name="request_id",
                        type="Optional[str]",
                        docstring="""
                            [Deprecated] This attribute is not used from
                            Vault version 2.0.
                            The idempotency key. If not specified,
                            defaults to a unique-enough value.
                        """,
                    ),
                ],
            ),
        ]
        for method in public_methods:
            spec.public_methods[method.name] = method
        return spec
