from functools import lru_cache

from .....utils import symbols, types_utils
from ....version_350.common import types as types350


class PostingInstruction(types350.PostingInstruction):

    insertion_timestamp = NotImplementedError('Missing implementation')

    def balances(self):
        raise NotImplementedError('Missing implementation')

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)
        super_spec.public_attributes['insertion_timestamp'] = types_utils.ValueSpec(
            name='insertion_timestamp',
            type='Optional[datetime]',
            docstring='''
                The timestamp indicating when the Posting Instruction Batch was inserted into the
                posting ledger. **Only available in version 3.6+.**
            '''
        )

        return super_spec


class PostingInstructionBatch(types350.PostingInstructionBatch):

    def __init__(self, insertion_timestamp=None, **kwargs):
        super().__init__(**kwargs)
        if not kwargs.get('_from_proto', False):
            self._spec().assert_constructor_args(
                self._registry,
                {'insertion_timestamp': insertion_timestamp}
            )
        self.insertion_timestamp = insertion_timestamp

    def balances(self, exclude_advice: bool = False):
        raise NotImplementedError('Missing implementation')

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        super_spec = super()._spec(language_code)
        super_spec.constructor.args['insertion_timestamp'] = types_utils.ValueSpec(
            name='insertion_timestamp',
            type='Optional[datetime]',
            docstring='''
                The timestamp indicating when the Posting Instruction Batch was inserted into the
                posting ledger. **Only available in version 3.6+.**
            '''
        )
        super_spec.public_attributes['insertion_timestamp'] = types_utils.ValueSpec(
            name='insertion_timestamp',
            type='Optional[datetime]',
            docstring='''
                The timestamp indicating when the Posting Instruction Batch was inserted into the
                posting ledger. **Only available in version 3.6+.**
            '''
        )

        return super_spec


class ClientTransaction(types350.ClientTransaction):
    pass
