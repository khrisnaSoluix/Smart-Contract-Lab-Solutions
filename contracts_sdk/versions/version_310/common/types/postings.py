from functools import lru_cache

from ....version_300.common.types import postings as postings300
from .....utils import symbols
from .....utils import types_utils


class PostingInstructionBatch(postings300.PostingInstructionBatch):
    pass


class PostingInstruction(postings300.PostingInstruction):

    def __init__(self, **kwargs):
        if not kwargs.get('_from_proto', False):
            self._spec().assert_constructor_args(
                self._registry,
                {'override_all_restrictions': kwargs.get('override_all_restrictions', False)}
            )
        super().__init__(**kwargs)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        super_spec = super()._spec()
        super_spec.constructor.args['override_all_restrictions'] = types_utils.ValueSpec(
            name='override_all_restrictions',
            type='bool',
            docstring='''
                Specifies whether to ignore all restrictions. Available on versions 3.1.0+.
            '''
        )

        return super_spec

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError('Language not supported')

        super_public_attr = super()._public_attributes()
        super_public_attr.append(
            types_utils.ValueSpec(
                name='override_all_restrictions',
                type='bool',
                docstring='''
                    Specifies whether to ignore all restrictions. Available on versions 3.1.0+.
                '''
            )
        )

        return super_public_attr
