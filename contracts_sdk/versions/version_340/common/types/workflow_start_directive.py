from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class WorkflowStartDirective:

    def __init__(self, *, workflow, context, account_id, idempotency_key, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry, {
                    'workflow': workflow,
                    'context': context,
                    'account_id': account_id,
                    'idempotency_key': idempotency_key
                }
            )

        self.workflow = workflow
        self.context = context
        self.account_id = account_id
        self.idempotency_key = idempotency_key

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')
        return types_utils.ClassSpec(
            name='WorkflowStartDirective',
            docstring='''
                A [HookDirective](#classes-HookDirectives) that instructs the start of a
                Worfklow. **Only available in version 3.4.0+**.
            ''',
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring='Constructs a new WorkflowStartDirective',
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
                name='workflow',
                type='str',
                docstring='The unique ID of the Workflow Definition to start.'
            ),
            types_utils.ValueSpec(
                name='context',
                type='Dict[str, str]',
                docstring='''The context (key-value pairs of data)
                            to be passed to the Workflow Instance.'''
            ),
            types_utils.ValueSpec(
                name='account_id',
                type='str',
                docstring='''
                    The Account ID that this
                    [HookDirective](#classes-HookDirectives) starts a Workflow for.
                '''
            ),
            types_utils.ValueSpec(
                name='idempotency_key',
                type='Optional[str]',
                docstring='''
                    If the `idempotency_key` is specified, the Workflow will only be added if a
                    `start_workflow` call has not previously been made for this Account with this
                    `idempotency_key`. If the `idempotency_key` is not supplied, the Workflow will
                    always be started.
                '''
            )
        ]
