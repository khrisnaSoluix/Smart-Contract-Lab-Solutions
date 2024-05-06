from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class AddAccountNoteDirective:

    def __init__(
        self, *, idempotency_key, account_id, body, note_type, date, is_visible_to_customer,
        _from_proto=False
    ):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'idempotency_key': idempotency_key,
                    'account_id': account_id,
                    'body': body,
                    'note_type': note_type,
                    'date': date,
                    'is_visible_to_customer': is_visible_to_customer,
                }
            )

        self.idempotency_key = idempotency_key
        self.account_id = account_id
        self.body = body
        self.note_type = note_type
        self.date = date
        self.is_visible_to_customer = is_visible_to_customer

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')
        return types_utils.ClassSpec(
            name='AddAccountNoteDirective',
            docstring='''
                A [HookDirective](#classes-HookDirectives) that instructs adding an Account Note.
                **Only available in version 3.4.0+**.
            ''',
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring='Constructs a new AddAccountNoteDirective',
                args=cls._public_attributes(language_code)
            )
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')
        return [
            types_utils.ValueSpec(
                name='idempotency_key',
                type='str',
                docstring='''
                    If the `idempotency_key` is specified, the Account Note will only be added if
                    an Account Note with this `idempotency_key` is not already on the Account. If
                    the `idempotency_key` is not supplied, the Account Note will always be added.
                '''
            ),
            types_utils.ValueSpec(
                name='account_id',
                type='str',
                docstring='''
                    The Account ID that this [HookDirective](#classes-HookDirectives) adds an
                    Account Note to.
                '''
            ),
            types_utils.ValueSpec(
                name='body',
                type='str',
                docstring='''
                    Can be the text of the Account Note, or a code depending on the Account Note
                    type.
                '''
            ),
            types_utils.ValueSpec(
                name='note_type',
                type='NoteType',
                docstring='The type of the Account Note. Used to interpret the Account Note body.'
            ),
            types_utils.ValueSpec(
                name='date',
                type='datetime',
                docstring='The effective date of the Account Note.'
            ),
            types_utils.ValueSpec(
                name='is_visible_to_customer',
                type='bool',
                docstring='''
                    If true, the customer will see the Account Note, otherwise it will only be
                    visible to operations users.
                '''
            ),
        ]
